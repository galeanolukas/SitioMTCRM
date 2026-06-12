from django.db import models
from django.utils import timezone
from datetime import datetime
from django.contrib.auth import get_user_model

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
        item = model_to_dict(self)  #(self, exclude=['user_creation', 'user_updated'])
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
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    name = models.CharField(max_length=150, verbose_name='Nombre', unique=True)
    code = models.CharField(max_length=64, verbose_name='Código', null=True, blank=True)
    codigo_proveedor = models.CharField(max_length=64, verbose_name='Código Proveedor', null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True, verbose_name='Descripción')
    qr_token = models.CharField(max_length=32, verbose_name='Token público QR', unique=True, null=True, blank=True)
    cat = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='Categoría')
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Proveedor')
    image = models.ImageField(upload_to='product/%Y/%m/%d', null=True, blank=True, verbose_name='Imagen')
    cost_price = models.DecimalField(default=0.00, max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Precio de costo (sin IVA)')
    pvp = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='Precio neto (sin IVA)')
    iva_rate = models.DecimalField(default=0.21, max_digits=5, decimal_places=2, verbose_name='IVA (%)')
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
        item = model_to_dict(self)
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
    surnames = models.CharField(max_length=150, verbose_name='Apellidos')
    dni = models.CharField(max_length=10, unique=True, verbose_name='Dni')
    cuit_cuil = models.CharField(max_length=13, null=True, blank=True, verbose_name='CUIT/CUIL')
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
        item['condicion_iva'] = {'id': self.condicion_iva, 'name': self.get_condicion_iva_display()}
        item['tipo_cliente'] = {'id': self.tipo_cliente, 'name': self.get_tipo_cliente_display()}
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
    local_timezone = models.CharField(max_length=50, blank=True, null=True, verbose_name='Zona horaria local')
    subtotal = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    iva = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    total = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    payment_method = models.CharField(max_length=12, choices=payment_method_choices, default='cash', verbose_name='Forma de pago')
    payment_details = models.JSONField(default=dict, blank=True, verbose_name='Detalles de pago combinado')
    # Facturación
    invoice_number = models.CharField(max_length=20, null=True, blank=True, unique=True)
    invoice_pos = models.CharField(max_length=5, default='0001')
    invoice_type = models.CharField(max_length=1, default='B')  # A/B/C
    is_invoiced = models.BooleanField(default=False)
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    local_sale_id = models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de venta local', help_text='ID de la venta en la base de datos local para evitar duplicados')
    local_uuid = models.CharField(max_length=64, blank=True, null=True, db_index=True, verbose_name='UUID local', help_text='UUID para sincronización (índice para búsquedas rápidas)')
    source = models.CharField(max_length=20, blank=True, null=True, verbose_name='Origen', help_text='Origen de la venta (local_pos, web, etc.)')
    synced_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de sincronización')

    def __str__(self):
        return self.cli.names

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
        item = model_to_dict(self)
        item['cli'] = (self.cli.names if self.cli_id else 'Anónimo')
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


class DetSale(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE)
    prod = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    cant = models.DecimalField(default=0, max_digits=9, decimal_places=3)
    subtotal = models.DecimalField(default=0.00, max_digits=9, decimal_places=2)
    iva_amount = models.DecimalField(default=0.00, max_digits=9, decimal_places=2, verbose_name='Monto IVA')

    def __str__(self):
        return self.prod.name
    
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

    def toJSON(self):
        item = model_to_dict(self, exclude=['sale'])
        item['prod'] = self.prod.toJSON()
        item['price'] = format(self.price, '.2f') if self.price is not None else '0.00'
        item['subtotal'] = format(self.subtotal, '.2f') if self.subtotal is not None else '0.00'
        item['iva_amount'] = format(self.iva_amount, '.2f') if self.iva_amount is not None else '0.00'
        # Agregar información del IVA del producto
        item['prod']['iva_rate'] = float(self.prod.iva_rate) if self.prod and self.prod.iva_rate else 0.0
        item['prod']['pvp_with_iva'] = format(self.prod.pvp_final, '.2f') if self.prod and self.prod.pvp_final else '0.00'
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

class Expense(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Proveedor')
    date = models.DateField(default=datetime.now, verbose_name='Fecha')
    time = models.TimeField(default=datetime.now, verbose_name='Hora', blank=True, null=True)
    description = models.CharField(max_length=255, verbose_name='Descripción', blank=True, null=True)
    recurring_reason = models.CharField(max_length=30, choices=EXPENSE_RECURRING_REASONS, blank=True, null=True, verbose_name='Motivo recurrente')
    amount = models.DecimalField(default=0.00, max_digits=12, decimal_places=2, verbose_name='Importe')
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
        item = model_to_dict(self)
        item['supplier'] = (self.supplier.name if self.supplier_id else None)
        item['supplier_id'] = self.supplier_id
        item['date'] = self.date.strftime('%Y-%m-%d') if self.date else None
        item['time'] = self.time.strftime('%H:%M') if self.time else None
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
    
    def save(self, *args, **kwargs):        # Calcular subtotal automáticamente
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


class AfipConfig(models.Model):
    """Configuración de AFIP SDK por empresa"""
    ENVIRONMENT_CHOICES = (
        ('dev', 'Desarrollo'),
        ('prod', 'Producción'),
    )
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    cuit = models.CharField(max_length=20, verbose_name='CUIT')
    access_token = models.CharField(max_length=255, verbose_name='Access Token AFIP SDK')
    cert = models.TextField(blank=True, null=True, verbose_name='Certificado (solo producción)')
    key = models.TextField(blank=True, null=True, verbose_name='Key (solo producción)')
    environment = models.CharField(max_length=10, choices=ENVIRONMENT_CHOICES, default='dev', verbose_name='Ambiente')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')
    
    def __str__(self):
        return f"AFIP Config - {self.company.name if self.company else 'Global'} ({self.cuit})"
    
    class Meta:
        verbose_name = 'Configuración AFIP'
        verbose_name_plural = 'Configuraciones AFIP'
        ordering = ['-is_active', 'company__name']


class CatalogoConfig(models.Model):
    """Configuración de sincronización con SitioCatalogoMarcos por empresa"""
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa', null=True, blank=True)
    catalogo_url = models.URLField(max_length=255, verbose_name='URL del Catálogo')
    api_key = models.CharField(max_length=255, verbose_name='API Key del Catálogo')
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
            return True  # Default to True on error
    
    @classmethod
    def ensure_sync_enabled(cls):
        """Ensure sync is enabled - called during login for operators"""
        try:
            status, created = cls.objects.get_or_create(
                pk=1,
                defaults={'sync_enabled': True, 'updated_by': 'system'}
            )
            if not created and not status.sync_enabled:
                # Auto-enable sync for operators
                status.sync_enabled = True
                status.updated_by = 'system_auto_enable'
                status.save()
                print("Sincronización automática activada para operadores")
            return True
        except Exception:
            return True
    
    @classmethod
    def set_sync_status(cls, enabled, updated_by=None):
        """Set global sync status"""
        status, created = cls.objects.get_or_create(
            pk=1,  # Use a single record
            defaults={'sync_enabled': enabled, 'updated_by': updated_by or 'system'}
        )
        if not created:
            status.sync_enabled = enabled
            status.updated_by = updated_by or 'system'
            status.save()
    
    def __str__(self):
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
        item = model_to_dict(self)
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
    prod = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='Producto')
    cantidad = models.DecimalField(max_digits=9, decimal_places=3, verbose_name='Cantidad')
    precio_unitario = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Precio Unitario')
    subtotal = models.DecimalField(max_digits=9, decimal_places=2, verbose_name='Subtotal')
    
    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)
    
    def toJSON(self):
        item = model_to_dict(self, exclude=['remito'])
        item['prod'] = self.prod.toJSON()
        item['cantidad'] = format(self.cantidad, '.3f') if self.cantidad is not None else '0.000'
        item['precio_unitario'] = format(self.precio_unitario, '.2f') if self.precio_unitario is not None else '0.00'
        item['subtotal'] = format(self.subtotal, '.2f') if self.subtotal is not None else '0.00'
        return item
    
    class Meta:
        verbose_name = 'Detalle Remito de Entrada'
        verbose_name_plural = 'Detalles Remitos de Entrada'
        ordering = ['id']