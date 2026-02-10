import time
import random
from django.core.management.base import BaseCommand
from django.db import connections, transaction
from django.utils import timezone
from core.erp.models import Product, Category, Company


class Command(BaseCommand):
    help = 'Sincronización segura de productos que preserva el stock local'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de la empresa a sincronizar (opcional, si no se especifica sincroniza todas)'
        )
        parser.add_argument(
            '--company-name',
            type=str,
            help='Nombre de la empresa a sincronizar (opcional, si no se especifica sincroniza todas)'
        )

    def retry_database_operation(self, operation, max_retries=5, base_delay=0.1):
        """Reintenta operaciones de base de datos con manejo de database locked"""
        for attempt in range(max_retries):
            try:
                return operation()
            except Exception as e:
                if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                    # Delay exponencial con jitter aleatorio
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                    time.sleep(delay)
                    continue
                else:
                    raise e
        return None

    def handle(self, *args, **options):
        if 'remote' not in connections:
            self.stdout.write(self.style.ERROR('No hay conexión a base de datos remota configurada'))
            return

        self.stdout.write(self.style.NOTICE("Iniciando sincronización segura de productos (preservando stock local)..."))
        
        try:
            # Obtener parámetros de empresa
            company_id = options.get('company_id')
            company_name = options.get('company_name')
            
            # Determinar qué empresas sincronizar
            if company_id:
                companies = Company.objects.filter(id=company_id)
            elif company_name:
                companies = Company.objects.filter(name=company_name)
            else:
                # Si no se especifica, sincronizar todas las empresas activas
                companies = Company.objects.filter(is_active=True)
            
            if not companies.exists():
                self.stdout.write(self.style.ERROR('No se encontraron empresas para sincronizar'))
                return
            
            # Sincronizar cada empresa
            for company in companies:
                self.stdout.write(f"\n{'='*60}")
                self.stdout.write(f"Sincronizando empresa: {company.name} (ID: {company.id})")
                self.stdout.write(f"{'='*60}")
                
                # Establecer como activa temporalmente
                company.is_active = True
                company.save()
                
                # Sincronizar productos de esta empresa
                self.sync_products_safe(company)
            
            self.stdout.write(self.style.SUCCESS("\nSincronización segura completada"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error en sincronización: {e}"))

    def sync_products_safe(self, active_company):
        """Sincroniza productos preservando el stock local"""
        
        # Obtener productos remotos usando SQL directo para evitar problemas de campos
        remote_products = self.get_remote_products(active_company.id)
        
        synced = 0
        updated = 0
        stock_preserved = 0
        error_count = 0
        
        self.stdout.write(f"Procesando {len(remote_products)} productos remotos...")
        
        for remote_prod_data in remote_products:
            try:
                with transaction.atomic(using='default'):
                    # Buscar producto local por código o nombre
                    local_prod = None
                    
                    if remote_prod_data.get('code'):
                        local_prod = Product.objects.using('default').filter(
                            code=remote_prod_data['code'],
                            company_id=active_company.id
                        ).first()
                    
                    if not local_prod and remote_prod_data.get('name'):
                        local_prod = Product.objects.using('default').filter(
                            name=remote_prod_data['name'],
                            company_id=active_company.id
                        ).first()

                    # Sincronizar categoría
                    local_cat = None
                    if remote_prod_data.get('cat_id'):
                        # Obtener categoría remota
                        remote_cat = self.get_remote_category(remote_prod_data['cat_id'])
                        if remote_cat:
                            local_cat = Category.objects.using('default').filter(
                                name=remote_cat['name'],
                                company_id=active_company.id
                            ).first()
                            
                            if not local_cat:
                                local_cat = Category.objects.using('default').create(
                                    name=remote_cat['name'],
                                    desc=remote_cat.get('description', ''),
                                    company_id=active_company.id,
                                    synced_to_server=True
                                )

                    if local_prod is None:
                        # Crear nuevo producto local con nombre único (con reintentos)
                        def create_product():
                            original_name = remote_prod_data['name']
                            name = original_name
                            counter = 1
                            
                            # Asegurar que el nombre sea único
                            while Product.objects.using('default').filter(name=name, company_id=active_company.id).exists():
                                name = f"{original_name} ({counter})"
                                counter += 1
                            
                            return Product.objects.using('default').create(
                                company_id=active_company.id,
                                cat=local_cat,
                                code=remote_prod_data.get('code', ''),
                                name=name,
                                pvp=remote_prod_data.get('pvp', 0),
                                pvp_final=remote_prod_data.get('pvp_final', 0),
                                cost_price=remote_prod_data.get('cost_price', 0),
                                unit=remote_prod_data.get('unit', 'unit'),
                                stock=remote_prod_data.get('stock', 0),
                                min_stock=remote_prod_data.get('min_stock', 5),
                                iva_rate=remote_prod_data.get('iva_rate', 0.21),
                                synced_from_server=True,
                                server_product_id=remote_prod_data['id'],
                                synced_to_server=True,
                            )
                        
                        try:
                            local_prod = self.retry_database_operation(create_product)
                            synced += 1
                            display_name = local_prod.name if local_prod.name != remote_prod_data['name'] else remote_prod_data['name']
                            self.stdout.write(f"✅ Producto '{display_name}' creado localmente (stock: {remote_prod_data.get('stock', 0)})")
                        except Exception as e:
                            error_count += 1
                            self.stdout.write(f"❌ Error creando producto '{remote_prod_data['name']}': {e}")
                            continue
                        
                    else:
                        # Producto existente: lógica segura de stock (con reintentos)
                        def update_product():
                            old_stock = local_prod.stock
                            remote_stock = remote_prod_data.get('stock', 0)
                            
                            # Campos que siempre se sincronizan (excepto stock)
                            local_prod.name = remote_prod_data['name']
                            local_prod.pvp = remote_prod_data.get('pvp', 0)
                            local_prod.pvp_final = remote_prod_data.get('pvp_final', 0)
                            local_prod.cost_price = remote_prod_data.get('cost_price', 0)
                            local_prod.unit = remote_prod_data.get('unit', 'unit')
                            local_prod.min_stock = remote_prod_data.get('min_stock', 5)
                            local_prod.iva_rate = remote_prod_data.get('iva_rate', 0.21)
                            local_prod.synced_from_server = True
                            
                            # Lógica segura de stock
                            if self.should_update_stock_safe(local_prod, remote_stock):
                                local_prod.stock = remote_stock
                                local_prod.last_stock_sync = timezone.now()
                                stock_changed = True
                            else:
                                stock_changed = False
                            
                            local_prod.save(using='default')
                            return old_stock, remote_stock, stock_changed
                        
                        try:
                            old_stock, remote_stock, stock_changed = self.retry_database_operation(update_product)
                            
                            if stock_changed:
                                updated += 1
                                self.stdout.write(f"📦 Stock actualizado '{remote_prod_data['name']}': {old_stock} → {remote_stock}")
                            else:
                                stock_preserved += 1
                                self.stdout.write(f"🔒 Stock preservado '{remote_prod_data['name']}': {old_stock} (local)")
                            
                            updated += 1
                            
                        except Exception as e:
                            error_count += 1
                            self.stdout.write(f"❌ Error actualizando producto '{remote_prod_data['name']}': {e}")
                            continue

                        # Actualizar campos de sincronización
                        local_prod.server_product_id = remote_prod_data['id']
                        local_prod.synced_to_server = True
                        
                        local_prod.save(using='default')
                            
            except Exception as e:
                self.stderr.write(f"❌ Error sincronizando producto {remote_prod_data.get('id', 'unknown')}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización segura finalizada.\n"
            f"Empresa: {active_company.name}\n"
            f"Productos creados: {synced}\n"
            f"Productos actualizados: {updated}\n"
            f"Stock preservado: {stock_preserved}\n"
            f"Total procesados: {len(remote_products)}\n"
            f"Errores: {error_count}"
        ))

    def get_remote_products(self, company_id):
        """Obtener productos remotos usando SQL directo"""
        from django.db import connections
        
        with connections['remote'].cursor() as cursor:
            cursor.execute("""
                SELECT id, name, code, pvp, pvp_final, cost_price, unit, stock, 
                       min_stock, iva_rate, cat_id, company_id
                FROM erp_product 
                WHERE company_id = %s
            """, [company_id])
            
            columns = [col[0] for col in cursor.description]
            products = []
            
            for row in cursor.fetchall():
                product_dict = dict(zip(columns, row))
                products.append(product_dict)
            
            return products

    def get_remote_category(self, cat_id):
        """Obtener categoría remota usando SQL directo"""
        from django.db import connections
        
        with connections['remote'].cursor() as cursor:
            cursor.execute("""
                SELECT id, name, "desc" as description
                FROM erp_category 
                WHERE id = %s
            """, [cat_id])
            
            row = cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
            return None

    def should_update_stock_safe(self, local_prod, remote_stock):
        """
        Decide si se debe actualizar el stock local con el del servidor
        Versión segura que no depende de campos nuevos
        """
        
        # Si el stock local es menor que el del servidor, preservar el local
        # (probablemente por ventas locales)
        if local_prod.stock < remote_stock:
            return False  # Preservar stock local (más bajo por ventas)
        
        # Si el stock local es mayor o igual, actualizar con el del servidor
        # (probablemente por reposición en el servidor)
        return True
