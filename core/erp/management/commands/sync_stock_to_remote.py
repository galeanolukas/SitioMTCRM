from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.erp.models import Product, Company


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
            
            # Obtener productos locales de esta empresa
            local_products = Product.objects.using('default').filter(company=company)
            
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
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Producto local {local_product.name} no tiene equivalente en servidor remoto"
                            )
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
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Stock sincronizado - {local_product.name}: {local_stock}"
                            )
                        )

                except Exception as e:
                    errors += 1
                    self.stderr.write(
                        f"Error sincronizando stock del producto {local_product.name}: {e}"
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización de stock finalizada. Productos actualizados: {synced}. Errores: {errors}."
        ))
