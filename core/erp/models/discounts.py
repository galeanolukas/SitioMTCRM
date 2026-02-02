from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal

from core.models import BaseModel

User = get_user_model()


class DiscountRule(BaseModel):
    """Reglas de descuento por cantidad"""
    
    DISCOUNT_TYPES = [
        ('percentage', 'Porcentaje'),
        ('fixed', 'Monto Fijo'),
        ('special_price', 'Precio Especial'),
        ('bxgy', 'Lleva X Paga Y'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='Nombre de la oferta')
    description = models.TextField(blank=True, null=True, verbose_name='Descripción')
    
    # Aplicación
    product = models.ForeignKey('erp.Product', on_delete=models.CASCADE, null=True, blank=True, 
                              verbose_name='Producto específico', related_name='discount_rules')
    category = models.ForeignKey('erp.Category', on_delete=models.CASCADE, null=True, blank=True,
                               verbose_name='Categoría', related_name='discount_rules')
    
    # Condiciones
    min_quantity = models.PositiveIntegerField(default=1, verbose_name='Cantidad mínima')
    max_quantity = models.PositiveIntegerField(null=True, blank=True, verbose_name='Cantidad máxima')
    
    # Descuento
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, 
                                   default='percentage', verbose_name='Tipo de descuento')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, 
                                        verbose_name='Valor del descuento')
    
    # Lleva X Paga Y específico
    buy_quantity = models.PositiveIntegerField(null=True, blank=True, 
                                               verbose_name='Lleva cantidad (BXGY)')
    pay_quantity = models.PositiveIntegerField(null=True, blank=True, 
                                              verbose_name='Paga cantidad (BXGY)')
    
    # Configuración
    priority = models.PositiveIntegerField(default=0, verbose_name='Prioridad')
    is_active = models.BooleanField(default=True, verbose_name='Activa')
    is_cumulative = models.BooleanField(default=False, verbose_name='Acumulable')
    
    # Vigencia
    start_date = models.DateTimeField(default=timezone.now, verbose_name='Fecha de inicio')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de fin')
    
    # Límites
    max_uses = models.PositiveIntegerField(null=True, blank=True, verbose_name='Uso máximo')
    used_count = models.PositiveIntegerField(default=0, verbose_name='Veces usada')
    
    class Meta:
        verbose_name = 'Regla de Descuento'
        verbose_name_plural = 'Reglas de Descuento'
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_discount_type_display()})"
    
    def is_valid(self):
        """Verificar si la regla es válida actualmente"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        if self.max_uses and self.used_count >= self.max_uses:
            return False
        
        return True
    
    def applies_to_product(self, product):
        """Verificar si la regla aplica a un producto"""
        if self.product and self.product != product:
            return False
        
        if self.category and product.cat != self.category:
            return False
        
        return True
    
    def calculate_discount(self, quantity, unit_price):
        """Calcular monto de descuento"""
        if not self.is_valid() or quantity < self.min_quantity:
            return Decimal('0.00')
        
        if self.max_quantity and quantity > self.max_quantity:
            quantity = self.max_quantity
        
        if self.discount_type == 'percentage':
            return (unit_price * quantity) * (self.discount_value / 100)
        
        elif self.discount_type == 'fixed':
            return self.discount_value * quantity
        
        elif self.discount_type == 'special_price':
            normal_total = unit_price * quantity
            special_total = self.discount_value * quantity
            return max(Decimal('0.00'), normal_total - special_total)
        
        elif self.discount_type == 'bxgy' and self.buy_quantity and self.pay_quantity:
            if quantity >= self.buy_quantity:
                free_units = (quantity // self.buy_quantity) * (self.buy_quantity - self.pay_quantity)
                return unit_price * free_units
        
        return Decimal('0.00')


class SaleDiscount(BaseModel):
    """Descuentos aplicados en ventas"""
    
    sale = models.ForeignKey('erp.Sale', on_delete=models.CASCADE, related_name='discounts')
    discount_rule = models.ForeignKey(DiscountRule, on_delete=models.CASCADE, related_name='applications')
    product = models.ForeignKey('erp.Product', on_delete=models.CASCADE, related_name='sale_discounts')
    
    quantity = models.PositiveIntegerField(verbose_name='Cantidad')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio unitario')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto descontado')
    
    class Meta:
        verbose_name = 'Descuento Aplicado'
        verbose_name_plural = 'Descuentos Aplicados'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.sale.id} - {self.product.name} - ${self.discount_amount}"
