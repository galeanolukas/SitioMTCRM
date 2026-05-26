# StockControlMixin - Mixin para validación de control de stock
class StockControlMixin:
    """Mixin para validar y asegurar control de stock consistente"""
    
    @staticmethod
    def validate_track_stock(product):
        """Valida y retorna un valor booleano para track_stock"""
        if product.track_stock is None:
            return True
        return bool(product.track_stock)
    
    @staticmethod
    def should_update_stock(product, quantity):
        """Determina si se debe actualizar el stock de un producto"""
        track_stock = StockControlMixin.validate_track_stock(product)
        return track_stock and quantity != 0
    
    @staticmethod
    def check_stock_availability(product, required_quantity):
        """Verifica disponibilidad de stock considerando control de stock"""
        track_stock = StockControlMixin.validate_track_stock(product)
        if not track_stock:
            return True  # Si no controla stock, siempre está disponible
        
        return product.stock >= required_quantity
    
    @staticmethod
    def update_product_stock(product, quantity_change):
        """Actualiza stock de producto si corresponde"""
        if StockControlMixin.should_update_stock(product, quantity_change):
            from django.db.models import F
            from django.utils import timezone
            Product.objects.filter(pk=product.pk).update(
                stock=F('stock') + quantity_change,
                stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                synced_to_server=False
            )
            return True
        return False
