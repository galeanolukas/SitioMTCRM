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
                    # Verificar si ya existe venta duplicada usando múltiples criterios mejorados
                    # PRIORIDAD 1: Buscar por local_uuid (método más confiable)
                    existing_sale = None
                    
                    if hasattr(sale, 'local_uuid') and sale.local_uuid:
                        existing_sale = Sale.objects.using('remote').filter(
                            local_uuid=sale.local_uuid
                        ).first()
                        
                        if existing_sale:
                            self.stdout.write(
                                self.style.WARNING(f"Venta {sale.id} ya existe por UUID (ID: {existing_sale.id}), omitiendo...")
                            )
                            # Marcar como sincronizada y continuar
                            Sale.objects.using('default').filter(pk=sale.pk).update(synced_to_server=True)
                            synced += 1
                            continue
                    
                    # PRIORIDAD 2: Buscar por local_sale_id (método secundario)
                    if hasattr(sale, 'local_sale_id') and sale.local_sale_id:
                        existing_sale = Sale.objects.using('remote').filter(
                            local_sale_id=sale.local_sale_id,
                            company_id=remote_company.id if remote_company else None
                        ).first()
                        
                        if existing_sale:
                            self.stdout.write(
                                self.style.WARNING(f"Venta {sale.id} ya existe por local_sale_id (ID: {existing_sale.id}), omitiendo...")
                            )
                            # Marcar como sincronizada y continuar
                            Sale.objects.using('default').filter(pk=sale.pk).update(synced_to_server=True)
                            synced += 1
                            continue
                    
                    # PRIORIDAD 3: Búsqueda estricta por tiempo y campos (último recurso)
                    # Reducir ventana de tiempo a ±1 segundo para mayor precisión
                    existing_sale = Sale.objects.using('remote').filter(
                        date_joined__gte=sale.date_joined - timezone.timedelta(seconds=1),
                        date_joined__lte=sale.date_joined + timezone.timedelta(seconds=1),
                        total=sale.total,
                        payment_method=sale.payment_method,
                        company_id=remote_company.id if remote_company else None
                    )
                    
                    # Si hay cliente, agregarlo a la búsqueda
                    if sale.cli_id:
                        existing_sale = existing_sale.filter(cli_id=sale.cli_id)
                    
                    existing_sale = existing_sale.first()
                    
                    if existing_sale:
                        # Verificación final: comparar timestamp exacto
                        time_diff = abs((existing_sale.date_joined - sale.date_joined).total_seconds())
                        if time_diff < 2:  # Solo si la diferencia es menor a 2 segundos
                            self.stdout.write(
                                self.style.WARNING(f"Venta {sale.id} duplicada por tiempo (ID: {existing_sale.id}), omitiendo...")
                            )
                            # Marcar como sincronizada y continuar
                            Sale.objects.using('default').filter(pk=sale.pk).update(synced_to_server=True)
                            synced += 1
                            continue
                    
                    # ANTES DE CREAR: Verificación final de UUID para evitar duplicados
                    if hasattr(sale, 'local_uuid') and sale.local_uuid:
                        # Verificar si el UUID ya existe en el servidor (doble verificación)
                        uuid_check = Sale.objects.using('remote').filter(
                            local_uuid=sale.local_uuid
                        ).exists()
                        
                        if uuid_check:
                            self.stdout.write(
                                self.style.WARNING(f"Venta {sale.id}: UUID {sale.local_uuid} ya existe en servidor, omitiendo...")
                            )
                            # Marcar como sincronizada y continuar
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
                        payment_details=getattr(sale, 'payment_details', None),
                        invoice_number=sale.invoice_number,
                        invoice_pos=sale.invoice_pos,
                        invoice_type=sale.invoice_type,
                        is_invoiced=sale.is_invoiced,
                        synced_to_server=True,  # Marcar como sincronizada en servidor
                        local_uuid=sale.local_uuid,  # Importante: mantener UUID local
                        local_sale_id=sale.id,  # Importante: mantener ID local
                        source=getattr(sale, 'source', 'local_pos'),  # Mantener origen
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
                        
                        # ACTUALIZAR STOCK DEL PRODUCTO EN SERVIDOR
                        current_stock = remote_prod.stock or 0
                        new_stock = current_stock - det.cant
                        Product.objects.using('remote').filter(pk=remote_prod.id).update(
                            stock=new_stock
                        )
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Stock actualizado - Producto: {remote_prod.name}, "
                                f"Anterior: {current_stock}, Vendido: {det.cant}, Nuevo: {new_stock}"
                            )
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
