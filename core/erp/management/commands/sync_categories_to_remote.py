from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Category, Company


class Command(BaseCommand):
    help = "Sincroniza categorias desde la BD local (default) hacia la BD remota (remote) con soporte de empresa."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de categorias hacia servidor remoto..."))

        # Obtener empresa activa
        try:
            from django.contrib.auth import get_user_model
            from crum import get_current_user
            User = get_user_model()
            
            # Intentar obtener empresa del usuario logueado actual
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

        # Filtrar categorías por empresa (si tienen company_id) o todas (si no)
        try:
            if Category.objects.filter(company__isnull=False).exists():
                # Hay categorías con empresa, sincronizar categorías no sincronizadas de TODAS las empresas
                local_qs = Category.objects.using('default').filter(synced_to_server=False).order_by('company_id', 'id')
                self.stdout.write(f"Sincronizando categorías no sincronizadas de todas las empresas")
            else:
                # Categorías sin empresa (modo compatibilidad), sincronizar todas no sincronizadas
                local_qs = Category.objects.using('default').filter(synced_to_server=False).order_by('id')
                self.stdout.write("Modo compatibilidad: sincronizando todas las categorías no sincronizadas")
        except Exception:
            # Si hay error en el filtro, sincronizar todas no sincronizadas
            local_qs = Category.objects.using('default').filter(synced_to_server=False).order_by('id')
            self.stdout.write("Fallback: sincronizando todas las categorías no sincronizadas")

        total = local_qs.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay categorias para sincronizar."))
            return

        synced = 0
        errors = 0

        for cat in local_qs:
            try:
                # Determinar company_id para sincronización
                company_id = getattr(cat, 'company_id', None) or active_company.id

                # Verificar que la empresa existe en el servidor remoto
                remote_company = Company.objects.using('remote').filter(id=company_id).first()
                if not remote_company:
                    self.stderr.write(f"❌ Error sincronizando categoria {cat.name}: La empresa ID {company_id} no existe en el servidor remoto")
                    errors += 1
                    # Marcar como sincronizada para no volver a intentar
                    cat.synced_to_server = True
                    cat.save(using='default')
                    continue

                # Buscar categoría existente por nombre y empresa primero
                remote_cat = Category.objects.using('remote').filter(name=cat.name, company_id=company_id).first()
                if not remote_cat:
                    # Fallback: buscar por nombre sin empresa (puede tener company_id=None)
                    remote_cat = Category.objects.using('remote').filter(name=cat.name).first()

                created = False
                if remote_cat:
                    # La categoría ya existe
                    if remote_cat.company_id != company_id:
                        # Actualizar la empresa de la categoría remota
                        if remote_cat.company_id is None:
                            self.stdout.write(f"⚠️ Categoría '{cat.name}' existía sin empresa, asignando a Empresa {company_id}")
                        else:
                            self.stdout.write(f"⚠️ Categoría '{cat.name}' existía (Empresa {remote_cat.company_id}), reasignando a Empresa {company_id}")
                        remote_cat.company_id = company_id
                        remote_cat.save(using='remote')
                        action = "actualizada (empresa reasignada)"
                    else:
                        self.stdout.write(f"✅ Categoría '{cat.name}' encontrada (Empresa {company_id})")
                        action = "reutilizada (ya existía)"
                else:
                    # Crear nueva categoría con empresa
                    try:
                        with transaction.atomic(using='remote'):
                            remote_cat = Category.objects.using('remote').create(
                                name=cat.name,
                                desc=cat.desc,
                                company_id=company_id
                            )
                        created = True
                        action = "creada"
                        self.stdout.write(f"✅ Categoría '{cat.name}' creada (Empresa: {company_id})")
                    except Exception as create_error:
                        # Si hay error de duplicado, buscar la categoría existente
                        if "duplicate key" in str(create_error) and "name" in str(create_error):
                            remote_cat = Category.objects.using('remote').filter(name=cat.name).first()
                            if remote_cat:
                                created = False
                                action = "reutilizada (error duplicado)"
                                self.stdout.write(f"⚠️ Categoría '{cat.name}' ya existía, reutilizando")
                            else:
                                raise create_error
                        else:
                            raise create_error
                
                # Marcar como sincronizada localmente
                cat.synced_to_server = True
                cat.save(using='default')
                
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"❌ Error sincronizando categoria {cat.name}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de categorias finalizada. Categorias sincronizadas: {synced} / {total}. Errores: {errors}."
        ))
