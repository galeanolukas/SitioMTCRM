from decimal import Decimal
from django.utils import timezone
from core.erp.models.discounts import DiscountRule, SaleDiscount


class DiscountService:
    """Servicio para calcular y aplicar descuentos"""
    
    @staticmethod
    def get_applicable_rules(product, quantity):
        """Obtener reglas aplicables a un producto y cantidad"""
        rules = DiscountRule.objects.filter(
            is_active=True,
            min_quantity__lte=quantity
        ).filter(
            models.Q(product=product) | 
            models.Q(category=product.cat) |
            models.Q(product__isnull=True, category__isnull=True)
        ).filter(
            models.Q(start_date__lte=timezone.now()) |
            models.Q(start_date__isnull=True)
        ).filter(
            models.Q(end_date__gte=timezone.now()) |
            models.Q(end_date__isnull=True)
        ).order_by('-priority', '-created_at')
        
        applicable_rules = []
        for rule in rules:
            if rule.applies_to_product(product):
                if not rule.max_quantity or quantity <= rule.max_quantity:
                    if not rule.max_uses or rule.used_count < rule.max_uses:
                        applicable_rules.append(rule)
        
        return applicable_rules
    
    @staticmethod
    def calculate_best_discount(product, quantity, unit_price):
        """Calcular el mejor descuento para un producto"""
        rules = DiscountService.get_applicable_rules(product, quantity)
        
        if not rules:
            return Decimal('0.00'), None
        
        best_discount = Decimal('0.00')
        best_rule = None
        
        for rule in rules:
            discount = rule.calculate_discount(quantity, unit_price)
            if discount > best_discount:
                best_discount = discount
                best_rule = rule
        
        return best_discount, best_rule
    
    @staticmethod
    def calculate_cart_discounts(cart_items):
        """Calcular descuentos para todo el carrito"""
        discounts = []
        total_discount = Decimal('0.00')
        
        for item in cart_items:
            product = item['product']
            quantity = item['quantity']
            unit_price = Decimal(str(item.get('unit_price', product.pvp)))
            
            discount_amount, rule = DiscountService.calculate_best_discount(
                product, quantity, unit_price
            )
            
            if discount_amount > 0 and rule:
                discounts.append({
                    'product': product,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'rule': rule,
                    'discount_amount': discount_amount
                })
                total_discount += discount_amount
        
        return discounts, total_discount
    
    @staticmethod
    def apply_discounts_to_sale(sale, cart_items):
        """Aplicar descuentos a una venta"""
        discounts, total_discount = DiscountService.calculate_cart_discounts(cart_items)
        
        # Crear registros de descuentos
        for discount_info in discounts:
            SaleDiscount.objects.create(
                sale=sale,
                discount_rule=discount_info['rule'],
                product=discount_info['product'],
                quantity=discount_info['quantity'],
                unit_price=discount_info['unit_price'],
                discount_amount=discount_info['discount_amount']
            )
            
            # Incrementar contador de uso
            rule = discount_info['rule']
            rule.used_count += 1
            rule.save()
        
        return total_discount
    
    @staticmethod
    def get_product_discount_info(product):
        """Obtener información de descuentos para mostrar en producto"""
        rules = DiscountRule.objects.filter(
            is_active=True
        ).filter(
            models.Q(product=product) | 
            models.Q(category=product.cat) |
            models.Q(product__isnull=True, category__isnull=True)
        ).filter(
            models.Q(start_date__lte=timezone.now()) |
            models.Q(start_date__isnull=True)
        ).filter(
            models.Q(end_date__gte=timezone.now()) |
            models.Q(end_date__isnull=True)
        ).order_by('-priority')
        
        applicable_rules = []
        for rule in rules:
            if rule.applies_to_product(product):
                applicable_rules.append(rule)
        
        return {
            'has_discount': len(applicable_rules) > 0,
            'rules': applicable_rules,
            'best_rule': applicable_rules[0] if applicable_rules else None
        }
