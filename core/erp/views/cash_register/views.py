from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Sum, Q
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse

from core.erp.mixins import ValidatePermissionRequiredMixin
from core.erp.models import CashRegister, CashMovement, Sale, Expense


class CashRegisterListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = CashRegister
    template_name = 'cash_register/list.html'
    permission_required = 'erp.view_cash_register'
    
    def get_queryset(self):
        # Determinar empresa activa igual que en la creación de caja
        active_cid = self.request.session.get('company_id')
        if not active_cid:
            active_cid = getattr(self.request.user, 'company_id', None)

        qs = CashRegister.objects.all()
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        return qs.order_by('-date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = context.get('object_list') or []

        # Calcular totales en vivo para cajas abiertas
        for cr in qs:
            if cr.is_closed:
                continue

            sales_qs = Sale.objects.filter(
                date_joined__date=cr.date,
                company_id=cr.company_id,
            )

            live_cash = sales_qs.filter(payment_method='cash').aggregate(total=Sum('total'))['total'] or 0
            live_card = sales_qs.filter(payment_method='card').aggregate(total=Sum('total'))['total'] or 0
            live_transfer = sales_qs.filter(payment_method='transfer').aggregate(total=Sum('total'))['total'] or 0

            expenses_qs = Expense.objects.filter(
                date=cr.date,
                company_id=cr.company_id,
            )
            live_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0

            live_total_sales = live_cash + live_card + live_transfer

            cr.live_cash_sales = live_cash
            cr.live_card_sales = live_card
            cr.live_transfer_sales = live_transfer
            cr.live_total_sales = live_total_sales
            cr.live_expenses = live_expenses

        context['title'] = 'Cierres de Caja'
        context['create_url'] = reverse_lazy('erp:cash_register_create')
        context['list_url'] = reverse_lazy('erp:cash_register_list')
        context['entity'] = 'Cierres de Caja'
        return context


class CashRegisterCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    model = CashRegister
    template_name = 'cash_register/create.html'
    fields = ['opening_balance', 'notes']
    success_url = reverse_lazy('erp:cash_register_list')
    permission_required = 'erp.add_cashregister'

    def _assign_company_and_user(self, obj):
        """Asigna company_id y user al objeto de caja usando la lógica de empresa activa."""
        active_cid = self.request.session.get('company_id')
        if not active_cid:
            active_cid = getattr(self.request.user, 'company_id', None)

        if not active_cid:
            raise ValueError('No hay una empresa activa asignada')

        obj.company_id = active_cid
        obj.user = self.request.user

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST.get('action')
            if action == 'add':
                form = self.get_form()
                if form.is_valid():
                    cash_register = form.save(commit=False)
                    self._assign_company_and_user(cash_register)
                    cash_register.save()
                    messages.success(request, 'Caja abierta correctamente')
                    data['success'] = True
                else:
                    data['error'] = form.errors
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except ValueError as e:
            # Empresa no asignada
            data['error'] = str(e)
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Apertura de Caja'
        context['action'] = 'add'
        context['list_url'] = reverse_lazy('erp:cash_register_list')
        return context


class CashRegisterCloseView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = CashRegister
    template_name = 'cash_register/close.html'
    fields = ['closing_balance', 'notes']
    success_url = reverse_lazy('erp:cash_register_list')
    permission_required = 'erp.close_cash_register'

    def form_valid(self, form):
        cash_register = self.get_object()
        today = timezone.now().date()

        # Determinar empresa activa igual que en apertura/lista
        active_cid = self.request.session.get('company_id')
        if not active_cid:
            active_cid = getattr(self.request.user, 'company_id', None)

        # Base de ventas del día para la empresa activa
        sales_qs = Sale.objects.filter(date_joined__date=today)
        if active_cid:
            sales_qs = sales_qs.filter(company_id=active_cid)

        # Calcular totales de ventas por forma de pago
        cash_total = sales_qs.filter(payment_method='cash').aggregate(total=Sum('total'))['total'] or 0
        card_total = sales_qs.filter(payment_method='card').aggregate(total=Sum('total'))['total'] or 0
        transfer_total = sales_qs.filter(payment_method='transfer').aggregate(total=Sum('total'))['total'] or 0

        # Calcular gastos del día
        expenses_qs = Expense.objects.all()
        if active_cid:
            expenses_qs = expenses_qs.filter(company_id=active_cid)
        expenses_total = expenses_qs.filter(date=today).aggregate(total=Sum('amount'))['total'] or 0

        # Actualizar caja
        form.instance.cash_sales = cash_total
        form.instance.card_sales = card_total
        form.instance.transfer_sales = transfer_total
        form.instance.expenses = expenses_total
        form.instance.is_closed = True

        messages.success(self.request, 'Caja cerrada correctamente')
        return super().form_valid(form)


class CashRegisterDetailView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DetailView):
    model = CashRegister
    template_name = 'cash_register/detail.html'
    permission_required = 'erp.view_cash_register'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cash_register = self.object

        # Totales "en vivo" para la fecha y empresa de esta caja
        sales_qs = Sale.objects.filter(
            date_joined__date=cash_register.date,
            company_id=cash_register.company_id,
        )

        dynamic_cash = sales_qs.filter(payment_method='cash').aggregate(total=Sum('total'))['total'] or 0
        dynamic_card = sales_qs.filter(payment_method='card').aggregate(total=Sum('total'))['total'] or 0
        dynamic_transfer = sales_qs.filter(payment_method='transfer').aggregate(total=Sum('total'))['total'] or 0

        expenses_qs = Expense.objects.filter(
            date=cash_register.date,
            company_id=cash_register.company_id,
        )
        dynamic_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0

        dynamic_total_sales = dynamic_cash + dynamic_card + dynamic_transfer
        dynamic_calculated_balance = cash_register.opening_balance + dynamic_total_sales - dynamic_expenses

        context['movements'] = cash_register.movements.all()
        context['dynamic_cash_sales'] = dynamic_cash
        context['dynamic_card_sales'] = dynamic_card
        context['dynamic_transfer_sales'] = dynamic_transfer
        context['dynamic_expenses'] = dynamic_expenses
        context['dynamic_total_sales'] = dynamic_total_sales
        context['dynamic_calculated_balance'] = dynamic_calculated_balance
        return context


class CashMovementCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    model = CashMovement
    fields = ['movement_type', 'amount', 'description', 'payment_type']
    permission_required = 'erp.add_cashmovement'

    def form_valid(self, form):
        cash_register = get_object_or_404(
            CashRegister,
            pk=self.kwargs['cash_register_id'],
            company=self.request.user.company
        )
        form.instance.cash_register = cash_register
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Movimiento registrado correctamente')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('erp:cash_register_detail', kwargs={'pk': self.kwargs['cash_register_id']})


class CashRegisterDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = CashRegister
    template_name = 'cash_register/delete.html'
    success_url = reverse_lazy('erp:cash_register_list')
    permission_required = 'erp.delete_cashregister'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Opcional: bloquear borrado si la caja ya está cerrada
        if self.object.is_closed:
            messages.error(request, 'No se puede eliminar una caja ya cerrada.')
            return redirect('erp:cash_register_list')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            self.object.delete()
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminación de una Caja'
        context['entity'] = 'Cierres de Caja'
        context['list_url'] = self.success_url
        return context