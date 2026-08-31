from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from core.erp.models import Company
from django.db import connections, OperationalError
from django.conf import settings
import logging
import time

from core.utils.media_sync import download_remote_image

logger = logging.getLogger(__name__)

User = get_user_model()

class Command(BaseCommand):
    help = 'Sincronizar usuarios desde servidor remoto con grupos y permisos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se haría sin ejecutar cambios',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY-RUN: No se realizarán cambios reales"))
        
        self.stdout.write("Iniciando sincronización de usuarios desde servidor remoto...")
        
        # 1. Sincronizar empresas PRIMERO (para mantener relaciones)
        self.sync_companies_from_server(dry_run)
        
        # 2. Sincronizar grupos
        self.sync_groups_from_server(dry_run)
        
        # 3. Sincronizar usuarios con sus grupos y empresas
        self.sync_users_with_groups(dry_run)
        
        # 4. Mostrar resumen final
        self.show_final_summary()

    def sync_companies_from_server(self, dry_run=False):
        """Sincronizar empresas desde el servidor remoto"""
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                # Obtener empresas del servidor
                cursor.execute('SELECT id, name, address, phone, email, is_active FROM erp_company ORDER BY id')
                empresas_servidor = cursor.fetchall()
                
                self.stdout.write(f"Empresas encontradas en servidor: {len(empresas_servidor)}")
                
                for empresa_id, name, address, phone, email, is_active in empresas_servidor:
                    try:
                        # Verificar si la empresa existe localmente
                        empresa_local = Company.objects.get(id=empresa_id)
                        
                        # Actualizar si es diferente
                        if (empresa_local.name != name or 
                            empresa_local.address != address or 
                            empresa_local.phone != phone or 
                            empresa_local.email != email or 
                            empresa_local.is_active != is_active):
                            
                            if not dry_run:
                                empresa_local.name = name
                                empresa_local.address = address
                                empresa_local.phone = phone
                                empresa_local.email = email
                                empresa_local.is_active = is_active
                                empresa_local.save()
                            
                    except Company.DoesNotExist:
                        # Crear empresa localmente
                        if not dry_run:
                            empresa_local = Company.objects.create(
                                id=empresa_id,
                                name=name,
                                address=address,
                                phone=phone,
                                email=email,
                                is_active=is_active
                            )
                
                # Sincronización finalizada
                if empresas_servidor:
                    self.stdout.write(self.style.SUCCESS(
                        f"Sincronización de empresas (servidor -> local) finalizada. "
                        f"Empresas sincronizadas: {len(empresas_servidor)}."
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        "No se encontraron empresas para sincronizar."
                    ))
                
        except Exception as e:
            self.stderr.write(f"Error sincronizando empresas: {e}")
            logger.error(f"Error sincronizando empresas: {e}", exc_info=True)

    def sync_groups_from_server(self, dry_run=False):
        """Sincronizar grupos y permisos desde el servidor"""
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                # Obtener grupos del servidor
                cursor.execute('SELECT id, name FROM auth_group ORDER BY name')
                grupos_servidor = cursor.fetchall()
                
                self.stdout.write(f"Grupos encontrados en servidor: {len(grupos_servidor)}")
                
                for grupo_id, grupo_name in grupos_servidor:
                    # Usar get_or_create para evitar problemas de concurrencia
                    grupo_local, created = Group.objects.get_or_create(
                        id=grupo_id,
                        defaults={'name': grupo_name}
                    )
                    
                    # Actualizar nombre si es diferente
                    if not created and grupo_local.name != grupo_name:
                        if not dry_run:
                            grupo_local.name = grupo_name
                            grupo_local.save()
                
                # Sincronizar permisos de grupos
                self.sync_group_permissions(grupos_servidor, dry_run)
                
        except Exception as e:
            self.stderr.write(f"Error sincronizando grupos: {e}")
            logger.error(f"Error sincronizando grupos: {e}", exc_info=True)

    def sync_group_permissions(self, grupos_servidor, dry_run=False):
        """Sincronizar permisos para cada grupo"""
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                for grupo_id, grupo_name in grupos_servidor:
                    # Obtener permisos del grupo en el servidor
                    cursor.execute('''
                        SELECT p.codename, p.name
                        FROM auth_group_permissions gp
                        JOIN auth_permission p ON gp.permission_id = p.id
                        WHERE gp.group_id = %s
                    ''', [grupo_id])
                    
                    permisos_servidor = cursor.fetchall()
                    
                    # Obtener grupo local
                    try:
                        grupo_local = Group.objects.get(id=grupo_id)
                        
                        # Limpiar permisos existentes y agregar los nuevos
                        if not dry_run:
                            grupo_local.permissions.clear()
                            
                            for codename, name in permisos_servidor:
                                try:
                                    permiso = Permission.objects.get(codename=codename)
                                    grupo_local.permissions.add(permiso)
                                except Permission.DoesNotExist:
                                    pass
                        
                    except Group.DoesNotExist:
                        self.stdout.write(f"    Grupo no encontrado localmente: {grupo_name}")
                        
        except Exception as e:
            self.stderr.write(f"Error sincronizando permisos de grupos: {e}")
            logger.error(f"Error sincronizando permisos de grupos: {e}", exc_info=True)

    def sync_users_with_groups(self, dry_run=False):
        """Sincronizar usuarios y asignarles sus grupos"""
        try:
            # Obtener usuarios del servidor con sus grupos
            remote_users = self.get_remote_users_with_groups()
            
            synced_count = 0
            created_count = 0
            
            for remote_user in remote_users:
                username = remote_user.get('username')
                image_path = remote_user.get('image')
                image_remote_url = f"{settings.REMOTE_SERVER_URL.rstrip('/')}/media/{image_path}" if image_path else ''
                
                try:
                    # Usuario existe, actualizar
                    local_user = User.objects.get(username=username)
                    
                    # Actualizar datos básicos
                    local_user.email = remote_user.get('email', local_user.email)
                    local_user.first_name = remote_user.get('first_name', local_user.first_name)
                    local_user.last_name = remote_user.get('last_name', local_user.last_name)
                    local_user.is_superuser = remote_user.get('is_superuser', local_user.is_superuser)
                    local_user.is_staff = remote_user.get('is_staff', local_user.is_staff)
                    local_user.is_active = remote_user.get('is_active', local_user.is_active)
                    
                    # NO sobrescribir contraseña de usuarios existentes.
                    # La contraseña se gestiona localmente; solo se copia del servidor
                    # cuando se crea un usuario nuevo (ver más abajo en User.DoesNotExist).
                    # EXCEPCIÓN: si el hash del servidor es diferente, sincronizar
                    # (ej: superusuario cambió la contraseña en el servidor)
                    remote_password = remote_user.get('password')
                    if remote_password and local_user.password != remote_password:
                        local_user.password = remote_password
                        if not dry_run:
                            local_user.save(update_fields=['password'])
                        self.stdout.write(f"  Contraseña actualizada para usuario '{username}' (hash cambiado en servidor)")
                    
                    # Asignar empresa si existe (manteniendo ID exacto del servidor)
                    company_id = remote_user.get('company_id')
                    if company_id:
                        try:
                            company = Company.objects.get(id=company_id)
                            local_user.company = company
                        except Company.DoesNotExist:
                            # La empresa no existe localmente, obtenerla del servidor y crearla
                            company_data = self.get_company_from_server(company_id)
                            if company_data:
                                # Crear empresa con ID específico del servidor
                                company = Company.objects.create(
                                    id=company_id,
                                    name=company_data.get('name', f'Empresa {company_id}'),
                                    address=company_data.get('address', ''),
                                    phone=company_data.get('phone', ''),
                                    email=company_data.get('email', ''),
                                    is_active=company_data.get('is_active', True)
                                )
                                local_user.company = company
                    
                    # Asignar imagen y URL remota
                    local_user.image = image_path
                    local_user.image_remote_url = image_remote_url

                    # Asignar grupos del usuario
                    self.assign_user_groups(local_user, remote_user.get('groups', []), dry_run)
                    
                    # Guardar cambios
                    if not dry_run:
                        local_user.save()
                        download_remote_image(image_path)
                    synced_count += 1
                    
                except User.DoesNotExist:
                    # Crear nuevo usuario con todos los datos del servidor
                    password_hash = remote_user.get('password')
                    if not password_hash:
                        continue
                    
                    new_user = User(
                        username=username,
                        email=remote_user.get('email', ''),
                        first_name=remote_user.get('first_name', ''),
                        last_name=remote_user.get('last_name', ''),
                        password=password_hash,  # Hash exacto del servidor
                        is_superuser=remote_user.get('is_superuser', False),
                        is_staff=remote_user.get('is_staff', False),
                        is_active=remote_user.get('is_active', True)
                    )
                    
                    # Asignar empresa si existe
                    company_id = remote_user.get('company_id')
                    if company_id:
                        try:
                            company = Company.objects.get(id=company_id)
                            new_user.company = company
                        except Company.DoesNotExist:
                            # La empresa no existe localmente, obtenerla del servidor y crearla
                            company_data = self.get_company_from_server(company_id)
                            if company_data:
                                # Crear empresa con ID específico del servidor
                                company = Company.objects.create(
                                    id=company_id,
                                    name=company_data.get('name', f'Empresa {company_id}'),
                                    address=company_data.get('address', ''),
                                    phone=company_data.get('phone', ''),
                                    email=company_data.get('email', ''),
                                    is_active=company_data.get('is_active', True)
                                )
                                new_user.company = company
                    
                    # Asignar imagen y URL remota
                    new_user.image = image_path
                    new_user.image_remote_url = image_remote_url

                    # Guardar usuario primero
                    if not dry_run:
                        new_user.save()
                        download_remote_image(image_path)
                    
                    # Asignar grupos del usuario
                    self.assign_user_groups(new_user, remote_user.get('groups', []), dry_run)
                    
                    created_count += 1
            
            # Resumen con colores como otras sincronizaciones
            total_processed = synced_count + created_count
            if created_count > 0 or synced_count > 0:
                self.stdout.write(self.style.SUCCESS(
                    f"Sincronización de usuarios (servidor -> local) finalizada. "
                    f"Usuarios sincronizados: {total_processed} (Creados: {created_count}, Actualizados: {synced_count})."
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    "No se encontraron usuarios para sincronizar."
                ))
            
        except Exception as e:
            self.stdout.write(f" Error en sincronización: {e}")
            logger.error(f"Error en sincronización de usuarios: {e}", exc_info=True)

    def assign_user_groups(self, user, group_names, dry_run=False):
        """Asignar grupos a un usuario"""
        try:
            # Limpiar grupos existentes
            if not dry_run:
                user.groups.clear()
            
            # Asignar nuevos grupos
            for group_name in group_names:
                try:
                    group = Group.objects.get(name=group_name)
                    if not dry_run:
                        user.groups.add(group)
                except Group.DoesNotExist:
                    pass
                    
        except Exception as e:
            self.stderr.write(f"Error asignando grupos al usuario {user.username}: {e}")

    def show_final_summary(self):
        """Mostrar resumen final de la sincronización"""
        try:
            # Mostrar grupos
            grupos = Group.objects.all()
            self.stdout.write(f"Grupos sincronizados: {grupos.count()}")
            for grupo in grupos:
                perm_count = grupo.permissions.count()
                user_count = grupo.user_set.count()
                self.stdout.write(f"  - {grupo.name}: {perm_count} permisos, {user_count} usuarios")
            
            # Mostrar usuarios con grupos
            usuarios = User.objects.all()
            self.stdout.write(f"Usuarios sincronizados: {usuarios.count()}")
            for usuario in usuarios:
                grupos_usuario = usuario.groups.all()
                nombres_grupos = [g.name for g in grupos_usuario]
                empresa_nombre = usuario.company.name if usuario.company else 'Sin empresa'
                self.stdout.write(f"  - {usuario.username}: {nombres_grupos if nombres_grupos else 'Sin grupos'} | Empresa: {empresa_nombre}")
                
        except Exception as e:
            self.stderr.write(f"Error mostrando resumen final: {e}")

    def get_remote_users_with_groups(self):
        """Obtener usuarios desde el servidor con sus grupos asignados"""
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.id, u.username, u.email, u.first_name, u.last_name, 
                           u.is_superuser, u.is_staff, u.is_active, u.company_id, 
                           u.password, u.date_joined, u.image, u.phone,
                           STRING_AGG(g.name, ',' ORDER BY g.name) as groups
                    FROM user_user u
                    LEFT JOIN user_user_groups ug ON u.id = ug.user_id
                    LEFT JOIN auth_group g ON ug.group_id = g.id
                    GROUP BY u.id, u.username, u.email, u.first_name, u.last_name,
                             u.is_superuser, u.is_staff, u.is_active, u.company_id,
                             u.password, u.date_joined, u.image, u.phone
                    ORDER BY u.username
                """)
                
                columns = [col[0] for col in cursor.description]
                users = []
                
                for row in cursor.fetchall():
                    user_dict = dict(zip(columns, row))
                    # Convertir grupos de string a lista
                    if user_dict['groups']:
                        user_dict['groups'] = [g.strip() for g in user_dict['groups'].split(',') if g.strip()]
                    else:
                        user_dict['groups'] = []
                    users.append(user_dict)
                
                return users
                
        except Exception as e:
            self.stderr.write(f"Error obteniendo usuarios remotos: {e}")
            logger.error(f"Error obteniendo usuarios remotos: {e}", exc_info=True)
            return []

    def get_company_from_server(self, company_id):
        """Obtener datos de una empresa específica desde el servidor remoto"""
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, address, phone, email, is_active
                    FROM erp_company
                    WHERE id = %s
                """, [company_id])
                
                row = cursor.fetchone()
                if row:
                    columns = ['id', 'name', 'address', 'phone', 'email', 'is_active']
                    company_dict = dict(zip(columns, row))
                    return company_dict
                else:
                    return None
                    
        except Exception as e:
            return None

    def get_remote_users_direct(self):
        """Obtener usuarios desde la base de datos remota con todos sus datos"""
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.id, u.username, u.email, u.first_name, u.last_name, 
                           u.is_superuser, u.is_staff, u.is_active, u.company_id, 
                           u.password, u.date_joined, u.image, u.phone
                    FROM user_user u
                    ORDER BY u.username
                """)
                
                columns = [col[0] for col in cursor.description]
                users = []
                
                for row in cursor.fetchall():
                    user_dict = dict(zip(columns, row))
                    users.append(user_dict)
                
                return users
                
        except Exception as e:
            logger.error(f"Error obteniendo usuarios remotos: {e}", exc_info=True)
            return []
