from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from core.erp.models import Company

from .forms import PaymentForm, PlanForm, SubscriptionEditForm
from .models import Subscription, SubscriptionPlan
from .services import get_company_access_state


class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class SubscriptionListView(SuperuserRequiredMixin, ListView):
    """Panel de suscripciones: estado de cada empresa (solo superusuario)."""
    template_name = 'subscriptions/list.html'
    context_object_name = 'companies'

    def get_queryset(self):
        return Company.objects.filter(is_active=True).select_related(
            'subscription', 'subscription__plan'
        ).order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        rows = []
        for company in ctx['companies']:
            sub = getattr(company, 'subscription', None)
            info = get_company_access_state(company.id, today)
            rows.append({'company': company, 'subscription': sub, 'info': info})
        ctx['rows'] = rows
        ctx['title'] = 'Suscripciones'
        return ctx


class SubscriptionDetailView(SuperuserRequiredMixin, View):
    """Detalle de la suscripción de una empresa + registro de pagos."""
    template_name = 'subscriptions/detail.html'

    def _get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        sub = getattr(company, 'subscription', None)
        return company, sub

    def get(self, request, pk):
        company, sub = self._get(request, pk)
        payment_form = PaymentForm(initial={
            'amount': sub.plan.price if sub else 0,
            'paid_at': timezone.localdate(),
        })
        edit_form = SubscriptionEditForm(instance=sub)
        return render(request, self.template_name, {
            'title': f'Suscripción - {company.name}',
            'company': company,
            'subscription': sub,
            'info': get_company_access_state(company.id),
            'payment_form': payment_form,
            'edit_form': edit_form,
            'payments': sub.payments.select_related('created_by')[:20] if sub else [],
            'plans': SubscriptionPlan.objects.filter(is_active=True),
        })

    def post(self, request, pk):
        company, sub = self._get(request, pk)
        action = request.POST.get('action')

        if action == 'register_payment':
            if not sub:
                messages.error(request, 'La empresa no tiene suscripción. Cree una primero.')
                return redirect('subscriptions:detail', pk=pk)
            form = PaymentForm(request.POST)
            if form.is_valid():
                payment = sub.register_payment(
                    amount=form.cleaned_data['amount'],
                    method=form.cleaned_data['method'],
                    paid_at=form.cleaned_data['paid_at'],
                    notes=form.cleaned_data['notes'],
                    user=request.user,
                )
                messages.success(
                    request,
                    f'Pago de ${payment.amount} registrado. '
                    f'Nuevo vencimiento: {sub.end_date:%d/%m/%Y}.'
                )
                return redirect('subscriptions:detail', pk=pk)
            messages.error(request, 'Datos de pago inválidos.')

        elif action == 'create':
            form = SubscriptionEditForm(request.POST)
            if form.is_valid():
                new_sub = form.save(commit=False)
                new_sub.company = company
                new_sub.save()
                messages.success(request, 'Suscripción creada.')
                return redirect('subscriptions:detail', pk=pk)
            messages.error(request, 'Datos de suscripción inválidos.')

        elif action == 'update' and sub:
            form = SubscriptionEditForm(request.POST, instance=sub)
            if form.is_valid():
                form.save()
                messages.success(request, 'Suscripción actualizada.')
                return redirect('subscriptions:detail', pk=pk)
            messages.error(request, 'Datos de suscripción inválidos.')

        elif action in ('suspend', 'reactivate', 'cancel') and sub:
            sub.status = {'suspend': 'suspended', 'reactivate': 'active', 'cancel': 'cancelled'}[action]
            sub.save(update_fields=['status', 'updated_at'])
            messages.success(request, f'Estado actualizado a {sub.get_status_display()}.')
            return redirect('subscriptions:detail', pk=pk)

        return self.get(request, pk)


class PlanListView(SuperuserRequiredMixin, View):
    """Gestión de planes de suscripción."""
    template_name = 'subscriptions/plans.html'

    def get(self, request):
        return render(request, self.template_name, {
            'title': 'Planes de suscripción',
            'plans': SubscriptionPlan.objects.all(),
            'form': PlanForm(),
        })

    def post(self, request):
        action = request.POST.get('action')
        if action == 'create':
            form = PlanForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Plan creado.')
            else:
                messages.error(request, 'Datos de plan inválidos.')
        elif action == 'toggle':
            plan = get_object_or_404(SubscriptionPlan, pk=request.POST.get('plan_id'))
            plan.is_active = not plan.is_active
            plan.save(update_fields=['is_active'])
        elif action == 'update':
            plan = get_object_or_404(SubscriptionPlan, pk=request.POST.get('plan_id'))
            form = PlanForm(request.POST, instance=plan)
            if form.is_valid():
                form.save()
                messages.success(request, 'Plan actualizado.')
            else:
                messages.error(request, 'Datos de plan inválidos.')
        return redirect('subscriptions:plans')


class SuspendedView(TemplateView):
    """Página informativa de suscripción suspendida."""
    template_name = 'subscriptions/suspended.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Suscripción suspendida'
        return ctx


class PublicPlansView(ListView):
    """Página pública de planes disponibles (sin login)."""
    template_name = 'subscriptions/public_plans.html'
    context_object_name = 'plans'

    def get_queryset(self):
        return SubscriptionPlan.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Planes y suscripciones'
        return ctx


# ============================================================
# Solicitudes publicas de alta (desde /planes/)
# ============================================================
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import PlanRequest


def solicitar_plan(request):
    """Formulario publico de solicitud de cuenta (desde /planes/)."""
    if request.method != 'POST':
        return redirect('public_plans')
    plan = SubscriptionPlan.objects.filter(
        pk=request.POST.get('plan_id'), is_active=True
    ).first()
    if not plan:
        return redirect('/planes/?error=plan')
    fields = {k: (request.POST.get(k) or '').strip()
              for k in ('first_name', 'last_name', 'email', 'phone',
                        'company_name', 'cuit', 'message')}
    if not (fields['first_name'] and fields['email']
            and fields['company_name'] and fields['phone']):
        return redirect('/planes/?error=datos')
    PlanRequest.objects.create(plan=plan, **fields)
    return redirect('/planes/?solicitado=1')


def _superuser_required(request):
    return request.user.is_authenticated and request.user.is_superuser


def _unique_username(User, base):
    base = re.sub(r'[^a-zA-Z0-9_.-]', '',
                  (base or 'usuario').split('@')[0].lower()) or 'usuario'
    username, n = base, 0
    while User.objects.filter(username=username).exists():
        n += 1
        username = f'{base}{n}'
    return username


def _billing_mp_config():
    """Config MP de la plataforma para cobrar suscripciones
    (la plata va a la cuenta del servicio, no a la del cliente).
    Configurable con settings.SUBSCRIPTION_BILLING_COMPANY_ID."""
    from core.erp.models import MercadoPagoConfig
    qs = MercadoPagoConfig.objects.filter(enabled=True).exclude(access_token='')
    cid = getattr(settings, 'SUBSCRIPTION_BILLING_COMPANY_ID', None)
    if cid:
        cfg = qs.filter(company_id=cid).first()
        if cfg:
            return cfg
    return qs.order_by('company_id').first()


class PlanRequestListView(SuperuserRequiredMixin, ListView):
    """Solicitudes de alta recibidas desde la pagina publica de planes."""
    template_name = 'subscriptions/requests.html'
    context_object_name = 'requests'

    def get_queryset(self):
        return PlanRequest.objects.select_related('plan', 'company').all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Solicitudes de alta'
        ctx['entity'] = 'Solicitudes'
        return ctx


@require_POST
def plan_request_approve(request, pk):
    """Aprueba la solicitud: crea empresa + usuario + suscripcion.
    Devuelve las credenciales generadas para enviar al cliente."""
    if not _superuser_required(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    req = get_object_or_404(PlanRequest, pk=pk)
    if req.status == 'approved':
        return JsonResponse({'error': 'La solicitud ya fue aprobada'}, status=400)
    if req.status == 'rejected':
        return JsonResponse({'error': 'La solicitud fue rechazada'}, status=400)
    User = get_user_model()
    with transaction.atomic():
        company = Company.objects.create(
            name=req.company_name, cuit=req.cuit or None,
            phone=req.phone, email=req.email,
        )
        username = _unique_username(User, req.email or req.company_name)
        password = secrets.token_urlsafe(6)
        user = User.objects.create_user(
            username=username, email=req.email, password=password,
            first_name=req.first_name, last_name=req.last_name,
            company=company,
        )
        group = Group.objects.filter(name='admin_empresa').first()
        if group:
            user.groups.add(group)
        today = timezone.localdate()
        sub = Subscription.objects.create(
            company=company, plan=req.plan,
            start_date=today,
            end_date=today + timedelta(days=req.plan.duration_days),
            status='active',
        )
        req.status = 'approved'
        req.company = company
        req.user = user
        req.save(update_fields=['status', 'company', 'user', 'updated_at'])
    return JsonResponse({
        'success': True, 'username': username, 'password': password,
        'company': company.name, 'vence': sub.end_date.strftime('%d/%m/%Y'),
    })


@require_POST
def plan_request_pay_link(request, pk):
    """Genera el link de pago MP del primer periodo (cuenta de la plataforma)."""
    if not _superuser_required(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    req = get_object_or_404(PlanRequest, pk=pk)
    if req.payment_link_url and req.payment_status == 'pending':
        return JsonResponse({'success': True, 'url': req.payment_link_url, 'reused': True})
    cfg = _billing_mp_config()
    if not cfg:
        return JsonResponse({
            'error': 'No hay cuenta MP de facturacion configurada. Habilite una config '
                     'MP o defina settings.SUBSCRIPTION_BILLING_COMPANY_ID'
        }, status=400)
    from core.erp import mp_qr as mp_svc
    try:
        pref = mp_svc.create_preference(
            cfg, total=req.plan.price,
            title=f'Suscripcion {req.plan.name} - {req.company_name}',
            external_reference=req.external_reference,
            notification_url=request.build_absolute_uri(reverse('erp:mp_webhook')),
            back_url=request.build_absolute_uri(reverse('erp:mp_payment_result')),
            expiration_hours=168,
        )
    except mp_svc.MpQrError as e:
        return JsonResponse({'error': str(e)}, status=502)
    req.preference_id = str(pref.get('id') or '')
    req.payment_link_url = pref.get('init_point') or ''
    req.save(update_fields=['preference_id', 'payment_link_url', 'updated_at'])
    return JsonResponse({'success': True, 'url': req.payment_link_url})


@require_POST
def plan_request_pay_status(request, pk):
    """Verificacion manual del pago (respaldo del webhook)."""
    if not _superuser_required(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    req = get_object_or_404(PlanRequest, pk=pk)
    if req.payment_status == 'pending' and req.external_reference:
        cfg = _billing_mp_config()
        if cfg:
            from core.erp import mp_qr as mp_svc
            pay = mp_svc.get_payment_by_ref(cfg, req.external_reference)
            if pay and pay.get('status') == 'approved':
                req.payment_status = 'paid'
                req.payment_id = str(pay.get('id') or '')
                req.paid_at = timezone.now()
                req.save(update_fields=['payment_status', 'payment_id', 'paid_at'])
    return JsonResponse({'status': req.payment_status, 'paid': req.payment_status == 'paid'})


@require_POST
def plan_request_reject(request, pk):
    if not _superuser_required(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)
    req = get_object_or_404(PlanRequest, pk=pk)
    req.status = 'rejected'
    req.save(update_fields=['status', 'updated_at'])
    return JsonResponse({'success': True})
