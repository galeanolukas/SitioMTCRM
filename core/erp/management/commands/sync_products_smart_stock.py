from django.core.management.base import BaseCommand
from django.db import transaction, connections
from django.utils import timezone
from core.erp.models import Product, Category, Company


class Command(BaseCommand):
    help = 'Sincronización inteligente de productos que respeta el stock local'

    def handle(self, *args, **options):
        if 'remote' not in connections:
            self.stdout.write(self.style.ERROR('No hay conexión a base de datos remota configurada'))
            return

        self.stdout.write(self.style.NOTICE("Iniciando sincronización inteligente de productos (preservando stock local)..."))
        
        try:
            # Obtener empresa activa
            active_company = Company.objects.filter(is_active=True).first()
            if not active_company:
                self.stdout.write(self.style.ERROR('No hay empresa activa configurada'))
                return

            self.stdout.write(f"Empresa activa: {active_company.name}")
            
            # Sincronizar productos
            self.sync_products_smart_stock(active_company)
            
            self.stdout.write(self.style.SUCCESS("Sincronización inteligente completada"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error en sincronización: {e}"))

    def sync_products_smart_stock(self, active_company):
        """Sincroniza productos preservando el stock local cuando hay ventas"""
        
        # Obtener productos remotos
        remote_qs = Product.objects.using('remote').filter(company_id=active_company.id)
        total = remote_qs.count()
        synced = 0
        updated = 0
        stock_preserved = 0
        
        self.stdout.write(f"Procesando {total} productos remotos...")
        
        for remote_prod in remote_qs:
            try:
                with transaction.atomic(using='default'):
                    # Buscar producto local por código o nombre
                    local_prod = None
                    
                    if remote_prod.code:
                        local_prod = Product.objects.using('default').filter(
                            code=remote_prod.code,
                            company_id=active_company.id
                        ).first()
                    
                    if not local_prod and remote_prod.name:
                        local_prod = Product.objects.using('default').filter(
                            name=remote_prod.name,
                            company_id=active_company.id
                        ).first()

                    # Sincronizar categoría
                    local_cat = None
                    if remote_prod.cat_id:
                        local_cat = Category.objects.using('default').filter(
                            name=remote_prod.cat.name,
                            company_id=active_company.id
                        ).first()
                        
                        if not local_cat:
                            local_cat = Category.objects.using('default').create(
                                name=remote_prod.cat.name,
                                desc=getattr(remote_prod.cat, 'desc', ''),
                                company_id=active_company.id,
                                synced_to_server=True
                            )

                    if local_prod is None:
                        # Crear nuevo producto local (usa stock del servidor)
                        local_prod = Product.objects.using('default').create(
                            company_id=active_company.id,
                            cat=local_cat,
                            code=remote_prod.code,
                            name=remote_prod.name,
                            pvp=remote_prod.pvp,
                            pvp_final=remote_prod.pvp_final,
                            cost_price=getattr(remote_prod, 'cost_price', 0),
                            unit=remote_prod.unit,
                            stock=remote_prod.stock,  # Nuevo producto: usar stock del servidor
                            min_stock=getattr(remote_prod, 'min_stock', 5),
                            iva_rate=remote_prod.iva_rate,
                            synced_from_server=True,
                            server_product_id=remote_prod.id,
                            synced_to_server=True,
                            last_stock_sync=timezone.now(),  # Marcar timestamp de sincronización
                        )
                        synced += 1
                        self.stdout.write(f"✅ Producto '{remote_prod.name}' creado localmente (stock: {remote_prod.stock})")
                        
                    else:
                        # Producto existente: lógica inteligente de stock
                        stock_changed = False
                        old_stock = local_prod.stock
                        
                        # Campos que siempre se sincronizan (excepto stock)
                        fields_to_sync = ['name', 'pvp', 'pvp_final', 'cost_price', 'unit', 'min_stock', 'iva_rate']
                        
                        for field in fields_to_sync:
                            if hasattr(remote_prod, field):
                                setattr(local_prod, field, getattr(remote_prod, field))
                        
                        # LÓGICA INTELIGENTE DE STOCK
                        should_update_stock = self.should_update_stock(local_prod, remote_prod)
                        
                        if should_update_stock:
                            local_prod.stock = remote_prod.stock
                            local_prod.last_stock_sync = timezone.now()
                            stock_changed = True
                            self.stdout.write(f"📦 Stock actualizado '{remote_prod.name}': {old_stock} → {remote_prod.stock}")
                        else:
                            stock_preserved += 1
                            self.stdout.write(f"🔒 Stock preservado '{remote_prod.name}': {old_stock} (local)")
                        
                        # Actualizar campos de sincronización
                        local_prod.synced_from_server = True
                        local_prod.server_product_id = remote_prod.id
                        local_prod.synced_to_server = True
                        
                        local_prod.save()
                        updated += 1
                        
                        if stock_changed:
                            self.stdout.write(f"🔄 Producto '{remote_prod.name}' actualizado (stock modificado)")
                        else:
                            self.stdout.write(f"🔄 Producto '{remote_prod.name}' actualizado (stock preservado)")
                            
            except Exception as e:
                self.stderr.write(f"❌ Error sincronizando producto {remote_prod.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización inteligente finalizada.\n"
            f"Empresa: {active_company.name}\n"
            f"Productos creados: {synced}\n"
            f"Productos actualizados: {updated}\n"
            f"Stock preservado: {stock_preserved}\n"
            f"Total procesados: {total}"
        ))

    def should_update_stock(self, local_prod, remote_prod):
        """
        Decide si se debe actualizar el stock local con el del servidor
        Lógica: Solo actualizar si el stock del servidor es más reciente
        """
        
        # Si el producto local nunca se ha sincronizado el stock, usar el del servidor
        if not hasattr(local_prod, 'last_stock_sync') or not local_prod.last_stock_sync:
            return True
        
        # Si el producto local está marcado como modificado localmente, preservar
        if hasattr(local_prod, 'stock_modified_locally') and local_prod.stock_modified_locally:
            # Verificar cuánto tiempo pasó desde la última modificación local
            time_since_modification = timezone.now() - local_prod.stock_modified_locally
            # Si pasaron menos de 5 minutos, preservar el stock local
            if time_since_modification.total_seconds() < 300:  # 5 minutos
                return False
        
        # Si el stock del servidor es diferente y ha pasado tiempo suficiente, actualizar
        if local_prod.stock != remote_prod.stock:
            # Dar preferencia al stock local si es menor (probablemente por ventas)
            if local_prod.stock < remote_prod.stock:
                return False  # Preservar stock local (más bajo por ventas)
        
        # Por defecto, no actualizar el stock para preservar ventas locales
        return False
