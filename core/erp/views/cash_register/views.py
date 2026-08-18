from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Sum, Q, F
from django.db import transaction
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
    paginate_by = 10
    
    def get_queryset(self):
        # Determinar empresa activa igual que en la creación de caja
        active_cid = self.request.session.get('company_id')
        if not active_cid:
            active_cid = getattr(self.request.user, 'company_id', None)

        qs = CashRegister.objects.select_related('user', 'company').all()
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        return qs.order_by('-date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = context.get('object_list') or []

        # Calcular totales en vivo para todas las cajas (abiertas y cerradas)
        from datetime import date as date_class
        current_date = date_class.today()

        for cr in qs:
            # Una sola query con agregación condicional en vez de 4 separadas
            sales_date = cr.date if cr.is_closed else current_date
            sales_agg = Sale.objects.filter(
                date_joined__date=sales_date,
                company_id=cr.company_id,
            ).aggregate(
                live_cash=Sum('total', filter=Q(payment_method='cash')),
                live_card=Sum('total', filter=Q(payment_method='card')),
                live_transfer=Sum('total', filter=Q(payment_method='transfer')),
                live_mp=Sum('total', filter=Q(payment_method='mp')),
            )

            live_cash = sales_agg['live_cash'] or 0
            live_card = sales_agg['live_card'] or 0
            live_transfer = sales_agg['live_transfer'] or 0
            live_mp = sales_agg['live_mp'] or 0
            live_total_sales = live_cash + live_card + live_transfer + live_mp

            # Una sola query para gastos por método de pago
            expenses_date = cr.date if cr.is_closed else current_date
            expenses_agg = Expense.objects.filter(
                company_id=cr.company_id,
                date=expenses_date,
            ).aggregate(
                live_cash_exp=Sum('amount', filter=Q(payment_method='efectivo')),
                live_transfer_exp=Sum('amount', filter=Q(payment_method='transferencia')),
                live_mp_exp=Sum('amount', filter=Q(payment_method='mercadopago')),
                live_card_exp=Sum('amount', filter=Q(payment_method='tarjeta')),
                live_cheque_exp=Sum('amount', filter=Q(payment_method='cheque')),
                live_other_exp=Sum('amount', filter=Q(payment_method='otro')),
            )

            live_cash_expenses = expenses_agg['live_cash_exp'] or 0
            live_transfer_expenses = expenses_agg['live_transfer_exp'] or 0
            live_mp_expenses = expenses_agg['live_mp_exp'] or 0
            live_card_expenses = expenses_agg['live_card_exp'] or 0
            live_cheque_expenses = expenses_agg['live_cheque_exp'] or 0
            live_other_expenses = expenses_agg['live_other_exp'] or 0
            live_total_expenses = live_cash_expenses + live_transfer_expenses + live_mp_expenses + live_card_expenses + live_cheque_expenses + live_other_expenses

            # Asignar valores como atributos dinámicos (sin guardar en BD)
            cr.live_cash_sales = live_cash
            cr.live_card_sales = live_card
            cr.live_transfer_sales = live_transfer
            cr.live_mp_sales = live_mp
            cr.live_total_sales = live_total_sales
            cr.live_cash_expenses = live_cash_expenses
            cr.live_transfer_expenses = live_transfer_expenses
            cr.live_mp_expenses = live_mp_expenses
            cr.live_card_expenses = live_card_expenses
            cr.live_cheque_expenses = live_cheque_expenses
            cr.live_other_expenses = live_other_expenses
            cr.live_total_expenses = live_total_expenses

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

    @transaction.atomic
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
                    # Usar fecha local del sistema, no UTC
                    from datetime import date
                    today_local = date.today()
                    existing = CashRegister.objects.filter(
                        company=cash_register.company,
                        date=today_local,
                        user=cash_register.user
                    ).first()

                    if existing and not existing.is_closed:
                        data['error'] = f'Ya existe una caja abierta para {existing.user.get_full_name() or existing.user.username} en la fecha {today_local}. Debe cerrarla antes de abrir una nueva.'
                    else:
                        # Establecer la fecha local del sistema, no UTC
                        cash_register.date = today_local
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
        dynamic_cash_expenses = expenses_qs.filter(payment_method='efectivo').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_transfer_expenses = expenses_qs.filter(payment_method='transferencia').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_mp_expenses = expenses_qs.filter(payment_method='mercadopago').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_card_expenses = expenses_qs.filter(payment_method='tarjeta').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_cheque_expenses = expenses_qs.filter(payment_method='cheque').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_other_expenses = expenses_qs.filter(payment_method='otro').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_total_expenses = dynamic_cash_expenses + dynamic_transfer_expenses + dynamic_mp_expenses + dynamic_card_expenses + dynamic_cheque_expenses + dynamic_other_expenses

        dynamic_total_sales = dynamic_cash + dynamic_card + dynamic_transfer + dynamic_mp
        dynamic_calculated_balance = cash_register.opening_balance + dynamic_total_sales - dynamic_total_expenses

        context['movements'] = cash_register.movements.all()
        context['dynamic_cash_sales'] = dynamic_cash
        context['dynamic_card_sales'] = dynamic_card
        context['dynamic_transfer_sales'] = dynamic_transfer
        context['dynamic_mp_sales'] = dynamic_mp
        context['dynamic_cash_expenses'] = dynamic_cash_expenses
        context['dynamic_transfer_expenses'] = dynamic_transfer_expenses
        context['dynamic_mp_expenses'] = dynamic_mp_expenses
        context['dynamic_card_expenses'] = dynamic_card_expenses
        context['dynamic_cheque_expenses'] = dynamic_cheque_expenses
        context['dynamic_other_expenses'] = dynamic_other_expenses
        context['dynamic_total_expenses'] = dynamic_total_expenses
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

        # Calcular gastos del día por método de pago (usando fecha de la caja y empresa de la caja)
        expenses_qs = Expense.objects.filter(date=cash_register_date, company_id=company_id)
        cash_expenses_total = expenses_qs.filter(payment_method='efectivo').aggregate(total=Sum('amount'))['total'] or 0
        transfer_expenses_total = expenses_qs.filter(payment_method='transferencia').aggregate(total=Sum('amount'))['total'] or 0
        mp_expenses_total = expenses_qs.filter(payment_method='mercadopago').aggregate(total=Sum('amount'))['total'] or 0
        card_expenses_total = expenses_qs.filter(payment_method='tarjeta').aggregate(total=Sum('amount'))['total'] or 0
        cheque_expenses_total = expenses_qs.filter(payment_method='cheque').aggregate(total=Sum('amount'))['total'] or 0
        other_expenses_total = expenses_qs.filter(payment_method='otro').aggregate(total=Sum('amount'))['total'] or 0
        expenses_total = cash_expenses_total + transfer_expenses_total + mp_expenses_total + card_expenses_total + cheque_expenses_total + other_expenses_total

        # Actualizar caja
        form.instance.cash_sales = cash_total
        form.instance.card_sales = card_total
        form.instance.transfer_sales = transfer_total
        form.instance.mp_sales = mp_total
        form.instance.expenses = expenses_total
        form.instance.cash_expenses = cash_expenses_total
        form.instance.transfer_expenses = transfer_expenses_total
        form.instance.mp_expenses = mp_expenses_total
        form.instance.card_expenses = card_expenses_total
        form.instance.cheque_expenses = cheque_expenses_total
        form.instance.other_expenses = other_expenses_total
        form.instance.is_closed = True
        # Resetear is_synced para forzar sincronización del cierre
        form.instance.is_synced = False
        
        # Debug: imprimir valores para verificar
        print(f"Cerrando caja ID {cash_register.id} - Fecha: {cash_register_date} - Empresa: {company_id}")
        print(f"Ventas efectivo: {cash_total}, tarjeta: {card_total}, transfer: {transfer_total}, MP: {mp_total}")
        print(f"Gastos efectivo: {cash_expenses_total}, transfer: {transfer_expenses_total}, MP: {mp_expenses_total}, tarjeta: {card_expenses_total}, cheque: {cheque_expenses_total}, otro: {other_expenses_total}")
        print(f"Total gastos: {expenses_total}")
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

        # Para cajas abiertas, incluir ventas desde la fecha de apertura hasta ahora
        if cash_register.is_closed:
            # Si está cerrada, filtrar ventas solo del día de la caja
            sales_qs = Sale.objects.filter(
                date_joined__date=cash_register.date,
                company_id=cash_register.company_id,
            )
        else:
            # Si está abierta, filtrar ventas del día actual (usando fecha local)
            from datetime import date
            current_date = date.today()  # Fecha local del sistema
            sales_qs = Sale.objects.filter(
                date_joined__date=current_date,  # Ventas del día actual
                company_id=cash_register.company_id,
            )

        # Ventas por métodos simples
        dynamic_cash = sales_qs.filter(payment_method='cash').aggregate(total=Sum('total'))['total'] or 0
        dynamic_card = sales_qs.filter(payment_method='card').aggregate(total=Sum('total'))['total'] or 0
        dynamic_transfer = sales_qs.filter(payment_method='transfer').aggregate(total=Sum('total'))['total'] or 0
        dynamic_mp = sales_qs.filter(payment_method='mp').aggregate(total=Sum('total'))['total'] or 0
        dynamic_check = sales_qs.filter(payment_method='check').aggregate(total=Sum('total'))['total'] or 0

        # Desglosar ventas combinadas y sumar a los métodos individuales
        combined_sales = sales_qs.filter(payment_method='combined')
        for sale in combined_sales:
            if sale.payment_details:
                # Sumar cada método del pago combinado
                payment_breakdown = sale.payment_details
                if isinstance(payment_breakdown, dict):
                    dynamic_cash += payment_breakdown.get('cash', 0)
                    dynamic_card += payment_breakdown.get('card', 0)
                    dynamic_transfer += payment_breakdown.get('transfer', 0)
                    dynamic_mp += payment_breakdown.get('mp', 0)
                    dynamic_check += payment_breakdown.get('check', 0)

        # Para cajas abiertas, incluir gastos desde la fecha de apertura hasta ahora
        if cash_register.is_closed:
            # Si está cerrada, filtrar gastos solo del día de la caja
            expenses_qs = Expense.objects.filter(
                date=cash_register.date,
                company_id=cash_register.company_id,
            )
        else:
            # Si está abierta, filtrar gastos del día actual (usando fecha local)
            from datetime import date
            current_date = date.today()  # Fecha local del sistema
            expenses_qs = Expense.objects.filter(
                date=current_date,  # Gastos del día actual
                company_id=cash_register.company_id,
            )
        dynamic_cash_expenses = expenses_qs.filter(payment_method='efectivo').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_transfer_expenses = expenses_qs.filter(payment_method='transferencia').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_mp_expenses = expenses_qs.filter(payment_method='mercadopago').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_card_expenses = expenses_qs.filter(payment_method='tarjeta').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_cheque_expenses = expenses_qs.filter(payment_method='cheque').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_other_expenses = expenses_qs.filter(payment_method='otro').aggregate(total=Sum('amount'))['total'] or 0
        dynamic_total_expenses = dynamic_cash_expenses + dynamic_transfer_expenses + dynamic_mp_expenses + dynamic_card_expenses + dynamic_cheque_expenses + dynamic_other_expenses

        dynamic_total_sales = dynamic_cash + dynamic_card + dynamic_transfer + dynamic_mp + dynamic_check
        dynamic_calculated_balance = cash_register.opening_balance + dynamic_total_sales - dynamic_total_expenses

        context['movements'] = cash_register.movements.all()
        context['dynamic_cash_sales'] = dynamic_cash
        context['dynamic_card_sales'] = dynamic_card
        context['dynamic_transfer_sales'] = dynamic_transfer
        context['dynamic_mp_sales'] = dynamic_mp
        context['dynamic_check_sales'] = dynamic_check
        context['dynamic_cash_expenses'] = dynamic_cash_expenses
        context['dynamic_transfer_expenses'] = dynamic_transfer_expenses
        context['dynamic_mp_expenses'] = dynamic_mp_expenses
        context['dynamic_card_expenses'] = dynamic_card_expenses
        context['dynamic_cheque_expenses'] = dynamic_cheque_expenses
        context['dynamic_other_expenses'] = dynamic_other_expenses
        context['dynamic_total_expenses'] = dynamic_total_expenses
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

    @transaction.atomic
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