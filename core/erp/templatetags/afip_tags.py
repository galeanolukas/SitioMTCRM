from django import template

register = template.Library()


@register.simple_tag
def get_afip_punto_venta(sale):
    """
    Obtiene el punto de venta AFIP para una venta.
    Primero intenta obtener el punto de venta activo de la empresa,
    si no existe, usa el invoice_pos de la venta.
    """
    if sale.company:
        from core.erp.models import AfipPuntoVenta
        punto_venta = AfipPuntoVenta.objects.filter(
            company=sale.company,
            is_active=True
        ).first()
        if punto_venta:
            return f"{punto_venta.numero:04d}"
    # Fallback a invoice_pos
    return sale.invoice_pos or "0001"
