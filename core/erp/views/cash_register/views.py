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
from core.erp.sync_utils import sync_cash_register_immediately


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

        # Calcular totales en vivo para todas las cajas (abiertas y cerradas)
        for cr in qs:
            sales_qs = Sale.objects.filter(
                date_joined__date=cr.date,
                company_id=cr.company_id,
            )

            live_cash = sales_qs.filter(payment_method='cash').aggregate(total=Sum('total'))['total'] or 0
            live_card = sales_qs.filter(payment_method='card').aggregate(total=Sum('total'))['total'] or 0
            live_transfer = sales_qs.filter(payment_method='transfer').aggregate(total=Sum('total'))['total'] or 0
            live_mp = sales_qs.filter(payment_method='mp').aggregate(total=Sum('total'))['total'] or 0

            expenses_qs = Expense.objects.filter(
                date=cr.date,
                company_id=cr.company_id,
            )
            live_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0

            live_total_sales = live_cash + live_card + live_transfer + live_mp

            # Para cajas abiertas, usar valores en vivo
            if not cr.is_closed:
                cr.live_cash_sales = live_cash
                cr.live_card_sales = live_card
                cr.live_transfer_sales = live_transfer
                cr.live_mp_sales = live_mp
                cr.live_total_sales = live_total_sales
                cr.live_expenses = live_expenses
            else:
                # Para cajas cerradas, verificar si los valores guardados son correctos
                # Si no, usar los valores en vivo para mostrar datos correctos
                cr.live_cash_sales = live_cash
                cr.live_card_sales = live_card
                cr.live_transfer_sales = live_transfer
                cr.live_mp_sales = live_mp
                cr.live_total_sales = live_total_sales
                cr.live_expenses = live_expenses
                
                # Debug: mostrar diferencias si existen
                if (cr.cash_sales != live_cash or cr.card_sales != live_card or 
                    cr.transfer_sales != live_transfer or cr.mp_sales != live_mp or
                    cr.expenses != live_expenses):
                    print(f"⚠️  Caja {cr.id} cerrada tiene datos desactualizados:")
                    print(f"   Guardado - Efectivo: {cr.cash_sales}, Real: {live_cash}")
                    print(f"   Guardado - Tarjeta: {cr.card_sales}, Real: {live_card}")
                    print(f"   Guardado - Transfer: {cr.transfer_sales}, Real: {live_transfer}")
                    print(f"   Guardado - MP: {cr.mp_sales}, Real: {live_mp}")
                    print(f"   Guardado - Gastos: {cr.expenses}, Real: {live_expenses}")

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
                    
                    # Check if cash register already exists for this company, date, and user
                    from django.utils import timezone
                    today = timezone.now().date()
                    existing = CashRegister.objects.filter(
                        company=cash_register.company,
                        date=today,
                        user=cash_register.user
                    ).first()
                    
                    if existing and not existing.is_closed:
                        data['error'] = f'Ya existe una caja abierta para {existing.user.get_full_name() or existing.user.username} en la fecha {today}. Debe cerrarla antes de abrir una nueva.'
                    else:
                        # Establecer la fecha explícitamente antes de guardar
                        from django.utils import timezone
                        cash_register.date = timezone.now().date()
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
        dynamic_mp = sales_qs.filter(payment_method='mp').aggregate(total=Sum('total'))['total'] or 0

        expenses_qs = Expense.objects.filter(
            date=cash_register.date,
            company_id=cash_register.company_id,
        )
        dynamic_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0

        dynamic_total_sales = dynamic_cash + dynamic_card + dynamic_transfer + dynamic_mp
        dynamic_calculated_balance = cash_register.opening_balance + dynamic_total_sales - dynamic_expenses

        context['movements'] = cash_register.movements.all()
        context['dynamic_cash_sales'] = dynamic_cash
        context['dynamic_card_sales'] = dynamic_card
        context['dynamic_transfer_sales'] = dynamic_transfer
        context['dynamic_mp_sales'] = dynamic_mp
        context['dynamic_expenses'] = dynamic_expenses
        context['dynamic_total_sales'] = dynamic_total_sales
        context['dynamic_calculated_balance'] = dynamic_calculated_balance
        context['title'] = 'Cierre de Caja'
        context['entity'] = 'Cierre de Caja'
        return context

    def form_valid(self, form):
        cash_register = self.get_object()
        
        # Usar la fecha de la caja, no la fecha actual
        cash_register_date = cash_register.date

        # Usar la empresa de la caja para consistencia con la vista de detalle
        company_id = cash_register.company_id

        # Base de ventas del día para la empresa de la caja (usando fecha de la caja)
        sales_qs = Sale.objects.filter(date_joined__date=cash_register_date, company_id=company_id)

        # Calcular totales de ventas por forma de pago
        cash_total = sales_qs.filter(payment_method='cash').aggregate(total=Sum('total'))['total'] or 0
        card_total = sales_qs.filter(payment_method='card').aggregate(total=Sum('total'))['total'] or 0
        transfer_total = sales_qs.filter(payment_method='transfer').aggregate(total=Sum('total'))['total'] or 0
        mp_total = sales_qs.filter(payment_method='mp').aggregate(total=Sum('total'))['total'] or 0

        # Calcular gastos del día (usando fecha de la caja y empresa de la caja)
        expenses_qs = Expense.objects.filter(date=cash_register_date, company_id=company_id)
        expenses_total = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0

        # Actualizar caja
        form.instance.cash_sales = cash_total
        form.instance.card_sales = card_total
        form.instance.transfer_sales = transfer_total
        form.instance.mp_sales = mp_total
        form.instance.expenses = expenses_total
        form.instance.is_closed = True
        # Resetear is_synced para forzar sincronización del cierre
        form.instance.is_synced = False
        
        # Debug: imprimir valores para verificar
        print(f"Cerrando caja ID {cash_register.id} - Fecha: {cash_register_date} - Empresa: {company_id}")
        print(f"Ventas efectivo: {cash_total}, tarjeta: {card_total}, transfer: {transfer_total}, MP: {mp_total}")
        print(f"Gastos: {expenses_total}")
        print(f"Saldo calculado esperado: {cash_register.opening_balance + cash_total + card_total + transfer_total + mp_total - expenses_total}")

        messages.success(self.request, 'Caja cerrada correctamente')
        
        # Disparar sincronización inmediata con el servidor
        try:
            result = super().form_valid(form)
            # Siempre sincronizar el cierre de caja, independientemente del entorno
            sync_cash_register_immediately(cash_register.id)
            return result
        except Exception as e:
            messages.error(self.request, f'Error al sincronizar cierre de caja: {e}')
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
        dynamic_mp = sales_qs.filter(payment_method='mp').aggregate(total=Sum('total'))['total'] or 0

        expenses_qs = Expense.objects.filter(
            date=cash_register.date,
            company_id=cash_register.company_id,
        )
        dynamic_expenses = expenses_qs.aggregate(total=Sum('amount'))['total'] or 0

        dynamic_total_sales = dynamic_cash + dynamic_card + dynamic_transfer + dynamic_mp
        dynamic_calculated_balance = cash_register.opening_balance + dynamic_total_sales - dynamic_expenses

        context['movements'] = cash_register.movements.all()
        context['dynamic_cash_sales'] = dynamic_cash
        context['dynamic_card_sales'] = dynamic_card
        context['dynamic_transfer_sales'] = dynamic_transfer
        context['dynamic_mp_sales'] = dynamic_mp
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


class CashMovementDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = CashMovement
    template_name = 'cash_register/delete_movement.html'
    permission_required = 'erp.delete_cashmovement'
    success_url = reverse_lazy('erp:cash_register_list')
    
    def dispatch(self, request, *args, **kwargs):
        movement = self.get_object()
        # Permitir si:
        # 1. Tiene permiso general, o
        # 2. Es superusuario, o
        # 3. Es el creador del movimiento y la caja no está cerrada
        can_delete = (
            request.user.has_perm('erp.delete_cashmovement') or
            request.user.is_superuser or
            (movement.created_by == request.user and not movement.cash_register.is_closed)
        )
        
        if not can_delete:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("No tiene permisos para eliminar este movimiento")
        
        return super().dispatch(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        movement = self.get_object()
        cash_register = movement.cash_register
        
        # No permitir eliminar movimientos de cajas cerradas
        if cash_register.is_closed:
            messages.error(request, 'No se pueden eliminar movimientos de una caja cerrada')
            return redirect('erp:cash_register_detail', pk=cash_register.pk)
        
        # Actualizar totales del cash register
        if movement.movement_type == 'in':
            # Restar ingreso
            if movement.payment_type == 'cash':
                cash_register.cash_sales -= movement.amount
            elif movement.payment_type == 'card':
                cash_register.card_sales -= movement.amount
            elif movement.payment_type == 'transfer':
                cash_register.transfer_sales -= movement.amount
            elif movement.payment_type == 'mp':
                cash_register.mp_sales -= movement.amount
        else:
            # Sumar egreso (restar de gastos)
            cash_register.expenses -= movement.amount
        
        cash_register.save()
        
        # Eliminar movimiento
        movement.delete()
        
        messages.success(request, f'Movimiento de {movement.amount} eliminado correctamente')
        return redirect('erp:cash_register_detail', pk=cash_register.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Anular Movimiento de Caja'
        context['entity'] = 'Movimientos'
        context['list_url'] = reverse_lazy('erp:cash_register_detail', kwargs={'pk': self.object.cash_register.pk})
        return context