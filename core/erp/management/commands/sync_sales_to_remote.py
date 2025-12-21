from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.erp.models import Sale, DetSale, Company, Product


class Command(BaseCommand):
    help = "Sincroniza ventas y sus detalles desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de ventas hacia servidor remoto..."))

        # Ventas locales que aún no se han sincronizado
        pending_sales = Sale.objects.using('default').filter(synced_to_server=False).order_by('id')
        total = pending_sales.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay ventas pendientes de sincronizar."))
            return

        synced = 0
        errors = 0

        for sale in pending_sales:
            try:
                # Resolver empresa remota a partir de la empresa local de la venta.
                remote_company = None
                if sale.company_id:
                    local_company = Company.objects.using('default').filter(pk=sale.company_id).first()
                    if local_company:
                        # 1) Intentar mapear por CUIT
                        if local_company.cuit:
                            remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
                        # 2) Si no hay CUIT o no se encontró, intentar por nombre exacto
                        if not remote_company:
                            remote_company = Company.objects.using('remote').filter(name=local_company.name).first()

                # Si la venta tiene empresa local pero no existe equivalente remota,
                # no la sincronizamos para evitar error de FK.
                if sale.company_id and not remote_company:
                    errors += 1
                    self.stderr.write(
                        f"Error sincronizando venta {sale.id}: empresa local {sale.company_id} "
                        f"no tiene equivalente en servidor remoto (por CUIT/nombre)."
                    )
                    continue

                with transaction.atomic(using='remote'):
                    # Verificar si ya existe venta con misma fecha y monto para evitar duplicados
                    existing_sale = Sale.objects.using('remote').filter(
                        date_joined=sale.date_joined,
                        total=sale.total,
                        cli_id=sale.cli_id
                    ).first()
                    
                    if existing_sale:
                        # Ya existe, marcar como sincronizada y continuar
                        Sale.objects.using('default').filter(pk=sale.pk).update(synced_to_server=True)
                        synced += 1
                        continue
                    
                    # Crear cabecera de venta en remoto
                    # Si no es factura facturada, el IVA debe ser 0
                    iva_amount = sale.iva if sale.is_invoiced else 0
                    
                    # Mantener el horario local original de la venta
                    # Preservamos el date_joined tal como está para mantener la hora local del POS
                    remote_sale = Sale.objects.using('remote').create(
                        company_id=remote_company.id if remote_company else None,
                        cli_id=sale.cli_id,
                        date_joined=sale.date_joined,
                        local_timezone=sale.local_timezone,
                        subtotal=sale.subtotal,
                        iva=iva_amount,
                        total=sale.total,
                        payment_method=sale.payment_method,
                        invoice_number=sale.invoice_number,
                        invoice_pos=sale.invoice_pos,
                        invoice_type=sale.invoice_type,
                        is_invoiced=sale.is_invoiced,
                    )

                    # Crear detalles en remoto
                    for det in sale.detsale_set.all():
                        # Mapear producto local -> remoto. No podemos asumir que los IDs coinciden.
                        remote_prod = None
                        local_prod = Product.objects.using('default').filter(pk=det.prod_id).first()
                        if local_prod:
                            # 1) Buscar en remoto por code si existe
                            if local_prod.code:
                                remote_prod = Product.objects.using('remote').filter(code=local_prod.code).first()
                            # 2) Si no hay code o no matchea, intentar por nombre exacto
                            if not remote_prod:
                                remote_prod = Product.objects.using('remote').filter(name=local_prod.name).first()

                        if not remote_prod:
                            # Si no encontramos el producto remoto, registramos el error y abortamos
                            raise Exception(
                                f"Producto local {det.prod_id} ('{getattr(local_prod, 'name', '?')}') "
                                f"no tiene equivalente en servidor remoto (por code/nombre)."
                            )

                        DetSale.objects.using('remote').create(
                            sale=remote_sale,
                            prod_id=remote_prod.id,
                            price=det.price,
                            cant=det.cant,
                            subtotal=det.subtotal,
                        )

                # Marcar venta local como sincronizada
                Sale.objects.using('default').filter(pk=sale.pk).update(
                    synced_to_server=True,
                )
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando venta {sale.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion finalizada. Ventas sincronizadas: {synced} / {total}. Errores: {errors}."
        ))
