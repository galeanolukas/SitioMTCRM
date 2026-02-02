from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from crum import get_current_user

from core.erp.models import Product, Category, Company


class Command(BaseCommand):
    help = "Sincroniza productos desde la BD remota (remote) hacia la BD local (default). El servidor es la fuente de verdad."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronización de productos desde servidor remoto hacia POS local..."))

        # Determinar empresa activa (similar a otros comandos de sync)
        try:
            User = get_user_model()
            active_company = None
            current_user = get_current_user()
            
            if current_user and not current_user.is_anonymous and hasattr(current_user, 'company') and current_user.company:
                active_company = current_user.company
                self.stdout.write(f"Empresa del usuario logueado: {active_company.name} (ID: {active_company.id})")
            else:
                # Si no hay usuario logueado, buscar usuario con último login más reciente
                try:
                    user_with_last_login = User.objects.exclude(company__isnull=True).exclude(last_login__isnull=True).order_by('-last_login').first()
                    if user_with_last_login:
                        active_company = user_with_last_login.company
                        self.stdout.write(f"Usuario con último login: {user_with_last_login.username} ({user_with_last_login.last_login})")
                    else:
                        # Si nadie tiene login, usar el más reciente por fecha de creación
                        user_most_recent = User.objects.exclude(company__isnull=True).order_by('-date_joined').first()
                        if user_most_recent:
                            active_company = user_most_recent.company
                            self.stdout.write(f"Usuario más reciente: {user_most_recent.username}")
                except Exception:
                    # Último fallback: primer usuario con empresa
                    user_with_company = User.objects.exclude(company__isnull=True).first()
                    if user_with_company:
                        active_company = user_with_company.company
                        self.stdout.write(f"Usuario activo (fallback): {user_with_company.username}")
            
            if not active_company:
                # Fallback: usar primera empresa disponible
                active_company = Company.objects.first()
                self.stdout.write("Fallback: usando primera empresa disponible")
            
            if not active_company:
                self.stdout.write(self.style.ERROR("No se encontró ninguna empresa configurada."))
                return
                
            self.stdout.write(f"Empresa activa: {active_company.name} (ID: {active_company.id})")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error obteniendo empresa activa: {e}"))
            return

        # Obtener productos remotos de la empresa activa
        try:
            remote_qs = Product.objects.using('remote').filter(company_id=active_company.id).order_by('id')
            total = remote_qs.count()
            if not total:
                self.stdout.write(self.style.WARNING(f"No hay productos para la empresa {active_company.name} en la BD remota."))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error obteniendo productos remotos: {e}"))
            return

        synced = 0
        updated = 0
        errors = 0

        for remote_prod in remote_qs:
            try:
                with transaction.atomic(using='default'):
                    # Buscar producto local por código (método más confiable)
                    local_prod = None
                    
                    if remote_prod.code:
                        local_prod = Product.objects.using('default').filter(
                            code=remote_prod.code,
                            company_id=active_company.id
                        ).first()
                    
                    # Si no encuentra por código, buscar por nombre
                    if not local_prod and remote_prod.name:
                        local_prod = Product.objects.using('default').filter(
                            name=remote_prod.name,
                            company_id=active_company.id
                        ).first()

                    # Sincronizar categoría primero si existe
                    local_cat = None
                    if remote_prod.cat_id:
                        # Buscar categoría local equivalente
                        local_cat = Category.objects.using('default').filter(
                            name=remote_prod.cat.name,
                            company_id=active_company.id
                        ).first()
                        
                        if not local_cat:
                            # Crear categoría local si no existe
                            local_cat = Category.objects.using('default').create(
                                name=remote_prod.cat.name,
                                desc=getattr(remote_prod.cat, 'desc', ''),
                                company_id=active_company.id,
                                synced_to_server=True  # Viene del servidor
                            )
                            self.stdout.write(f"✅ Categoría '{remote_prod.cat.name}' creada localmente")

                    if local_prod is None:
                        # Crear nuevo producto local
                        local_prod = Product.objects.using('default').create(
                            company_id=active_company.id,
                            cat=local_cat,
                            code=remote_prod.code,
                            name=remote_prod.name,
                            pvp=remote_prod.pvp,
                            pvp_final=remote_prod.pvp_final,
                            cost_price=getattr(remote_prod, 'cost_price', 0),
                            unit=remote_prod.unit,
                            stock=remote_prod.stock,
                            min_stock=getattr(remote_prod, 'min_stock', 5),
                            iva_rate=remote_prod.iva_rate,
                            # Campos de sincronización
                            synced_from_server=True,
                            server_product_id=remote_prod.id,
                            synced_to_server=True,  # Ya está sincronizado
                        )
                        synced += 1
                        self.stdout.write(f"✅ Producto '{remote_prod.name}' creado localmente")
                    else:
                        # Actualizar producto existente
                        update_fields = ['name', 'pvp', 'pvp_final', 'cost_price', 'unit', 'stock', 
                                       'min_stock', 'iva_rate']
                        
                        for field in update_fields:
                            if hasattr(remote_prod, field):
                                setattr(local_prod, field, getattr(remote_prod, field))
                        
                        if local_cat:
                            local_prod.cat = local_cat
                        
                        # Actualizar campos de sincronización
                        local_prod.synced_from_server = True
                        local_prod.server_product_id = remote_prod.id
                        local_prod.synced_to_server = True
                        
                        local_prod.save()
                        updated += 1
                        self.stdout.write(f"🔄 Producto '{remote_prod.name}' actualizado localmente")

            except Exception as e:
                errors += 1
                self.stderr.write(f"❌ Error sincronizando producto {remote_prod.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización de productos (remoto → local) finalizada.\n"
            f"Empresa: {active_company.name}\n"
            f"Productos creados: {synced}\n"
            f"Productos actualizados: {updated}\n"
            f"Errores: {errors}\n"
            f"Total procesados: {total}"
        ))
