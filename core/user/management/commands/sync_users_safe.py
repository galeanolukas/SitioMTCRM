from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connections, transaction
from core.erp.models import Company
from django.contrib.auth.models import Group, Permission

User = get_user_model()

class Command(BaseCommand):
    help = 'Sincroniza usuarios desde servidor remoto sin afectar sesiones activas'

    def handle(self, *args, **options):
        if 'remote' not in connections:
            self.stdout.write(self.style.ERROR('No hay conexión a base de datos remota configurada'))
            return

        try:
            # Sincronizar TODOS los usuarios (operadores y superusuarios)
            remote_users = User.objects.using('remote').filter(is_active=True)
            synced_count = 0
            
            for remote_user in remote_users:
                # Crear o crear usuario local
                local_user, created = User.objects.using('default').get_or_create(
                    username=remote_user.username,
                    defaults={
                        'email': remote_user.email,
                        'first_name': remote_user.first_name,
                        'last_name': remote_user.last_name,
                        'is_active': remote_user.is_active,
                        'is_staff': remote_user.is_staff or remote_user.is_superuser,
                        'is_superuser': remote_user.is_superuser,
                        'phone': getattr(remote_user, 'phone', ''),
                        'image': getattr(remote_user, 'image', None),
                        'password': remote_user.password,  # Copiar el hash del password del servidor
                    }
                )
                
                if not created:
                    # Actualizar datos existentes PERO NO password si tiene sesión activa
                    local_user.email = remote_user.email
                    local_user.first_name = remote_user.first_name
                    local_user.last_name = remote_user.last_name
                    local_user.is_active = remote_user.is_active
                    # Mantener is_staff y is_superuser del servidor
                    local_user.is_staff = remote_user.is_staff or remote_user.is_superuser
                    local_user.is_superuser = remote_user.is_superuser
                    local_user.phone = getattr(remote_user, 'phone', '')
                    if getattr(remote_user, 'image', None):
                        local_user.image = remote_user.image
                    
                    # SOLO actualizar password si es diferente o no hay sesión activa
                    # Para evitar desloguear usuarios activos
                    if local_user.password != remote_user.password:
                        # Verificar si hay sesiones activas para este usuario
                        from django.contrib.sessions.models import Session
                        active_sessions = 0
                        for session in Session.objects.all():
                            if str(local_user.id) in session.get_decoded().get('_auth_user_id', ''):
                                active_sessions += 1
                        
                        if active_sessions == 0:
                            # No hay sesiones activas, seguro actualizar password
                            local_user.password = remote_user.password
                        # else: Hay sesiones activas, no actualizar password
                
                # Asignar empresa si tiene
                if hasattr(remote_user, 'company') and remote_user.company:
                    try:
                        local_company = Company.objects.using('default').get(name=remote_user.company.name)
                        local_user.company = local_company
                    except Company.DoesNotExist:
                        pass
                
                # NO asignar password - mantener el existente para no afectar sesión
                
                local_user.save(using='default')
                
                # Asignar permisos según tipo de usuario
                if remote_user.is_superuser:
                    # Para superusuarios, asignar todos los permisos disponibles
                    all_permissions = Permission.objects.using('default').all()
                    local_user.user_permissions.set(all_permissions)
                else:
                    # Para operadores, copiar grupos y permisos del servidor
                    # 1) Obtener grupos del usuario remoto
                    remote_groups = remote_user.groups.all()
                    
                    if remote_groups:
                        # 2) Para cada grupo remoto, crear o obtener el grupo local
                        local_groups = []
                        for remote_group in remote_groups:
                            local_group, _ = Group.objects.using('default').get_or_create(
                                name=remote_group.name
                            )
                            # Copiar permisos del grupo remoto al local (buscando equivalentes)
                            local_permissions = []
                            for remote_perm in remote_group.permissions.all():
                                # Buscar permiso equivalente en base de datos local
                                try:
                                    local_perm = Permission.objects.using('default').get(
                                        content_type__app_label=remote_perm.content_type.app_label,
                                        codename=remote_perm.codename
                                    )
                                    local_permissions.append(local_perm)
                                except Permission.DoesNotExist:
                                    # Si no existe localmente, ignorar
                                    pass
                            
                            local_group.permissions.set(local_permissions)
                            local_groups.append(local_group)
                        
                        # 3) Asignar grupos al usuario local
                        local_user.groups.set(local_groups)
                    else:
                        # Si no tiene grupos, asignar grupo 'operadores' por defecto
                        op_group_local, _ = Group.objects.using('default').get_or_create(name='operadores')
                        local_user.groups.set([op_group_local])
                
                synced_count += 1
            
            self.stdout.write(self.style.SUCCESS(f'Usuarios sincronizados: {synced_count}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
