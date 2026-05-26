from django.core.management.base import BaseCommand
from django.db import transaction, models
from django.db.models import Q
from django.utils import timezone

from core.erp.models import Product, Company, Category


class Command(BaseCommand):
    help = "Sincroniza stock de productos desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronización de stock hacia servidor remoto..."))

        synced = 0
        errors = 0

        # Obtener todas las empresas
        companies = Company.objects.using('default').all()
        
        for company in companies:
            self.stdout.write(f"Procesando empresa: {company.name}")
            
            # Obtener productos locales de esta empresa que necesitan sincronización
            # Solo productos donde stock_modified_locally > last_stock_sync o last_stock_sync es null
            local_products = Product.objects.using('default').filter(
                company=company
            ).filter(
                Q(last_stock_sync__isnull=True) | Q(stock_modified_locally__gt=models.F('last_stock_sync'))
            )
            
            if not local_products.exists():
                self.stdout.write(f"  No hay productos con cambios de stock pendientes")
                continue
            
            self.stdout.write(f"  {local_products.count()} productos con cambios de stock pendientes")
            
            for local_product in local_products:
                try:
                    # Buscar producto remoto correspondiente
                    remote_product = None
                    
                    # 1) Buscar por server_product_id si existe
                    if local_product.server_product_id:
                        remote_product = Product.objects.using('remote').filter(
                            pk=local_product.server_product_id
                        ).first()
                    
                    # 2) Si no hay server_product_id o no se encontró, buscar por code
                    if not remote_product and local_product.code:
                        remote_product = Product.objects.using('remote').filter(
                            code=local_product.code,
                            company_id=company.id
                        ).first()
                    
                    # 3) Si no hay code, buscar por nombre exacto
                    if not remote_product:
                        remote_product = Product.objects.using('remote').filter(
                            name=local_product.name,
                            company_id=company.id
                        ).first()

                    if not remote_product:
                        # Producto no existe en servidor remoto, crearlo
                        try:
                            with transaction.atomic(using='remote'):
                                # Resolver categoría remota
                                remote_cat = None
                                if local_product.cat_id:
                                    remote_cat = Category.objects.using('remote').filter(
                                        name=local_product.cat.name,
                                        company_id=company.id
                                    ).first()
                                    if not remote_cat:
                                        # Crear categoría si no existe
                                        remote_cat = Category.objects.using('remote').create(
                                            name=local_product.cat.name,
                                            desc=local_product.cat.desc,
                                            company_id=company.id
                                        )
                                
                                # Crear producto en servidor remoto
                                remote_product = Product.objects.using('remote').create(
                                    company_id=company.id,
                                    name=local_product.name,
                                    code=local_product.code,
                                    cat=remote_cat,
                                    cost_price=local_product.cost_price,
                                    pvp=local_product.pvp,
                                    iva_rate=local_product.iva_rate,
                                    pvp_final=local_product.pvp_final,
                                    unit=local_product.unit,
                                    stock=local_product.stock,
                                    min_stock=local_product.min_stock,
                                    track_stock=local_product.track_stock
                                )
                                
                                # Actualizar server_product_id localmente
                                Product.objects.using('default').filter(pk=local_product.pk).update(
                                    server_product_id=remote_product.pk,
                                    synced_to_server=True,
                                    last_stock_sync=timezone.now()
                                )
                                
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"  Producto creado en servidor: {local_product.name}"
                                    )
                                )
                                synced += 1
                        except Exception as e:
                            errors += 1
                            self.stderr.write(
                                f"Error creando producto {local_product.name} en servidor: {e}"
                            )
                        continue

                    # Comparar stocks
                    local_stock = local_product.stock or 0
                    remote_stock = remote_product.stock or 0
                    
                    if local_stock != remote_stock:
                        # Actualizar stock en servidor
                        with transaction.atomic(using='remote'):
                            Product.objects.using('remote').filter(pk=remote_product.pk).update(
                                stock=local_stock,
                                last_stock_sync=timezone.now()
                            )
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  Stock actualizado - {local_product.name}: "
                                    f"{remote_stock} → {local_stock}"
                                )
                            )
                            synced += 1
                    else:
                        # Stock ya está sincronizado, actualizar last_stock_sync localmente
                        Product.objects.using('default').filter(pk=local_product.pk).update(
                            last_stock_sync=timezone.now()
                        )

                except Exception as e:
                    errors += 1
                    self.stderr.write(
                        f"Error sincronizando stock del producto {local_product.name}: {e}"
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización de stock finalizada. Productos actualizados: {synced}. Errores: {errors}."
        ))
