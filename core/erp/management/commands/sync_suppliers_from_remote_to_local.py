from django.core.management.base import BaseCommand
from django.db import transaction, DatabaseError
from django.contrib.auth import get_user_model
from crum import get_current_user
import time
import random

from core.erp.models import Supplier, Company


def retry_on_database_lock(max_retries=3, base_delay=0.1):
    """
    Decorador para reintentar operaciones de base de datos cuando hay bloqueos
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except DatabaseError as e:
                    if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                        # Backoff exponencial con jitter aleatorio
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                        time.sleep(delay)
                        continue
                    else:
                        raise e
            return None
        return wrapper
    return decorator


class Command(BaseCommand):
    help = "Sincroniza proveedores desde la BD remota (remote) hacia la BD local (default). El servidor es la fuente de verdad."

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de la empresa a sincronizar (opcional, usa empresa activa por defecto)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronización de proveedores desde servidor remoto hacia POS local..."))

        # Determinar empresa activa
        try:
            company_id = options.get('company_id')
            active_company = None
            
            if company_id:
                active_company = Company.objects.using('default').filter(id=company_id).first()
                if active_company:
                    self.stdout.write(f"Empresa especificada: {active_company.name} (ID: {active_company.id})")
                else:
                    self.stdout.write(self.style.ERROR(f"No se encontró empresa con ID {company_id}"))
                    return
            else:
                User = get_user_model()
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

        # Obtener proveedores remotos de la empresa activa
        try:
            remote_qs = Supplier.objects.using('remote').filter(company_id=active_company.id).order_by('id')
            total = remote_qs.count()
            if not total:
                self.stdout.write(self.style.WARNING(f"No hay proveedores para la empresa {active_company.name} en la BD remota."))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error obteniendo proveedores remotos: {e}"))
            return

        synced = 0
        updated = 0
        errors = 0
        lock_errors = 0

        for remote_supplier in remote_qs:
            try:
                @retry_on_database_lock()
                def sync_supplier():
                    nonlocal synced, updated, errors, lock_errors
                    
                    try:
                        # Buscar proveedor local por CUIT o código
                        local_supplier = None
                        if remote_supplier.cuit:
                            local_supplier = Supplier.objects.using('default').filter(
                                company_id=active_company.id,
                                cuit=remote_supplier.cuit
                            ).first()
                        if not local_supplier and remote_supplier.code:
                            local_supplier = Supplier.objects.using('default').filter(
                                company_id=active_company.id,
                                code=remote_supplier.code
                            ).first()
                        
                        if local_supplier:
                            # Actualizar proveedor existente
                            local_supplier.name = remote_supplier.name
                            local_supplier.code = remote_supplier.code
                            local_supplier.cuit = remote_supplier.cuit
                            local_supplier.address = remote_supplier.address
                            local_supplier.phone = remote_supplier.phone
                            local_supplier.email = remote_supplier.email
                            local_supplier.is_active = remote_supplier.is_active
                            local_supplier.save(using='default')
                            updated += 1
                        else:
                            # Crear nuevo proveedor
                            Supplier.objects.using('default').create(
                                company_id=active_company.id,
                                name=remote_supplier.name,
                                code=remote_supplier.code,
                                cuit=remote_supplier.cuit,
                                address=remote_supplier.address,
                                phone=remote_supplier.phone,
                                email=remote_supplier.email,
                                is_active=remote_supplier.is_active,
                            )
                            synced += 1
                            
                    except DatabaseError as e:
                        if 'database is locked' in str(e).lower():
                            lock_errors += 1
                            raise
                        else:
                            errors += 1
                            self.stderr.write(f"Error de base de datos en proveedor {remote_supplier.id}: {e}")
                    except Exception as e:
                        errors += 1
                        self.stderr.write(f"Error sincronizando proveedor {remote_supplier.id}: {e}")
                
                sync_supplier()
                
            except DatabaseError:
                # Error de bloqueo ya manejado por el decorador
                pass
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error en proveedor {remote_supplier.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización de proveedores finalizada. "
            f"Creados: {synced}, Actualizados: {updated}, Errores: {errors}, Bloqueos: {lock_errors}"
        ))
