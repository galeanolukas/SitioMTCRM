from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Remito, DetalleRemito, Product, Supplier
from core.erp.management.commands._restore_common import (
    get_local_company,
    resolve_remote_company,
    map_remote_product,
    map_remote_supplier,
)


class Command(BaseCommand):
    help = ("Restaura remitos desde el servidor (remote) hacia la BD local, "
            "con sus detalles. Dedup por numero+fecha+tipo+proveedor. "
            "No modifica stock aunque el remito venga procesado.")

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=None,
                            help='ID de la empresa local a restaurar')
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo muestra que se restauraria, sin escribir')

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando restauracion de remitos remoto -> local..."))

        local_company = get_local_company(options.get('company_id'))
        if not local_company:
            self.stdout.write(self.style.ERROR("No se encontro empresa local."))
            return
        remote_company = resolve_remote_company(local_company, self.stdout)
        if not remote_company:
            self.stdout.write(self.style.ERROR("No se pudo resolver la empresa en el servidor."))
            return
        self.stdout.write(f"Empresa: {local_company.name} (local {local_company.id} -> remoto {remote_company.id})")

        remote_remitos = (Remito.objects.using('remote')
                          .filter(company_id=remote_company.id)
                          .order_by('id'))
        total = remote_remitos.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay remitos en el servidor para esta empresa."))
            return

        dry_run = options.get('dry_run')
        created = skipped = errors = 0

        for rr in remote_remitos.iterator():
            try:
                # Mapear proveedor para dedup consistente
                remote_sup = None
                if rr.supplier_id:
                    remote_sup = Supplier.objects.using('remote').filter(pk=rr.supplier_id).first()
                local_sup = map_remote_supplier(remote_sup, local_company.id, create=not dry_run)

                exists = Remito.objects.using('default').filter(
                    numero=rr.numero,
                    fecha=rr.fecha,
                    tipo=rr.tipo,
                    supplier_id=local_sup.id if local_sup else None,
                    company_id=local_company.id,
                ).exists()
                if exists:
                    skipped += 1
                    continue
                if dry_run:
                    self.stdout.write(f"[dry-run] Restauraria remito {rr.numero} ({rr.fecha})")
                    created += 1
                    continue

                with transaction.atomic(using='default'):
                    remito = Remito.objects.using('default').create(
                        company_id=local_company.id,
                        tipo=rr.tipo,
                        supplier=local_sup,
                        numero=rr.numero,
                        fecha=rr.fecha,
                        estado=rr.estado,
                        observaciones=rr.observaciones,
                        iva_porcentaje=rr.iva_porcentaje,
                        iva_modo=getattr(rr, 'iva_modo', 'incluido') or 'incluido',
                        synced_to_server=True,
                    )
                    missing = 0
                    for rd in DetalleRemito.objects.using('remote').filter(remito_id=rr.id):
                        remote_prod = Product.objects.using('remote').filter(pk=rd.prod_id).first() if rd.prod_id else None
                        local_prod = map_remote_product(remote_prod, local_company.id) if remote_prod else None
                        if rd.prod_id and not local_prod:
                            missing += 1
                            continue
                        DetalleRemito.objects.using('default').create(
                            remito=remito,
                            prod=local_prod,
                            cantidad=rd.cantidad,
                            precio_unitario=rd.precio_unitario,
                        )
                    msg = f"Remito {rr.numero} restaurado (estado: {rr.estado})"
                    if missing:
                        msg += f" - {missing} detalle(s) omitidos (producto no encontrado)"
                    self.stdout.write(msg)
                    created += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error restaurando remito remoto {rr.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Restauracion de remitos finalizada. Creados: {created}, "
            f"ya existian: {skipped}, errores: {errors}, total remoto: {total}"
        ))
