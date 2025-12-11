from django.db import models
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from crum import get_current_user
from django.forms import model_to_dict
import uuid

from core.erp.choices import gender_choices, payment_method_choices
from core.models import BaseModel
from config.settings import MEDIA_URL, STATIC_URL
from django.db import models
from django.conf import settings
# ... other imports ...


class Company(models.Model):
    name = models.CharField(max_length=150, verbose_name='Nombre')
    address = models.CharField(max_length=200, verbose_name='Dirección', blank=True, null=True)
    cuit = models.CharField(max_length=20, verbose_name='CUIT', blank=True, null=True)
    iibb = models.CharField(max_length=30, verbose_name='IIBB', blank=True, null=True)
    start = models.DateField(verbose_name='Inicio de actividades', blank=True, null=True)
    pos = models.CharField(max_length=5, verbose_name='Punto de venta', default='0001')
    phone = models.CharField(max_length=30, verbose_name='Teléfono', blank=True, null=True)
    email = models.EmailField(verbose_name='Email', blank=True, null=True)
    logo = models.ImageField(upload_to='company/', null=True, blank=True, verbose_name='Logo')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    def __str__(self):
        return self.name

    def get_logo_url(self):
        if self.logo:
            return f"{MEDIA_URL}{self.logo}"
        return f"{STATIC_URL}img/logo1.jpeg"

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresa'
        ordering = ['id']


class PosTerminal(models.Model):
    """Terminal / Punto de venta por empresa.

    number es un correlativo por empresa (1, 2, 3, ...).
    El identificador "humano" se construye a partir del nombre de la empresa
    y el número formateado, por ejemplo: MIEMP-001.
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', related_name='pos_terminals')
    number = models.PositiveIntegerField(verbose_name='Número de POS')
    name = models.CharField(max_length=150, verbose_name='Nombre descriptivo', blank=True, null=True)
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Terminal POS'
        verbose_name_plural = 'Terminales POS'
        ordering = ['company_id', 'number']
        unique_together = ('company', 'number')

    def __str__(self):
        return self.code

    @property
    def code(self) -> str:
        """ID legible del POS, basado en empresa + correlativo.

        Se usa un prefijo corto derivado del nombre de la empresa, sin espacios,
        en mayúsculas, y el número con 3 dígitos: PREFIX-001.
        """

        base_name = (self.company.name or '').upper().replace(' ', '') if self.company_id else 'POS'
        prefix = base_name[:6] or 'POS'
        return f"{prefix}-{self.number:03d}"


class Category(BaseModel):
    name = models.CharField(max_length=150, verbose_name='Nombre', unique=True)
    desc = models.CharField(max_length=500, null=True, blank=True, verbose_name='Descripción')

    def __str__(self):
        return self.name

    # def save(self, force_insert=False, force_update=False, using=None,
    #          update_fields=None):
    #     user = get_current_user()
    #     if user is not None:
    #         if not self.pk:
    #             self.user_creation = user
    #         else:
    #             self.user_updated = user
    #     super(Category, self).save()

    def toJSON(self):
        item = model_to_dict(self)  #(self, exclude=['user_creation', 'user_updated'])
        return item

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['id']


class Product(models.Model):
    UNIT_CHOICES = (
        ('unit', 'Unidad'),
        ('kg', 'Kilogramo'),
        ('mt', 'Metro'),
        ('lt', 'Litro'),
        ('bx', 'Caja'),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    name = models.CharField(max_length=150, verbose_name='Nombre', unique=True)
    code = models.CharField(max_length=64, verbose_name='Código', null=True, blank=True)
    qr_token = models.CharField(max_length=32, verbose_name='Token público QR', unique=True, null=True, blank=True)
    cat = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='Categoría')
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Proveedor')
    image = models.ImageField(upload_to='product/%Y/%m/%d', null=True, blank=True, verbose_name='Imagen')
    cost_price = models.DecimalField(default=0.00, max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Precio de costo (sin IVA)')
    pvp = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='Precio neto (sin IVA)')
    iva_rate = models.DecimalField(default=0.21, max_digits=5, decimal_places=2, verbose_name='IVA (%)')
    pvp_final = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='Precio final (con IVA)')
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='unit', verbose_name='Unidad de medida')
    stock = models.DecimalField(default=0.00, max_digits=12, decimal_places=2, verbose_name='Stock')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    track_stock = models.BooleanField(default=True, verbose_name='Controlar stock')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Setear empresa por defecto
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        # Generar token QR si no existe
        if not self.qr_token:
            self.qr_token = uuid.uuid4().hex
        # Calcular precio final con IVA
        try:
            pvp = Decimal(self.pvp or 0)
            rate = Decimal(self.iva_rate or 0)
            # Normalizar rate: si es mayor que 1, tratarlo como porcentaje (21 -> 0.21)
            if rate > Decimal('1.0'):
                rate = rate / Decimal('100.0')
            self.iva_rate = rate  # Guardar el valor normalizado
            self.pvp_final = (pvp * (Decimal('1.0') + rate)).quantize(Decimal('0.01'))
        except Exception:
            self.pvp_final = Decimal('0.00')
        super().save(*args, **kwargs)

    def toJSON(self):
        item = model_to_dict(self)
        item['cat'] = self.cat.toJSON()
        item['supplier'] = (self.supplier.name if self.supplier_id else None)
        item['supplier_id'] = self.supplier_id
        item['image'] = self.get_image()
        item['pvp'] = format(self.pvp, '.2f') if self.pvp is not None else '0.00'
        item['cost_price'] = format(self.cost_price, '.2f') if self.cost_price is not None else '0.00'
        item['iva_rate'] = float(self.iva_rate) if self.iva_rate is not None else 0.0
        item['pvp_final'] = format(self.pvp_final, '.2f') if self.pvp_final is not None else '0.00'
        item['unit'] = self.unit
        item['unit_display'] = self.get_unit_display()
        item['stock'] = format(self.stock, '.2f') if self.stock is not None else '0.00'
        item['code'] = self.code
        item['track_stock'] = self.track_stock
        return item

    def get_image(self):
        if self.image:
            return '{}{}'.format(MEDIA_URL, self.image)
        return '{}{}'.format(STATIC_URL, 'img/empty.png')

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['id']


class Client(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    names = models.CharField(max_length=150, verbose_name='Nombres')
    surnames = models.CharField(max_length=150, verbose_name='Apellidos')
    dni = models.CharField(max_length=10, unique=True, verbose_name='Dni')
    date_birthday = models.DateField(default=datetime.now, verbose_name='Fecha de nacimiento')
    address = models.CharField(max_length=150, null=True, blank=True, verbose_name='Dirección')
    gender = models.CharField(max_length=10, choices=gender_choices, default='male', verbose_name='Sexo')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    def __str__(self):
        return self.names

    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        super().save(*args, **kwargs)

    def toJSON(self):
        item = model_to_dict(self)
        item['gender'] = {'id': self.gender, 'name': self.get_gender_display()}
        item['date_birthday'] = self.date_birthday.strftime('%Y-%m-%d')
        return item

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['id']


class Supplier(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    name = models.CharField(max_length=150, verbose_name='Nombre')
    cuit = models.CharField(max_length=20, verbose_name='CUIT', blank=True, null=True)
    address = models.CharField(max_length=200, verbose_name='Dirección', blank=True, null=True)
    phone = models.CharField(max_length=30, verbose_name='Teléfono', blank=True, null=True)
    email = models.EmailField(verbose_name='Email', blank=True, null=True)
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        super().save(*args, **kwargs)

    def toJSON(self):
        item = model_to_dict(self)
        return item

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['id']


class Sale(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    cli = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Cliente')
    date_joined = models.DateTimeField(default=timezone.now)
    subtotal = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    iva = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    total = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    payment_method = models.CharField(max_length=12, choices=payment_method_choices, default='cash', verbose_name='Forma de pago')
    # Facturación
    invoice_number = models.CharField(max_length=20, null=True, blank=True, unique=True)
    invoice_pos = models.CharField(max_length=5, default='0001')
    invoice_type = models.CharField(max_length=1, default='B')  # A/B/C
    is_invoiced = models.BooleanField(default=False)
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')

    def __str__(self):
        return self.cli.names

    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        super().save(*args, **kwargs)

    def next_sequential_for_pos_type(self):
        # Filtrar por empresa, punto de venta y tipo para evitar conflictos entre múltiples POS
        last = Sale.objects.filter(
            company_id=self.company_id,
            invoice_pos=self.invoice_pos, 
            invoice_type=self.invoice_type, 
            invoice_number__isnull=False
        ).order_by('-id').first()
        if last and last.invoice_number:
            try:
                seq = int(last.invoice_number.split('-')[-1]) + 1
            except Exception:
                seq = 1
        else:
            seq = 1
        return f"{self.invoice_pos}-{self.invoice_type}-{seq:08d}"

    def toJSON(self):
        item = model_to_dict(self)
        item['cli'] = (self.cli.names if self.cli_id else 'Anónimo')
        item['date_joined'] = self.date_joined.strftime('%d-%m-%Y %H:%M')
        item['subtotal'] = format(self.subtotal, '.2f') if self.subtotal is not None else '0.00'
        item['iva'] = format(self.iva, '.2f') if self.iva is not None else '0.00'
        item['total'] = format(self.total, '.2f') if self.total is not None else '0.00'
        item['det'] = [i.toJSON() for i in self.detsale_set.all()]
        item['invoice_number'] = self.invoice_number
        item['invoice_pos'] = self.invoice_pos
        item['invoice_type'] = self.invoice_type
        item['is_invoiced'] = self.is_invoiced
        item['payment_method'] = self.payment_method
        item['payment_method_display'] = self.get_payment_method_display()
        return item

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['id']


class DetSale(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE)
    prod = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    cant = models.DecimalField(default=0, max_digits=9, decimal_places=3)
    subtotal = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)

    def __str__(self):
        return self.prod.name

    def toJSON(self):
        item = model_to_dict(self, exclude=['sale'])
        item['prod'] = self.prod.toJSON()
        item['price'] = format(self.price, '.2f') if self.price is not None else '0.00'
        item['subtotal'] = format(self.subtotal, '.2f') if self.subtotal is not None else '0.00'
        return item

    class Meta:
        verbose_name = 'Detalle de Venta'
        verbose_name_plural = 'Detalle de Ventas'
        ordering = ['id']


class MercadoPagoConfig(models.Model):
    MODE_CHOICES = (
        ('sandbox', 'Sandbox'),
        ('prod', 'Producción'),
    )

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='mp_config', verbose_name='Empresa')
    name = models.CharField(max_length=150, verbose_name='Nombre de configuración', blank=True, null=True)
    access_token = models.CharField(max_length=255, verbose_name='Access Token')
    public_key = models.CharField(max_length=255, verbose_name='Public Key', blank=True, null=True)
    enabled = models.BooleanField(default=False, verbose_name='Habilitado')
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='sandbox', verbose_name='Modo')

    def __str__(self):
        base = self.name or f"Credenciales MP {self.company.name}" if self.company_id else 'Credenciales MP'
        return base

    class Meta:
        verbose_name = 'Configuración Mercado Pago'
        verbose_name_plural = 'Configuraciones Mercado Pago'
        ordering = ['company_id']


class QuickOrder(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('paid', 'Pagada'),
        ('cancelled', 'Cancelada'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    preference_id = models.CharField(max_length=64, blank=True, null=True, verbose_name='Preference ID MP')
    init_point = models.URLField(blank=True, null=True)
    total = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    currency = models.CharField(max_length=5, default='ARS')
    items = models.JSONField(default=list, verbose_name='Items del carrito')

    def __str__(self):
        return f"QuickOrder #{self.id} - {self.company} - {self.status}"

    class Meta:
        verbose_name = 'Orden rápida'
        verbose_name_plural = 'Órdenes rápidas'
        ordering = ['-created_at']


class Expense(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Proveedor')
    date = models.DateField(default=datetime.now, verbose_name='Fecha')
    description = models.CharField(max_length=255, verbose_name='Descripción', blank=True, null=True)
    amount = models.DecimalField(default=0.00, max_digits=12, decimal_places=2, verbose_name='Importe')
    payer = models.CharField(max_length=150, verbose_name='Pagado por', blank=True, null=True)
    receipt = models.FileField(upload_to='expenses/%Y/%m/%d', null=True, blank=True, verbose_name='Comprobante (PDF/Imagen)')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    def __str__(self):
        base = self.description or 'Gasto'
        return f"{base} - {self.amount}"

    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        super().save(*args, **kwargs)

    def get_receipt_url(self):
        if self.receipt:
            return f"{MEDIA_URL}{self.receipt}"
        return None

    def toJSON(self):
        item = model_to_dict(self)
        item['supplier'] = (self.supplier.name if self.supplier_id else None)
        item['supplier_id'] = self.supplier_id
        item['date'] = self.date.strftime('%Y-%m-%d') if self.date else None
        item['amount'] = format(self.amount, '.2f') if self.amount is not None else '0.00'
        item['receipt_url'] = self.get_receipt_url()
        return item

    class Meta:
        verbose_name = 'Gasto'
        verbose_name_plural = 'Gastos'
        ordering = ['-date', '-id']


class AutoSyncConfig(models.Model):
    """Configuración local del intervalo de sincronización automática del POS.

    Se guarda en segundos, pero se mostrará en minutos en el formulario.
    """

    interval_seconds = models.PositiveIntegerField(default=300, verbose_name='Intervalo de sync (segundos)')

    def __str__(self):
        return f"Intervalo sync: {self.interval_seconds}s"

    class Meta:
        verbose_name = 'Configuración de sync automática'
        verbose_name_plural = 'Configuración de sync automática'


class SyncLog(models.Model):
    """Historial de sincronizaciones POS -> servidor.

    Se guarda en la BD del servidor (default en producción, 'remote' cuando se escribe desde el POS).
    """

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y hora')
    node_name = models.CharField(max_length=100, verbose_name='Nodo / POS', blank=True, null=True)
    success = models.BooleanField(default=True, verbose_name='Éxito')
    message = models.TextField(blank=True, null=True, verbose_name='Resumen')

    class Meta:
        verbose_name = 'Historial de sincronización'
        verbose_name_plural = 'Historial de sincronización'
        ordering = ['-created_at']

    def __str__(self):
        status = 'OK' if self.success else 'ERROR'
        return f"[{status}] {self.created_at:%Y-%m-%d %H:%M} - {self.node_name or 'POS'}"


class CashRegister(models.Model):
    PAYMENT_TYPES = (
        ('cash', 'Efectivo'),
        ('card', 'Tarjeta'),
        ('transfer', 'Transferencia'),
        ('mp', 'Mercado Pago'),
        ('other', 'Otro'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Usuario')
    date = models.DateField(verbose_name='Fecha', auto_now_add=True)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Saldo inicial')
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Saldo final')
    cash_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Ventas en efectivo')
    card_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Ventas con tarjeta')
    transfer_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Ventas por transferencia')
    mp_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Ventas por Mercado Pago')
    expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Gastos')
    notes = models.TextField(blank=True, null=True, verbose_name='Notas')
    is_closed = models.BooleanField(default=False, verbose_name='Caja cerrada')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_synced = models.BooleanField(default=False, verbose_name='Sincronizado')
    sync_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = 'Cierre de caja'
        verbose_name_plural = 'Cierres de caja'
        ordering = ['-date', '-created_at']
        permissions = [
            ("close_cash_register", "Puede cerrar caja"),
            ("view_cash_register", "Puede ver cierres de caja"),
        ]

    def __str__(self):
        return f"Caja {self.date} - {self.user.get_full_name()}"

    @property
    def total_sales(self):
        return self.cash_sales + self.card_sales + self.transfer_sales + self.mp_sales

    @property
    def calculated_balance(self):
        return self.opening_balance + self.total_sales - self.expenses

    @property
    def difference(self):
        """Diferencia entre el saldo final registrado y el saldo esperado."""
        return (self.closing_balance or 0) - (self.calculated_balance or 0)


class ProfitReport(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa')
    date_from = models.DateField(verbose_name='Fecha desde')
    date_to = models.DateField(verbose_name='Fecha hasta')
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name='Ventas totales')
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name='Costo total')
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name='Ganancia total')
    profit_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name='Margen de ganancia (%)')
    total_products_sold = models.IntegerField(default=0, verbose_name='Productos vendidos')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    
    class Meta:
        verbose_name = 'Reporte de Ganancias'
        verbose_name_plural = 'Reportes de Ganancias'
        ordering = ['-date_from', '-created_at']
        indexes = [
            models.Index(fields=['company', 'date_from', 'date_to']),
        ]
    
    def __str__(self):
        return f"Reporte {self.company.name} ({self.date_from} - {self.date_to})"
    
    @property
    def period_type(self):
        """Determinar tipo de período (diario, mensual, personalizado)"""
        days = (self.date_to - self.date_from).days + 1
        if days == 1:
            return "Diario"
        elif days <= 31 and self.date_from.day == 1 and self.date_to.month == self.date_from.month:
            return "Mensual"
        else:
            return "Personalizado"
    
    def calculate_profit_data(self):
        """Calcular datos de ganancias para este período"""
        from django.db.models import Sum, Count, F, FloatField
        from django.db.models.functions import Coalesce
        
        # Obtener ventas del período
        sales = Sale.objects.filter(
            company=self.company,
            date_joined__date__range=[self.date_from, self.date_to]
        )
        
        # Calcular totales
        self.total_sales = sales.aggregate(
            total=Coalesce(Sum('total'), 0)
        )['total'] or 0
        
        # Calcular costo total basado en productos vendidos
        total_cost = 0
        total_products = 0
        
        for sale in sales:
            for detail in sale.detsale_set.all():
                if detail.prod.cost_price:
                    product_cost = float(detail.prod.cost_price) * detail.cant
                    total_cost += product_cost
                    total_products += detail.cant
        
        self.total_cost = total_cost
        self.total_profit = self.total_sales - self.total_cost
        self.total_products_sold = total_products
        
        # Calcular margen de ganancia
        if self.total_cost > 0:
            self.profit_margin = (self.total_profit / self.total_cost) * 100
        else:
            self.profit_margin = 0
        
        self.save()


class CashMovement(models.Model):
    MOVEMENT_TYPES = (
        ('in', 'Ingreso'),
        ('out', 'Egreso'),
    )

    cash_register = models.ForeignKey(CashRegister, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=3, choices=MOVEMENT_TYPES, verbose_name='Tipo de movimiento')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto')
    description = models.CharField(max_length=255, verbose_name='Descripción')
    payment_type = models.CharField(max_length=10, choices=CashRegister.PAYMENT_TYPES, verbose_name='Tipo de pago')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Creado por')
    created_at = models.DateTimeField(auto_now_add=True)
    is_synced = models.BooleanField(default=False)
    sync_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = 'Movimiento de caja'
        verbose_name_plural = 'Movimientos de caja'
        ordering = ['-created_at']


# Modelos para Transferencias Internas entre POS
class InternalTransfer(models.Model):
    """Transferencia interna de productos entre puntos de venta"""
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('in_transit', 'En Tránsito'),
        ('received', 'Recibido'),
        ('cancelled', 'Cancelado'),
    )
    
    origin_pos = models.CharField(max_length=5, verbose_name='POS Origen')
    destination_pos = models.CharField(max_length=5, verbose_name='POS Destino')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Creado por')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha Creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última Actualización')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Estado')
    observations = models.TextField(blank=True, verbose_name='Observaciones')
    transfer_number = models.CharField(max_length=20, unique=True, verbose_name='Número de Remito')
    
    def __str__(self):
        return f"Transferencia {self.transfer_number} - {self.origin_pos} → {self.destination_pos}"
    
    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        
        if not self.transfer_number:
            self.transfer_number = self.generate_transfer_number()
        
        super().save(*args, **kwargs)
    
    def generate_transfer_number(self):
        """Generar número correlativo de transferencia por empresa"""
        last = InternalTransfer.objects.filter(company_id=self.company_id).order_by('-id').first()
        if last and last.transfer_number:
            try:
                seq = int(last.transfer_number.split('-')[-1]) + 1
            except Exception:
                seq = 1
        else:
            seq = 1
        return f"REM-{seq:08d}"
    
    def get_total_amount(self):
        """Calcular monto total de la transferencia"""
        return sum(detail.quantity * detail.unit_price for detail in self.details.all())
    
    def toJSON(self):
        item = model_to_dict(self)
        item['created_by_name'] = self.created_by.get_full_name() or self.created_by.username
        item['company_name'] = self.company.name if self.company else None
        item['total_amount'] = self.get_total_amount()
        item['status_display'] = self.get_status_display()
        item['details'] = [detail.toJSON() for detail in self.details.all()]
        return item
    
    class Meta:
        verbose_name = 'Transferencia Interna'
        verbose_name_plural = 'Transferencias Internas'
        ordering = ['-created_at']


class InternalTransferDetail(models.Model):
    """Detalle de productos en una transferencia interna"""
    transfer = models.ForeignKey(InternalTransfer, on_delete=models.CASCADE, related_name='details', verbose_name='Transferencia')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Producto')
    quantity = models.DecimalField(max_digits=9, decimal_places=3, verbose_name='Cantidad')
    unit_price = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Precio Unitario')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Subtotal')
    
    def __str__(self):
        return f"{self.product.name} - {self.quantity}"
    
    def save(self, *args, **kwargs):
        # Calcular subtotal automáticamente
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def toJSON(self):
        item = model_to_dict(self)
        item['product_name'] = self.product.name
        item['product_code'] = self.product.code
        item['product_unit'] = self.product.get_unit_display()
        return item
    
    class Meta:
        verbose_name = 'Detalle de Transferencia'
        verbose_name_plural = 'Detalles de Transferencia'
        ordering = ['id']

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.amount} - {self.description}"