from django.views.generic import TemplateView, UpdateView, ListView, CreateView, UpdateView, DeleteView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.db.models import Sum, Count
from django.apps import apps
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db import connections
from django.conf import settings
from django.contrib import messages
import json
import urllib.request
import urllib.error
from decimal import Decimal
from core.erp.mixins import ValidatePermissionRequiredMixin
from core.erp.sync_utils import run_full_sync
from core.erp.services.server_sync_service import ServerSyncService
from core.erp.forms import CompanyForm, SupplierForm, ExpenseForm, MercadoPagoConfigForm, AutoSyncConfigForm
from core.utils.version_utils import get_version_info, format_version_display
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

    def dispatch(self, request, *args, **kwargs):
        print(f"DEBUG Launcher: User: {request.user.username if request.user.is_authenticated else 'Anonymous'}, Authenticated: {request.user.is_authenticated}")
        print(f"DEBUG Launcher: Session key: {request.session.session_key}")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        import os
        ctx = super().get_context_data(**kwargs)
        
        # Agregar información del entorno
        ctx['environment'] = os.getenv('ENVIRONMENT', 'development')
        
        # Agregar información de la base de datos actual
        db_config = settings.DATABASES.get('default', {})
        db_engine = db_config.get('ENGINE', '')
        if 'sqlite' in db_engine:
            ctx['database_type'] = 'SQLite'
            ctx['database_name'] = db_config.get('NAME', 'db.sqlite3')
        elif 'postgresql' in db_engine:
            ctx['database_type'] = 'PostgreSQL'
            ctx['database_name'] = db_config.get('NAME', 'N/A')
            ctx['database_host'] = db_config.get('HOST', 'localhost')
        else:
            ctx['database_type'] = 'Desconocido'
            ctx['database_name'] = 'N/A'
        
        # Agregar información de la base de datos remota si existe
        if 'remote' in connections:
            remote_db_config = settings.DATABASES.get('remote', {})
            ctx['remote_database_type'] = 'PostgreSQL'
            ctx['remote_database_name'] = remote_db_config.get('NAME', 'N/A')
            ctx['remote_database_host'] = remote_db_config.get('HOST', 'N/A')
        
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
        
        # Usar el nuevo sistema de versiones
        version_info = get_version_info()
        ctx.update({
            'app_version': format_version_display(version_info['current_version']),
            'latest_version': format_version_display(version_info['latest_version']),
            'update_available': version_info['update_available'],
            'is_dev_version': version_info['is_dev_version']
        })
        
        return ctx


@csrf_exempt
@login_required
def sync_data_view(request):
    """Endpoint para lanzar sincronizacion de datos desde el launcher.

    Devuelve JSON con ok y lista de errores (si los hubiera).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    # Obtener company_id del usuario logueado para filtrar sincronización
    company_id = None
    if hasattr(request.user, 'company_id') and request.user.company_id:
        company_id = request.user.company_id
    elif request.session.get('company_id'):
        company_id = request.session.get('company_id')

    ok, errors = run_full_sync(company_id=company_id)
    status = 200 if ok else 207
    return JsonResponse({'ok': ok, 'errors': errors}, status=status)

class DashboardView(TemplateView):
    template_name = 'base/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        print(f"DEBUG Dashboard: User: {request.user.username if request.user.is_authenticated else 'Anonymous'}, Authenticated: {request.user.is_authenticated}")
        print(f"DEBUG Dashboard: Session key: {request.session.session_key}")
        if not request.user.is_authenticated:
            print("DEBUG: User not authenticated, redirecting to login")
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        print("DEBUG: User authenticated, proceeding to dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener parámetros de filtro
        time_filter = self.request.GET.get('time_filter', 'today')  # today, week, month
        
        # Calcular fechas según el filtro
        today = date.today()
        if time_filter == 'today':
            start_date = today
            end_date = today
            filter_label = "Hoy"
        elif time_filter == 'week':
            # Calcular semana desde hoy hacia atrás, excluyendo domingos
            start_date = today
            days_checked = 0
            current_date = today
            
            while days_checked < 7:  # Buscar 7 días laborales hacia atrás
                current_date -= timedelta(days=1)
                if current_date.weekday() != 6:  # 6 = domingo, excluir domingos
                    days_checked += 1
            
            start_date = current_date + timedelta(days=1)  # El día después del último día no laboral encontrado
            end_date = today
            filter_label = "Últimos 7 días laborales"
            
            # Debug: mostrar fechas calculadas
            print(f"DEBUG: Día actual: {today}")
            print(f"DEBUG: Período: {start_date} al {end_date}")
            print(f"DEBUG: Días laborales calculados: {days_checked}")
        elif time_filter == 'month':
            # Calcular mes desde hoy hacia atrás, excluyendo domingos
            start_date = today
            days_checked = 0
            current_date = today
            
            # Buscar hacia atrás hasta encontrar 30 días laborales (aproximadamente un mes)
            while days_checked < 30:
                current_date -= timedelta(days=1)
                if current_date.weekday() != 6:  # 6 = domingo, excluir domingos
                    days_checked += 1
            
            start_date = current_date + timedelta(days=1)  # El día después del último día no laboral encontrado
            end_date = today
            filter_label = "Últimos 30 días laborales"
            
            # Debug: mostrar fechas calculadas
            print(f"DEBUG: Día actual: {today}")
            print(f"DEBUG: Período: {start_date} al {end_date}")
            print(f"DEBUG: Días laborales calculados: {days_checked}")
        else:
            start_date = today
            end_date = today
            filter_label = "Hoy"
        
        context['time_filter'] = time_filter
        context['filter_label'] = filter_label
        context['start_date'] = start_date
        context['end_date'] = end_date
        
        # Resolver empresa activa
        active_cid = self.request.session.get('company_id')
        
        # Para superusuario, permitir cambiar empresa mediante parámetro GET
        if self.request.user.is_superuser:
            url_company_id = self.request.GET.get('company_id')
            if url_company_id:
                try:
                    company_id = int(url_company_id)
                    if Company.objects.filter(id=company_id).exists():
                        self.request.session['company_id'] = company_id
                        active_cid = company_id
                    else:
                        # Si la empresa no existe, limpiar la sesión
                        self.request.session.pop('company_id', None)
                        active_cid = None
                except (ValueError, TypeError):
                    pass
            elif 'clear_company' in self.request.GET:
                # Limpiar selección de empresa
                self.request.session.pop('company_id', None)
                active_cid = None
            else:
                # Si no hay parámetro GET, usar el valor de la sesión
                active_cid = self.request.session.get('company_id')
        else:
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)
        # KPIs básicos con filtro de tiempo
        UserModel = get_user_model()
        user_qs = UserModel.objects.all()
        if active_cid:
            user_qs = user_qs.filter(company_id=active_cid)
        context['users_count'] = user_qs.count()
        context['companies_count'] = Company.objects.count()
        prod_qs = Product.objects.all()
        sale_qs = Sale.objects.filter(date_joined__date__gte=start_date, date_joined__date__lte=end_date)
        expense_qs = Expense.objects.filter(date__gte=start_date, date__lte=end_date, is_active=True)
        if active_cid:
            prod_qs = prod_qs.filter(company_id=active_cid)
            sale_qs = sale_qs.filter(company_id=active_cid)
            expense_qs = expense_qs.filter(company_id=active_cid)
        context['products_count'] = prod_qs.count()
        context['sales_count'] = sale_qs.count()
        context['revenue_total'] = sale_qs.aggregate(total=Sum('total'))['total'] or 0
        context['expenses_total'] = expense_qs.aggregate(total=Sum('amount'))['total'] or 0
        # Gráfico de recaudación según el período
        if time_filter == 'today':
            # Para hoy, mostrar horas
            from django.db import connection
            if connection.vendor == 'postgresql':
                # PostgreSQL usa EXTRACT
                qs = (
                    sale_qs.filter(date_joined__date=today)
                    .extra({'hour': "EXTRACT(HOUR FROM date_joined)"})
                    .values('hour')
                    .annotate(total=Sum('total'))
                    .order_by('hour')
                )
            else:
                # SQLite usa strftime
                qs = (
                    sale_qs.filter(date_joined__date=today)
                    .extra({'hour': "strftime('%%H', date_joined)"})
                    .values('hour')
                    .annotate(total=Sum('total'))
                    .order_by('hour')
                )
            labels = [f"{h:02d}:00" for h in range(8, 22)]  # 8 AM a 10 PM
            data = []
            series_map = {int(float(x['hour'])): float(x['total']) for x in qs}
            for h in range(8, 22):
                data.append(series_map.get(h, 0.0))
        elif time_filter == 'week':
            # Para semana, mostrar días
            qs = (
                sale_qs.filter(date_joined__date__gte=start_date, date_joined__date__lte=end_date)
                .values('date_joined__date')
                .annotate(total=Sum('total'))
                .order_by('date_joined__date')
            )
            labels = []
            data = []
            series_map = {x['date_joined__date']: float(x['total']) for x in qs}
            for i in range(7):
                day = start_date + timedelta(days=i)
                labels.append(day.strftime('%d/%m'))
                data.append(series_map.get(day, 0.0))
        else:  # month
            # Para mes, mostrar semanas
            weeks = []
            current = start_date
            while current <= end_date:
                week_end = min(current + timedelta(days=6), end_date)
                weeks.append((current, week_end))
                current = week_end + timedelta(days=1)
            
            labels = []
            data = []
            for i, (week_start, week_end) in enumerate(weeks):
                week_total = sale_qs.filter(
                    date_joined__date__gte=week_start,
                    date_joined__date__lte=week_end
                ).aggregate(total=Sum('total'))['total'] or 0
                labels.append(f"Sem {i+1}")
                data.append(float(week_total))
        
        context['chart_labels'] = json.dumps(labels)
        context['chart_data'] = json.dumps(data)
        # Desglose por forma de pago
        pm_map = dict(payment_method_choices)
        pm_qs = (
            sale_qs.values('payment_method')
            .annotate(total=Sum('total'))
            .order_by()
        )
        context['pm_labels'] = json.dumps([pm_map.get(x['payment_method'], x['payment_method']) for x in pm_qs])
        context['pm_data'] = json.dumps([float(x['total']) for x in pm_qs])

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
            # Calcular ganancias para superusuario
            context.update(self.calculate_profits_data(active_cid))
        context['active_company_id'] = self.request.session.get('company_id')
        context['panel'] = 'Panel de administrador'
        context['app_version'] = getattr(settings, 'APP_VERSION', '1.0.0')
        return context

    def calculate_profits_data(self, active_cid):
        """Calcular datos de ganancias para el dashboard"""
        data = {}
        
        if self.request.user.is_superuser:
            # Ganancias generales (todas las empresas)
            all_sales = Sale.objects.all()
            all_expenses = Expense.objects.filter(is_active=True)
            
            # Calcular costo total de ventas
            total_cost_all = Decimal('0')
            for sale in all_sales:
                for detail in sale.detsale_set.all():
                    if detail.prod.cost_price:
                        total_cost_all += Decimal(str(detail.prod.cost_price)) * detail.cant
            
            total_revenue_all = Decimal(str(all_sales.aggregate(total=Sum('total'))['total'] or 0))
            total_expenses_all = Decimal(str(all_expenses.aggregate(total=Sum('amount'))['total'] or 0))
            total_profit_all = total_revenue_all - total_cost_all - total_expenses_all
            
            # Asegurar que los valores sean numéricos
            data['total_profit_all'] = float(round(total_profit_all, 2)) if total_profit_all else 0.0
            data['total_revenue_all'] = float(round(total_revenue_all, 2)) if total_revenue_all else 0.0
            data['total_cost_all'] = float(round(total_cost_all, 2)) if total_cost_all else 0.0
            data['total_expenses_all'] = float(round(total_expenses_all, 2)) if total_expenses_all else 0.0
            
            # Ganancias por empresa
            company_profits = []
            for company in Company.objects.all():
                company_sales = Sale.objects.filter(company=company)
                company_expenses = Expense.objects.filter(company=company, is_active=True)
                
                # Calcular costo de ventas de la empresa
                company_cost = Decimal('0')
                for sale in company_sales:
                    for detail in sale.detsale_set.all():
                        if detail.prod.cost_price:
                            company_cost += Decimal(str(detail.prod.cost_price)) * detail.cant
                
                company_revenue = Decimal(str(company_sales.aggregate(total=Sum('total'))['total'] or 0))
                company_expense_total = Decimal(str(company_expenses.aggregate(total=Sum('amount'))['total'] or 0))
                company_profit = company_revenue - company_cost - company_expense_total
                
                company_profits.append({
                    'company': company,
                    'revenue': company_revenue,
                    'cost': company_cost,
                    'expenses': company_expense_total,
                    'profit': company_profit
                })
            
            data['company_profits'] = company_profits
            
            # Si hay una empresa activa, mostrar sus ganancias específicas
            if active_cid:
                active_company = Company.objects.filter(id=active_cid).first()
                if active_company:
                    active_sales = Sale.objects.filter(company=active_company)
                    active_expenses = Expense.objects.filter(company=active_company, is_active=True)
                    
                    # Calcular costo de ventas de la empresa activa
                    active_cost = Decimal('0')
                    for sale in active_sales:
                        for detail in sale.detsale_set.all():
                            if detail.prod.cost_price:
                                active_cost += Decimal(str(detail.prod.cost_price)) * detail.cant
                    
                    active_revenue = Decimal(str(active_sales.aggregate(total=Sum('total'))['total'] or 0))
                    active_expense_total = Decimal(str(active_expenses.aggregate(total=Sum('amount'))['total'] or 0))
                    active_profit = active_revenue - active_cost - active_expense_total
                    
                    # Asegurar que los valores sean numéricos
                    data['active_company_profit'] = float(round(active_profit, 2)) if active_profit else 0.0
                    data['active_company'] = active_company
        
        return data


class UpdatesView(TemplateView):
    template_name = 'vtc/updates.html'

    def dispatch(self, request, *args, **kwargs):
        if request.path == '/erp/backup-to-server/':
            return self.backup_to_server(request)
        elif request.path == '/erp/updates/' and request.method == 'POST':
            return self.execute_update(request)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Usar el nuevo sistema de versiones
        version_info = get_version_info()
        ctx.update({
            'app_version': format_version_display(version_info['current_version']),
            'latest_version': format_version_display(version_info['latest_version']),
            'update_available': version_info['update_available'],
            'is_dev_version': version_info['is_dev_version']
        })
        
        # Detectar sistema operativo para mostrar el botón correcto
        import platform
        system_os = platform.system().lower()  # 'windows', 'linux', 'darwin'
        ctx['is_windows'] = system_os == 'windows'
        ctx['is_linux'] = system_os == 'linux'
        ctx['is_mac'] = system_os == 'darwin'  # macOS
        
        # Verificar estado del sistema de actualización
        try:
            import subprocess
            import os
            base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
            script_path = os.path.join(base_dir, 'update_system.py')
            
            if os.path.exists(script_path):
                result = subprocess.run([
                    'python3' if system_os == 'linux' else 'python', 
                    script_path, '--status', '--json'
                ], cwd=base_dir, capture_output=True, text=True)
                
                if result.returncode == 0:
                    import json
                    status = json.loads(result.stdout)
                    ctx.update({
                        'update_status': status,
                        'can_update': status.get('git_available') and status.get('git_repo'),
                        'has_changes': status.get('has_changes', False)
                    })
        except:
            pass
        
        return ctx
    
    def execute_update(self, request):
        """Ejecuta el script de actualización según el SO detectado."""
        import platform
        import subprocess
        import os
        from django.contrib import messages
        
        system_os = platform.system().lower()
        base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
        
        # Verificar si se debe forzar la actualización
        force = request.POST.get('force', 'false').lower() == 'true'
        
        try:
            # Script Python unificado
            script_path = os.path.join(base_dir, 'update_system.py')
            
            if not os.path.exists(script_path):
                messages.error(request, "No se encuentra el script de actualización")
                return redirect('erp:updates')
            
            # Construir comando según el sistema operativo
            if system_os == 'windows':
                command = ['actualizar_pos_simple.bat']
                if force:
                    command.append('--force')
            elif system_os == 'darwin':  # macOS
                command = ['python3', 'update_system.py']
                if force:
                    command.append('--force')
            elif system_os == 'linux':
                command = ['python3', 'update_system.py']
                if force:
                    command.append('--force')
            else:
                messages.error(request, f"Sistema operativo no soportado: {system_os}")
                return redirect('erp:updates')
            
            # Ejecutar el script en segundo plano
            if system_os == 'windows':
                subprocess.Popen(
                    command,
                    shell=True,
                    cwd=base_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                subprocess.Popen(
                    command,
                    cwd=base_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
            
            messages.success(request, "Actualización iniciada en segundo plano")
            
        except Exception as e:
            messages.error(request, f"Error al iniciar la actualización: {str(e)}")
        
        return redirect('erp:updates')
    
    def backup_to_server(self, request):
        """Vista para hacer backup al servidor."""
        from core.erp.sync_utils import backup_to_server
        
        success, messages = backup_to_server()
        
        if success:
            from django.contrib import messages
            if isinstance(messages, list) and messages:
                messages.success(request, f"Backup enviado: {messages[0]}")
            else:
                messages.success(request, "Backup enviado exitosamente")
        else:
            from django.contrib import messages
            if isinstance(messages, list) and messages:
                messages.error(request, f"Error en backup: {messages[0]}")
            else:
                messages.error(request, "Error en backup")
        
        return redirect('erp:updates')


class ExpenseListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = Expense
    template_name = 'expense/list.html'
    permission_required = 'erp.view_expense'

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'searchdata':
                data = []
                for i in self.get_queryset():
                    data.append(i.toJSON())
            elif action == 'delete_duplicates':
                # Eliminar gastos duplicados de la base de datos remota
                data = self.delete_duplicate_expenses()
            else:
                data['error'] = 'Ha ocurrido un error'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def delete_duplicate_expenses(self):
        """Eliminar gastos duplicados de la base de datos remota"""
        from django.db import connections
        
        if 'remote' not in connections:
            return {'error': 'No hay conexión a base de datos remota'}
        
        try:
            # Obtener todos los gastos de la base remota
            remote_expenses = []
            with connections['remote'].cursor() as cursor:
                cursor.execute("""
                    SELECT id, local_uuid, local_expense_id, amount, date, desc, company_id, 
                           synced_to_server, source
                    FROM erp_expense 
                    WHERE is_active = TRUE
                    ORDER BY date DESC, id DESC
                """)
                columns = [col[0] for col in cursor.description]
                for row in cursor.fetchall():
                    expense_dict = dict(zip(columns, row))
                    remote_expenses.append(expense_dict)
            
            # Identificar duplicados basados en local_uuid o local_expense_id
            duplicates_to_delete = []
            seen_uuids = set()
            seen_local_ids = set()
            
            for expense in remote_expenses:
                is_duplicate = False
                
                # Verificar duplicado por local_uuid
                if expense['local_uuid']:
                    if expense['local_uuid'] in seen_uuids:
                        is_duplicate = True
                    else:
                        seen_uuids.add(expense['local_uuid'])
                
                # Verificar duplicado por local_expense_id
                if expense['local_expense_id']:
                    if expense['local_expense_id'] in seen_local_ids:
                        is_duplicate = True
                    else:
                        seen_local_ids.add(expense['local_expense_id'])
                
                # Si es duplicado, agregar a lista para eliminar (mantener el más reciente)
                if is_duplicate:
                    duplicates_to_delete.append(expense['id'])
            
            # Eliminar duplicados
            deleted_count = 0
            if duplicates_to_delete:
                with connections['remote'].cursor() as cursor:
                    # Marcar como inactivos en lugar de eliminar físicamente
                    placeholders = ','.join(['%s'] * len(duplicates_to_delete))
                    cursor.execute(f"""
                        UPDATE erp_expense 
                        SET is_active = FALSE, 
                            synced_to_server = FALSE 
                        WHERE id IN ({placeholders})
                    """, duplicates_to_delete)
                    deleted_count = cursor.rowcount
                
                return {
                    'success': True,
                    'message': f'Se han eliminado {deleted_count} gastos duplicados',
                    'deleted_count': deleted_count
                }
            else:
                return {
                    'success': True,
                    'message': 'No se encontraron gastos duplicados',
                    'deleted_count': 0
                }
                
        except Exception as e:
            return {'error': f'Error al eliminar duplicados: {str(e)}'}

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Handle period parameter
        period = self.request.GET.get('period')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        # If period is specified, calculate dates
        if period and not (start_date or end_date):
            from django.utils import timezone
            from datetime import timedelta
            
            today = timezone.now().date()
            
            if period == 'today':
                start_date = today.strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            elif period == 'week':
                # Start of week (Monday)
                start_of_week = today - timedelta(days=today.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                start_date = start_of_week.strftime('%Y-%m-%d')
                end_date = end_of_week.strftime('%Y-%m-%d')
            elif period == 'month':
                # Start of month
                start_of_month = today.replace(day=1)
                # End of month
                from calendar import monthrange
                last_day = monthrange(today.year, today.month)[1]
                end_of_month = today.replace(day=last_day)
                start_date = start_of_month.strftime('%Y-%m-%d')
                end_date = end_of_month.strftime('%Y-%m-%d')
        
        # Apply date range filters
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
        
        if not self.request.user.is_superuser:
            active_cid = self.request.session.get('company_id') or getattr(self.request.user, 'company_id', None)
            if active_cid:
                qs = qs.filter(company_id=active_cid)
        
        # Ordenar para mostrar los más recientes primero
        qs = qs.order_by('-date', '-id')
        
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Gastos/Compras'
        ctx['entity'] = 'Gastos/Compras'
        ctx['list_url'] = reverse_lazy('erp:expense_list')
        ctx['create_url'] = reverse_lazy('erp:expense_create')
        return ctx


class ExpenseCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expense/create.html'
    success_url = reverse_lazy('erp:expense_list')
    permission_required = 'erp.add_expense'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Nuevo Gasto/Compra'
        ctx['entity'] = 'Gastos/Compras'
        ctx['list_url'] = reverse_lazy('erp:expense_list')
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        try:
            # Usar nuestro método save personalizado
            result = form.save()

            # Verificar si hay error en el resultado
            if 'error' in result:
                messages.error(self.request, f'Error al guardar gasto: {result["error"]}')
                return self.form_invalid(form)

            # Éxito
            messages.success(self.request, 'Gasto/Compra creado correctamente')
            return HttpResponseRedirect(reverse_lazy('erp:expense_list'))

        except Exception as e:
            messages.error(self.request, f'Error inesperado: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)


class ExpenseUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expense/create.html'
    success_url = reverse_lazy('erp:expense_list')
    permission_required = 'erp.change_expense'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Editar Gasto/Compra'
        ctx['entity'] = 'Gastos/Compras'
        ctx['list_url'] = reverse_lazy('erp:expense_list')
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        try:
            # Usar nuestro método save personalizado
            result = form.save()

            # Verificar si hay error en el resultado
            if 'error' in result:
                messages.error(self.request, f'Error al actualizar gasto: {result["error"]}')
                return self.form_invalid(form)

            # Éxito
            messages.success(self.request, 'Gasto/Compra actualizado correctamente')
            return HttpResponseRedirect(self.get_success_url())

        except Exception as e:
            messages.error(self.request, f'Error inesperado: {str(e)}')
            return self.form_invalid(form)


class ExpenseDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = Expense
    template_name = 'expense/delete.html'
    success_url = reverse_lazy('erp:expense_list')
    permission_required = 'erp.delete_expense'

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, 'Gasto/Compra eliminado correctamente')
        return response


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
                with transaction.atomic():
                    form = CompanyForm(request.POST, request.FILES)
                    if form.is_valid():
                        obj = form.save()
                        data = {'id': obj.id}
                    else:
                        data['error'] = form.errors
            elif action == 'edit':
                with transaction.atomic():
                    obj = Company.objects.get(pk=request.POST['id'])
                    form = CompanyForm(request.POST, request.FILES, instance=obj)
                    if form.is_valid():
                        obj = form.save()
                        data = {'id': obj.id}
                    else:
                        data['error'] = form.errors
            elif action == 'delete':
                with transaction.atomic():
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
                if request.user.is_superuser:
                    active_cid = request.session.get('company_id')
                else:
                    active_cid = getattr(request.user, 'company_id', None)
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                for i in qs:
                    data.append({
                        'id': i.id,
                        'code': i.code or '',
                        'name': i.name,
                        'cuit': i.cuit or '',
                        'address': i.address or '',
                        'phone': i.phone or '',
                        'email': i.email or '',
                        'company': i.company_id or None,
                    })
            elif action == 'add':
                with transaction.atomic():
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
                with transaction.atomic():
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
                with transaction.atomic():
                    obj = Supplier.objects.get(pk=request.POST['id'])
                    obj.is_active = False
                    obj.synced_to_server = False
                    obj.save()
            elif action == 'delete_all':
                qs = Supplier.objects.filter(is_active=True)
                if request.user.is_superuser:
                    active_cid = request.session.get('company_id')
                else:
                    active_cid = getattr(request.user, 'company_id', None)
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                count = qs.count()
                qs.update(is_active=False, synced_to_server=False)
                data = {'success': True, 'count': count}
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
    template_name = 'base/form.html'
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
    template_name = 'base/form.html'
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

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return response

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Error en el formulario', 'errors': form.errors})
        return super().form_invalid(form)


class AutoSyncConfigUpdateView(LoginRequiredMixin, UpdateView):
    model = AutoSyncConfig
    form_class = AutoSyncConfigForm
    template_name = 'base/form.html'
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
        ctx['list_url'] = reverse_lazy('erp:profit_report_list')
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
    # Permitir a cualquier usuario autenticado descargar el inventario,
    # filtrando por empresa activa/relacionada con _filter_company_qs.
    if not request.user.is_authenticated:
        return HttpResponse(status=403)

    fmt = (request.GET.get('format') or 'csv').lower()
    qs = Product.objects.all().select_related('cat', 'company')
    qs = _filter_company_qs(request, qs)

    # Definir encabezados en español
    headers = [
        'ID', 'Código', 'Producto', 'Categoría',
        'Precio', 'IVA (%)', 'Precio con IVA',
        'Unidad', 'Stock', 'Empresa',
    ]

    rows = []
    for p in qs:
        rows.append({
            'ID': p.id,
            'Código': p.code or '',
            'Producto': p.name,
            'Categoría': getattr(p.cat, 'name', ''),
            'Precio': float(p.pvp or 0),
            'IVA (%)': float(p.iva_rate or 0),
            'Precio con IVA': float(p.pvp_final or 0),
            'Unidad': p.unit,
            'Stock': float(p.stock or 0),
            'Empresa': getattr(p.company, 'name', '') if p.company_id else '',
        })

    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'reporte_inventario_{ts}'

    if fmt == 'csv':
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        writer = csv.DictWriter(resp, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        return resp

    if fmt in ('xlsx', 'xls'):
        if pd is None:
            return HttpResponse('Pandas no está instalado. Instala: pip install pandas openpyxl', status=400)
        import io
        buf = io.BytesIO()
        # Si no hay filas, crear DataFrame vacío solo con encabezados
        if rows:
            df = pd.DataFrame(rows, columns=headers)
        else:
            df = pd.DataFrame(columns=headers)
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
            'Fecha': e.date.strftime('%d/%m/%Y') if e.date else '',
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


def expense_export(request):
    """Export expense report with daily summary and total sum"""
    # Debug: Log user and permissions
    print(f"DEBUG: User {request.user.username}, is_superuser: {request.user.is_superuser}")
    print(f"DEBUG: User permissions: {[p.codename for p in request.user.user_permissions.all()]}")
    print(f"DEBUG: Has erp.view_expense: {request.user.has_perm('erp.view_expense')}")
    print(f"DEBUG: Is authenticated: {request.user.is_authenticated}")
    
    # Allow all authenticated users for testing
    if not request.user.is_authenticated:
        print("DEBUG: User not authenticated, returning 403")
        return HttpResponse(status=403)
    
    print("DEBUG: User authenticated, proceeding with export")
    
    fmt = (request.GET.get('format') or 'csv').lower()
    print(f"DEBUG: Export format: {fmt}")
    
    # Get today's date or use date range if provided
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models.functions import TruncDay
    
    today = timezone.now().date()
    start_date = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', today.strftime('%Y-%m-%d'))
    
    # Filter expenses for the date range
    qs = Expense.objects.filter(date__range=[start_date, end_date]).select_related('supplier', 'company')
    qs = _filter_company_qs(request, qs).order_by('date')
    
    # Get daily summary
    daily_summary = qs.annotate(
        day=TruncDay('date')
    ).values('day').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('day')
    
    # Get total sum
    total_amount = qs.aggregate(total=Sum('amount'))['total'] or 0
    total_count = qs.count()
    
    # Prepare detailed rows with items as columns
    detailed_rows = []
    for expense in qs:
        # Get expense items if they exist
        items = []
        if hasattr(expense, 'items'):
            for item in expense.items.all():
                items.append(f"{item.description} (${item.amount:.2f})")
        items_str = " | ".join(items) if items else "N/A"
        
        detailed_rows.append({
            'Fecha': expense.date.strftime('%d/%m/%Y') if expense.date else '',
            'Proveedor': expense.supplier.name if expense.supplier else 'N/A',
            'Descripción': expense.description or '',
            'Items': items_str,
            'Monto': float(expense.amount or 0),
            'Pagado por': expense.payer or '',
            'Empresa': expense.company.name if expense.company else 'N/A'
        })
    
    # Prepare daily summary rows
    summary_rows = []
    for day_data in daily_summary:
        summary_rows.append({
            'Fecha': day_data['day'].strftime('%d/%m/%Y') if day_data['day'] else '',
            'Total Gastos': float(day_data['total'] or 0),
            'Cantidad': day_data['count'] or 0
        })
    
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'gastos_diarios_{start_date}_al_{end_date}_{ts}'
    
    if fmt == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
        writer = csv.writer(response)
        
        # Title
        writer.writerow(['REPORTE DE GASTOS DIARIOS'])
        writer.writerow([f'Período: {start_date} al {end_date}'])
        writer.writerow([])
        
        # Detailed expenses
        writer.writerow(['DETALLE DE GASTOS'])
        writer.writerow(['Fecha', 'Proveedor', 'Descripción', 'Items', 'Monto', 'Pagado por', 'Empresa'])
        for row in detailed_rows:
            writer.writerow([
                row['Fecha'],
                row['Proveedor'],
                row['Descripción'],
                row['Items'],
                row['Monto'],
                row['Pagado por'],
                row['Empresa']
            ])
        
        # Add total sum row
        writer.writerow([])
        writer.writerow(['TOTAL GENERAL', '', '', '', '', total_amount, '', ''])
        
        # Daily summary
        writer.writerow([])
        writer.writerow(['RESUMEN DIARIO'])
        writer.writerow(['Fecha', 'Total Gastos', 'Cantidad'])
        for row in summary_rows:
            writer.writerow([
                row['Fecha'],
                row['Total Gastos'],
                row['Cantidad']
            ])
        
        # Total summary
        writer.writerow([])
        writer.writerow(['RESUMEN GENERAL'])
        writer.writerow(['Total General de Gastos', total_amount])
        writer.writerow(['Total de Registros', total_count])
        writer.writerow(['Promedio por Gasto', total_amount / total_count if total_count > 0 else 0])
        
        return response
    
    if fmt in ('xlsx', 'xls'):
        if pd is None:
            return HttpResponse('Pandas no está instalado. Instala: pip install pandas openpyxl', status=400)
        
        import io
        buf = io.BytesIO()
        
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            # Detailed expenses sheet
            if detailed_rows:
                df_detailed = pd.DataFrame(detailed_rows)
                df_detailed.to_excel(writer, index=False, sheet_name='Detalle Gastos')
            
            # Add total sum row to detailed sheet
            if detailed_rows:
                total_row = pd.DataFrame([{
                    'Fecha': 'TOTAL GENERAL',
                    'Proveedor': '',
                    'Descripción': '',
                    'Items': '',
                    'Monto': total_amount,
                    'Pagado por': '',
                    'Empresa': ''
                }])
                pd.concat([df_detailed, total_row]).to_excel(writer, index=False, sheet_name='Detalle Gastos', startrow=0)
            
            # Daily summary sheet
            if summary_rows:
                df_summary = pd.DataFrame(summary_rows)
                df_summary.to_excel(writer, index=False, sheet_name='Resumen Diario')
            
            # Add total summary sheet
            total_data = [{
                'Concepto': 'Total General de Gastos',
                'Monto': total_amount,
                'Cantidad': total_count,
                'Promedio': total_amount / total_count if total_count > 0 else 0
            }]
            df_total = pd.DataFrame(total_data)
            df_total.to_excel(writer, index=False, sheet_name='Resumen General')
        
        response = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return response
    
    if fmt == 'pdf':
        # Try using ReportLab as alternative to WeasyPrint
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from io import BytesIO
            
            # Create PDF buffer
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []
            
            # Styles
            styles = getSampleStyleSheet()
            title_style = styles['Heading1']
            heading_style = styles['Heading2']
            normal_style = styles['Normal']
            
            # Title
            elements.append(Paragraph("REPORTE DE GASTOS", title_style))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(f"<b>Período:</b> {start_date} al {end_date}", normal_style))
            elements.append(Spacer(1, 20))
            
            # Summary Table
            elements.append(Paragraph("RESUMEN DE GASTOS", heading_style))
            elements.append(Spacer(1, 12))
            
            # Table data
            table_data = [['Fecha', 'Proveedor', 'Descripción', 'Items', 'Monto', 'Pagado por', 'Empresa']]
            for row in detailed_rows:
                table_data.append([
                    row['Fecha'],
                    row['Proveedor'],
                    row['Descripción'],
                    row['Items'],
                    f"${row['Monto']:.2f}",
                    row['Pagado por'],
                    row['Empresa']
                ])
            
            # Add total row
            table_data.append(['', '', '', '', f"${total_amount:.2f}", '', ''])
            
            # Create table
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
                ('FONTNAME', (4, -1), (4, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (4, -1), (4, -1), colors.lightgrey),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 20))
            
            # Statistics
            elements.append(Paragraph("RESUMEN ESTADÍSTICO", heading_style))
            elements.append(Spacer(1, 12))
            
            stats_data = [
                ['Total de Gastos', f"${total_amount:.2f}"],
                ['Cantidad de Registros', str(total_count)],
                ['Promedio por Gasto', f"${total_amount / total_count if total_count > 0 else 0:.2f}"]
            ]
            
            stats_table = Table(stats_data)
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ]))
            
            elements.append(stats_table)
            
            # Build PDF
            doc.build(elements)
            buffer.seek(0)
            
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="resumen_gastos_{start_date}_al_{end_date}.pdf"'
            return response
            
        except ImportError:
            # Fallback to HTML if ReportLab is not available
            return HttpResponse('ReportLab no está instalado. Instala: pip install reportlab', status=400)
        except Exception as e:
            # Fallback to HTML if PDF generation fails
            html = f'''
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h1 {{ text-align: center; color: #333; }}
                    h2 {{ color: #333; border-bottom: 1px solid #ccc; }}
                    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; font-weight: bold; }}
                    .text-right {{ text-align: right; }}
                    .summary {{ background-color: #f9f9f9; font-weight: bold; }}
                    .total {{ background-color: #e0e0e0; font-weight: bold; font-size: 14px; }}
                </style>
            </head>
            <body>
                <h1>REPORTE DE GASTOS</h1>
                <p><strong>Período:</strong> {start_date} al {end_date}</p>
                
                <h2>RESUMEN DE GASTOS</h2>
                <table>
                    <tr>
                        <th>Fecha</th>
                        <th>Proveedor</th>
                        <th>Descripción</th>
                        <th>Items</th>
                        <th class="text-right">Monto</th>
                        <th>Pagado por</th>
                        <th>Empresa</th>
                    </tr>
            '''
            
            for row in detailed_rows:
                html += f'''
                    <tr>
                        <td>{row['Fecha']}</td>
                        <td>{row['Proveedor']}</td>
                        <td>{row['Descripción']}</td>
                        <td>{row['Items']}</td>
                        <td class="text-right">${row['Monto']:.2f}</td>
                        <td>{row['Pagado por']}</td>
                        <td>{row['Empresa']}</td>
                    </tr>
                '''
            
            html += f'''
                    <tr class="total">
                        <td colspan="4"><strong>TOTAL GENERAL</strong></td>
                        <td class="text-right"><strong>${total_amount:.2f}</strong></td>
                        <td colspan="2"></td>
                    </tr>
                </table>
                
                <h2>RESUMEN ESTADÍSTICO</h2>
                <table>
                    <tr class="summary">
                        <td><strong>Total de Gastos</strong></td>
                        <td class="text-right">${total_amount:.2f}</td>
                    </tr>
                    <tr class="summary">
                        <td><strong>Cantidad de Registros</strong></td>
                        <td class="text-right">{total_count}</td>
                    </tr>
                    <tr class="summary">
                        <td><strong>Promedio por Gasto</strong></td>
                        <td class="text-right">${total_amount / total_count if total_count > 0 else 0:.2f}</td>
                    </tr>
                </table>
            </body>
            </html>
            '''
            
            response = HttpResponse(html, content_type='text/html')
            response['Content-Disposition'] = f'attachment; filename="resumen_gastos_{start_date}_al_{end_date}.html"'
            return response
    
    return HttpResponse('Formato no soportado', status=400)


class DatabaseCleanupView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Vista para limpiar datos de negocio (solo modo servidor y superusuario)."""
    template_name = 'database_cleanup.html'

    def test_func(self):
        return self.request.user.is_superuser

    def dispatch(self, request, *args, **kwargs):
        if not ServerSyncService.is_server_mode():
            return HttpResponseForbidden('Solo disponible en modo servidor.')
        return super().dispatch(request, *args, **kwargs)

    PROTECTED_MODELS = {
        'Company',
        'PosTerminal',
        'AfipConfig',
        'AfipPuntoVenta',
        'MercadoPagoConfig',
        'AutoSyncConfig',
        'GlobalSyncStatus',
        'GlobalPosConfig',
        'CatalogoConfig',
        'ActivityLog',
        'SyncLog',
        'CardInstallmentPlan',
        'PriceList',
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        targets = self._get_targets()
        counts = []
        for model in targets:
            counts.append({
                'name': model._meta.verbose_name_plural or model.__name__,
                'count': model.objects.count(),
                'class': model.__name__,
            })
        context['counts'] = counts
        context['total'] = sum(c['count'] for c in counts)
        return context

    def _get_targets(self):
        models = apps.get_app_config('erp').get_models()
        targets = [m for m in models if m.__name__ not in self.PROTECTED_MODELS]
        targets.sort(key=lambda x: x.__name__)
        return targets

    def post(self, request, *args, **kwargs):
        if not request.POST.get('confirm'):
            messages.error(request, 'Debe confirmar la limpieza.')
            return redirect('erp:database_cleanup')
        targets = self._get_targets()
        order = self._deletion_order(targets)
        try:
            with transaction.atomic():
                for model in order:
                    model.objects.all().delete()
        except Exception as e:
            messages.error(request, f'Error al limpiar la base de datos: {e}')
            return redirect('erp:database_cleanup')
        messages.success(request, 'Base de datos limpiada correctamente.')
        return redirect('erp:database_cleanup')

    def _deletion_order(self, models):
        model_set = set(models)
        graph = {m: set() for m in models}
        for m in models:
            for f in m._meta.get_fields():
                if not f.is_relation:
                    continue
                if not (getattr(f, 'many_to_one', False) or getattr(f, 'one_to_one', False)):
                    continue
                if getattr(f, 'auto_created', False):
                    continue
                rel = getattr(f, 'related_model', None)
                if rel in model_set:
                    graph[m].add(rel)

        in_degree = {m: 0 for m in models}
        for m, deps in graph.items():
            for d in deps:
                in_degree[d] += 1

        queue = [m for m in models if in_degree[m] == 0]
        queue.sort(key=lambda x: x.__name__)
        order = []
        while queue:
            n = queue.pop(0)
            order.append(n)
            for m, deps in graph.items():
                if n in deps:
                    in_degree[m] -= 1
                    if in_degree[m] == 0:
                        queue.append(m)
                        queue.sort(key=lambda x: x.__name__)

        if len(order) != len(models):
            remaining = [m for m in models if m not in order]
            remaining.sort(key=lambda x: x.__name__)
            order.extend(remaining)
        return order