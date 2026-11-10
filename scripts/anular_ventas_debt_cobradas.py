#!/usr/bin/env python
"""
Anula ventas "a deber" (payment_method='debt') cuyo fiado ya fue cobrado.

Contexto (informe Nro 4): cuando una cuenta corriente nacida como venta 'debt'
se cobraba, el sistema creaba UNA SEGUNDA venta de cobro y dejaba la 'debt'
original confirmada -> el mismo fiado se contaba dos veces en los reportes
(~$1.8M inflado en Acro Activo).

Este script detecta ventas 'debt' que ya tienen su cuenta corriente PAGADA
(matcheada por empresa + fecha + total) y las ANULA (status='cancelled').
NO borra las ventas ni toca el stock: la mercaderia ya fue entregada al fiar
y el cobro ya existe como venta aparte. Borrarlas devolveria stock fantasma.

Uso:
    DJENV/bin/python scripts/anular_ventas_debt_cobradas.py            # dry-run (solo lista)
    DJENV/bin/python scripts/anular_ventas_debt_cobradas.py --apply    # aplica los cambios
    DJENV/bin/python scripts/anular_ventas_debt_cobradas.py --apply --company 10
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.erp.models import Sale, EmployeeAccountSale

APPLY = '--apply' in sys.argv
COMPANY_ID = None
if '--company' in sys.argv:
    COMPANY_ID = int(sys.argv[sys.argv.index('--company') + 1])

debt_qs = Sale.objects.using('remote').filter(payment_method='debt', status='confirmed')
cc_qs = EmployeeAccountSale.objects.using('remote').filter(is_paid=True, is_cancelled=False)
if COMPANY_ID:
    debt_qs = debt_qs.filter(company_id=COMPANY_ID)
    cc_qs = cc_qs.filter(company_id=COMPANY_ID)

# IDs de ventas vinculadas a CUALQUIER cuenta corriente:
# - de CC pagada  -> es la venta de cobro (no tocar)
# - de CC impaga  -> es la venta 'debt' del fiado vigente (deuda real, no tocar)
linked_qs = EmployeeAccountSale.objects.using('remote').filter(related_sale_id__isnull=False)
if COMPANY_ID:
    linked_qs = linked_qs.filter(company_id=COMPANY_ID)
linked_sale_ids = set(linked_qs.values_list('related_sale_id', flat=True))

print(f"{'MODO':<8} {'VENTA':<7} {'FECHA':<18} {'TOTAL':>12}  CUENTA PAGADA")
print('-' * 70)

cancelled = 0
total_amount = 0.0
for sale in debt_qs.order_by('date_joined'):
    if sale.id in linked_sale_ids:
        continue  # Es el registro de cobro de una CC, no una 'debt' original
    # Buscar una cuenta corriente pagada del mismo dia y monto -> la 'debt' ya se cobro
    match = cc_qs.filter(
        company_id=sale.company_id,
        total=sale.total,
        date_joined__date=sale.date_joined.date(),
    ).first()
    if not match:
        print(f"{'SIN CC':<8} {sale.id:<7} {sale.date_joined:%d/%m/%Y %H:%M}  ${sale.total:>10,.0f}  (revisar a mano)")
        continue
    print(f"{'ANULAR':<8} {sale.id:<7} {sale.date_joined:%d/%m/%Y %H:%M}  ${sale.total:>10,.0f}  cc {match.id} (cobro: venta {match.related_sale_id})")
    total_amount += float(sale.total)
    if APPLY:
        # Anular en el servidor (queda el registro con status cancelled, sin tocar stock)
        Sale.objects.using('remote').filter(id=sale.id).update(status='cancelled')
        # Anular tambien la copia local si existe (mismo local_uuid)
        if sale.local_uuid:
            Sale.objects.filter(local_uuid=sale.local_uuid).update(status='cancelled')
        cancelled += 1

print('-' * 70)
print(f"Total a anular: ${total_amount:,.0f}")
if APPLY:
    print(f"Anuladas: {cancelled} ventas (status='cancelled', stock intacto)")
else:
    print("Dry-run: nada modificado. Correr con --apply para aplicar.")
