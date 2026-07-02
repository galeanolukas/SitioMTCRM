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
                # No podemos reutilizar directamente company_id porque los IDs
                # de Company en local y remoto no tienen por qué coincidir.
                remote_company = None
                if prod.company_id:
                    local_company = Company.objects.using('default').filter(pk=prod.company_id).first()
                    if local_company:
                        # 1) Intentar mapear por CUIT
                        if local_company.cuit:
                            remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
                        # 2) Si no hay CUIT o no se encontró, intentar por nombre exacto
                        if not remote_company:
                            remote_company = Company.objects.using('remote').filter(name=local_company.name).first()

                # Si no encontramos empresa remota y el producto tenía empresa local,
                # no intentamos sincronizarlo para evitar errores de FK.
                if prod.company_id and not remote_company:
                    errors += 1
                    self.stderr.write(
                        f"Error sincronizando producto {prod.id}: empresa local {prod.company_id} "
                        f"no tiene equivalente en servidor remoto (por CUIT/nombre)."
                    )
                    continue

                with transaction.atomic(using='remote'):
                    # Asegurar categoria en remoto
                    remote_cat = None
                    if prod.cat_id:
                        remote_cat = Category.objects.using('remote').filter(name=prod.cat.name).first()
                        if not remote_cat:
                            remote_cat = Category.objects.using('remote').create(
                                name=prod.cat.name,
                                desc=prod.cat.desc,
                            )

                    # Resolver proveedor en remoto si existe con mismo ID
                    remote_supplier = None
                    if prod.supplier_id:
                        if Supplier.objects.using('remote').filter(pk=prod.supplier_id).exists():
                            remote_supplier = Supplier.objects.using('remote').get(pk=prod.supplier_id)

                    # Lógica mejorada de búsqueda:
                    # 1) Si tiene código, buscar por código primero
                    # 2) Si no encuentra por código, buscar por nombre
                    # 3) Si no tiene código, buscar por nombre directamente
                    remote_prod = None
                    if prod.code:
                        remote_prod = Product.objects.using('remote').filter(code=prod.code).first()
                        if not remote_prod:
                            remote_prod = Product.objects.using('remote').filter(name=prod.name).first()
                    else:
                        remote_prod = Product.objects.using('remote').filter(name=prod.name).first()

                    # Si no se encontró, crear nuevo
                    if not remote_prod:
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
                            'stock': prod.stock,
                        }
                        
                        # Incluir código solo si existe
                        if prod.code:
                            defaults['code'] = prod.code

                        remote_prod = Product.objects.using('remote').create(**defaults)
                        created = True
                    else:
                        # Actualizar producto existente
                        created = False
                    if not created:
                        if remote_company:
                            remote_prod.company_id = remote_company.id
                        remote_prod.name = prod.name
                        # Actualizar código si existe localmente pero no remotamente
                        if prod.code and not remote_prod.code:
                            remote_prod.code = prod.code
                        if remote_cat:
                            remote_prod.cat = remote_cat
                        remote_prod.supplier = remote_supplier
                        remote_prod.cost_price = prod.cost_price
                        remote_prod.pvp = prod.pvp
                        remote_prod.iva_rate = prod.iva_rate
                        remote_prod.pvp_final = prod.pvp_final
                        remote_prod.unit = prod.unit
                        remote_prod.stock = prod.stock
                        remote_prod.save()

                # Marcar producto local como sincronizado
                Product.objects.using('default').filter(pk=prod.pk).update(synced_to_server=True)
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando producto {prod.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de productos finalizada. Productos sincronizados: {synced} / {total}. Errores: {errors}."
        ))
