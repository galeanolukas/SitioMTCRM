from django.db import models
from django.utils import timezone
from datetime import datetime
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from core.models import BaseModel
from decimal import Decimal
from django.utils import timezone
from crum import get_current_user
from django.forms import model_to_dict
import uuid

from core.erp.choices import gender_choices, payment_method_choices
from core.models import BaseModel
from config.settings import MEDIA_URL, STATIC_URL
from django.conf import settings
# ... other imports ...

CONDICION_IVA_CHOICES = [
    ('RI', 'Responsable Inscripto'),
    ('M', 'Monotributista'),
    ('CF', 'Consumidor Final'),
    ('EX', 'Exento'),
    ('NC', 'No Categorizado'),
]

def validate_cuit(value):
    """
    Validador de CUIT/CUIL argentino.
    Formato: XX-XXXXXXXX-X (11 dígitos total)
    """
    if not value:
        return

    # Quitar guiones y espacios
    cuit_clean = str(value).replace('-', '').replace(' ', '').strip()

    # Verificar longitud
    if len(cuit_clean) != 11:
        raise ValidationError('El CUIT/CUIL debe tener 11 dígitos')

    # Verificar que sean todos dígitos
    if not cuit_clean.isdigit():
        raise ValidationError('El CUIT/CUIL debe contener solo dígitos')

    # Calcular dígito verificador
    cuit_sin_verif = cuit_clean[:10]
    verificador = int(cuit_clean[10])

    # Algoritmo de módulo 11
    multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = 0
    for i in range(10):
        suma += int(cuit_sin_verif[i]) * multiplicadores[i]

    resto = suma % 11
    if resto == 0:
        calculado = 0
    elif resto == 1:
        calculado = 9
    else:
        calculado = 11 - resto

    if calculado != verificador:
        raise ValidationError('El CUIT/CUIL no es válido (dígito verificador incorrecto)')



class Company(models.Model):
    SYNC_DESTINATION_CHOICES = (
        ('cloud', 'Nube (Servidor Central)'),
        ('local', 'Servidor Local'),
        ('both', 'Ambos'),
    )
    
    name = models.CharField(max_length=150, verbose_name='Nombre')
    address = models.CharField(max_length=200, verbose_name='Dirección', blank=True, null=True)
    cuit = models.CharField(max_length=20, verbose_name='CUIT', blank=True, null=True, validators=[validate_cuit])
    iibb = models.CharField(max_length=30, verbose_name='IIBB', blank=True, null=True)
    condicion_iva = models.CharField(max_length=2, choices=CONDICION_IVA_CHOICES, default='RI', verbose_name='Condición IVA')
    start = models.DateField(verbose_name='Inicio de actividades', blank=True, null=True)
    pos = models.CharField(max_length=5, verbose_name='Punto de venta', default='0001')
    phone = models.CharField(max_length=30, verbose_name='Teléfono', blank=True, null=True)
    email = models.EmailField(verbose_name='Email', blank=True, null=True)
    logo = models.ImageField(upload_to='company/', null=True, blank=True, verbose_name='Logo')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    sync_destination = models.CharField(
        max_length=10, 
        choices=SYNC_DESTINATION_CHOICES, 
        default='cloud',
        verbose_name='Destino de Sincronización'
    )
    local_server_url = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name='URL del Servidor Local',
        help_text='URL del servidor local para sincronización (ej: http://192.168.1.100:8000)'
    )
    logo_round = models.BooleanField(default=False, verbose_name='Logo Redondo', help_text='Mostrar logo con forma redonda en el login')
    custom_title = models.CharField(max_length=150, blank=True, null=True, verbose_name='Título Personalizado', help_text='Título personalizado para mostrar en el login')
    logo_remote_url = models.CharField(max_length=500, blank=True, null=True, verbose_name='URL Remota del Logo', help_text='URL remota del logo para usar en servidores locales (ej: https://servidor.com/media/company/logo.png)')

    def __str__(self):
        return self.name

    def get_logo_url(self):
        from django.conf import settings
        # En modo local (no production), usar URL remota si está configurada
        if settings.ENVIRONMENT != 'production' and self.logo_remote_url:
            return self.logo_remote_url
        # Si hay logo local, usarlo
        if self.logo:
            return f"{MEDIA_URL}{self.logo}"
        # Logo por defecto
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
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    name = models.CharField(max_length=150, verbose_name='Nombre')
    desc = models.CharField(max_length=500, null=True, blank=True, verbose_name='Descripción')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')

    def __str__(self):
        company_name = f"({self.company.name})" if self.company else ""
        return f"{self.name} {company_name}"

    # def save(self, force_insert=False, force_update=False, using=None,
    #          update_fields=None):
    #     user = get_current_user()
    #     if user is not None:
    #         if not self.pk:
    #             self.user_creation = user
    #         else:
    #             self.user_updated = user
    #     super(Category, self).save()

    def save(self, *args, **kwargs):
        # Convertir el nombre a mayúsculas antes de guardar
        if self.name:
            self.name = self.name.upper()
        
        # Asignar empresa automáticamente si no tiene
        if not self.company_id:
            user = get_current_user()
            if user and hasattr(user, 'company') and user.company:
                self.company = user.company
        
        super(Category, self).save(*args, **kwargs)

    def toJSON(self):
        item = model_to_dict(self, exclude=['date_creation', 'date_updated', 'user_creation', 'user_updated'])
        # Asegurar que el nombre esté en mayúsculas
        if 'name' in item and item['name']:
            item['name'] = item['name'].upper()
        return item

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['company', 'name']
        unique_together = [['company', 'name']]  # Mismo nombre permitido en diferentes empresas


class Product(models.Model):
    UNIT_CHOICES = (
        ('unit', 'Unidad'),
        ('kg', 'Kilogramo'),
        ('mt', 'Metro'),
        ('lt', 'Litro'),
        ('bx', 'Caja'),
    )
    VAT_CODE_CHOICES = (
        ('5', '21%'),
        ('4', '10.5%'),
        ('6', '27%'),
        ('3', '0% (Exento)'),
        ('2', '2.5%'),
        ('8', '5%'),
        ('9', 'No gravado'),
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    name = models.CharField(max_length=150, verbose_name='Nombre', unique=True)
    code = models.CharField(max_length=64, verbose_name='Código Barras', null=True, blank=True)
    codigo_proveedor = models.CharField(max_length=64, verbose_name='Código Proveedor', null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True, verbose_name='Descripción')
    qr_token = models.CharField(max_length=32, verbose_name='Token público QR', unique=True, null=True, blank=True)
    cat = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='Categoría')
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Proveedor')
    image = models.ImageField(upload_to='product/%Y/%m/%d', null=True, blank=True, verbose_name='Imagen')
    cost_price = models.DecimalField(default=0.00, max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Precio de costo (sin IVA)')
    pvp = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='Precio neto (sin IVA)')
    iva_rate = models.DecimalField(default=0.21, max_digits=5, decimal_places=2, verbose_name='IVA (%)')
    vat_code = models.CharField(max_length=1, choices=VAT_CODE_CHOICES, default='5', verbose_name='Código AFIP')
    margin_percentage = models.DecimalField(default=0.00, max_digits=5, decimal_places=2, verbose_name='Margen de ganancia (%)')
    pvp_final = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='Precio final (con IVA)')
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='unit', verbose_name='Unidad de medida')
    stock = models.DecimalField(default=0.00, max_digits=12, decimal_places=2, verbose_name='Stock')
    min_stock = models.DecimalField(default=5.00, max_digits=12, decimal_places=2, verbose_name='Stock mínimo alerta')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    synced_from_server = models.BooleanField(default=False, verbose_name='Sincronizado desde servidor')
    server_product_id = models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de producto en servidor', help_text='ID del producto en la base de datos del servidor')
    last_server_sync = models.DateTimeField(blank=True, null=True, verbose_name='Última sincronización desde servidor')
    last_stock_sync = models.DateTimeField(blank=True, null=True, verbose_name='Última sincronización de stock')
    stock_modified_locally = models.DateTimeField(blank=True, null=True, verbose_name='Última modificación local de stock')
    track_stock = models.BooleanField(default=True, verbose_name='Controlar stock')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Setear empresa por defecto SOLO si no tiene y es creación
        # NO modificar empresa en ediciones para evitar cruzado
        if not self.pk and not self.company_id:  # Solo en creación
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        # Asegurar que track_stock siempre tenga un valor booleano válido
        if self.track_stock is None:
            self.track_stock = True
        # Generar token QR si no existe
        if not self.qr_token:
            self.qr_token = uuid.uuid4().hex
        # Calcular precio final con IVA solo si pvp_final está vacío o es 0
        try:
            pvp = Decimal(self.pvp or 0)
            rate = Decimal(self.iva_rate or 0)
            # Normalizar rate: si es mayor que 1, tratarlo como porcentaje (21 -> 0.21)
            if rate > Decimal('1.0'):
                rate = rate / Decimal('100.0')
            self.iva_rate = rate  # Guardar el valor normalizado
            
            # Solo calcular pvp_final si está vacío, es 0, o no se ha modificado manualmente
            if not self.pvp_final or self.pvp_final == Decimal('0.00'):
                self.pvp_final = (pvp * (Decimal('1.0') + rate)).quantize(Decimal('0.01'))
        except Exception:
            # Solo asignar 0 si pvp_final está vacío
            if not self.pvp_final or self.pvp_final == Decimal('0.00'):
                self.pvp_final = Decimal('0.00')
        
        # Marcar para sincronizar si el producto ya existe y hay cambios
        if self.pk:
            # Verificar si hay cambios relevantes para sincronizar
            old_product = Product.objects.filter(pk=self.pk).first()
            if old_product:
                changes = (
                    old_product.stock != self.stock or
                    old_product.pvp != self.pvp or
                    old_product.cost_price != self.cost_price or
                    old_product.pvp_final != self.pvp_final or
                    old_product.iva_rate != self.iva_rate
                )
                if changes:
                    self.synced_to_server = False
        
        super().save(*args, **kwargs)

    def get_stock_status(self):
        """Determinar el estado del stock"""
        if not self.track_stock:
            return 'no_track'
        if self.stock <= 0:
            return 'out_of_stock'
        elif self.stock <= self.min_stock:
            return 'low_stock'
        else:
            return 'in_stock'

    def get_stock_status_display(self):
        """Obtener descripción del estado del stock"""
        status = self.get_stock_status()
        displays = {
            'no_track': 'No controla stock',
            'out_of_stock': 'Sin stock',
            'low_stock': 'Stock bajo',
            'in_stock': 'En stock'
        }
        return displays.get(status, 'Desconocido')

    def has_low_stock(self):
        """Verificar si tiene stock bajo"""
        return self.track_stock and self.stock > 0 and self.stock <= self.min_stock

    def is_out_of_stock(self):
        """Verificar si está sin stock"""
        return self.track_stock and self.stock <= 0

    def toJSON(self):
        item = model_to_dict(self, exclude=['date_creation', 'date_updated', 'user_creation', 'user_updated', 'stock_modified_locally', 'last_server_sync', 'last_stock_sync'])
        item['cat'] = self.cat.toJSON()
        item['supplier'] = (self.supplier.name if self.supplier_id else None)
        item['supplier_id'] = self.supplier_id
        item['image'] = self.get_image()
        item['pvp'] = format(self.pvp, '.2f') if self.pvp is not None else '0.00'
        item['cost_price'] = format(self.cost_price, '.2f') if self.cost_price is not None else '0.00'
        item['iva_rate'] = float(self.iva_rate) if self.iva_rate is not None else 0.0
        item['margin_percentage'] = float(self.margin_percentage) if self.margin_percentage is not None else 0.0
        item['pvp_final'] = format(self.pvp_final, '.2f') if self.pvp_final is not None else '0.00'
        item['unit'] = self.unit
        item['unit_display'] = self.get_unit_display()
        item['stock'] = format(self.stock, '.2f') if self.stock is not None else '0.00'
        item['min_stock'] = format(self.min_stock, '.2f') if self.min_stock is not None else '5.00'
        item['code'] = self.code
        item['track_stock'] = bool(self.track_stock)
        item['stock_status'] = self.get_stock_status()
        item['stock_status_display'] = self.get_stock_status_display()
        item['has_low_stock'] = bool(self.has_low_stock())
        item['is_out_of_stock'] = bool(self.is_out_of_stock())
        item['unit_display'] = self.get_unit_display()
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
    CONDICION_IVA_CHOICES = [
        ('RI', 'Responsable Inscripto'),
        ('M', 'Monotributista'),
        ('CF', 'Consumidor Final'),
        ('EX', 'Exento'),
        ('NC', 'No Categorizado'),
    ]
    
    TIPO_CLIENTE_CHOICES = [
        ('minorista', 'Minorista'),
        ('mayorista', 'Mayorista'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    names = models.CharField(max_length=150, verbose_name='Nombres')
    surnames = models.CharField(max_length=150, null=True, blank=True, verbose_name='Apellidos')
    dni = models.CharField(max_length=15, null=True, blank=True, verbose_name='Dni')
    cuit_cuil = models.CharField(max_length=13, null=True, blank=True, verbose_name='CUIT/CUIL', validators=[validate_cuit])
    condicion_iva = models.CharField(max_length=2, choices=CONDICION_IVA_CHOICES, default='CF', verbose_name='Condición IVA')
    date_birthday = models.DateField(default=timezone.now, verbose_name='Fecha de nacimiento')
    address = models.CharField(max_length=150, null=True, blank=True, verbose_name='Dirección')
    ciudad = models.CharField(max_length=100, null=True, blank=True, verbose_name='Ciudad')
    provincia = models.CharField(max_length=100, null=True, blank=True, verbose_name='Provincia')
    codigo_postal = models.CharField(max_length=10, null=True, blank=True, verbose_name='Código Postal')
    email = models.EmailField(null=True, blank=True, verbose_name='Email')
    telefono = models.CharField(max_length=20, null=True, blank=True, verbose_name='Teléfono')
    telefono_alternativo = models.CharField(max_length=20, null=True, blank=True, verbose_name='Teléfono Alternativo')
    gender = models.CharField(max_length=10, choices=gender_choices, default='male', verbose_name='Sexo')
    tipo_cliente = models.CharField(max_length=20, choices=TIPO_CLIENTE_CHOICES, default='minorista', verbose_name='Tipo de Cliente')
    limite_credito = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Límite de Crédito')
    descuento_habitual = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Descuento Habitual (%)')
    observaciones = models.TextField(null=True, blank=True, verbose_name='Observaciones')
    precio_lista = models.ForeignKey('PriceList', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Lista de precios')
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
        item = model_to_dict(self, exclude=['date_creation', 'date_updated', 'user_creation', 'user_updated'])
        item['gender'] = {'id': self.gender, 'name': self.get_gender_display()}
        item['condicion_iva'] = {'id': self.condicion_iva, 'name': self.get_condicion_iva_display()}
        item['tipo_cliente'] = {'id': self.tipo_cliente, 'name': self.get_tipo_cliente_display()}
        item['date_birthday'] = self.date_birthday.strftime('%Y-%m-%d') if self.date_birthday else ''
        # Agregar info de lista de precios
        if self.precio_lista:
            item['precio_lista'] = {
                'id': self.precio_lista.id,
                'name': self.precio_lista.name,
                'discount_percentage': float(self.precio_lista.discount_percentage)
            }
        else:
            item['precio_lista'] = None
        return item

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['id']


class PriceList(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    name = models.CharField(max_length=100, verbose_name='Nombre')
    discount_percentage = models.DecimalField(default=0, max_digits=5, decimal_places=2, verbose_name='Descuento (%)')
    is_active = models.BooleanField(default=True, verbose_name='Activa')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')

    def __str__(self):
        return f"{self.name} ({self.discount_percentage}%)"

    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        super().save(*args, **kwargs)

    def get_price_for_product(self, product):
        """Devuelve el precio para un producto dado.
        Si hay un PriceListProduct con precio fijo, usa ese.
        Si no, aplica el descuento porcentual al pvp del producto.
        Si el producto está marcado como excepción sin precio, devuelve el pvp original.
        """
        from decimal import Decimal
        try:
            plp = self.products.select_related('product').get(product=product)
            if plp.is_exception:
                return product.pvp
            if plp.fixed_price is not None:
                return plp.fixed_price
            # excepción con descuento override
            if plp.discount_override is not None:
                discount = plp.discount_override
            else:
                discount = self.discount_percentage
            return (Decimal(product.pvp) * (Decimal('1') - discount / Decimal('100'))).quantize(Decimal('0.01'))
        except PriceListProduct.DoesNotExist:
            # No hay override: aplicar descuento general
            return (Decimal(product.pvp) * (Decimal('1') - self.discount_percentage / Decimal('100'))).quantize(Decimal('0.01'))

    class Meta:
        verbose_name = 'Lista de Precios'
        verbose_name_plural = 'Listas de Precios'
        ordering = ['name']


class PriceListProduct(models.Model):
    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name='products', verbose_name='Lista de precios')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Producto')
    fixed_price = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, verbose_name='Precio fijo (override)')
    discount_override = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Descuento override (%)')
    is_exception = models.BooleanField(default=False, verbose_name='Excepción (no aplicar descuento)')

    def __str__(self):
        return f"{self.product.name} - {self.price_list.name}"

    class Meta:
        verbose_name = 'Producto en Lista'
        verbose_name_plural = 'Productos en Lista'
        unique_together = [['price_list', 'product']]
        ordering = ['product__name']


class Supplier(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    code = models.CharField(max_length=50, verbose_name='Código', blank=True, null=True, unique=True)
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
        item = model_to_dict(self, exclude=['date_creation', 'date_updated', 'user_creation', 'user_updated'])
        return item

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['id']


class CardInstallmentPlan(models.Model):
    """Planes de cuotas para pagos con tarjeta de crédito"""
    name = models.CharField(max_length=50, verbose_name='Nombre del plan')
    installments = models.IntegerField(verbose_name='Cantidad de cuotas')
    multiplier = models.DecimalField(max_digits=5, decimal_places=4, verbose_name='Multiplicador (ej: 1.14 para 14% recargo)')
    afip_code = models.IntegerField(blank=True, null=True, verbose_name='Código AFIP (opcional)')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    
    def __str__(self):
        return f"{self.name} - {self.installments} cuotas ({self.multiplier}x)"
    
    class Meta:
        verbose_name = 'Plan de cuotas'
        verbose_name_plural = 'Planes de cuotas'
        ordering = ['name', 'installments']


class Sale(models.Model):
    STATUS_CHOICES = (
        ('budget', 'Presupuesto'),
        ('confirmed', 'Venta Confirmada'),
        ('cancelled', 'Cancelado'),
    )
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    cli = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Cliente')
    date_joined = models.DateTimeField(default=timezone.now)
    local_timezone = models.CharField(max_length=50, blank=True, null=True, verbose_name='Zona horaria local')
    subtotal = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    iva = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    total = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    payment_method = models.CharField(max_length=12, choices=payment_method_choices, default='cash', verbose_name='Forma de pago')
    payment_details = models.JSONField(default=dict, blank=True, verbose_name='Detalles de pago combinado')
    # Campos para pagos con tarjeta
    card_type = models.CharField(max_length=10, choices=[('debit', 'Débito'), ('credit', 'Crédito')], blank=True, null=True, verbose_name='Tipo de tarjeta')
    card_brand = models.CharField(max_length=20, choices=[('visa', 'Visa'), ('mastercard', 'Mastercard'), ('amex', 'American Express'), ('other', 'Otra')], blank=True, null=True, verbose_name='Marca de tarjeta')
    card_installments = models.IntegerField(blank=True, null=True, verbose_name='Cantidad de cuotas')
    card_plan = models.ForeignKey('erp.CardInstallmentPlan', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Plan de cuotas', related_name='sales')
    card_auth_code = models.CharField(max_length=20, blank=True, null=True, verbose_name='Código de autorización (módulo fiscal)')
    # Facturación
    invoice_number = models.CharField(max_length=20, null=True, blank=True)
    invoice_pos = models.CharField(max_length=5, default='0001')
    invoice_type = models.CharField(max_length=1, default='B')  # A/B/C/X
    is_credit_note = models.BooleanField(default=False, verbose_name='Es Nota de Crédito')
    is_invoiced = models.BooleanField(default=False)
    is_ticket_x = models.BooleanField(default=False, verbose_name='Es Ticket X (sin valor fiscal)')
    # Campos AFIP
    afip_cae = models.CharField(max_length=14, null=True, blank=True, verbose_name='CAE AFIP')
    afip_cae_vto = models.DateField(null=True, blank=True, verbose_name='Vencimiento CAE')
    afip_voucher_number = models.IntegerField(null=True, blank=True, verbose_name='Número de Comprobante AFIP')
    afip_result = models.JSONField(default=dict, blank=True, verbose_name='Resultado AFIP')
    afip_error = models.TextField(blank=True, null=True, verbose_name='Error AFIP')
    afip_qr = models.TextField(blank=True, null=True, verbose_name='Código QR AFIP (base64 PNG)')
    afip_pdf_url = models.URLField(blank=True, null=True, verbose_name='URL del PDF AFIP')
    afip_contingencia = models.BooleanField(default=False, verbose_name='Factura en Contingencia')
    afip_contingencia_fecha = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de Contingencia')
    afip_pendiente_autorizacion = models.BooleanField(default=False, verbose_name='Pendiente de Autorización AFIP')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    local_sale_id = models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de venta local', help_text='ID de la venta en la base de datos local para evitar duplicados')
    local_uuid = models.CharField(max_length=64, blank=True, null=True, db_index=True, verbose_name='UUID local', help_text='UUID para sincronización (índice para búsquedas rápidas)')
    source = models.CharField(max_length=20, blank=True, null=True, verbose_name='Origen', help_text='Origen de la venta (local_pos, web, etc.)')
    synced_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de sincronización')
    pos_id = models.CharField(max_length=50, blank=True, null=True, verbose_name='ID del POS', help_text='Identificador del POS que creó la venta/presupuesto')
    catalogo_pedido_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='ID de pedido del catálogo', help_text='ID del pedido en el sistema de catálogo integrado')
    # Campos para presupuestos
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed', verbose_name='Estado')
    is_budget = models.BooleanField(default=False, verbose_name='Es Presupuesto')
    sent_to_local = models.BooleanField(default=False, verbose_name='Enviado a Servidor Local')
    local_server_response = models.JSONField(default=dict, blank=True, verbose_name='Respuesta del Servidor Local')
    budget_notes = models.TextField(blank=True, null=True, verbose_name='Notas del Presupuesto')

    def __str__(self):
        if self.cli:
            return self.cli.names
        return f"Venta #{self.id} (Sin cliente)"

    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        
        # Generar local_uuid para nuevas ventas locales
        if not self.pk and not self.local_uuid:
            import uuid
            self.local_uuid = f"sale_{uuid.uuid4().hex}"
            self.source = 'local_pos'
        
        # Capturar la zona horaria local solo para nuevas ventas
        if not self.pk and not self.local_timezone:
            try:
                import pytz
                from django.conf import settings
                # Obtener la zona horaria local del sistema
                local_tz = pytz.timezone(getattr(settings, 'TIME_ZONE', 'America/Argentina/Buenos_Aires'))
                # Guardar la zona horaria actual
                self.local_timezone = str(timezone.now().astimezone(local_tz).tzinfo)
            except Exception:
                # Si hay error, usar zona horaria por defecto
                self.local_timezone = 'America/Argentina/Buenos_Aires'
        
        super().save(*args, **kwargs)

        # Emitir factura AFIP automáticamente si está configurado y la venta está confirmada
        if self.status == 'confirmed' and not self.is_budget and not self.afip_cae:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[AFIP DEBUG] Venta confirmada - Iniciando emisión automática de factura AFIP - Venta ID: {self.id}, Empresa: {self.company.name if self.company else 'N/A'}")
            self.emitir_factura_afip()

    def emitir_factura_afip(self, user=None):
        """
        Emite la factura electrónica AFIP para esta venta

        Args:
            user: Usuario que está emitiendo la factura (opcional, para validación de empresa)
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            from core.erp.afip.client import AfipClient, AfipCompanyMismatchError
            from core.erp.afip.config import get_afip_config
            from datetime import datetime

            logger.info(f"[AFIP DEBUG] Iniciando emisión de factura AFIP - Venta ID: {self.id}, Empresa: {self.company.name if self.company else 'N/A'}")

            # Validar que la venta tiene una empresa asignada
            if not self.company:
                logger.warning(f"[AFIP DEBUG] La venta {self.id} no tiene empresa asignada. No se puede emitir factura AFIP.")
                return False

            # Validar que el usuario pertenece a la misma empresa que tiene configurado AFIP
            if user and hasattr(user, 'company') and user.company:
                logger.debug(f"[AFIP DEBUG] Validando empresa - Usuario: {user.username}, Empresa usuario: {user.company.name}, Empresa venta: {self.company.name}")
                if user.company.id != self.company_id:
                    raise AfipCompanyMismatchError(
                        f"El usuario {user.username} pertenece a la empresa {user.company.name} "
                        f"pero la venta pertenece a la empresa {self.company.name}. "
                        "No tiene permiso para emitir facturas AFIP de esta empresa."
                    )

            # Obtener configuración AFIP
            logger.debug(f"[AFIP DEBUG] Obteniendo configuración AFIP para empresa ID: {self.company_id}")
            afip_config = get_afip_config(self.company_id)
            if not afip_config or not afip_config.get('is_active'):
                logger.warning(f"[AFIP DEBUG] No hay configuración AFIP activa para empresa {self.company.name}")
                return False

            logger.info(f"[AFIP DEBUG] Configuración AFIP encontrada - CUIT: {afip_config.get('CUIT')}, Ambiente: {afip_config.get('environment')}, Activa: {afip_config.get('is_active')}")

            # Inicializar cliente AFIP
            logger.debug(f"[AFIP DEBUG] Inicializando cliente AFIP para empresa ID: {self.company_id}")
            client = AfipClient(company_id=self.company_id)

            # Obtener configuración de punto de venta y tipo de comprobante
            config_obj = self.company.afipconfig_set.filter(is_active=True).first()
            if not config_obj:
                logger.warning(f"[AFIP DEBUG] No hay configuración AfipConfig activa para empresa {self.company.name}")
                return False

            logger.info(f"[AFIP DEBUG] Configuración AfipConfig encontrada - Tipo comprobante: {config_obj.tipo_comprobante}, Concepto: {config_obj.concepto}, Moneda: {config_obj.moneda}")

            # Obtener punto de venta activo (usar el primero disponible)
            punto_venta_obj = self.company.afippuntoventa_set.filter(is_active=True).first()
            if not punto_venta_obj:
                # Fallback: usar punto de venta 1 por defecto
                punto_venta = 1
                logger.warning(f"[AFIP DEBUG] No hay punto de venta activo, usando fallback: {punto_venta}")
            else:
                punto_venta = punto_venta_obj.numero
                logger.info(f"[AFIP DEBUG] Punto de venta activo: {punto_venta}")

            # Calcular IVA por alícuota
            iva_details = []
            logger.debug(f"[AFIP DEBUG] Calculando IVA por alícuota - Detalles de venta: {self.detsale_set.count()} items")
            for det in self.detsale_set.all():
                if det.iva_amount > 0:
                    # Determinar tipo de IVA según el porcentaje
                    iva_rate = (det.iva_amount / det.subtotal) * 100 if det.subtotal > 0 else 0
                    if iva_rate == 21:
                        iva_id = 5
                    elif iva_rate == 10.5:
                        iva_id = 4
                    elif iva_rate == 0:
                        iva_id = 3
                    else:
                        iva_id = 5  # Default 21%

                    logger.debug(f"[AFIP DEBUG] IVA detalle - Tasa: {iva_rate}%, ID: {iva_id}, Base: {det.subtotal}, Importe: {det.iva_amount}")

                    iva_details.append({
                        'Id': iva_id,
                        'BaseImp': float(det.subtotal),
                        'Importe': float(det.iva_amount)
                    })

            # Si hay importe neto pero no hay detalles de IVA, agregar alícuota 0 (No gravado/Exento)
            # AFIP requiere el objeto Iva cuando ImpNeto > 0 (error 10070)
            if self.subtotal > 0 and not iva_details:
                logger.info(f"[AFIP DEBUG] Agregando alícuota IVA 0 (No gravado) - Base: {self.subtotal}")
                iva_details.append({
                    'Id': 3,  # No gravado/Exento
                    'BaseImp': float(self.subtotal),
                    'Importe': 0.0
                })

            # Preparar datos del voucher
            fecha_afip = datetime.now().strftime('%Y%m%d')
            logger.info(f"[AFIP DEBUG] Preparando voucher - Fecha: {fecha_afip}, Total: {self.total}, Subtotal: {self.subtotal}, IVA: {self.iva}")

            # Determinar tipo y número de documento según datos del cliente
            # Para facturas A (tipo_comprobante = 1), DocTipo debe ser 80 (CUIT) obligatoriamente
            if config_obj.tipo_comprobante == 1:  # Factura A
                # Para facturas A, AFIP requiere CUIT obligatoriamente
                if self.cli and self.cli.cuit_cuil:
                    doc_tipo = 80  # CUIT
                    doc_nro = int(self.cli.cuit_cuil.replace('-', ''))
                    logger.info(f"[AFIP DEBUG] Factura A - Cliente con CUIT - DocTipo: {doc_tipo}, DocNro: {doc_nro}")
                else:
                    # Si el cliente no tiene CUIT, usar CUIT de la empresa
                    if config_obj.cuit:
                        doc_tipo = 80  # CUIT
                        doc_nro = int(config_obj.cuit.replace('-', ''))
                        logger.info(f"[AFIP DEBUG] Factura A - Sin CUIT cliente, usando CUIT empresa - DocTipo: {doc_tipo}, DocNro: {doc_nro}")
                    else:
                        # Error: Factura A requiere CUIT
                        logger.error(f"[AFIP DEBUG] Factura A requiere CUIT pero no hay CUIT de cliente ni empresa")
                        self.afip_error = "Factura A requiere CUIT del cliente o de la empresa"
                        self.save(update_fields=['afip_error'])
                        return False
            else:
                # Para otros tipos de comprobante (B, C, etc.), usar lógica normal
                if self.cli and self.cli.cuit_cuil:
                    doc_tipo = 80  # CUIT
                    doc_nro = int(self.cli.cuit_cuil.replace('-', ''))
                    logger.info(f"[AFIP DEBUG] Cliente con CUIT - DocTipo: {doc_tipo}, DocNro: {doc_nro}")
                elif self.cli and self.cli.dni:
                    doc_tipo = 96  # DNI
                    doc_nro = int(self.cli.dni)
                    logger.info(f"[AFIP DEBUG] Cliente con DNI - DocTipo: {doc_tipo}, DocNro: {doc_nro}")
                else:
                    doc_tipo = 99  # Consumidor Final sin datos
                    doc_nro = 0
                    logger.info(f"[AFIP DEBUG] Cliente consumidor final - DocTipo: {doc_tipo}, DocNro: {doc_nro}")

            # Determinar condición IVA del receptor según normativa AFIP RG 5616/2024
            # Mapeo: RI=1, M=4, CF=5, EX=6, NC=9
            condicion_iva_cliente = self.cli.condicion_iva if self.cli else 'CF'
            condicion_iva_map = {
                'RI': 1,  # Responsable Inscripto
                'M': 4,   # Monotributista
                'CF': 5,  # Consumidor Final
                'EX': 6,  # Exento
                'NC': 9   # No Categorizado
            }
            condicion_iva_receptor_id = condicion_iva_map.get(condicion_iva_cliente, 5)  # Default: Consumidor Final
            logger.info(f"[AFIP DEBUG] Condición IVA cliente: {condicion_iva_cliente}, ID receptor: {condicion_iva_receptor_id}")

            # Mapear invoice_type ('A', 'B', 'C') a código AFIP numérico
            invoice_type_map = {
                'A': 1,   # Factura A
                'B': 6,   # Factura B
                'C': 11,  # Factura C
                'X': 99   # Ticket X (sin valor fiscal)
            }
            cbte_tipo = invoice_type_map.get(self.invoice_type, config_obj.tipo_comprobante)
            logger.info(f"[AFIP DEBUG] Invoice type: {self.invoice_type}, CbteTipo AFIP: {cbte_tipo}")

            # Preparar voucher_data SIN CbteDesde/CbteHasta (createNextVoucher los calcula automáticamente)
            voucher_data = {
                'CantReg': 1,
                'PtoVta': punto_venta,  # Usar punto de venta de AfipPuntoVenta
                'CbteTipo': cbte_tipo,  # Usar el tipo determinado según condición IVA del cliente
                'Concepto': config_obj.concepto,  # Usar concepto de la configuración
                'DocTipo': doc_tipo,
                'DocNro': doc_nro,
                'CbteFch': int(fecha_afip),
                'ImpTotal': float(self.total),
                'ImpTotConc': 0.0,
                'ImpNeto': float(self.subtotal),
                'ImpOpEx': 0.0,
                'ImpIVA': float(self.iva),
                'ImpTrib': 0.0,
                'MonId': config_obj.moneda,  # Usar moneda de la configuración
                'MonCotiz': float(config_obj.cotizacion),  # Usar cotización de la configuración
                'CondicionIVAReceptorId': condicion_iva_receptor_id,  # Condición IVA del receptor (RG 5616/2024)
            }
            
            # Para facturas tipo C (CbteTipo 11), NO enviar el objeto Iva (error 10071)
            if cbte_tipo != 11:
                voucher_data['Iva'] = iva_details if iva_details else []
                logger.info(f"[AFIP DEBUG] Incluyendo objeto Iva - Tipo: {cbte_tipo}, Detalles: {len(iva_details)}")
            else:
                logger.info(f"[AFIP DEBUG] Factura tipo C - NO enviando objeto Iva (AFIP error 10071)")

            logger.info(f"[AFIP DEBUG] Voucher data preparado - PtoVta: {punto_venta}, CbteTipo: {cbte_tipo}")
            logger.debug(f"[AFIP DEBUG] Datos completos del voucher: {voucher_data}")

            # Crear voucher usando createNextVoucher (calcula número automáticamente)
            logger.info(f"[AFIP DEBUG] Enviando solicitud de voucher a AFIP usando createNextVoucher")
            result = client.create_next_voucher(voucher_data, full_response=True)

            logger.debug(f"[AFIP DEBUG] Respuesta completa de createNextVoucher: {result}")
            logger.debug(f"[AFIP DEBUG] Tipo de respuesta: {type(result)}")
            logger.debug(f"[AFIP DEBUG] Claves en respuesta: {result.keys() if isinstance(result, dict) else 'N/A'}")

            if 'error' in result:
                logger.error(f"[AFIP DEBUG] Error al crear voucher: {result['error']}")
                self.afip_error = str(result['error'])
                self.save(update_fields=['afip_error'])
                return False

            # Guardar resultado AFIP
            self.afip_cae = result.get('CAE', '')
            # AFIP devuelve fecha en formato YYYY-MM-DD (ej: 2026-07-20)
            cae_fch_vto = result.get('CAEFchVto', '')
            if cae_fch_vto:
                try:
                    # Intentar formato YYYY-MM-DD
                    self.afip_cae_vto = datetime.strptime(cae_fch_vto, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        # Fallback a formato YYYYMMDD
                        self.afip_cae_vto = datetime.strptime(cae_fch_vto, '%Y%m%d').date()
                    except ValueError:
                        logger.error(f"[AFIP] Error parseando fecha CAE vencimiento: {cae_fch_vto}")
                        self.afip_cae_vto = None
            else:
                self.afip_cae_vto = None

            # createNextVoucher devuelve el número de comprobante en distintas claves según el modo
            # Intentar múltiples claves para encontrar el número (incluyendo camelCase)
            next_nro = result.get('voucherNumber') or result.get('voucher_number') or result.get('CbteDesde') or result.get('CbteHasta') or result.get('cbte_desde') or result.get('cbte_hasta')

            # Si no está en las claves principales, buscar en respuestas anidadas
            if not next_nro and isinstance(result, dict):
                for key in ['FECAESolicitarResponse', 'response', 'result']:
                    if key in result and isinstance(result[key], dict):
                        nested = result[key]
                        next_nro = nested.get('voucherNumber') or nested.get('voucher_number') or nested.get('CbteDesde') or nested.get('CbteHasta') or nested.get('cbte_desde') or nested.get('cbte_hasta')
                        if next_nro:
                            logger.debug(f"[AFIP DEBUG] Número encontrado en respuesta anidada [{key}]: {next_nro}")
                            break

            if next_nro:
                self.afip_voucher_number = next_nro
                logger.info(f"[AFIP DEBUG] Número de comprobante asignado por AFIP: {next_nro}")
            else:
                logger.error(f"[AFIP DEBUG] No se recibió número de comprobante en respuesta AFIP")
                logger.error(f"[AFIP DEBUG] Estructura de respuesta completa: {result}")
                self.afip_error = "No se recibió número de comprobante de AFIP"
                self.save(update_fields=['afip_error'])
                return False

            self.afip_result = result
            self.is_invoiced = True
            # Generar código QR
            self.afip_qr = self._generate_afip_qr(config_obj, next_nro, punto_venta)
            self.save(update_fields=['afip_cae', 'afip_cae_vto', 'afip_voucher_number', 'afip_result', 'is_invoiced', 'afip_qr'])

            logger.info(f"[AFIP DEBUG] Factura AFIP emitida exitosamente - CAE: {self.afip_cae}, Vencimiento: {self.afip_cae_vto}, Número: {self.afip_voucher_number}")

            # Crear registro en Libro IVA para ventas
            logger.debug(f"[AFIP DEBUG] Creando registro en Libro IVA")
            self._crear_registro_libro_iva(config_obj, punto_venta, next_nro)

            # Crear movimiento en cuenta corriente del cliente
            if self.cli:
                logger.debug(f"[AFIP DEBUG] Creando movimiento en cuenta corriente del cliente")
                self._crear_movimiento_cuenta_corriente(config_obj, punto_venta, next_nro)

            # Crear asiento contable básico
            logger.debug(f"[AFIP DEBUG] Creando asiento contable básico")
            self._crear_asiento_contable(config_obj, punto_venta, next_nro)

            logger.info(f"[AFIP DEBUG] Proceso de emisión de factura AFIP completado exitosamente para venta ID: {self.id}")
            return True

        except Exception as e:
            # Si falla AFIP, marcar como contingencia si está configurado
            error_msg = str(e)
            logger.error(f"[AFIP DEBUG] Error en emisión de factura AFIP: {error_msg}")
            self.afip_error = error_msg

            # Verificar si debe activar modo contingencia
            from .afip.config import get_afip_config
            afip_config = get_afip_config(self.company_id)
            usar_contingencia = afip_config.get('usar_contingencia', False) if afip_config else False

            logger.info(f"[AFIP DEBUG] Modo contingencia configurado: {usar_contingencia}")

            if usar_contingencia:
                # Activar modo contingencia
                logger.warning(f"[AFIP DEBUG] Activando modo contingencia para venta ID: {self.id}")
                self.afip_contingencia = True
                self.afip_contingencia_fecha = timezone.now()
                self.afip_pendiente_autorizacion = True
                self.is_invoiced = True  # Marcar como facturada aunque sin CAE

                # Generar número de comprobante local
                punto_venta_obj = self.company.afippuntoventa_set.filter(is_active=True).first()
                punto_venta = punto_venta_obj.numero if punto_venta_obj else 1
                config_obj = self.company.afipconfig_set.filter(is_active=True).first()
                tipo_map = {1: 1, 6: 6, 11: 11}
                tipo_comprobante_libro = tipo_map.get(config_obj.tipo_comprobante, 6) if config_obj else 6

                # Asignar número de comprobante temporal (se actualizará al autorizar)
                if not self.afip_voucher_number:
                    self.afip_voucher_number = 0  # Temporal, se actualizará al autorizar

                self.save(update_fields=['afip_error', 'afip_contingencia', 'afip_contingencia_fecha', 'afip_pendiente_autorizacion', 'is_invoiced', 'afip_voucher_number'])
                return True  # Retornar True para no bloquear la venta
            else:
                self.save(update_fields=['afip_error'])
                return False

    def _crear_registro_libro_iva(self, config_obj, punto_venta, nro_cbte):
        """
        Crea automáticamente un registro en el Libro IVA para ventas.
        """
        from .models import LibroIvaRegistro

        try:
            # Mapear tipo de comprobante AFIP a tipo de comprobante del Libro IVA
            tipo_map = {1: 1, 6: 6, 11: 11}  # A, B, C
            tipo_comprobante_libro = tipo_map.get(config_obj.tipo_comprobante, 6)

            # Calcular IVA por alícuota
            iva_21 = 0
            iva_10_5 = 0
            iva_27 = 0
            iva_2_5 = 0
            iva_0 = 0

            for det in self.detsale_set.all():
                if det.iva_amount > 0:
                    iva_rate = (det.iva_amount / det.subtotal) * 100 if det.subtotal > 0 else 0
                    if iva_rate == 21:
                        iva_21 += float(det.iva_amount)
                    elif iva_rate == 10.5:
                        iva_10_5 += float(det.iva_amount)
                    elif iva_rate == 27:
                        iva_27 += float(det.iva_amount)
                    elif iva_rate == 2.5:
                        iva_2_5 += float(det.iva_amount)
                    elif iva_rate == 0:
                        iva_0 += float(det.iva_amount)

            # Determinar condición IVA del cliente
            condicion_iva = self.cli.condicion_iva if self.cli else 'CF'

            # Determinar aplicación IVA según condición del cliente
            if condicion_iva == 'RI':
                aplicacion_iva = 3  # Gravado
            elif condicion_iva == 'M':
                aplicacion_iva = 2  # Exento
            elif condicion_iva == 'CF':
                aplicacion_iva = 3  # Gravado
            else:
                aplicacion_iva = 3  # Gravado por defecto

            # Calcular neto gravado
            neto_gravado = float(self.subtotal) if aplicacion_iva == 3 else 0
            neto_exento = float(self.subtotal) if aplicacion_iva == 2 else 0

            LibroIvaRegistro.objects.create(
                company=self.company,
                tipo_registro='venta',
                fecha=self.date_joined.date() if self.date_joined else timezone.now().date(),
                tipo_comprobante=tipo_comprobante_libro,
                punto_venta=punto_venta,
                numero_comprobante=nro_cbte,
                cuit_emisor=self.company.cuit or config_obj.cuit,
                cuit_receptor=self.cli.cuit_cuil if self.cli else None,
                razon_social=f"{self.cli.names} {self.cli.surnames or ''}".strip() if self.cli else 'Consumidor Final',
                condicion_iva=condicion_iva,
                aplicacion_iva=aplicacion_iva,
                neto_gravado=neto_gravado,
                neto_no_gravado=0,
                neto_exento=neto_exento,
                iva_21=iva_21,
                iva_10_5=iva_10_5,
                iva_27=iva_27,
                iva_2_5=iva_2_5,
                iva_0=iva_0,
                impuesto_interno=0,
                total=float(self.total),
                cae=self.afip_cae,
                cae_vto=self.afip_cae_vto,
                sale=self
            )
        except Exception as e:
            # No fallar la factura si falla el registro del libro IVA
            print(f"Error creando registro Libro IVA: {e}")

    def _crear_movimiento_cuenta_corriente(self, config_obj, punto_venta, nro_cbte):
        """
        Crea automáticamente un movimiento en la cuenta corriente del cliente.
        """
        from .models import CuentaCorrienteCliente

        try:
            # Obtener el último saldo del cliente
            ultimo_movimiento = CuentaCorrienteCliente.objects.filter(
                client=self.cli,
                company=self.company
            ).order_by('-fecha', '-created_at').first()

            saldo_anterior = ultimo_movimiento.saldo if ultimo_movimiento else 0

            # Crear movimiento de venta (débito)
            tipo_map = {1: 'A', 6: 'B', 11: 'C'}
            tipo_letra = tipo_map.get(config_obj.tipo_comprobante, 'B') if config_obj else 'B'

            descripcion = f"Factura {tipo_letra} {punto_venta:04d}-{nro_cbte:08d}"

            from decimal import Decimal
            CuentaCorrienteCliente.objects.create(
                company=self.company,
                client=self.cli,
                tipo_movimiento='venta',
                fecha=self.date_joined.date() if self.date_joined else timezone.now().date(),
                descripcion=descripcion,
                debe=float(self.total),
                haber=0,
                saldo=saldo_anterior + Decimal(str(self.total)),
                sale=self
            )
        except Exception as e:
            # No fallar la factura si falla el movimiento de cuenta corriente
            print(f"Error creando movimiento cuenta corriente: {e}")

    def _crear_asiento_contable(self, config_obj, punto_venta, nro_cbte):
        """
        Crea automáticamente un asiento contable básico para la venta.
        """
        from .models import AsientoContable

        try:
            tipo_map = {1: 'A', 6: 'B', 11: 'C'}
            tipo_letra = tipo_map.get(config_obj.tipo_comprobante, 'B') if config_obj else 'B'

            descripcion = f"Venta - Factura {tipo_letra} {punto_venta:04d}-{nro_cbte:08d}"

            # Asiento contable básico: Debe = Total venta, Haber = Total venta (equilibrado)
            AsientoContable.objects.create(
                company=self.company,
                tipo_asiento='venta',
                fecha=self.date_joined.date() if self.date_joined else timezone.now().date(),
                descripcion=descripcion,
                debe_total=float(self.total),
                haber_total=float(self.total),
                sale=self
            )
        except Exception as e:
            # No fallar la factura si falla el asiento contable
            print(f"Error creando asiento contable: {e}")

    def _generate_afip_qr(self, config_obj, nro_cbte, punto_venta):
        """
        Genera el código QR de AFIP como base64 PNG.
        El QR contiene una URL con los datos del comprobante codificados en base64.
        """
        import base64
        import json as json_mod
        import io
        try:
            # Construir el payload según especificación AFIP
            cuit_clean = str(config_obj.cuit or self.company.cuit or '').replace('-', '')
            fecha_cbte = self.date_joined.strftime('%Y-%m-%d') if self.date_joined else datetime.now().strftime('%Y-%m-%d')

            # Tipo y número de documento del receptor
            if self.cli and self.cli.cuit_cuil:
                doc_tipo = 80  # CUIT
                doc_nro = int(str(self.cli.cuit_cuil).replace('-', ''))
            elif self.cli and self.cli.dni:
                doc_tipo = 96  # DNI
                doc_nro = int(str(self.cli.dni).replace('-', ''))
            else:
                doc_tipo = 99  # Sin documento
                doc_nro = 0

            payload = {
                "ver": 1,
                "fecha": fecha_cbte,
                "cuit": int(cuit_clean) if cuit_clean else 0,
                "ptoVta": punto_venta,  # Usar punto de venta de AfipPuntoVenta
                "tipoCmp": config_obj.tipo_comprobante,
                "nroCmp": nro_cbte,
                "importe": float(self.total),
                "moneda": "PES",
                "ctz": 1,
                "tipoDocRec": doc_tipo,
                "nroDocRec": doc_nro,
                "tipoCodAut": "E",
                "codAut": int(self.afip_cae) if self.afip_cae else 0,
            }

            # Codificar payload en base64
            payload_json = json_mod.dumps(payload, separators=(',', ':'))
            payload_b64 = base64.b64encode(payload_json.encode('utf-8')).decode('utf-8')

            # URL del QR de AFIP
            qr_url = f"https://www.afip.gob.ar/fe/qr/?p={payload_b64}"

            # Generar imagen QR
            import qrcode
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=6,
                border=2,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color='black', back_color='white')
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            return f"data:image/png;base64,{qr_b64}"

        except Exception as e:
            import logging
            logging.getLogger('erp').error(f"Error generando QR AFIP: {e}")
            return None

    def next_sequential_for_pos_type(self):
        """
        Genera número de factura secuencial consultando primero el servidor
        para mantener numeración unificada entre todos los POS.
        Usa MAX() para obtener el número más alto real, no el último registro.
        """
        try:
            # Intentar obtener el número MÁXIMO del servidor primero
            from django.db import connections
            with connections['remote'].cursor() as cursor:
                cursor.execute('''
                    SELECT MAX(invoice_number) 
                    FROM erp_sale 
                    WHERE company_id = %s AND invoice_pos = %s AND invoice_type = %s AND invoice_number IS NOT NULL
                ''', [self.company_id, self.invoice_pos, self.invoice_type])
                
                result = cursor.fetchone()
                max_server_number = result[0] if result and result[0] else None
                
                if max_server_number:
                    try:
                        seq = int(max_server_number.split('-')[-1]) + 1
                    except Exception:
                        seq = 1
                else:
                    seq = 1
                    
                return f"{self.invoice_pos}-{self.invoice_type}-{seq:08d}"
                
        except Exception:
            # Fallback a lógica actual local si hay error de conexión
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
        item = model_to_dict(self, exclude=['date_creation', 'date_updated', 'user_creation', 'user_updated'])
        item['cli'] = (self.cli.names if self.cli else 'Anónimo')
        # Formatear la fecha sin conversión de zona horaria (Django ya maneja esto)
        try:
            # Usar timezone.localtime para convertir a la zona horaria local configurada
            local_dt = timezone.localtime(self.date_joined)
            item['date_joined'] = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            item['date_joined_display'] = local_dt.strftime('%d-%m-%Y %H:%M')
        except Exception as e:
            # Fallback si hay error
            item['date_joined'] = self.date_joined.strftime('%Y-%m-%d %H:%M:%S') if self.date_joined else ''
            item['date_joined_display'] = self.date_joined.strftime('%d-%m-%Y %H:%M') if self.date_joined else ''
        
        # Formatear valores monetarios como strings para consistencia
        item['subtotal'] = format(self.subtotal, '.2f')
        item['iva'] = format(self.iva, '.2f')
        item['total'] = format(self.total, '.2f')
        item['payment_method'] = {'id': self.payment_method, 'name': self.get_payment_method_display()}
        # Incluir detalles de pago combinado si existen
        if hasattr(self, 'payment_details') and self.payment_details:
            item['payment_details'] = self.payment_details
        else:
            item['payment_details'] = []
        item['invoice_number'] = self.invoice_number or ''
        item['invoice_pos'] = self.invoice_pos or ''
        item['invoice_type'] = self.invoice_type or ''
        item['is_invoiced'] = self.is_invoiced
        item['local_uuid'] = self.local_uuid or ''
        item['source'] = self.source or ''
        item['synced_to_server'] = self.synced_to_server
        item['synced_at'] = self.synced_at.strftime('%Y-%m-%d %H:%M:%S') if self.synced_at else ''
        item['det'] = [i.toJSON() for i in self.detsale_set.all()]
        return item

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['id']


class SaleVatBreakdown(models.Model):
    """Apertura de alícuotas de IVA por venta para Libro IVA Digital"""
    VAT_CODE_CHOICES = (
        ('5', '21%'),
        ('4', '10.5%'),
        ('6', '27%'),
        ('3', '0% (Exento)'),
        ('2', '2.5%'),
        ('8', '5%'),
        ('9', 'No gravado'),
    )
    
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='vat_breakdowns')
    vat_code = models.CharField(max_length=1, choices=VAT_CODE_CHOICES, verbose_name='Código AFIP')
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Tasa IVA (%)')
    taxable_base = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Base imponible')
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto IVA')

    def __str__(self):
        return f"{self.sale.id} - {self.get_vat_code_display()}: ${self.taxable_base} + ${self.vat_amount}"

    class Meta:
        verbose_name = 'Apertura de IVA'
        verbose_name_plural = 'Aperturas de IVA'
        unique_together = ['sale', 'vat_code']

    def toJSON(self):
        item = model_to_dict(self, exclude=['sale'])
        item['vat_code_display'] = self.get_vat_code_display()
        item['taxable_base'] = format(self.taxable_base, '.2f') if self.taxable_base is not None else '0.00'
        item['vat_amount'] = format(self.vat_amount, '.2f') if self.vat_amount is not None else '0.00'
        item['vat_rate'] = format(self.vat_rate, '.2f') if self.vat_rate is not None else '0.00'
        return item


class DetSale(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE)
    prod = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    cant = models.DecimalField(default=0, max_digits=9, decimal_places=3)
    subtotal = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    iva_amount = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='Monto IVA')

    def __str__(self):
        return self.prod.name
    
    def toJSON(self):
        item = model_to_dict(self, exclude=['date_creation', 'date_updated', 'user_creation', 'user_updated'])
        item['prod'] = self.prod.toJSON() if self.prod else {}
        item['cant'] = float(self.cant)
        item['subtotal'] = float(self.subtotal)
        item['iva_amount'] = float(self.iva_amount)
        return item
    
    def calculate_iva_amount(self):
        """Calcular el monto de IVA para este detalle"""
        if self.prod and self.prod.iva_rate:
            # Calcular IVA basado en el subtotal
            iva_rate = Decimal(str(self.prod.iva_rate))
            # Normalizar rate: si es mayor que 1, tratarlo como porcentaje (21 -> 0.21)
            if iva_rate > Decimal('1.0'):
                iva_rate = iva_rate / Decimal('100.0')
            subtotal_decimal = Decimal(str(self.subtotal))
            return (subtotal_decimal * iva_rate).quantize(Decimal('0.01'))
        return Decimal('0.00')
    
    def save(self, *args, **kwargs):        # Calcular el monto de IVA automáticamente
        self.iva_amount = self.calculate_iva_amount()
        super().save(*args, **kwargs)

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


# Choices para motivos recurrentes de gastos
EXPENSE_RECURRING_REASONS = [
    ('alquiler', 'Alquiler'),
    ('habilitacion_comercial', 'Habilitación comercial'),
    ('boletas_luz', 'Boletas de luz'),
    ('servicio_internet', 'Servicio de internet'),
    ('bidon_agua', 'Bidón de agua'),
    ('combustible', 'Combustible'),
    ('comision_ventas', 'Comisión de ventas'),
    ('bolserios', 'Bolseríos'),
    ('libreria', 'Librería'),
    ('otro', 'Otro'),
]

EXPENSE_PAYMENT_METHOD_CHOICES = (
    ('efectivo', 'Efectivo'),
    ('transferencia', 'Transferencia'),
    ('mercadopago', 'MercadoPago'),
    ('tarjeta', 'Tarjeta'),
    ('cheque', 'Cheque'),
    ('otro', 'Otro'),
)

class Expense(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Proveedor')
    date = models.DateField(default=datetime.now, verbose_name='Fecha')
    time = models.TimeField(default=datetime.now, verbose_name='Hora', blank=True, null=True)
    description = models.CharField(max_length=255, verbose_name='Descripción', blank=True, null=True)
    recurring_reason = models.CharField(max_length=30, choices=EXPENSE_RECURRING_REASONS, blank=True, null=True, verbose_name='Motivo recurrente')
    amount = models.DecimalField(default=0.00, max_digits=12, decimal_places=2, verbose_name='Importe')
    payment_method = models.CharField(max_length=20, choices=EXPENSE_PAYMENT_METHOD_CHOICES, default='efectivo', verbose_name='Método de pago')
    payer = models.CharField(max_length=150, verbose_name='Pagado por', blank=True, null=True)
    receipt = models.FileField(upload_to='expenses/%Y/%m/%d', null=True, blank=True, verbose_name='Comprobante (PDF/Imagen)')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    local_uuid = models.CharField(max_length=64, blank=True, null=True, db_index=True, verbose_name='UUID local', help_text='UUID para sincronización (índice para búsquedas rápidas)')
    local_expense_id = models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de gasto local', help_text='ID del gasto en la base de datos local para evitar duplicados')
    source = models.CharField(max_length=20, blank=True, null=True, verbose_name='Origen', help_text='Origen del gasto (local_pos, web, etc.)')
    synced_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de sincronización')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    def __str__(self):
        base = self.description or 'Gasto'
        return f"{base} - {self.amount}"

    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        
        # Si la descripción está vacía y hay un motivo recurrente, usar el motivo como descripción
        if not self.description and self.recurring_reason:
            reason_dict = dict(EXPENSE_RECURRING_REASONS)
            self.description = reason_dict.get(self.recurring_reason, self.recurring_reason)
        
        # Generar local_uuid para nuevos gastos locales
        if not self.pk and not self.local_uuid:
            import uuid
            self.local_uuid = f"expense_{uuid.uuid4().hex}"
            self.source = 'local_pos'
        
        super().save(*args, **kwargs)

    def get_receipt_url(self):
        if self.receipt:
            return f"{MEDIA_URL}{self.receipt}"
        return None

    def toJSON(self):
        item = model_to_dict(self, exclude=['date_creation', 'date_updated', 'user_creation', 'user_updated'])
        item['supplier'] = (self.supplier.name if self.supplier_id else None)
        item['supplier_id'] = self.supplier_id
        item['date'] = self.date.strftime('%Y-%m-%d') if self.date else None
        item['time'] = self.time.strftime('%H:%M') if self.time else None
        item['amount'] = format(self.amount, '.2f') if self.amount is not None else '0.00'
        item['receipt_url'] = self.get_receipt_url()
        return item

    class Meta:
        verbose_name = 'Gasto/Compra'
        verbose_name_plural = 'Gastos/Compras'
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
    date = models.DateField(verbose_name='Fecha')
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Saldo inicial')
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Saldo final')
    cash_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Ventas en efectivo')
    card_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Ventas con tarjeta')
    transfer_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Ventas por transferencia')
    mp_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Ventas por Mercado Pago')
    expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name='Gastos')
    notes = models.TextField(blank=True, null=True, verbose_name='Notas')
    is_closed = models.BooleanField(default=False, verbose_name='Caja cerrada')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_synced = models.BooleanField(default=False, verbose_name='Sincronizado')
    sync_id = models.CharField(max_length=100, blank=True, null=True)
    local_uuid = models.UUIDField(unique=True, default=None, null=True, editable=False, verbose_name='UUID local')

    class Meta:
        verbose_name = 'Cierre de caja'
        verbose_name_plural = 'Cierres de caja'
        ordering = ['-date', '-created_at']
        # unique_together = [['date', 'user', 'company']]  # Comentado por conflictos con datos existentes
        permissions = [
            ("close_cash_register", "Puede cerrar caja"),
            ("view_cash_register", "Puede ver cierres de caja"),
        ]

    def __str__(self):
        return f"Caja {self.date} - {self.user.get_full_name()}"

    def save(self, *args, **kwargs):
        # Generar local_uuid automáticamente para nuevos cierres de caja
        if not self.local_uuid:
            import uuid
            self.local_uuid = uuid.uuid4()
        super().save(*args, **kwargs)

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
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    
    def __str__(self):
        return f"Transferencia {self.transfer_number} - {self.origin_pos} → {self.destination_pos}"
    
    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        
        if not self.transfer_number:
            self.transfer_number = self.generate_transfer_number()
        
        # Marcar para sincronizar si la transferencia ya existe y hay cambios
        if self.pk:
            # Verificar si hay cambios relevantes para sincronizar
            old_transfer = InternalTransfer.objects.filter(pk=self.pk).first()
            if old_transfer:
                changes = (
                    old_transfer.status != self.status or
                    old_transfer.observations != self.observations
                )
                if changes:
                    self.synced_to_server = False
        else:
            # Nueva transferencia, marcar para sincronizar
            self.synced_to_server = False
        
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
        item = model_to_dict(self, exclude=['date_creation', 'date_updated', 'user_creation', 'user_updated'])
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
    
    def save(self, *args, **kwargs):        # Calcular subtotal automáticamente
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    def toJSON(self):
        item = model_to_dict(self, exclude=['date_creation', 'date_updated', 'user_creation', 'user_updated'])
        item['product_name'] = self.product.name
        item['product_code'] = self.product.code
        item['product_unit'] = self.product.get_unit_display()
        return item
    
    class Meta:
        verbose_name = 'Detalle de Transferencia'
        verbose_name_plural = 'Detalles de Transferencia'
        ordering = ['id']


class AfipConfig(models.Model):
    """Configuración de AFIP SDK por empresa"""
    ENVIRONMENT_CHOICES = (
        ('dev', 'Desarrollo'),
        ('prod', 'Producción'),
    )
    CONCEPTO_CHOICES = (
        (1, 'Productos'),
        (2, 'Servicios'),
        (3, 'Productos y Servicios'),
    )
    MONEDA_CHOICES = (
        ('PES', 'Pesos Argentinos'),
        ('DOL', 'Dólar Estadounidense'),
        ('EUR', 'Euro'),
        ('BRL', 'Real Brasileño'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    cuit = models.CharField(max_length=20, verbose_name='CUIT', validators=[validate_cuit])
    access_token = models.CharField(max_length=255, verbose_name='Access Token AFIP SDK')
    clave_fiscal_username = models.CharField(max_length=100, blank=True, null=True, verbose_name='Usuario Clave Fiscal')
    clave_fiscal_password = models.CharField(max_length=100, blank=True, null=True, verbose_name='Contraseña Clave Fiscal')
    cert = models.TextField(blank=True, null=True, verbose_name='Certificado (solo producción)')
    key = models.TextField(blank=True, null=True, verbose_name='Key (solo producción)')
    environment = models.CharField(max_length=10, choices=ENVIRONMENT_CHOICES, default='dev', verbose_name='Ambiente')
    tipo_comprobante = models.IntegerField(default=6, verbose_name='Tipo de Comprobante (default: 6=Factura B)')
    concepto = models.IntegerField(default=1, choices=CONCEPTO_CHOICES, verbose_name='Concepto (1=Productos, 2=Servicios, 3=Ambos)')
    moneda = models.CharField(max_length=3, choices=MONEDA_CHOICES, default='PES', verbose_name='Moneda')
    cotizacion = models.DecimalField(max_digits=10, decimal_places=2, default=1.0, verbose_name='Cotización (si no es PES)')
    usar_contingencia = models.BooleanField(default=False, verbose_name='Usar Modo Contingencia (operar sin AFIP)')
    wsfe_authorized = models.BooleanField(default=False, verbose_name='WSFE Autorizado')
    wsfe_authorized_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de autorización WSFE')
    wsfe_automation_id = models.CharField(max_length=255, blank=True, null=True, verbose_name='ID de automatización de autorización WSFE')
    
    # Configuración de módulo fiscal físico
    FISCAL_PRINTER_CHOICES = (
        ('none', 'Sin impresora fiscal'),
        ('hasar', 'Hasar (715/615)'),
        ('epson', 'Epson TM-T88'),
    )
    fiscal_printer_enabled = models.BooleanField(default=False, verbose_name='Habilitar impresora fiscal física')
    fiscal_printer_type = models.CharField(max_length=20, choices=FISCAL_PRINTER_CHOICES, default='none', verbose_name='Tipo de impresora fiscal')
    fiscal_printer_port = models.CharField(max_length=50, blank=True, null=True, verbose_name='Puerto serial (ej: /dev/ttyUSB0)')
    fiscal_printer_baudrate = models.IntegerField(default=9600, verbose_name='Velocidad de comunicación')
    
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')
    
    def __str__(self):
        return f"AFIP Config - {self.company.name if self.company else 'Global'} ({self.cuit})"
    
    class Meta:
        verbose_name = 'Configuración AFIP'
        verbose_name_plural = 'Configuraciones AFIP'
        ordering = ['-is_active', 'company__name']


class AfipPuntoVenta(models.Model):
    """Puntos de venta AFIP por empresa"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa')
    numero = models.IntegerField(verbose_name='Número de Punto de Venta')
    descripcion = models.CharField(max_length=100, blank=True, null=True, verbose_name='Descripción')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')

    def __str__(self):
        return f"Punto de Venta {self.numero:04d} - {self.company.name}"

    class Meta:
        verbose_name = 'Punto de Venta AFIP'
        verbose_name_plural = 'Puntos de Venta AFIP'
        unique_together = ['company', 'numero']
        ordering = ['company__name', 'numero']


class LibroIvaRegistro(models.Model):
    """Registros para Libro IVA Digital (compras y ventas)"""
    TIPO_REGISTRO_CHOICES = (
        ('compra', 'Compra'),
        ('venta', 'Venta'),
    )
    TIPO_COMPROBANTE_CHOICES = (
        (1, 'Factura A'),
        (2, 'Nota de Crédito A'),
        (3, 'Nota de Débito A'),
        (4, 'Recibo A'),
        (6, 'Factura B'),
        (7, 'Nota de Crédito B'),
        (8, 'Nota de Débito B'),
        (9, 'Recibo B'),
        (11, 'Factura C'),
        (12, 'Nota de Crédito C'),
        (13, 'Nota de Débito C'),
        (15, 'Recibo C'),
    )
    APLICACION_IVA_CHOICES = (
        (1, 'No Gravado'),
        (2, 'Exento'),
        (3, 'Gravado'),
        (4, 'Gravado - No Gravado'),
        (5, 'Gravado - Exento'),
        (6, 'Gravado - No Gravado - Exento'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa')
    tipo_registro = models.CharField(max_length=10, choices=TIPO_REGISTRO_CHOICES, verbose_name='Tipo de Registro')
    fecha = models.DateField(verbose_name='Fecha del Comprobante')
    tipo_comprobante = models.IntegerField(choices=TIPO_COMPROBANTE_CHOICES, verbose_name='Tipo de Comprobante')
    punto_venta = models.IntegerField(verbose_name='Punto de Venta')
    numero_comprobante = models.BigIntegerField(verbose_name='Número de Comprobante')
    cuit_emisor = models.CharField(max_length=20, blank=True, null=True, verbose_name='CUIT Emisor')
    cuit_receptor = models.CharField(max_length=20, blank=True, null=True, verbose_name='CUIT Receptor')
    razon_social = models.CharField(max_length=200, blank=True, null=True, verbose_name='Razón Social')
    condicion_iva = models.CharField(max_length=2, choices=CONDICION_IVA_CHOICES, verbose_name='Condición IVA')
    aplicacion_iva = models.IntegerField(choices=APLICACION_IVA_CHOICES, default=3, verbose_name='Aplicación IVA')
    neto_gravado = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Neto Gravado')
    neto_no_gravado = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Neto No Gravado')
    neto_exento = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Neto Exento')
    iva_21 = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA 21%')
    iva_10_5 = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA 10.5%')
    iva_27 = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA 27%')
    iva_2_5 = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA 2.5%')
    iva_0 = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA 0%')
    impuesto_interno = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Impuesto Interno')
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Total')
    cae = models.CharField(max_length=14, blank=True, null=True, verbose_name='CAE')
    cae_vto = models.DateField(blank=True, null=True, verbose_name='Vencimiento CAE')
    sale = models.ForeignKey('Sale', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Venta Relacionada')
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Proveedor Relacionado')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')

    def __str__(self):
        return f"{self.get_tipo_registro_display()} - {self.fecha} - {self.get_tipo_comprobante_display()} {self.punto_venta:04d}-{self.numero_comprobante:08d}"

    class Meta:
        verbose_name = 'Registro Libro IVA'
        verbose_name_plural = 'Registros Libro IVA'
        ordering = ['-fecha', '-tipo_registro', 'numero_comprobante']
        indexes = [
            models.Index(fields=['company', 'tipo_registro', 'fecha']),
            models.Index(fields=['fecha']),
            models.Index(fields=['cae']),
        ]


class CuentaCorrienteCliente(models.Model):
    """Movimientos de cuenta corriente de clientes"""
    TIPO_MOVIMIENTO_CHOICES = (
        ('venta', 'Venta (Débito)'),
        ('pago', 'Pago (Crédito)'),
        ('nota_credito', 'Nota de Crédito (Crédito)'),
        ('nota_debito', 'Nota de Débito (Débito)'),
        ('ajuste', 'Ajuste'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa')
    client = models.ForeignKey('Client', on_delete=models.CASCADE, verbose_name='Cliente')
    tipo_movimiento = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES, verbose_name='Tipo de Movimiento')
    fecha = models.DateField(verbose_name='Fecha')
    descripcion = models.CharField(max_length=200, verbose_name='Descripción')
    debe = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Debe')
    haber = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Haber')
    saldo = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Saldo Acumulado')
    sale = models.ForeignKey('Sale', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Venta Relacionada')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')

    def __str__(self):
        return f"{self.client.names} - {self.fecha} - {self.get_tipo_movimiento_display()} - ${self.debe - self.haber}"

    class Meta:
        verbose_name = 'Movimiento Cuenta Corriente'
        verbose_name_plural = 'Movimientos Cuenta Corriente'
        ordering = ['-fecha', '-created_at']
        indexes = [
            models.Index(fields=['company', 'client', 'fecha']),
            models.Index(fields=['client', 'fecha']),
        ]


class AsientoContable(models.Model):
    """Asientos contables básicos para ventas"""
    TIPO_ASIENTO_CHOICES = (
        ('venta', 'Venta'),
        ('pago', 'Pago'),
        ('compra', 'Compra'),
        ('ajuste', 'Ajuste'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa')
    tipo_asiento = models.CharField(max_length=20, choices=TIPO_ASIENTO_CHOICES, verbose_name='Tipo de Asiento')
    fecha = models.DateField(verbose_name='Fecha')
    descripcion = models.CharField(max_length=200, verbose_name='Descripción')
    debe_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Total Debe')
    haber_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Total Haber')
    sale = models.ForeignKey('Sale', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Venta Relacionada')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')

    def __str__(self):
        return f"{self.get_tipo_asiento_display()} - {self.fecha} - ${self.debe_total}"

    class Meta:
        verbose_name = 'Asiento Contable'
        verbose_name_plural = 'Asientos Contables'
        ordering = ['-fecha', '-created_at']
        indexes = [
            models.Index(fields=['company', 'fecha']),
            models.Index(fields=['tipo_asiento', 'fecha']),
        ]


class FacturaProveedor(models.Model):
    """Facturas de proveedores para Libro IVA Digital"""
    TIPO_COMPROBANTE_CHOICES = (
        (1, 'Factura A'),
        (2, 'Nota de Crédito A'),
        (3, 'Nota de Débito A'),
        (4, 'Recibo A'),
        (6, 'Factura B'),
        (7, 'Nota de Crédito B'),
        (8, 'Nota de Débito B'),
        (9, 'Recibo B'),
        (11, 'Factura C'),
        (12, 'Nota de Crédito C'),
        (13, 'Nota de Débito C'),
        (15, 'Recibo C'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='Proveedor')
    fecha = models.DateField(verbose_name='Fecha de Factura')
    tipo_comprobante = models.IntegerField(choices=TIPO_COMPROBANTE_CHOICES, verbose_name='Tipo de Comprobante')
    punto_venta = models.IntegerField(verbose_name='Punto de Venta')
    numero_comprobante = models.BigIntegerField(verbose_name='Número de Comprobante')
    cuit_proveedor = models.CharField(max_length=20, verbose_name='CUIT Proveedor')
    condicion_iva = models.CharField(max_length=2, choices=CONDICION_IVA_CHOICES, verbose_name='Condición IVA')
    neto_gravado = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Neto Gravado')
    neto_no_gravado = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Neto No Gravado')
    neto_exento = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Neto Exento')
    iva_21 = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA 21%')
    iva_10_5 = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA 10.5%')
    iva_27 = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA 27%')
    iva_2_5 = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA 2.5%')
    iva_0 = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA 0%')
    impuesto_interno = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Impuesto Interno')
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Total')
    cae = models.CharField(max_length=14, blank=True, null=True, verbose_name='CAE')
    cae_vto = models.DateField(blank=True, null=True, verbose_name='Vencimiento CAE')
    remito_entrada = models.ForeignKey('RemitoEntrada', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Remito de Entrada Relacionado')
    observaciones = models.TextField(blank=True, null=True, verbose_name='Observaciones')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')

    def __str__(self):
        return f"{self.supplier.name} - {self.fecha} - {self.get_tipo_comprobante_display()} {self.punto_venta:04d}-{self.numero_comprobante:08d}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Crear registro en Libro IVA automáticamente
        self._crear_registro_libro_iva()

    def _crear_registro_libro_iva(self):
        """Crea automáticamente un registro en el Libro IVA para compras."""
        from .models import LibroIvaRegistro

        try:
            # Verificar si ya existe un registro para esta factura
            if LibroIvaRegistro.objects.filter(supplier=self.supplier, tipo_registro='compra', 
                                            punto_venta=self.punto_venta, 
                                            numero_comprobante=self.numero_comprobante).exists():
                return

            # Determinar aplicación IVA según condición del proveedor
            if self.condicion_iva == 'RI':
                aplicacion_iva = 3  # Gravado
            elif self.condicion_iva == 'M':
                aplicacion_iva = 2  # Exento
            else:
                aplicacion_iva = 3  # Gravado por defecto

            LibroIvaRegistro.objects.create(
                company=self.company,
                tipo_registro='compra',
                fecha=self.fecha,
                tipo_comprobante=self.tipo_comprobante,
                punto_venta=self.punto_venta,
                numero_comprobante=self.numero_comprobante,
                cuit_emisor=self.cuit_proveedor,
                cuit_receptor=self.company.cuit,
                razon_social=self.supplier.name,
                condicion_iva=self.condicion_iva,
                aplicacion_iva=aplicacion_iva,
                neto_gravado=self.neto_gravado,
                neto_no_gravado=self.neto_no_gravado,
                neto_exento=self.neto_exento,
                iva_21=self.iva_21,
                iva_10_5=self.iva_10_5,
                iva_27=self.iva_27,
                iva_2_5=self.iva_2_5,
                iva_0=self.iva_0,
                impuesto_interno=self.impuesto_interno,
                total=self.total,
                cae=self.cae,
                cae_vto=self.cae_vto,
                supplier=self.supplier
            )
        except Exception as e:
            print(f"Error creando registro Libro IVA para factura de proveedor: {e}")

    class Meta:
        verbose_name = 'Factura de Proveedor'
        verbose_name_plural = 'Facturas de Proveedores'
        ordering = ['-fecha', '-numero_comprobante']
        indexes = [
            models.Index(fields=['company', 'supplier', 'fecha']),
            models.Index(fields=['fecha']),
            models.Index(fields=['cae']),
        ]


class CatalogoConfig(models.Model):
    """Configuración de sincronización con SitioCatalogoMarcos por empresa"""
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    catalogo_url = models.URLField(max_length=255, verbose_name='URL del Catálogo')
    api_key = models.CharField(max_length=255, verbose_name='API Key del Catálogo')
    erp_username = models.CharField(max_length=100, blank=True, null=True, verbose_name='Usuario ERP', help_text='Usuario del ERP para asignar ventas')
    erp_password = models.CharField(max_length=255, blank=True, null=True, verbose_name='Contraseña ERP', help_text='Contraseña del usuario ERP')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Creado por', related_name='catalogo_configs')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    auto_sync = models.BooleanField(default=False, verbose_name='Sincronización automática')
    sync_interval_hours = models.IntegerField(default=24, verbose_name='Intervalo de sincronización (horas)')
    last_sync = models.DateTimeField(blank=True, null=True, verbose_name='Última sincronización')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')
    
    def __str__(self):
        return f"Catálogo Config - {self.company.name if self.company else 'Global'} ({self.catalogo_url})"
    
    class Meta:
        verbose_name = 'Configuración de Catálogo'
        verbose_name_plural = 'Configuraciones de Catálogo'
        ordering = ['-is_active', 'company__name']


class GlobalSyncStatus(models.Model):
    """Model to store global sync status that can be checked by background threads"""
    sync_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Estado de Sincronización Global"
        verbose_name_plural = "Estados de Sincronización Global"

    @classmethod
    def is_sync_enabled(cls):
        """Check if sync is globally enabled - always returns True for operators"""
        try:
            status = cls.objects.first()
            # Always return True if no record exists or if sync is enabled
            if not status or status.sync_enabled:
                return True
            # Only return False if explicitly disabled and record exists
            return False
        except Exception:
            return True

    def __str__(self):
        return f"Sync {'Enabled' if self.sync_enabled else 'Disabled'}"


class GlobalPosConfig(models.Model):
    """Configuraciones globales del POS"""
    allow_sales_without_afip = models.BooleanField(
        default=False,
        verbose_name='Permitir ventas sin configuración AFIP',
        help_text='Permite realizar ventas sin configuración fiscal AFIP (emite ticket X sin valor fiscal)'
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Configuración Global del POS"
        verbose_name_plural = "Configuraciones Globales del POS"

    @classmethod
    def allow_sales_without_afip(cls):
        """Check if sales without AFIP are allowed"""
        try:
            config = cls.objects.first()
            if not config:
                return False  # Default: require AFIP config
            return config.allow_sales_without_afip
        except Exception:
            return False

    def __str__(self):
        return f"Configuración POS - Ventas sin AFIP: {'Sí' if self.allow_sales_without_afip else 'No'}"
        return f"Sync {'Enabled' if self.sync_enabled else 'Disabled'}"


# Obtener el modelo de usuario activo (después de que todos los modelos estén definidos)
User = get_user_model()


class ActivityLog(models.Model):
    """Registro de actividades de usuarios para modo servidor"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100, verbose_name='Acción')
    description = models.TextField(blank=True, verbose_name='Descripción')
    model_name = models.CharField(max_length=50, blank=True, verbose_name='Modelo')
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='ID del Objeto')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='Dirección IP')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y Hora')
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Empresa')
    
    class Meta:
        verbose_name = 'Registro de Actividad'
        verbose_name_plural = 'Registros de Actividad'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['company', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    def get_action_display(self):
        """Retorna una descripción más amigable de la acción"""
        action_descriptions = {
            'CREATE': 'Creación',
            'UPDATE': 'Actualización', 
            'DELETE': 'Eliminación',
            'LOGIN': 'Inicio de Sesión',
            'LOGOUT': 'Cierre de Sesión',
            'EMPLOYEE_ACCOUNT': 'Cuenta Corriente Empleado',
        }
        return action_descriptions.get(self.action, self.action)


class EmployeeAccountSale(models.Model):
    """Ventas por cuenta corriente de empleados - descuentan stock pero no suman al total de ventas"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Empleado')
    date_joined = models.DateTimeField(default=timezone.now, verbose_name='Fecha y hora')
    local_timezone = models.CharField(max_length=50, blank=True, null=True, verbose_name='Zona horaria local')
    subtotal = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='Subtotal')
    iva = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='IVA')
    total = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='Total')
    notes = models.TextField(blank=True, null=True, verbose_name='Notas')
    is_paid = models.BooleanField(default=False, verbose_name='Pagado')
    paid_date = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de pago')
    related_sale_id = models.IntegerField(null=True, blank=True, verbose_name='ID de venta relacionada')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    local_uuid = models.CharField(max_length=64, blank=True, null=True, db_index=True, verbose_name='UUID local', help_text='UUID para sincronización (índice para búsquedas rápidas)')
    payment_details = models.JSONField(default=dict, blank=True, verbose_name='Detalles de pago combinado')

    def __str__(self):
        return f"Cta. Cte. {self.employee.get_full_name()} - {self.date_joined.strftime('%d/%m/%Y')}"

    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        
        # Generar local_uuid para nuevos registros
        if not self.pk and not self.local_uuid:
            import uuid
            self.local_uuid = f"emp_acc_{uuid.uuid4().hex}"
        
        # Capturar la zona horaria local solo para nuevos registros
        if not self.pk and not self.local_timezone:
            try:
                import pytz
                from django.conf import settings
                # Obtener la zona horaria local del sistema
                local_tz = pytz.timezone(getattr(settings, 'TIME_ZONE', 'America/Argentina/Buenos_Aires'))
                # Guardar la zona horaria actual
                self.local_timezone = str(timezone.now().astimezone(local_tz).tzinfo)
            except Exception:
                # Si hay error, usar zona horaria por defecto
                self.local_timezone = 'America/Argentina/Buenos_Aires'
        
        super().save(*args, **kwargs)

    def toJSON(self):
        item = model_to_dict(self, exclude=['date_creation', 'date_updated', 'user_creation', 'user_updated'])
        item['employee'] = self.employee.get_full_name() or self.employee.username
        # Formatear la fecha sin conversión de zona horaria
        try:
            local_dt = timezone.localtime(self.date_joined)
            item['date_joined'] = local_dt.strftime('%Y-%m-%d %H:%M:%S')
            item['date_joined_display'] = local_dt.strftime('%d-%m-%Y %H:%M')
        except Exception:
            item['date_joined'] = self.date_joined.strftime('%Y-%m-%d %H:%M:%S') if self.date_joined else ''
            item['date_joined_display'] = self.date_joined.strftime('%d-%m-%Y %H:%M') if self.date_joined else ''
        
        if self.paid_date:
            try:
                local_paid_dt = timezone.localtime(self.paid_date)
                item['paid_date'] = local_paid_dt.strftime('%Y-%m-%d %H:%M:%S')
                item['paid_date_display'] = local_paid_dt.strftime('%d-%m-%Y %H:%M')
            except Exception:
                item['paid_date'] = self.paid_date.strftime('%Y-%m-%d %H:%M:%S') if self.paid_date else ''
                item['paid_date_display'] = self.paid_date.strftime('%d-%m-%Y %H:%M') if self.paid_date else ''
        else:
            item['paid_date'] = ''
            item['paid_date_display'] = ''
        
        # Formatear valores monetarios
        item['subtotal'] = format(self.subtotal, '.2f')
        item['iva'] = format(self.iva, '.2f')
        item['total'] = format(self.total, '.2f')
        item['local_uuid'] = self.local_uuid or ''
        item['synced_to_server'] = self.synced_to_server
        item['det'] = [i.toJSON() for i in self.detemployeeaccount_set.all()]
        return item

    class Meta:
        verbose_name = 'Venta Cuenta Corriente Empleado'
        verbose_name_plural = 'Ventas Cuenta Corriente Empleados'
        ordering = ['-date_joined']
        permissions = [
            ("manage_employee_accounts", "Puede gestionar cuentas corrientes de empleados"),
        ]


class DetEmployeeAccount(models.Model):
    """Detalle de venta por cuenta corriente de empleado"""
    employee_account = models.ForeignKey(EmployeeAccountSale, on_delete=models.CASCADE)
    prod = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    cant = models.DecimalField(default=0, max_digits=9, decimal_places=3)
    subtotal = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    iva_amount = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='Monto IVA')

    def __str__(self):
        return f"{self.prod.name} - {self.cant}"

    def calculate_iva_amount(self):
        """Calcular el monto de IVA para este detalle"""
        if self.prod and self.prod.iva_rate:
            # Calcular IVA basado en el subtotal
            iva_rate = Decimal(str(self.prod.iva_rate))
            # Normalizar rate: si es mayor que 1, tratarlo como porcentaje (21 -> 0.21)
            if iva_rate > Decimal('1.0'):
                iva_rate = iva_rate / Decimal('100.0')
            # Asegurar que subtotal es Decimal para consistencia
            subtotal_decimal = Decimal(str(self.subtotal))
            return (subtotal_decimal * iva_rate).quantize(Decimal('0.01'))
        return Decimal('0.00')
    
    def save(self, *args, **kwargs):        # Calcular el monto de IVA automáticamente
        self.iva_amount = self.calculate_iva_amount()
        super().save(*args, **kwargs)

    def toJSON(self):
        item = model_to_dict(self, exclude=['employee_account'])
        item['prod'] = self.prod.toJSON()
        item['price'] = format(self.price, '.2f') if self.price is not None else '0.00'
        item['subtotal'] = format(self.subtotal, '.2f') if self.subtotal is not None else '0.00'
        item['iva_amount'] = format(self.iva_amount, '.2f') if self.iva_amount is not None else '0.00'
        # Agregar información del IVA del producto
        item['prod']['iva_rate'] = float(self.prod.iva_rate) if self.prod and self.prod.iva_rate else 0.0
        item['prod']['pvp_with_iva'] = format(self.prod.pvp_final, '.2f') if self.prod and self.prod.pvp_final else '0.00'
        return item

    class Meta:
        verbose_name = 'Detalle Cuenta Corriente Empleado'
        verbose_name_plural = 'Detalles Cuenta Corriente Empleados'
        ordering = ['id']


class RemitoEntrada(models.Model):
    """Remito de entrada de proveedores para cargar stock"""
    ESTADO_CHOICES = [
        ('pending', 'Pendiente'),
        ('processed', 'Procesado'),
        ('cancelled', 'Anulado'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='Proveedor')
    numero = models.CharField(max_length=50, verbose_name='Número de Remito')
    fecha = models.DateField(verbose_name='Fecha')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pending', verbose_name='Estado')
    observaciones = models.TextField(blank=True, null=True, verbose_name='Observaciones')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Creado por')
    
    def __str__(self):
        return f"Remito {self.numero} - {self.supplier.name}"
    
    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'Remito de Entrada'
        verbose_name_plural = 'Remitos de Entrada'
        ordering = ['-fecha', '-numero']
        permissions = [
            ("manage_remitos_entrada", "Puede gestionar remitos de entrada"),
        ]


class DetalleRemitoEntrada(models.Model):
    """Detalle de remito de entrada"""
    remito = models.ForeignKey(RemitoEntrada, on_delete=models.CASCADE, verbose_name='Remito')
    prod = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Producto')
    cantidad = models.DecimalField(max_digits=9, decimal_places=3, verbose_name='Cantidad')
    precio_unitario = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Precio Unitario')
    subtotal = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Subtotal')
    
    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def toJSON(self):
        item = model_to_dict(self, exclude=['remito'])
        item['prod'] = self.prod.toJSON() if self.prod else {'id': None, 'name': 'Producto eliminado'}
        item['cantidad'] = format(self.cantidad, '.3f') if self.cantidad is not None else '0.000'
        item['precio_unitario'] = format(self.precio_unitario, '.2f') if self.precio_unitario is not None else '0.00'
        item['subtotal'] = format(self.subtotal, '.2f') if self.subtotal is not None else '0.00'
        return item
    
    class Meta:
        verbose_name = 'Detalle Remito de Entrada'
        verbose_name_plural = 'Detalles Remitos de Entrada'
        ordering = ['id']


class Remito(models.Model):
    """Remito unificado para entrada y salida de productos"""
    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
    ]
    ESTADO_CHOICES = [
        ('pending', 'Pendiente'),
        ('processed', 'Procesado'),
        ('cancelled', 'Anulado'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name='Tipo')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='Proveedor', null=True, blank=True)
    numero = models.CharField(max_length=50, verbose_name='Número de Remito')
    fecha = models.DateField(verbose_name='Fecha')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pending', verbose_name='Estado')
    observaciones = models.TextField(blank=True, null=True, verbose_name='Observaciones')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Creado por')
    
    def __str__(self):
        tipo_str = self.get_tipo_display()
        if self.supplier:
            return f"Remito {tipo_str} {self.numero} - {self.supplier.name}"
        return f"Remito {tipo_str} {self.numero}"
    
    def save(self, *args, **kwargs):
        if not self.company_id:
            user = get_current_user()
            if user and not user.is_anonymous:
                self.company_id = getattr(user, 'company_id', None)
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'Remito'
        verbose_name_plural = 'Remitos'
        ordering = ['-fecha', '-numero']
        permissions = [
            ("manage_remitos", "Puede gestionar remitos"),
        ]


class DetalleRemito(models.Model):
    """Detalle de remito (entrada o salida)"""
    remito = models.ForeignKey(Remito, on_delete=models.CASCADE, verbose_name='Remito')
    prod = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Producto')
    cantidad = models.DecimalField(max_digits=9, decimal_places=3, verbose_name='Cantidad')
    precio_unitario = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Precio Unitario')
    subtotal = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Subtotal')
    
    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def toJSON(self):
        item = model_to_dict(self, exclude=['remito'])
        item['prod'] = self.prod.toJSON() if self.prod else {'id': None, 'name': 'Producto eliminado'}
        item['cantidad'] = format(self.cantidad, '.3f') if self.cantidad is not None else '0.000'
        item['precio_unitario'] = format(self.precio_unitario, '.2f') if self.precio_unitario is not None else '0.00'
        item['subtotal'] = format(self.subtotal, '.2f') if self.subtotal is not None else '0.00'
        return item

    class Meta:
        verbose_name = 'Detalle de Remito'
        verbose_name_plural = 'Detalles de Remitos'
        ordering = ['id']