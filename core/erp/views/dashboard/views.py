from django.views.generic import TemplateView, UpdateView, ListView, CreateView, UpdateView, DeleteView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.db import connections
from core.erp.mixins import ValidatePermissionRequiredMixin
from core.erp.sync_utils import run_full_sync
from core.erp.forms import CompanyForm, SupplierForm, ExpenseForm, MercadoPagoConfigForm, AutoSyncConfigForm
from core.erp.models import Company, Product, Sale, DetSale, Supplier, Expense, MercadoPagoConfig, SyncLog, AutoSyncConfig
from core.erp.choices import payment_method_choices
from datetime import timedelta, date, datetime
import csv
try:
    import pandas as pd
except Exception:
    pd = None
try:
    from weasyprint import HTML, CSS
except Exception:
    HTML = CSS = None


class LauncherView(LoginRequiredMixin, TemplateView):
    template_name = 'launcher.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Obtener último registro de sincronización, priorizando la BD remota si existe
        last_log = None
        try:
            using = 'default'
            if 'remote' in connections:
                using = 'remote'
            last_log = SyncLog.objects.using(using).order_by('-created_at').first()
        except Exception:
            last_log = None

        ctx['last_sync'] = last_log
        return ctx


@csrf_exempt
@login_required
def sync_data_view(request):
    """Endpoint para lanzar sincronizacion de usuarios y ventas desde el launcher.

    Devuelve JSON con ok y lista de errores (si los hubiera).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    ok, errors = run_full_sync()
    status = 200 if ok else 207
    return JsonResponse({'ok': ok, 'errors': errors}, status=status)

class DashboardView(TemplateView):
    template_name = 'dashboard.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Resolver empresa activa
        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)
        # KPIs básicos
        UserModel = get_user_model()
        context['users_count'] = UserModel.objects.count()
        context['companies_count'] = Company.objects.count()
        prod_qs = Product.objects.all()
        sale_qs = Sale.objects.all()
        expense_qs = Expense.objects.filter(is_active=True)
        if active_cid:
            prod_qs = prod_qs.filter(company_id=active_cid)
            sale_qs = sale_qs.filter(company_id=active_cid)
            expense_qs = expense_qs.filter(company_id=active_cid)
        context['products_count'] = prod_qs.count()
        context['sales_count'] = sale_qs.count()
        context['revenue_total'] = sale_qs.aggregate(total=Sum('total'))['total'] or 0
        context['expenses_total'] = expense_qs.aggregate(total=Sum('amount'))['total'] or 0
        # Últimos 7 días de recaudación
        start = date.today() - timedelta(days=6)
        qs = (
            sale_qs.filter(date_joined__gte=start)
            .values('date_joined')
            .annotate(total=Sum('total'))
            .order_by('date_joined')
        )
        # Normalizar a 7 días consecutivos
        series_map = {x['date_joined']: float(x['total']) for x in qs}
        labels = []
        data = []
        for i in range(7):
            day = start + timedelta(days=i)
            labels.append(day.strftime('%d-%m-%Y'))
            data.append(series_map.get(day, 0.0))
        context['chart_labels'] = labels
        context['chart_data'] = data
        # Desglose por forma de pago
        pm_map = dict(payment_method_choices)
        pm_qs = (
            sale_qs.values('payment_method')
            .annotate(total=Sum('total'))
            .order_by()
        )
        context['pm_labels'] = [pm_map.get(x['payment_method'], x['payment_method']) for x in pm_qs]
        context['pm_data'] = [float(x['total']) for x in pm_qs]

        # Control de inventario (porcentaje de productos por estado de stock)
        LOW_STOCK_THRESHOLD = 10
        inv_qs = prod_qs.only('stock')
        total_prod = inv_qs.count() or 1
        out_stock = inv_qs.filter(stock__lte=0).count()
        low_stock = inv_qs.filter(stock__gt=0, stock__lt=LOW_STOCK_THRESHOLD).count()
        ok_stock = max(total_prod - out_stock - low_stock, 0)
        context['inv_labels'] = ['Sin stock', 'Stock bajo', 'Stock OK']
        context['inv_data'] = [
            round(out_stock * 100.0 / total_prod, 2),
            round(low_stock * 100.0 / total_prod, 2),
            round(ok_stock * 100.0 / total_prod, 2),
        ]

        # Empresas disponibles para superusuario
        if self.request.user.is_superuser:
            context['companies'] = Company.objects.all()
        context['active_company_id'] = self.request.session.get('company_id')
        context['panel'] = 'Panel de administrador'
        return context


class ExpenseListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = Expense
    template_name = 'expense/list.html'
    permission_required = 'erp.view_expense'

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        if not self.request.user.is_superuser:
            active_cid = self.request.session.get('company_id') or getattr(self.request.user, 'company_id', None)
            if active_cid:
                qs = qs.filter(company_id=active_cid)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Gastos'
        ctx['entity'] = 'Gastos'
        ctx['list_url'] = reverse_lazy('erp:expense_list')
        ctx['create_url'] = reverse_lazy('erp:expense_create')
        return ctx


class ExpenseCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expense/create.html'
    success_url = reverse_lazy('erp:expense_list')
    permission_required = 'erp.add_expense'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class ExpenseUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expense/create.html'
    success_url = reverse_lazy('erp:expense_list')
    permission_required = 'erp.change_expense'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class ExpenseDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = Expense
    template_name = 'expense/delete.html'
    success_url = reverse_lazy('erp:expense_list')
    permission_required = 'erp.delete_expense'

class CompanyView(LoginRequiredMixin, ValidatePermissionRequiredMixin, TemplateView):
    template_name = 'company/list.html'
    permission_required = 'erp.view_company'

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'searchdata':
                data = []
                qs = Company.objects.filter(is_active=True)
                for i in qs:
                    data.append({
                        'id': i.id,
                        'name': i.name,
                        'address': i.address or '',
                        'cuit': i.cuit or '',
                        'iibb': i.iibb or '',
                        'pos': i.pos or '',
                        'start': (i.start.strftime('%Y-%m-%d') if i.start else ''),
                        'phone': i.phone or '',
                        'email': i.email or '',
                    })
            elif action == 'add':
                form = CompanyForm(request.POST, request.FILES)
                if form.is_valid():
                    obj = form.save()
                    data = {'id': obj.id}
                else:
                    data['error'] = form.errors
            elif action == 'edit':
                obj = Company.objects.get(pk=request.POST['id'])
                form = CompanyForm(request.POST, request.FILES, instance=obj)
                if form.is_valid():
                    obj = form.save()
                    data = {'id': obj.id}
                else:
                    data['error'] = form.errors
            elif action == 'delete':
                obj = Company.objects.get(pk=request.POST['id'])
                obj.is_active = False
                obj.synced_to_server = False
                obj.save()
            else:
                data['error'] = 'Ha ocurrido un error'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Empresas'
        context['entity'] = 'Empresas'
        context['list_url'] = reverse_lazy('erp:company_list')
        context['create_url'] = reverse_lazy('erp:company_list')
        context['form'] = CompanyForm()
        return context


class SwitchCompanyView(LoginRequiredMixin, TemplateView):
    def get(self, request, pk=0, *args, **kwargs):
        if not request.user.is_superuser:
            return redirect('erp:dashboard')
        if pk and Company.objects.filter(pk=pk).exists():
            request.session['company_id'] = pk
        else:
            request.session.pop('company_id', None)
        return redirect('erp:dashboard')


class SupplierView(LoginRequiredMixin, ValidatePermissionRequiredMixin, TemplateView):
    template_name = 'supplier/list.html'
    permission_required = 'erp.view_supplier'

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'searchdata':
                data = []
                qs = Supplier.objects.filter(is_active=True)
                if not request.user.is_superuser:
                    active_cid = request.session.get('company_id') or getattr(request.user, 'company_id', None)
                    if active_cid:
                        qs = qs.filter(company_id=active_cid)
                for i in qs:
                    data.append({
                        'id': i.id,
                        'name': i.name,
                        'cuit': i.cuit or '',
                        'address': i.address or '',
                        'phone': i.phone or '',
                        'email': i.email or '',
                        'company': i.company_id or None,
                    })
            elif action == 'add':
                form = SupplierForm(request.POST, request.FILES, request=request)
                if form.is_valid():
                    obj = form.save(commit=True)
                    if isinstance(obj, dict) and 'error' in obj:
                        data['error'] = obj['error']
                    else:
                        data = {'id': obj.get('id') if isinstance(obj, dict) else getattr(obj, 'id', None)}
                else:
                    data['error'] = form.errors
            elif action == 'edit':
                obj = Supplier.objects.get(pk=request.POST['id'])
                form = SupplierForm(request.POST, request.FILES, instance=obj, request=request)
                if form.is_valid():
                    saved = form.save(commit=True)
                    if isinstance(saved, dict) and 'error' in saved:
                        data['error'] = saved['error']
                    else:
                        data = {'id': saved.get('id') if isinstance(saved, dict) else getattr(obj, 'id', None)}
                else:
                    data['error'] = form.errors
            elif action == 'delete':
                obj = Supplier.objects.get(pk=request.POST['id'])
                obj.is_active = False
                obj.synced_to_server = False
                obj.save()
            else:
                data['error'] = 'Ha ocurrido un error'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Proveedores'
        context['entity'] = 'Proveedores'
        context['list_url'] = reverse_lazy('erp:supplier_list')
        context['create_url'] = reverse_lazy('erp:supplier_list')
        context['form'] = SupplierForm(request=self.request)
        return context


class CompanyUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = Company
    form_class = CompanyForm
    template_name = 'form.html'
    success_url = reverse_lazy('erp:company')
    permission_required = 'erp.change_company'

    def get_object(self, queryset=None):
        obj = Company.objects.first()
        if obj is None:
            obj = Company.objects.create(name='Mi Empresa')
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Configuración de Empresa'
        context['entity'] = 'Empresa'
        context['list_url'] = reverse_lazy('erp:company')
        context['action'] = 'edit'
        return context


class MercadoPagoConfigUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = MercadoPagoConfig
    form_class = MercadoPagoConfigForm
    template_name = 'form.html'
    success_url = reverse_lazy('erp:dashboard')
    permission_required = 'erp.change_company'

    def dispatch(self, request, *args, **kwargs):
        # Solo superusuario puede editar credenciales MP
        if not request.user.is_superuser:
            return redirect('erp:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        # Resolver empresa activa (o la primera si no hay selección)
        active_cid = self.request.session.get('company_id')
        if not active_cid and hasattr(self.request.user, 'company_id'):
            active_cid = getattr(self.request.user, 'company_id', None)
        company = None
        if active_cid:
            company = Company.objects.filter(pk=active_cid).first()
        if company is None:
            company = Company.objects.first()
        if company is None:
            company = Company.objects.create(name='Mi Empresa')
        cfg, _ = MercadoPagoConfig.objects.get_or_create(company=company)
        return cfg

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Configuración Mercado Pago'
        ctx['entity'] = 'Mercado Pago'
        ctx['list_url'] = reverse_lazy('erp:mp_config')
        ctx['action'] = 'edit'
        return ctx


class AutoSyncConfigUpdateView(LoginRequiredMixin, UpdateView):
    model = AutoSyncConfig
    form_class = AutoSyncConfigForm
    template_name = 'form.html'
    success_url = reverse_lazy('erp:dashboard')

    def dispatch(self, request, *args, **kwargs):
        # Solo superusuario puede editar la configuración de sync automática
        if not request.user.is_superuser:
            return redirect('erp:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj, _ = AutoSyncConfig.objects.get_or_create(id=1, defaults={'interval_seconds': 300})
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Configuración de sync automática'
        ctx['entity'] = 'Sync automática'
        ctx['list_url'] = reverse_lazy('erp:sync_config')
        ctx['action'] = 'edit'
        return ctx


class ReportsHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'vtc/reports/home.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return redirect('erp:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Reportes'
        ctx['entity'] = 'Reportes'
        ctx['list_url'] = reverse_lazy('erp:reports_home')
        ctx['companies'] = Company.objects.all()
        ctx['active_company_id'] = self.request.session.get('company_id')
        return ctx


def _filter_company_qs(request, qs):
    active_cid = request.GET.get('company_id') or request.session.get('company_id')
    scope = request.GET.get('scope')
    if request.user.is_superuser:
        if scope != 'all' and active_cid:
            qs = qs.filter(company_id=active_cid)
    else:
        active_cid = active_cid or getattr(request.user, 'company_id', None)
        if active_cid:
            qs = qs.filter(company_id=active_cid)
    return qs


def report_inventory_export(request):
    if not request.user.is_superuser:
        return HttpResponse(status=403)
    fmt = (request.GET.get('format') or 'csv').lower()
    qs = Product.objects.all().select_related('cat')
    qs = _filter_company_qs(request, qs)
    rows = []
    for p in qs:
        rows.append({
            'ID': p.id,
            'Código': p.code or '',
            'Producto': p.name,
            'Categoría': getattr(p.cat, 'name', ''),
            'Precio': float(p.pvp or 0),
            'Unidad': p.unit,
            'Stock': float(p.stock or 0),
            'Empresa': p.company_id or '',
        })
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'reporte_inventario_{ts}'
    if fmt == 'csv':
        if not rows:
            return HttpResponse('', content_type='text/csv')
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        writer = csv.DictWriter(resp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        return resp
    if fmt in ('xlsx', 'xls'):
        if pd is None:
            return HttpResponse('Pandas no está instalado. Instala: pip install pandas openpyxl', status=400)
        import io
        buf = io.BytesIO()
        df = pd.DataFrame(rows)
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventario')
        resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return resp
    if fmt == 'pdf':
        if HTML is None:
            return HttpResponse('WeasyPrint no está instalado. Instala: pip install weasyprint', status=400)
        html = ['<html><head><meta charset=\"utf-8\"></head><body><h3>Inventario</h3><table border=\"1\" cellspacing=\"0\" cellpadding=\"4\">']
        if rows:
            html.append('<tr>' + ''.join(f'<th>{h}</th>' for h in rows[0].keys()) + '</tr>')
            for r in rows:
                html.append('<tr>' + ''.join(f'<td>{r[k]}</td>' for k in rows[0].keys()) + '</tr>')
        html.append('</table></body></html>')
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        base_url = request.build_absolute_uri('/')
        HTML(string=''.join(html), base_url=base_url).write_pdf(response)
        return response
    return HttpResponse('Formato no soportado', status=400)


def report_expenses_export(request):
    if not request.user.is_superuser:
        return HttpResponse(status=403)
    fmt = (request.GET.get('format') or 'csv').lower()
    qs = Expense.objects.all().select_related('supplier')
    qs = _filter_company_qs(request, qs)
    rows = []
    for e in qs:
        rows.append({
            'ID': e.id,
            'Fecha': e.date.strftime('%Y-%m-%d') if e.date else '',
            'Proveedor': getattr(e.supplier, 'name', '') if e.supplier_id else '',
            'Descripción': e.description or '',
            'Importe': float(e.amount or 0),
            'Pagado por': e.payer or '',
            'Empresa': e.company_id or '',
            'Comprobante': e.get_receipt_url() if hasattr(e, 'get_receipt_url') else '',
        })
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'reporte_gastos_{ts}'
    if fmt == 'csv':
        if not rows:
            return HttpResponse('', content_type='text/csv')
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        writer = csv.DictWriter(resp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        return resp
    if fmt in ('xlsx', 'xls'):
        if pd is None:
            return HttpResponse('Pandas no está instalado. Instala: pip install pandas openpyxl', status=400)
        import io
        buf = io.BytesIO()
        df = pd.DataFrame(rows)
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Gastos')
        resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return resp
    if fmt == 'pdf':
        if HTML is None:
            return HttpResponse('WeasyPrint no está instalado. Instala: pip install weasyprint', status=400)
        html = ['<html><head><meta charset="utf-8"></head><body><h3>Gastos</h3><table border="1" cellspacing="0" cellpadding="4">']
        if rows:
            html.append('<tr>' + ''.join(f'<th>{h}</th>' for h in rows[0].keys()) + '</tr>')
            for r in rows:
                html.append('<tr>' + ''.join(f'<td>{r[k]}</td>' for k in rows[0].keys()) + '</tr>')
        html.append('</table></body></html>')
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        base_url = request.build_absolute_uri('/')
        HTML(string=''.join(html), base_url=base_url).write_pdf(response)
        return response
    return HttpResponse('Formato no soportado', status=400)


def report_sales_export(request):
    if not request.user.is_superuser:
        return HttpResponse(status=403)
    fmt = (request.GET.get('format') or 'csv').lower()
    qs = Sale.objects.all()
    qs = _filter_company_qs(request, qs)
    pm_map = dict(payment_method_choices)
    rows = []
    for s in qs:
        rows.append({
            'ID': s.id,
            'Fecha': s.date_joined.strftime('%Y-%m-%d') if s.date_joined else '',
            'Total': float(s.total or 0),
            'Pago': pm_map.get(s.payment_method, s.payment_method),
            'Empresa': s.company_id or '',
        })
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'reporte_ventas_{ts}'
    if fmt == 'csv':
        if not rows:
            return HttpResponse('', content_type='text/csv')
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        writer = csv.DictWriter(resp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        return resp
    if fmt in ('xlsx', 'xls'):
        if pd is None:
            return HttpResponse('Pandas no está instalado. Instala: pip install pandas openpyxl', status=400)
        import io
        buf = io.BytesIO()
        df = pd.DataFrame(rows)
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Ventas')
        resp = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return resp
    if fmt == 'pdf':
        if HTML is None:
            return HttpResponse('WeasyPrint no está instalado. Instala: pip install weasyprint', status=400)
        html = ['<html><head><meta charset=\"utf-8\"></head><body><h3>Ventas</h3><table border=\"1\" cellspacing=\"0\" cellpadding=\"4\">']
        if rows:
            html.append('<tr>' + ''.join(f'<th>{h}</th>' for h in rows[0].keys()) + '</tr>')
            for r in rows:
                html.append('<tr>' + ''.join(f'<td>{r[k]}</td>' for k in rows[0].keys()) + '</tr>')
        html.append('</table></body></html>')
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        base_url = request.build_absolute_uri('/')
        HTML(string=''.join(html), base_url=base_url).write_pdf(response)
        return response
    return HttpResponse('Formato no soportado', status=400)