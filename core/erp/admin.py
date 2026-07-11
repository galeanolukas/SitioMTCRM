from django.contrib import admin
from django.apps import apps
from .models import Company, Product, Sale, Client, Supplier, Category, EmployeeAccountSale, AfipConfig, AfipPuntoVenta, LibroIvaRegistro, CuentaCorrienteCliente, AsientoContable, FacturaProveedor, CatalogoConfig, PriceList, PriceListProduct, GlobalPosConfig

# Clase base para admin con filtrado por empresa
class CompanyFilteredAdmin(admin.ModelAdmin):
    """Admin base que filtra por empresa para usuarios no superusuarios"""
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # Superusuarios ven todo
        # Usuarios normales solo ven registros de su empresa
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(company=request.user.company)
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
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(id=request.user.company.id)
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
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()

class AfipConfigAdmin(CompanyFilteredAdmin):
    list_display = ('id', 'company', 'cuit', 'environment', 'tipo_comprobante', 'wsfe_authorized', 'is_active', 'created_at')
    list_filter = ('company', 'environment', 'is_active', 'wsfe_authorized')
    search_fields = ('cuit', 'company__name')
    readonly_fields = ('created_at', 'updated_at', 'wsfe_authorized_at')
    fieldsets = (
        ('Información Básica', {
            'fields': ('company', 'cuit', 'access_token', 'environment', 'is_active')
        }),
        ('Credenciales Clave Fiscal', {
            'fields': ('clave_fiscal_username', 'clave_fiscal_password')
        }),
        ('Certificados (Producción)', {
            'fields': ('cert', 'key'),
            'classes': ('collapse',)
        }),
        ('Configuración de Facturación', {
            'fields': ('tipo_comprobante', 'concepto', 'moneda', 'cotizacion', 'usar_contingencia')
        }),
        ('Estado WSFE', {
            'fields': ('wsfe_authorized', 'wsfe_authorized_at', 'wsfe_automation_id')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()


class AfipPuntoVentaAdmin(CompanyFilteredAdmin):
    list_display = ('company', 'numero', 'descripcion', 'is_active', 'created_at')
    list_filter = ('company', 'is_active')
    search_fields = ('numero', 'descripcion', 'company__name')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()


class LibroIvaRegistroAdmin(CompanyFilteredAdmin):
    list_display = ('tipo_registro', 'fecha', 'tipo_comprobante', 'punto_venta', 'numero_comprobante', 'razon_social', 'total', 'cae')
    list_filter = ('company', 'tipo_registro', 'tipo_comprobante', 'fecha', 'condicion_iva')
    search_fields = ('razon_social', 'cuit_emisor', 'cuit_receptor', 'cae', 'numero_comprobante')
    date_hierarchy = 'fecha'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()


class CuentaCorrienteClienteAdmin(CompanyFilteredAdmin):
    list_display = ('client', 'fecha', 'tipo_movimiento', 'descripcion', 'debe', 'haber', 'saldo')
    list_filter = ('company', 'client', 'tipo_movimiento', 'fecha')
    search_fields = ('client__names', 'client__surnames', 'descripcion')
    date_hierarchy = 'fecha'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()


class AsientoContableAdmin(CompanyFilteredAdmin):
    list_display = ('tipo_asiento', 'fecha', 'descripcion', 'debe_total', 'haber_total')
    list_filter = ('company', 'tipo_asiento', 'fecha')
    search_fields = ('descripcion',)
    date_hierarchy = 'fecha'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()


class FacturaProveedorAdmin(CompanyFilteredAdmin):
    list_display = ('supplier', 'fecha', 'tipo_comprobante', 'punto_venta', 'numero_comprobante', 'total', 'cae')
    list_filter = ('company', 'supplier', 'tipo_comprobante', 'fecha', 'condicion_iva')
    search_fields = ('supplier__name', 'cuit_proveedor', 'cae', 'numero_comprobante')
    date_hierarchy = 'fecha'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()


class CatalogoConfigAdmin(CompanyFilteredAdmin):
    list_display = ('company', 'catalogo_url', 'is_active', 'auto_sync', 'last_sync', 'created_at')
    list_filter = ('company', 'is_active', 'auto_sync')
    search_fields = ('catalogo_url', 'company__name')
    readonly_fields = ('created_at', 'updated_at', 'last_sync')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'company') and request.user.company:
            return qs.filter(company=request.user.company)
        return qs.none()


class PriceListAdmin(CompanyFilteredAdmin):
    list_display = ('name', 'discount_percentage', 'is_active', 'company', 'created_at')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'company__name')


class PriceListProductAdmin(admin.ModelAdmin):
    list_display = ('product', 'price_list', 'fixed_price', 'discount_override', 'is_exception')
    list_filter = ('price_list', 'is_exception')
    search_fields = ('product__name', 'price_list__name')

class GlobalPosConfigAdmin(admin.ModelAdmin):
    list_display = ('allow_sales_without_afip', 'updated_at', 'updated_by')
    list_filter = ('allow_sales_without_afip',)
    readonly_fields = ('updated_at', 'updated_by')

    def has_add_permission(self, request):
        # Solo permitir un registro
        if self.model.objects.count() >= 1:
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # No permitir eliminar el único registro
        return False

# Registrar modelos principales con admin personalizado
admin.site.register(Company, CompanyAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Sale, SaleAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(Supplier, SupplierAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(EmployeeAccountSale, EmployeeAccountSaleAdmin)
admin.site.register(AfipConfig, AfipConfigAdmin)
admin.site.register(AfipPuntoVenta, AfipPuntoVentaAdmin)
admin.site.register(LibroIvaRegistro, LibroIvaRegistroAdmin)
admin.site.register(CuentaCorrienteCliente, CuentaCorrienteClienteAdmin)
admin.site.register(AsientoContable, AsientoContableAdmin)
admin.site.register(FacturaProveedor, FacturaProveedorAdmin)
admin.site.register(CatalogoConfig, CatalogoConfigAdmin)
admin.site.register(PriceList, PriceListAdmin)
admin.site.register(PriceListProduct, PriceListProductAdmin)
admin.site.register(GlobalPosConfig, GlobalPosConfigAdmin)

# Obtener todos los modelos de la aplicación
app_models = apps.get_app_config('erp').get_models()

# Registrar los modelos restantes que no tienen admin personalizado
registered_models = {Company, Product, Sale, Client, Supplier, Category, EmployeeAccountSale, AfipConfig, AfipPuntoVenta, LibroIvaRegistro, CuentaCorrienteCliente, AsientoContable, FacturaProveedor, CatalogoConfig, PriceList, PriceListProduct}
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