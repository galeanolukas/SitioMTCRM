import uuid as uuid_lib
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.erp.models import (
    LibroIvaRegistro, SaleVatBreakdown, CuentaCorrienteCliente,
    AsientoContable, Sale, Company, Client, Supplier
)


class Command(BaseCommand):
    help = "Sincroniza datos fiscales (Libro IVA, VatBreakdown, CuentaCorriente, Asientos) local -> remoto."

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Eliminar registros fiscales en servidor cuyas ventas ya no existen localmente',
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
            return self.cleanup_orphaned(dry_run)

        # Ejecutar cleanup antes de sync normal
        self.cleanup_orphaned(dry_run)

        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de datos fiscales..."))

        stats = {'libro_iva': 0, 'vat_breakdown': 0, 'cuenta_corriente': 0, 'asientos': 0}
        errors = 0

        # 1) LibroIvaRegistro
        errors += self.sync_libro_iva(stats, dry_run)
        # 2) SaleVatBreakdown
        errors += self.sync_vat_breakdowns(stats, dry_run)
        # 3) CuentaCorrienteCliente
        errors += self.sync_cuenta_corriente(stats, dry_run)
        # 4) AsientoContable
        errors += self.sync_asientos(stats, dry_run)

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion fiscal finalizada. "
            f"Libro IVA: {stats['libro_iva']}, VatBreakdown: {stats['vat_breakdown']}, "
            f"CuentaCorriente: {stats['cuenta_corriente']}, Asientos: {stats['asientos']}. "
            f"Errores: {errors}."
        ))

    def _resolve_remote_company(self, company_id):
        """Mapear empresa local a remota por CUIT o nombre"""
        if not company_id:
            return None
        comp = Company.objects.using('default').filter(pk=company_id).first()
        if not comp:
            return None
        remote_comp = None
        if comp.cuit:
            remote_comp = Company.objects.using('remote').filter(cuit=comp.cuit).first()
        if not remote_comp:
            remote_comp = Company.objects.using('remote').filter(name=comp.name).first()
        return remote_comp.id if remote_comp else None

    def _resolve_remote_sale(self, sale_id):
        """Mapear venta local a remota por local_uuid o local_sale_id"""
        if not sale_id:
            return None
        local_sale = Sale.objects.using('default').filter(pk=sale_id).first()
        if not local_sale:
            return None
        if local_sale.local_uuid:
            remote_sale = Sale.objects.using('remote').filter(local_uuid=local_sale.local_uuid).first()
            if remote_sale:
                return remote_sale.id
        if local_sale.local_sale_id:
            remote_sale = Sale.objects.using('remote').filter(local_sale_id=local_sale.local_sale_id).first()
            if remote_sale:
                return remote_sale.id
        # Buscar por local_sale_id = id local
        remote_sale = Sale.objects.using('remote').filter(local_sale_id=sale_id).first()
        return remote_sale.id if remote_sale else None

    def _resolve_remote_client(self, client_id):
        """Mapear cliente local a remoto por DNI/CUIT/nombre"""
        if not client_id:
            return None
        local_cli = Client.objects.using('default').filter(pk=client_id).first()
        if not local_cli:
            return None
        remote_cli = None
        if local_cli.dni:
            remote_cli = Client.objects.using('remote').filter(dni=local_cli.dni).first()
        if not remote_cli and local_cli.cuit_cuil:
            remote_cli = Client.objects.using('remote').filter(cuit_cuil=local_cli.cuit_cuil).first()
        if not remote_cli:
            remote_cli = Client.objects.using('remote').filter(names__iexact=local_cli.names).first()
        return remote_cli.id if remote_cli else None

    def _resolve_remote_supplier(self, supplier_id):
        """Mapear proveedor local a remoto por nombre"""
        if not supplier_id:
            return None
        local_supp = Supplier.objects.using('default').filter(pk=supplier_id).first()
        if not local_supp:
            return None
        remote_supp = Supplier.objects.using('remote').filter(name=local_supp.name).first()
        return remote_supp.id if remote_supp else None

    def sync_libro_iva(self, stats, dry_run=False):
        """Sincronizar LibroIvaRegistro"""
        self.stdout.write(self.style.NOTICE("Sincronizando Libro IVA..."))
        pending = LibroIvaRegistro.objects.using('default').filter(synced_to_server=False).order_by('id')
        errors = 0

        for reg in pending:
            try:
                remote_company_id = self._resolve_remote_company(reg.company_id)
                if reg.company_id and not remote_company_id:
                    errors += 1
                    self.stderr.write(f"  Saltando LibroIva {reg.id}: empresa sin equivalente remoto")
                    continue

                remote_sale_id = self._resolve_remote_sale(reg.sale_id) if reg.sale_id else None
                remote_supplier_id = self._resolve_remote_supplier(reg.supplier_id) if reg.supplier_id else None

                # Generar UUID si no tiene
                if not reg.local_uuid:
                    reg.local_uuid = f"libroiva_{uuid_lib.uuid4().hex}"
                    reg.save(update_fields=['local_uuid'])

                with transaction.atomic(using='remote'):
                    existing = LibroIvaRegistro.objects.using('remote').filter(local_uuid=reg.local_uuid).first()

                    defaults = {
                        'company_id': remote_company_id,
                        'tipo_registro': reg.tipo_registro,
                        'fecha': reg.fecha,
                        'tipo_comprobante': reg.tipo_comprobante,
                        'punto_venta': reg.punto_venta,
                        'numero_comprobante': reg.numero_comprobante,
                        'cuit_emisor': reg.cuit_emisor,
                        'cuit_receptor': reg.cuit_receptor,
                        'razon_social': reg.razon_social,
                        'condicion_iva': reg.condicion_iva,
                        'aplicacion_iva': reg.aplicacion_iva,
                        'neto_gravado': reg.neto_gravado,
                        'neto_no_gravado': reg.neto_no_gravado,
                        'neto_exento': reg.neto_exento,
                        'iva_21': reg.iva_21,
                        'iva_10_5': reg.iva_10_5,
                        'iva_27': reg.iva_27,
                        'iva_2_5': reg.iva_2_5,
                        'iva_0': reg.iva_0,
                        'impuesto_interno': reg.impuesto_interno,
                        'total': reg.total,
                        'cae': reg.cae,
                        'cae_vto': reg.cae_vto,
                        'sale_id': remote_sale_id,
                        'supplier_id': remote_supplier_id,
                        'synced_to_server': True,
                        'synced_at': timezone.now(),
                    }

                    if existing:
                        for field, value in defaults.items():
                            setattr(existing, field, value)
                        existing.save()
                    else:
                        LibroIvaRegistro.objects.using('remote').create(
                            local_uuid=reg.local_uuid,
                            **defaults,
                        )

                if not dry_run:
                    LibroIvaRegistro.objects.using('default').filter(pk=reg.pk).update(
                        synced_to_server=True,
                        synced_at=timezone.now(),
                    )
                stats['libro_iva'] += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"  Error LibroIva {reg.id}: {e}")

        return errors

    def sync_vat_breakdowns(self, stats, dry_run=False):
        """Sincronizar SaleVatBreakdown"""
        self.stdout.write(self.style.NOTICE("Sincronizando VatBreakdowns..."))
        pending = SaleVatBreakdown.objects.using('default').filter(synced_to_server=False).order_by('id')
        errors = 0

        for vb in pending:
            try:
                remote_sale_id = self._resolve_remote_sale(vb.sale_id)
                if not remote_sale_id:
                    errors += 1
                    self.stderr.write(f"  Saltando VatBreakdown {vb.id}: venta sin equivalente remoto")
                    continue

                if not vb.local_uuid:
                    vb.local_uuid = f"vatbd_{uuid_lib.uuid4().hex}"
                    vb.save(update_fields=['local_uuid'])

                with transaction.atomic(using='remote'):
                    existing = SaleVatBreakdown.objects.using('remote').filter(local_uuid=vb.local_uuid).first()

                    defaults = {
                        'sale_id': remote_sale_id,
                        'vat_code': vb.vat_code,
                        'vat_rate': vb.vat_rate,
                        'taxable_base': vb.taxable_base,
                        'vat_amount': vb.vat_amount,
                        'synced_to_server': True,
                        'synced_at': timezone.now(),
                    }

                    if existing:
                        for field, value in defaults.items():
                            setattr(existing, field, value)
                        existing.save()
                    else:
                        SaleVatBreakdown.objects.using('remote').create(
                            local_uuid=vb.local_uuid,
                            **defaults,
                        )

                if not dry_run:
                    SaleVatBreakdown.objects.using('default').filter(pk=vb.pk).update(
                        synced_to_server=True,
                        synced_at=timezone.now(),
                    )
                stats['vat_breakdown'] += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"  Error VatBreakdown {vb.id}: {e}")

        return errors

    def sync_cuenta_corriente(self, stats, dry_run=False):
        """Sincronizar CuentaCorrienteCliente"""
        self.stdout.write(self.style.NOTICE("Sincronizando CuentaCorriente..."))
        pending = CuentaCorrienteCliente.objects.using('default').filter(synced_to_server=False).order_by('id')
        errors = 0

        for cc in pending:
            try:
                remote_company_id = self._resolve_remote_company(cc.company_id)
                if cc.company_id and not remote_company_id:
                    errors += 1
                    self.stderr.write(f"  Saltando CuentaCorriente {cc.id}: empresa sin equivalente remoto")
                    continue

                remote_client_id = self._resolve_remote_client(cc.client_id)
                if not remote_client_id:
                    errors += 1
                    self.stderr.write(f"  Saltando CuentaCorriente {cc.id}: cliente sin equivalente remoto")
                    continue

                remote_sale_id = self._resolve_remote_sale(cc.sale_id) if cc.sale_id else None

                if not cc.local_uuid:
                    cc.local_uuid = f"cc_{uuid_lib.uuid4().hex}"
                    cc.save(update_fields=['local_uuid'])

                with transaction.atomic(using='remote'):
                    existing = CuentaCorrienteCliente.objects.using('remote').filter(local_uuid=cc.local_uuid).first()

                    defaults = {
                        'company_id': remote_company_id,
                        'client_id': remote_client_id,
                        'tipo_movimiento': cc.tipo_movimiento,
                        'fecha': cc.fecha,
                        'descripcion': cc.descripcion,
                        'debe': cc.debe,
                        'haber': cc.haber,
                        'saldo': cc.saldo,
                        'sale_id': remote_sale_id,
                        'synced_to_server': True,
                        'synced_at': timezone.now(),
                    }

                    if existing:
                        for field, value in defaults.items():
                            setattr(existing, field, value)
                        existing.save()
                    else:
                        CuentaCorrienteCliente.objects.using('remote').create(
                            local_uuid=cc.local_uuid,
                            **defaults,
                        )

                if not dry_run:
                    CuentaCorrienteCliente.objects.using('default').filter(pk=cc.pk).update(
                        synced_to_server=True,
                        synced_at=timezone.now(),
                    )
                stats['cuenta_corriente'] += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"  Error CuentaCorriente {cc.id}: {e}")

        return errors

    def sync_asientos(self, stats, dry_run=False):
        """Sincronizar AsientoContable"""
        self.stdout.write(self.style.NOTICE("Sincronizando AsientosContables..."))
        pending = AsientoContable.objects.using('default').filter(synced_to_server=False).order_by('id')
        errors = 0

        for ac in pending:
            try:
                remote_company_id = self._resolve_remote_company(ac.company_id)
                if ac.company_id and not remote_company_id:
                    errors += 1
                    self.stderr.write(f"  Saltando Asiento {ac.id}: empresa sin equivalente remoto")
                    continue

                remote_sale_id = self._resolve_remote_sale(ac.sale_id) if ac.sale_id else None

                if not ac.local_uuid:
                    ac.local_uuid = f"asiento_{uuid_lib.uuid4().hex}"
                    ac.save(update_fields=['local_uuid'])

                with transaction.atomic(using='remote'):
                    existing = AsientoContable.objects.using('remote').filter(local_uuid=ac.local_uuid).first()

                    defaults = {
                        'company_id': remote_company_id,
                        'tipo_asiento': ac.tipo_asiento,
                        'fecha': ac.fecha,
                        'descripcion': ac.descripcion,
                        'debe_total': ac.debe_total,
                        'haber_total': ac.haber_total,
                        'sale_id': remote_sale_id,
                        'synced_to_server': True,
                        'synced_at': timezone.now(),
                    }

                    if existing:
                        for field, value in defaults.items():
                            setattr(existing, field, value)
                        existing.save()
                    else:
                        AsientoContable.objects.using('remote').create(
                            local_uuid=ac.local_uuid,
                            **defaults,
                        )

                if not dry_run:
                    AsientoContable.objects.using('default').filter(pk=ac.pk).update(
                        synced_to_server=True,
                        synced_at=timezone.now(),
                    )
                stats['asientos'] += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"  Error Asiento {ac.id}: {e}")

        return errors

    def cleanup_orphaned(self, dry_run=False):
        """Eliminar registros fiscales en servidor cuyas ventas relacionadas ya no existen localmente"""
        self.stdout.write(self.style.NOTICE("Verificando registros fiscales huerfanos en servidor..."))

        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY RUN - No se ejecutaran cambios reales"))

        try:
            from django.db import connections

            # Obtener UUIDs locales de ventas
            local_sale_uuids = list(
                Sale.objects.using('default')
                .exclude(local_uuid__isnull=True)
                .exclude(local_uuid='')
                .values_list('local_uuid', flat=True)
            )

            with connections['remote'].cursor() as cursor:
                # Buscar registros fiscales en servidor que referencian ventas que ya no existen localmente
                # Tabla: erp_salevatbreakdown
                cursor.execute("""
                    SELECT vsb.id, vsb.sale_id, s.local_uuid
                    FROM erp_salevatbreakdown vsb
                    LEFT JOIN erp_sale s ON vsb.sale_id = s.id
                    WHERE s.local_uuid IS NOT NULL AND s.local_uuid != ''
                      AND s.local_uuid NOT IN (%s)
                """ % ','.join(['%s'] * len(local_sale_uuids)) if local_sale_uuids else "SELECT 1 WHERE 1=0",
                    local_sale_uuids if local_sale_uuids else [0])
                orphaned_vbd = cursor.fetchall()

                # Tabla: erp_libroivaregistro
                cursor.execute("""
                    SELECT lir.id, lir.sale_id, s.local_uuid
                    FROM erp_libroivaregistro lir
                    LEFT JOIN erp_sale s ON lir.sale_id = s.id
                    WHERE lir.sale_id IS NOT NULL
                      AND s.local_uuid IS NOT NULL AND s.local_uuid != ''
                      AND s.local_uuid NOT IN (%s)
                """ % ','.join(['%s'] * len(local_sale_uuids)) if local_sale_uuids else "SELECT 1 WHERE 1=0",
                    local_sale_uuids if local_sale_uuids else [0])
                orphaned_lir = cursor.fetchall()

                # Tabla: erp_cuentacorrientecliente
                cursor.execute("""
                    SELECT ccc.id, ccc.sale_id, s.local_uuid
                    FROM erp_cuentacorrientecliente ccc
                    LEFT JOIN erp_sale s ON ccc.sale_id = s.id
                    WHERE ccc.sale_id IS NOT NULL
                      AND s.local_uuid IS NOT NULL AND s.local_uuid != ''
                      AND s.local_uuid NOT IN (%s)
                """ % ','.join(['%s'] * len(local_sale_uuids)) if local_sale_uuids else "SELECT 1 WHERE 1=0",
                    local_sale_uuids if local_sale_uuids else [0])
                orphaned_ccc = cursor.fetchall()

                # Tabla: erp_asientocontable
                cursor.execute("""
                    SELECT ac.id, ac.sale_id, s.local_uuid
                    FROM erp_asientocontable ac
                    LEFT JOIN erp_sale s ON ac.sale_id = s.id
                    WHERE ac.sale_id IS NOT NULL
                      AND s.local_uuid IS NOT NULL AND s.local_uuid != ''
                      AND s.local_uuid NOT IN (%s)
                """ % ','.join(['%s'] * len(local_sale_uuids)) if local_sale_uuids else "SELECT 1 WHERE 1=0",
                    local_sale_uuids if local_sale_uuids else [0])
                orphaned_ac = cursor.fetchall()

                total_orphaned = len(orphaned_vbd) + len(orphaned_lir) + len(orphaned_ccc) + len(orphaned_ac)

                if total_orphaned == 0:
                    self.stdout.write(self.style.SUCCESS("No se encontraron registros fiscales huerfanos."))
                    return

                self.stdout.write(self.style.WARNING(
                    f"Registros huerfanos: VatBreakdown={len(orphaned_vbd)}, "
                    f"LibroIVA={len(orphaned_lir)}, "
                    f"CuentaCorriente={len(orphaned_ccc)}, "
                    f"Asientos={len(orphaned_ac)}"
                ))

                if not dry_run:
                    # Eliminar registros huerfanos
                    for table, orphaned in [
                        ('erp_salevatbreakdown', orphaned_vbd),
                        ('erp_libroivaregistro', orphaned_lir),
                        ('erp_cuentacorrientecliente', orphaned_ccc),
                        ('erp_asientocontable', orphaned_ac),
                    ]:
                        if orphaned:
                            ids = [r[0] for r in orphaned]
                            placeholders = ','.join(['%s'] * len(ids))
                            cursor.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
                            self.stdout.write(f"  {table}: {cursor.rowcount} eliminados")
                else:
                    self.stdout.write(self.style.WARNING(f"DRY RUN: Se eliminarian {total_orphaned} registros."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error en cleanup fiscal: {e}"))
            import traceback
            traceback.print_exc()
