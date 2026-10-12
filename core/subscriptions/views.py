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
