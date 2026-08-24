from django.core.management.base import BaseCommand
from django.db import connections
from core.erp.models import PriceList, PriceListProduct, Product, Company


class Command(BaseCommand):
    help = "Sincroniza listas de precios y sus productos override desde la BD local hacia la BD remota."

    def handle(self, *args, **options):
        if 'remote' not in connections:
            self.stdout.write(self.style.ERROR('No hay conexión a base de datos remota configurada'))
            return

        self.stdout.write(self.style.NOTICE("Iniciando sincronización de listas de precios hacia servidor remoto..."))

        synced = 0
        errors = 0

        # 1) Sincronizar PriceLists
        local_lists = PriceList.objects.using('default').all().prefetch_related('products')
        total = local_lists.count()

        if not total:
            self.stdout.write(self.style.WARNING("No hay listas de precios para sincronizar."))
            return

        # Mapeo de IDs locales -> remotos para usar despues con PriceListProduct
        list_id_map = {}

        for pl in local_lists:
            try:
                # Resolver empresa remota
                remote_company = None
                if pl.company_id:
                    local_company = Company.objects.using('default').filter(pk=pl.company_id).first()
                    if local_company:
                        if local_company.cuit:
                            remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
                        if not remote_company:
                            remote_company = Company.objects.using('remote').filter(name=local_company.name).first()

                # Buscar lista existente en remoto: por nombre + empresa, luego solo por nombre
                remote_pl = None
                if remote_company:
                    remote_pl = PriceList.objects.using('remote').filter(
                        name=pl.name, company_id=remote_company.id
                    ).first()
                if not remote_pl:
                    remote_pl = PriceList.objects.using('remote').filter(name__iexact=pl.name).first()

                if remote_pl:
                    # Actualizar lista existente
                    if remote_company:
                        remote_pl.company_id = remote_company.id
                    remote_pl.name = pl.name
                    remote_pl.discount_percentage = pl.discount_percentage
                    remote_pl.interest_percentage = pl.interest_percentage
                    remote_pl.is_active = pl.is_active
                    remote_pl.save(using='remote')
                else:
                    # Crear nueva lista
                    remote_pl = PriceList.objects.using('remote').create(
                        company_id=remote_company.id if remote_company else None,
                        name=pl.name,
                        discount_percentage=pl.discount_percentage,
                        interest_percentage=pl.interest_percentage,
                        is_active=pl.is_active,
                    )

                list_id_map[pl.id] = remote_pl.id
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando lista de precios {pl.id}: {e}")

        self.stdout.write(f"Listas de precios sincronizadas: {synced} / {total}. Errores: {errors}.")

        # 2) Sincronizar PriceListProducts (overrides y excepciones)
        local_plps = PriceListProduct.objects.using('default').select_related('product', 'price_list')
        plp_synced = 0
        plp_errors = 0

        for plp in local_plps:
            try:
                remote_pl_id = list_id_map.get(plp.price_list_id)
                if not remote_pl_id:
                    self.stderr.write(f"Saltando PLP {plp.id}: lista remota no encontrada para lista local {plp.price_list_id}")
                    continue

                # Buscar producto remoto por nombre (mismo patron que sync_products)
                remote_product = None
                if plp.product.code:
                    remote_product = Product.objects.using('remote').filter(code=plp.product.code).first()
                if not remote_product:
                    remote_product = Product.objects.using('remote').filter(name=plp.product.name).first()
                if not remote_product:
                    remote_product = Product.objects.using('remote').filter(name__iexact=plp.product.name).first()

                if not remote_product:
                    self.stderr.write(f"Saltando PLP {plp.id}: producto remoto no encontrado para '{plp.product.name}'")
                    continue

                # Buscar si ya existe el override en remoto
                remote_plp = PriceListProduct.objects.using('remote').filter(
                    price_list_id=remote_pl_id,
                    product_id=remote_product.id
                ).first()

                if remote_plp:
                    # Actualizar
                    remote_plp.fixed_price = plp.fixed_price
                    remote_plp.discount_override = plp.discount_override
                    remote_plp.is_exception = plp.is_exception
                    remote_plp.save(using='remote')
                else:
                    # Crear
                    PriceListProduct.objects.using('remote').create(
                        price_list_id=remote_pl_id,
                        product_id=remote_product.id,
                        fixed_price=plp.fixed_price,
                        discount_override=plp.discount_override,
                        is_exception=plp.is_exception,
                    )

                plp_synced += 1
            except Exception as e:
                plp_errors += 1
                self.stderr.write(f"Error sincronizando PLP {plp.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización de listas de precios finalizada. "
            f"Listas: {synced}/{total}. Overrides: {plp_synced}. Errores: {errors + plp_errors}."
        ))
