from django.contrib import admin
from django.apps import apps
from .models import Company, Product, Sale, Client, Supplier, Category, EmployeeAccountSale, AfipConfig

# Clase base para admin con filtrado por empresa
class CompanyFilteredAdmin(admin.ModelAdmin):
    """Admin base que filtra por empresa para usuarios no superusuarios"""
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # Superusuarios ven todo
        # Usuarios normales solo ven registros de su empresa
        if hasattr(request.user, 'company_id') and request.user.company_id:
            return qs.filter(company_id=request.user.company_id)
        return qs.none()  # Sin empresa asignada, no ven nada

# Admin personalizado para modelos con campo company
class CompanyAdmin(CompanyFilteredAdmin):
    list_display = ('name', 'cuit', 'is_active')
    search_fields = ('name', 'cuit')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Superusuarios ven todas las empresas
        if request.user.is_superuser:
            return qs
        # Usuarios normales solo ven su empresa
        if hasattr(request.user, 'company_id') and request.user.company_id:
            return qs.filter(id=request.user.company_id)
        return qs.none()

class ProductAdmin(CompanyFilteredAdmin):
    list_display = ('name', 'code', 'stock', 'pvp', 'pvp_final', 'company')
    list_filter = ('company', 'cat', 'unit', 'track_stock')
    search_fields = ('name', 'code')

class SaleAdmin(CompanyFilteredAdmin):
    list_display = ('id', 'cli', 'date_joined', 'total', 'payment_method', 'company')
    list_filter = ('company', 'payment_method', 'is_invoiced')
    search_fields = ('cli__names', 'invoice_number')
    date_hierarchy = 'date_joined'

class ClientAdmin(CompanyFilteredAdmin):
    list_display = ('names', 'dni', 'mobile', 'company')
    list_filter = ('company', 'gender')
    search_fields = ('names', 'dni', 'ruc')

class SupplierAdmin(CompanyFilteredAdmin):
    list_display = ('name', 'cuit', 'phone', 'is_active', 'company')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'cuit')

class CategoryAdmin(CompanyFilteredAdmin):
    list_display = ('name', 'company')
    list_filter = ('company',)
    search_fields = ('name',)

class EmployeeAccountSaleAdmin(CompanyFilteredAdmin):
    list_display = ('employee', 'date_joined', 'total', 'is_paid', 'paid_date', 'company')
    list_filter = ('company', 'is_paid', 'date_joined')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name', 'notes')
    date_hierarchy = 'date_joined'
    readonly_fields = ('local_uuid', 'synced_to_server')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Usuarios normales solo ven registros de su empresa
        if hasattr(request.user, 'company_id') and request.user.company_id:
            return qs.filter(company_id=request.user.company_id)
        return qs.none()

class AfipConfigAdmin(CompanyFilteredAdmin):
    list_display = ('company', 'cuit', 'environment', 'is_active', 'created_at')
    list_filter = ('company', 'environment', 'is_active')
    search_fields = ('cuit', 'company__name')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'company_id') and request.user.company_id:
            return qs.filter(company_id=request.user.company_id)
        return qs.none()

# Registrar modelos principales con admin personalizado
admin.site.register(Company, CompanyAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Sale, SaleAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(Supplier, SupplierAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(EmployeeAccountSale, EmployeeAccountSaleAdmin)
admin.site.register(AfipConfig, AfipConfigAdmin)

# Obtener todos los modelos de la aplicación
app_models = apps.get_app_config('erp').get_models()

# Registrar los modelos restantes que no tienen admin personalizado
registered_models = {Company, Product, Sale, Client, Supplier, Category, EmployeeAccountSale, AfipConfig}
for model in app_models:
    if model not in registered_models:
        try:
            # Intentar registrar con CompanyFilteredAdmin si tiene campo company
            if hasattr(model, 'company'):
                admin.site.register(model, CompanyFilteredAdmin)
            else:
                admin.site.register(model)
        except admin.sites.AlreadyRegistered:
            pass

# Importar los archivos de admin personalizados para modelos específicos
from .admin.cash_register import *