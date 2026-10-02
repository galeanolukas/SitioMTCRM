from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import PriceList, PriceListProduct, Product, Supplier
from core.erp.management.commands._restore_common import (
    get_local_company,
    resolve_remote_company,
    map_remote_product,
    map_remote_supplier,
)


class Command(BaseCommand):
    help = ("Restaura listas de precios desde el servidor (remote) hacia la BD local, "
            "con sus productos/overrides. Dedup por nombre+empresa+proveedor.")

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=None,
                            help='ID de la empresa local a restaurar')
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo muestra que se restauraria, sin escribir')

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando restauracion de listas de precios remoto -> local..."))

        local_company = get_local_company(options.get('company_id'))
        if not local_company:
            self.stdout.write(self.style.ERROR("No se encontro empresa local."))
            return
        remote_company = resolve_remote_company(local_company, self.stdout)
        if not remote_company:
            self.stdout.write(self.style.ERROR("No se pudo resolver la empresa en el servidor."))
            return
        self.stdout.write(f"Empresa: {local_company.name} (local {local_company.id} -> remoto {remote_company.id})")

        remote_lists = (PriceList.objects.using('remote')
                        .filter(company_id=remote_company.id)
                        .order_by('id'))
        total = remote_lists.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay listas de precios en el servidor para esta empresa."))
            return

        dry_run = options.get('dry_run')
        created = updated = skipped_items = errors = 0

        for rl in remote_lists.iterator():
            try:
                remote_sup = None
                if rl.supplier_id:
                    remote_sup = Supplier.objects.using('remote').filter(pk=rl.supplier_id).first()
                local_sup = map_remote_supplier(remote_sup, local_company.id, create=not dry_run)

                local_list = PriceList.objects.using('default').filter(
                    name=rl.name,
                    company_id=local_company.id,
                    supplier_id=local_sup.id if local_sup else None,
                ).first()

                if dry_run:
                    self.stdout.write(f"[dry-run] {'Actualizaria' if local_list else 'Restauraria'} lista '{rl.name}'")
                    continue

                with transaction.atomic(using='default'):
                    if not local_list:
                        local_list = PriceList.objects.using('default').create(
                            company_id=local_company.id,
                            name=rl.name,
                            supplier=local_sup,
                        )
                        created += 1
                    else:
                        updated += 1

                    # Copiar campos (la version del servidor manda)
                    for field in ('list_type', 'discount_percentage', 'interest_percentage',
                                  'cost_increase', 'applied_at', 'snapshot', 'undone', 'is_active'):
                        if hasattr(rl, field):
                            setattr(local_list, field, getattr(rl, field))
                    local_list.supplier = local_sup
                    local_list.save()

                    # Items de la lista
                    for rp in PriceListProduct.objects.using('remote').filter(price_list_id=rl.id):
                        remote_prod = Product.objects.using('remote').filter(pk=rp.product_id).first()
                        local_prod = map_remote_product(remote_prod, local_company.id) if remote_prod else None
                        if not local_prod:
                            skipped_items += 1
                            continue
                        PriceListProduct.objects.using('default').update_or_create(
                            price_list=local_list,
                            product=local_prod,
                            defaults={
                                'fixed_price': rp.fixed_price,
                                'discount_override': rp.discount_override,
                                'interest_override': rp.interest_override,
                                'is_exception': rp.is_exception,
                            },
                        )
                    self.stdout.write(f"Lista '{rl.name}' restaurada/actualizada")
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error restaurando lista remota {rl.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Restauracion de listas finalizada. Creadas: {created}, actualizadas: {updated}, "
            f"items omitidos: {skipped_items}, errores: {errors}, total remoto: {total}"
        ))
