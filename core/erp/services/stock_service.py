"""Servicio central de stock: toda mutación de Product.stock debe pasar por acá
para quedar registrada en StockMovement (auditoría).

- adjust_stock(): aplica un delta con signo y registra el movimiento.
- log_stock_movement(): solo registra el movimiento cuando el caller ya
  modificó y guardó prod.stock por otros motivos (ej: remitos que además
  recalculan precios en el mismo save()).
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone


def _clean_user(user):
    return user if getattr(user, 'is_authenticated', False) else None


def adjust_stock(product_id, delta, *, movement_type, user=None, ref='',
                 notes='', sale=None, remito=None, employee_account=None,
                 using='default'):
    """Aplica `delta` (con signo) a Product.stock y crea el StockMovement.

    Devuelve el stock resultante. Seguro dentro de una transaction.atomic()
    existente (usa savepoint) o standalone.
    """
    from core.erp.models import Product, StockMovement

    delta = Decimal(str(delta))
    with transaction.atomic(using=using):
        prod = Product.objects.using(using).select_for_update().only(
            'stock', 'company_id').get(pk=product_id)
        before = Decimal(str(prod.stock or 0))
        after = (before + delta).quantize(Decimal('0.01'))
        Product.objects.using(using).filter(pk=prod.pk).update(
            stock=after,
            stock_modified_locally=timezone.now(),
            synced_to_server=False,
        )
        StockMovement.objects.using(using).create(
            company_id=prod.company_id,
            product_id=prod.pk,
            movement_type=movement_type,
            quantity=delta,
            stock_before=before,
            stock_after=after,
            sale=sale,
            remito=remito,
            employee_account=employee_account,
            user=_clean_user(user),
            ref=(ref or '')[:120],
            notes=(notes or '')[:255],
        )
    return after


def log_stock_movement(prod, before, *, movement_type, user=None, ref='',
                       notes='', sale=None, remito=None,
                       employee_account=None, using='default'):
    """Registra un StockMovement cuando el caller ya modificó prod.stock.

    `before` es el stock previo a la mutación; el delta se calcula como
    stock actual - before.
    """
    from core.erp.models import StockMovement

    before = Decimal(str(before or 0))
    after = Decimal(str(prod.stock or 0))
    StockMovement.objects.using(using).create(
        company_id=prod.company_id,
        product_id=prod.pk,
        movement_type=movement_type,
        quantity=after - before,
        stock_before=before,
        stock_after=after,
        sale=sale,
        remito=remito,
        employee_account=employee_account,
        user=_clean_user(user),
        ref=(ref or '')[:120],
        notes=(notes or '')[:255],
    )
    return after
