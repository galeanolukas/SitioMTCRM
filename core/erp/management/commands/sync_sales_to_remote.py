from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.erp.models import Sale, DetSale, Company, Product, Client


class Command(BaseCommand):
    help = "Sincroniza ventas y sus detalles desde la BD local (default) hacia la BD remota (remote)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Eliminar ventas en servidor que fueron eliminadas localmente',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se haría sin ejecutar cambios',
        )

    def handle(self, *args, **options):
        cleanup_mode = options.get('cleanup', False)
        dry_run = options.get('dry_run', False)

        if cleanup_mode:
            return self.cleanup_deleted_sales(dry_run)

        # Ejecutar cleanup de eliminaciones antes de sync normal
        self.cleanup_deleted_sales(dry_run)

        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de ventas hacia servidor remoto..."))

        # Ventas locales que aún no se han sincronizado
        pending_sales = Sale.objects.using('default').filter(
            Q(synced_to_server=False) | Q(afip_pendiente_autorizacion=True)
        ).order_by('id')
        total = pending_sales.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay ventas pendientes de sincronizar."))
            return

        synced = 0
        errors = 0
        updated = 0

        for sale in pending_sales:
            try:
                # Reintentar autorización AFIP si la venta está en contingencia pendiente
                if sale.afip_pendiente_autorizacion and not sale.afip_cae:
                    self.stdout.write(
                        self.style.WARNING(f"Venta {sale.id}: reintentando autorización AFIP...")
                    )
                    sale.emitir_factura_afip(skip_afip_call_on_save=True)

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

                # Resolver cliente remoto (los IDs no coinciden entre local y remoto)
                remote_cli_id = None
                if sale.cli_id:
                    local_cli = Client.objects.using('default').filter(pk=sale.cli_id).first()
                    if local_cli:
                        remote_cli = None
                        # 1) Buscar por DNI si tiene
                        if local_cli.dni:
                            remote_cli = Client.objects.using('remote').filter(dni=local_cli.dni).first()
                        # 2) Buscar por CUIT/CUIL si tiene
                        if not remote_cli and local_cli.cuit_cuil:
                            remote_cli = Client.objects.using('remote').filter(cuit_cuil=local_cli.cuit_cuil).first()
                        # 3) Buscar por nombre exacto + empresa
                        if not remote_cli:
                            if remote_company:
                                remote_cli = Client.objects.using('remote').filter(
                                    names=local_cli.names, company_id=remote_company.id
                                ).first()
                            else:
                                remote_cli = Client.objects.using('remote').filter(names=local_cli.names).first()
                        # 4) Buscar por nombre case-insensitive
                        if not remote_cli:
                            remote_cli = Client.objects.using('remote').filter(names__iexact=local_cli.names).first()
                        # 5) Si no existe, crear el cliente en remoto
                        if not remote_cli:
                            remote_cli = Client.objects.using('remote').create(
                                company_id=remote_company.id if remote_company else local_cli.company_id,
                                names=local_cli.names,
                                surnames=local_cli.surnames,
                                dni=local_cli.dni,
                                cuit_cuil=local_cli.cuit_cuil,
                                date_birthday=local_cli.date_birthday,
                                address=local_cli.address,
                                gender=local_cli.gender,
                                is_active=local_cli.is_active,
                            )
                            self.stdout.write(f"  Cliente remoto creado: {remote_cli.names} (ID: {remote_cli.id})")
                        remote_cli_id = remote_cli.id

                with transaction.atomic(using='remote'):
                    # === Buscar venta existente por local_uuid (método principal) ===
                    existing_sale = None
                    if sale.local_uuid:
                        existing_sale = Sale.objects.using('remote').filter(
                            local_uuid=sale.local_uuid
                        ).first()

                    # === Si no hay UUID, buscar por local_sale_id + empresa ===
                    if not existing_sale and sale.local_sale_id:
                        existing_sale = Sale.objects.using('remote').filter(
                            local_sale_id=sale.local_sale_id,
                            company_id=remote_company.id if remote_company else None
                        ).first()

                    # === Si no hay UUID ni local_sale_id, buscar por invoice_number ===
                    if not existing_sale and sale.invoice_number:
                        existing_sale = Sale.objects.using('remote').filter(
                            invoice_number=sale.invoice_number
                        ).first()

                    # Campos comunes para update o create
                    iva_amount = sale.iva if sale.iva is not None else 0
                    sale_defaults = {
                        'company_id': remote_company.id if remote_company else None,
                        'cli_id': remote_cli_id,
                        'date_joined': sale.date_joined,
                        'local_timezone': sale.local_timezone,
                        'subtotal': sale.subtotal,
                        'iva': iva_amount,
                        'total': sale.total,
                        'payment_method': sale.payment_method,
                        'payment_details': getattr(sale, 'payment_details', None),
                        'invoice_number': sale.invoice_number,
                        'invoice_pos': sale.invoice_pos,
                        'invoice_type': sale.invoice_type,
                        'is_invoiced': sale.is_invoiced,
                        'synced_to_server': True,
                        'local_sale_id': sale.id,
                        'source': getattr(sale, 'source', 'local_pos'),
                        'pos_id': getattr(sale, 'pos_id', ''),
                        'status': getattr(sale, 'status', 'confirmed'),
                        'is_budget': getattr(sale, 'is_budget', False),
                        'sent_to_local': getattr(sale, 'sent_to_local', False),
                        'local_server_response': getattr(sale, 'local_server_response', {}),
                        'budget_notes': getattr(sale, 'budget_notes', ''),
                        'afip_cae': sale.afip_cae or '',
                        'afip_cae_vto': sale.afip_cae_vto,
                        'afip_voucher_number': sale.afip_voucher_number,
                        'afip_qr': sale.afip_qr or '',
                        'afip_error': sale.afip_error or '',
                        'afip_contingencia': sale.afip_contingencia,
                        'afip_contingencia_fecha': sale.afip_contingencia_fecha,
                        'afip_pendiente_autorizacion': sale.afip_pendiente_autorizacion,
                    }

                    if existing_sale:
                        # === ACTUALIZAR venta existente (no crear duplicado) ===
                        for field, value in sale_defaults.items():
                            setattr(existing_sale, field, value)
                        # Mantener local_uuid si el existente no lo tiene
                        if not existing_sale.local_uuid and sale.local_uuid:
                            existing_sale.local_uuid = sale.local_uuid
                        existing_sale.save()
                        remote_sale = existing_sale
                        created = False
                        self.stdout.write(
                            self.style.WARNING(f"Venta {sale.id} actualizada en servidor (ID remoto: {remote_sale.id})")
                        )
                    else:
                        # === CREAR nueva venta en remoto ===
                        remote_sale = Sale.objects.using('remote').create(
                            local_uuid=sale.local_uuid,
                            **sale_defaults,
                        )
                        created = True
                        self.stdout.write(
                            self.style.SUCCESS(f"Venta {sale.id} creada en servidor (ID remoto: {remote_sale.id})")
                        )

                    # Solo crear detalles si la venta fue creada (no actualizada)
                    if created:
                        for det in sale.detsale_set.all():
                            # Mapear producto local -> remoto
                            remote_prod = None
                            local_prod = Product.objects.using('default').filter(pk=det.prod_id).first()
                            if local_prod:
                                if local_prod.code:
                                    remote_prod = Product.objects.using('remote').filter(code=local_prod.code).first()
                                if not remote_prod:
                                    remote_prod = Product.objects.using('remote').filter(name=local_prod.name).first()

                            if not remote_prod:
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

                            # Actualizar stock del producto en servidor
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
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"  Omitiendo creación de detalles (venta ya existía)")
                        )

                # Marcar venta local como sincronizada
                Sale.objects.using('default').filter(pk=sale.pk).update(
                    synced_to_server=True,
                    synced_at=timezone.now(),
                )
                if created:
                    synced += 1
                else:
                    updated += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando venta {sale.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion finalizada. Ventas creadas: {synced}, actualizadas: {updated}, "
            f"errores: {errors}. Total procesado: {total}."
        ))

    def cleanup_deleted_sales(self, dry_run=False):
        """Eliminar en servidor las ventas que fueron eliminadas localmente"""
        self.stdout.write(self.style.NOTICE("Verificando ventas eliminadas localmente..."))

        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY RUN - No se ejecutarán cambios reales"))

        try:
            from django.db import connections

            # Obtener todos los local_uuid y local_sale_id de ventas locales
            local_uuids = list(
                Sale.objects.using('default')
                .exclude(local_uuid__isnull=True)
                .exclude(local_uuid='')
                .values_list('local_uuid', flat=True)
            )
            local_sale_ids = list(
                Sale.objects.using('default')
                .exclude(local_sale_id__isnull=True)
                .values_list('local_sale_id', flat=True)
            )

            # Buscar en servidor las ventas con source='local_pos' que ya no existen localmente
            with connections['remote'].cursor() as cursor:
                # Construir query para encontrar ventas huérfanas por local_uuid
                orphaned = []

                if local_uuids:
                    placeholders = ','.join(['%s'] * len(local_uuids))
                    cursor.execute(f'''
                        SELECT id, local_uuid, local_sale_id, invoice_number, total, date_joined
                        FROM erp_sale
                        WHERE source = 'local_pos'
                          AND local_uuid IS NOT NULL
                          AND local_uuid != ''
                          AND local_uuid NOT IN ({placeholders})
                    ''', local_uuids)
                    orphaned.extend(cursor.fetchall())

                # También buscar por local_sale_id si no tienen local_uuid
                if local_sale_ids:
                    placeholders = ','.join(['%s'] * len(local_sale_ids))
                    cursor.execute(f'''
                        SELECT id, local_uuid, local_sale_id, invoice_number, total, date_joined
                        FROM erp_sale
                        WHERE source = 'local_pos'
                          AND (local_uuid IS NULL OR local_uuid = '')
                          AND local_sale_id IS NOT NULL
                          AND local_sale_id NOT IN ({placeholders})
                    ''', local_sale_ids)
                    orphaned.extend(cursor.fetchall())

                if not orphaned:
                    self.stdout.write(self.style.SUCCESS("No se encontraron ventas eliminadas localmente pendientes de cleanup."))
                    return

                self.stdout.write(self.style.WARNING(
                    f"Se encontraron {len(orphaned)} ventas en servidor que fueron eliminadas localmente:"
                ))

                for row in orphaned:
                    self.stdout.write(
                        f"  ID remoto: {row[0]}, UUID: {row[1]}, local_sale_id: {row[2]}, "
                        f"Factura: {row[3]}, Total: {row[4]}, Fecha: {row[5]}"
                    )

                if not dry_run:
                    # Eliminar registros relacionados por FK primero, luego la venta
                    orphaned_ids = [row[0] for row in orphaned]
                    placeholders = ','.join(['%s'] * len(orphaned_ids))

                    # 1. SaleVatBreakdown
                    cursor.execute(f'''
                        DELETE FROM erp_salevatbreakdown
                        WHERE sale_id IN ({placeholders})
                    ''', orphaned_ids)

                    # 2. DetSale
                    cursor.execute(f'''
                        DELETE FROM erp_detsale
                        WHERE sale_id IN ({placeholders})
                    ''', orphaned_ids)
                    deleted_details = cursor.rowcount

                    # 3. LibroIvaRegistro
                    cursor.execute(f'''
                        DELETE FROM erp_libroivaregistro
                        WHERE sale_id IN ({placeholders})
                    ''', orphaned_ids)

                    # 4. CuentaCorrienteCliente
                    cursor.execute(f'''
                        DELETE FROM erp_cuentacorrientecliente
                        WHERE sale_id IN ({placeholders})
                    ''', orphaned_ids)

                    # 5. AsientoContable
                    cursor.execute(f'''
                        DELETE FROM erp_asientocontable
                        WHERE sale_id IN ({placeholders})
                    ''', orphaned_ids)

                    # 6. Sale (finalmente)
                    cursor.execute(f'''
                        DELETE FROM erp_sale
                        WHERE id IN ({placeholders})
                    ''', orphaned_ids)
                    deleted_sales = cursor.rowcount

                    self.stdout.write(self.style.SUCCESS(
                        f"{deleted_sales} ventas eliminadas del servidor ({deleted_details} detalles, "
                        f"registros IVA/contables limpiados)."
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"DRY RUN: Se eliminarían {len(orphaned)} ventas del servidor."
                    ))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error en cleanup de ventas eliminadas: {e}"))
            import traceback
            traceback.print_exc()
