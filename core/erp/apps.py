from django.apps import AppConfig
from django.conf import settings
import threading
import time
import sys


class ErpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.erp'

    _sync_thread_started = False
    _backup_thread_started = False

    def ready(self):
        """Lanza una sincronización periódica solo en POS locales."""
        # Importar admin.py para registrar los modelos en el admin de Django
        try:
            from . import admin
        except ImportError:
            pass
        
        # Forzar registro manual de modelos ERP
        self.force_register_erp_models()
        
        # No correr esto en producción (servidor central)
        if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
            return

        # Evitar múltiples hilos si ready() se llama más de una vez
        if ErpConfig._sync_thread_started and ErpConfig._backup_thread_started:
            return

        # Iniciar hilo de sincronización
        if not ErpConfig._sync_thread_started:
            ErpConfig._sync_thread_started = True
            self._start_sync_thread()

        # INICIAR HILO DE RESPALDO COMENTADO (DESACTIVADO)
        # if not ErpConfig._backup_thread_started:
        #     ErpConfig._backup_thread_started = True
        #     self._start_backup_thread()
    
    def force_register_erp_models(self):
        """Fuerza el registro de modelos ERP en el admin."""
        from django.contrib import admin
        from .models import (
            Company, Product, Sale, Client, Supplier, Category,
            ActivityLog, AutoSyncConfig, CashMovement, CashRegister,
            DetEmployeeAccount, DetSale, EmployeeAccountSale, Expense,
            GlobalSyncStatus, InternalTransfer, InternalTransferDetail,
            MercadoPagoConfig, PosTerminal, ProfitReport, QuickOrder, SyncLog
        )
        
        # Crear clases admin inline
        class CompanyFilteredAdmin(admin.ModelAdmin):
            def get_queryset(self, request):
                qs = super().get_queryset(request)
                if request.user.is_superuser:
                    return qs
                if hasattr(request.user, 'company_id') and request.user.company_id:
                    return qs.filter(company_id=request.user.company_id)
                return qs.none()
        
        class CompanyAdmin(CompanyFilteredAdmin):
            list_display = ('name', 'cuit', 'is_active')
            
            def get_queryset(self, request):
                qs = super().get_queryset(request)
                if request.user.is_superuser:
                    return qs
                if hasattr(request.user, 'company_id') and request.user.company_id:
                    return qs.filter(id=request.user.company_id)
                return qs.none()
        
        class ProductAdmin(CompanyFilteredAdmin):
            list_display = ('name', 'code', 'stock', 'pvp', 'pvp_final')
        
        class SaleAdmin(CompanyFilteredAdmin):
            list_display = ('id', 'cli', 'date_joined', 'total', 'payment_method')
        
        class ClientAdmin(CompanyFilteredAdmin):
            list_display = ('names', 'dni', 'address')
        
        class SupplierAdmin(CompanyFilteredAdmin):
            list_display = ('name', 'cuit', 'phone', 'is_active')
        
        class CategoryAdmin(CompanyFilteredAdmin):
            list_display = ('name', 'company')
        
        # Admins para modelos adicionales
        class ActivityLogAdmin(CompanyFilteredAdmin):
            list_display = ('user', 'action', 'timestamp', 'ip_address')
            readonly_fields = ('user', 'action', 'description', 'model_name', 'object_id', 'ip_address', 'user_agent', 'timestamp')
        
        class AutoSyncConfigAdmin(CompanyFilteredAdmin):
            list_display = ('interval_seconds',)
        
        class CashMovementAdmin(CompanyFilteredAdmin):
            list_display = ('cash_register', 'movement_type', 'amount', 'created_at')
        
        class CashRegisterAdmin(CompanyFilteredAdmin):
            list_display = ('user', 'date', 'opening_balance', 'closing_balance', 'is_closed')
        
        class DetEmployeeAccountAdmin(CompanyFilteredAdmin):
            list_display = ('employee_account', 'prod', 'price', 'cant', 'subtotal')
        
        class DetSaleAdmin(CompanyFilteredAdmin):
            list_display = ('sale', 'prod', 'price', 'cant', 'subtotal')
        
        class EmployeeAccountSaleAdmin(CompanyFilteredAdmin):
            list_display = ('employee', 'date_joined', 'total', 'is_paid', 'paid_date')
        
        class ExpenseAdmin(CompanyFilteredAdmin):
            list_display = ('description', 'amount', 'date', 'supplier')
        
        class GlobalSyncStatusAdmin(admin.ModelAdmin):
            list_display = ('sync_enabled', 'updated_at', 'updated_by')
            # Este modelo no tiene company, solo superusuarios lo ven
        
        class InternalTransferAdmin(CompanyFilteredAdmin):
            list_display = ('origin_pos', 'destination_pos', 'status', 'created_at')
        
        class InternalTransferDetailAdmin(CompanyFilteredAdmin):
            list_display = ('transfer', 'product', 'quantity')
        
        class MercadoPagoConfigAdmin(CompanyFilteredAdmin):
            list_display = ('company', 'enabled', 'mode', 'public_key')
        
        class PosTerminalAdmin(CompanyFilteredAdmin):
            list_display = ('code', 'company', 'is_active')
        
        class ProfitReportAdmin(CompanyFilteredAdmin):
            list_display = ('date_from', 'date_to', 'total_sales', 'total_profit')
        
        class QuickOrderAdmin(CompanyFilteredAdmin):
            list_display = ('total', 'currency', 'status', 'created_at')
        
        class SyncLogAdmin(admin.ModelAdmin):
            list_display = ('node_name', 'created_at', 'success', 'message')
            readonly_fields = ('node_name', 'created_at', 'success', 'message')
            # Este modelo no tiene company, solo superusuarios lo ven
        
        # Registrar todos los modelos
        model_admin_pairs = [
            (Company, CompanyAdmin),
            (Product, ProductAdmin),
            (Sale, SaleAdmin),
            (Client, ClientAdmin),
            (Supplier, SupplierAdmin),
            (Category, CategoryAdmin),
            (ActivityLog, ActivityLogAdmin),
            (AutoSyncConfig, AutoSyncConfigAdmin),
            (CashMovement, CashMovementAdmin),
            (CashRegister, CashRegisterAdmin),
            (DetEmployeeAccount, DetEmployeeAccountAdmin),
            (DetSale, DetSaleAdmin),
            (EmployeeAccountSale, EmployeeAccountSaleAdmin),
            (Expense, ExpenseAdmin),
            (InternalTransfer, InternalTransferAdmin),
            (InternalTransferDetail, InternalTransferDetailAdmin),
            (MercadoPagoConfig, MercadoPagoConfigAdmin),
            (PosTerminal, PosTerminalAdmin),
            (ProfitReport, ProfitReportAdmin),
            (QuickOrder, QuickOrderAdmin),
        ]
        
        # Modelos sin filtro de empresa (solo para superusuarios)
        global_models = [
            (GlobalSyncStatus, GlobalSyncStatusAdmin),
            (SyncLog, SyncLogAdmin),
        ]
        
        # Registrar modelos con filtro de empresa
        for model, admin_class in model_admin_pairs:
            try:
                admin.site.register(model, admin_class)
            except admin.sites.AlreadyRegistered:
                pass
        
        # Registrar modelos globales (solo superusuarios)
        for model, admin_class in global_models:
            try:
                admin.site.register(model, admin_class)
            except admin.sites.AlreadyRegistered:
                pass

    def _start_sync_thread(self):
        """Inicia el hilo de sincronización periódica."""
        # No correr durante comandos de mantenimiento
        blocked_cmds = {'makemigrations', 'migrate', 'collectstatic', 'shell', 'createsuperuser'}
        if any(cmd in sys.argv for cmd in blocked_cmds):
            return

        # IMPORTAR AQUÍ, no arriba, para evitar AppRegistryNotReady
        from core.erp.sync_utils import run_full_sync
        from core.erp.models import AutoSyncConfig

        # Intervalo base de sincronización (por defecto 10 min)
        base_interval = getattr(settings, 'POS_SYNC_INTERVAL_SECONDS', 600)

        def _sync_worker():
            while True:
                try:
                    # Check if sync is globally disabled before running
                    from core.erp.models import GlobalSyncStatus
                    if not GlobalSyncStatus.is_sync_enabled():
                        print("Sincronización desactivada globalmente - omitiendo ejecución automática")
                        time.sleep(base_interval)
                        continue
                    
                    print("Iniciando sincronización automática...")
                    run_full_sync()
                except Exception as e:
                    print(f"Error en sincronización automática: {e}")

                # Leer configuración dinámica del intervalo en cada vuelta.
                interval_seconds = base_interval
                try:
                    cfg = AutoSyncConfig.objects.first()
                    if cfg and cfg.interval_seconds:
                        # Forzar rango seguro 120s (2 min) a 3600s (60 min)
                        interval_seconds = max(120, min(3600, int(cfg.interval_seconds)))
                except Exception:
                    # Ante cualquier error, usar el intervalo base
                    interval_seconds = base_interval

                print(f"Próxima sincronización en {interval_seconds} segundos...")
                time.sleep(interval_seconds)

        t = threading.Thread(target=_sync_worker, daemon=True)
        t.start()

    def _start_backup_thread(self):
        """Inicia el hilo de respaldo automático periódico."""
        # No correr durante comandos de mantenimiento
        blocked_cmds = {'makemigrations', 'migrate', 'collectstatic', 'shell', 'createsuperuser', 'backup_sqlite'}
        if any(cmd in sys.argv for cmd in blocked_cmds):
            return

        # IMPORTAR AQUÍ, no arriba, para evitar AppRegistryNotReady
        from django.core.management import call_command

        # Intervalo base de respaldo (por defecto 4 horas)
        base_interval = getattr(settings, 'POS_BACKUP_INTERVAL_SECONDS', 14400)

        def _backup_worker():
            while True:
                try:
                    call_command("backup_sqlite")
                except Exception:
                    # No romper el hilo si hay errores de backup
                    pass

                # Usar intervalo configurado (rango seguro 1h a 24h)
                interval_seconds = max(3600, min(86400, base_interval))
                time.sleep(interval_seconds)

        t = threading.Thread(target=_backup_worker, daemon=True)
        t.start()