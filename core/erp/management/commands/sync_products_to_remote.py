from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Product, Category, Supplier, Company


class Command(BaseCommand):
    help = "Sincroniza productos (maestro + stock) desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de productos hacia servidor remoto..."))

        local_qs = Product.objects.using('default').filter(synced_to_server=False).order_by('id')
        total = local_qs.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay productos para sincronizar."))
            return

        synced = 0
        errors = 0

        for prod in local_qs:
            try:
                # Resolver empresa remota a partir de la empresa local del producto.
                remote_company = None
                if prod.company_id:
                    local_company = Company.objects.using('default').filter(pk=prod.company_id).first()
                    if local_company:
                        if local_company.cuit:
                            remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
                        if not remote_company:
                            remote_company = Company.objects.using('remote').filter(name=local_company.name).first()

                if prod.company_id and not remote_company:
                    errors += 1
                    self.stderr.write(
                        f"Error sincronizando producto {prod.id}: empresa local {prod.company_id} "
                        f"no tiene equivalente en servidor remoto (por CUIT/nombre)."
                    )
                    continue

                # Resolver categoria en remoto (fuera de atomic para no romper si falla)
                remote_cat = None
                if prod.cat_id:
                    remote_cat = Category.objects.using('remote').filter(name=prod.cat.name).first()
                    if not remote_cat:
                        remote_cat = Category.objects.using('remote').create(
                            name=prod.cat.name,
                            desc=prod.cat.desc,
                        )

                # Resolver proveedor en remoto
                remote_supplier = None
                if prod.supplier_id:
                    if Supplier.objects.using('remote').filter(pk=prod.supplier_id).exists():
                        remote_supplier = Supplier.objects.using('remote').get(pk=prod.supplier_id)

                # Buscar producto existente: por code, luego por nombre exacto, iexact, icontains
                remote_prod = None
                if prod.code:
                    remote_prod = Product.objects.using('remote').filter(code=prod.code).first()
                if not remote_prod:
                    remote_prod = Product.objects.using('remote').filter(name=prod.name).first()
                if not remote_prod:
                    remote_prod = Product.objects.using('remote').filter(name__iexact=prod.name).first()
                if not remote_prod:
                    # Busqueda mas amplia por si hay diferencias de espacios
                    clean_name = prod.name.strip()
                    remote_prod = Product.objects.using('remote').filter(name__icontains=clean_name).first()

                if remote_prod:
                    # Actualizar producto existente
                    if remote_company:
                        remote_prod.company_id = remote_company.id
                    remote_prod.name = prod.name
                    # Siempre usar el código del local si existe
                    if prod.code:
                        remote_prod.code = prod.code
                    # Siempre usar el código de proveedor del local si existe
                    if prod.codigo_proveedor:
                        remote_prod.codigo_proveedor = prod.codigo_proveedor
                    if remote_cat:
                        remote_prod.cat = remote_cat
                    remote_prod.supplier = remote_supplier
                    remote_prod.cost_price = prod.cost_price
                    remote_prod.pvp = prod.pvp
                    remote_prod.iva_rate = prod.iva_rate
                    remote_prod.pvp_final = prod.pvp_final
                    remote_prod.unit = prod.unit
                    # Stock no se sobreescribe aqui - se sincroniza via sync_stock_to_remote con delta
                    remote_prod.save(using='remote')
                else:
                    # Crear nuevo producto (con fallback si duplicate key)
                    defaults = {
                        'company_id': remote_company.id if remote_company else None,
                        'name': prod.name,
                        'cat': remote_cat,
                        'supplier': remote_supplier,
                        'cost_price': prod.cost_price,
                        'pvp': prod.pvp,
                        'iva_rate': prod.iva_rate,
                        'pvp_final': prod.pvp_final,
                        'unit': prod.unit,
                        'stock': prod.stock,  # Stock inicial solo en creacion
                    }
                    if prod.code:
                        defaults['code'] = prod.code
                    if prod.codigo_proveedor:
                        defaults['codigo_proveedor'] = prod.codigo_proveedor
                    try:
                        Product.objects.using('remote').create(**defaults)
                    except Exception as create_err:
                        if 'duplicate key' in str(create_err).lower() or 'unique constraint' in str(create_err).lower():
                            # Buscar de nuevo mas ampliamente y actualizar
                            remote_prod = Product.objects.using('remote').filter(name__icontains=prod.name.strip()).first()
                            if remote_prod:
                                if remote_company:
                                    remote_prod.company_id = remote_company.id
                                remote_prod.name = prod.name
                                # Siempre usar el código del local si existe
                                if prod.code:
                                    remote_prod.code = prod.code
                                # Siempre usar el código de proveedor del local si existe
                                if prod.codigo_proveedor:
                                    remote_prod.codigo_proveedor = prod.codigo_proveedor
                                if remote_cat:
                                    remote_prod.cat = remote_cat
                                remote_prod.supplier = remote_supplier
                                remote_prod.cost_price = prod.cost_price
                                remote_prod.pvp = prod.pvp
                                remote_prod.iva_rate = prod.iva_rate
                                remote_prod.pvp_final = prod.pvp_final
                                remote_prod.unit = prod.unit
                                # Stock no se sobreescribe aqui - se sincroniza via sync_stock_to_remote
                                remote_prod.save(using='remote')
                            else:
                                raise
                        else:
                            raise

                # Marcar producto local como sincronizado
                Product.objects.using('default').filter(pk=prod.pk).update(synced_to_server=True)
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando producto {prod.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de productos finalizada. Productos sincronizados: {synced} / {total}. Errores: {errors}."
        ))
