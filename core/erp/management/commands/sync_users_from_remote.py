from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.erp.models import Company
from django.db import connections
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class Command(BaseCommand):
    help = "Sincronización de usuarios desde servidor remoto (modo local)"

    def handle(self, *args, **options):
        """Sincronizar usuarios desde servidor remoto sin sobrescribir contraseñas locales"""
        try:
            self.stdout.write("🔍 Iniciando sincronización de usuarios desde servidor remoto...")
            
            # Obtener usuarios del servidor remoto directamente
            remote_users = self.get_remote_users_direct()
            
            if not remote_users:
                self.stdout.write("❌ No se encontraron usuarios en el servidor remoto")
                return
            
            self.stdout.write(f"✅ Se encontraron {len(remote_users)} usuarios en el servidor remoto")
            
            synced_count = 0
            created_count = 0
            
            for remote_user in remote_users:
                username = remote_user.get('username')
                if not username:
                    continue
                
                # Buscar usuario local
                try:
                    local_user = User.objects.get(username=username)
                    
                    # Actualizar datos básicos pero NO la contraseña
                    local_user.email = remote_user.get('email', local_user.email)
                    local_user.first_name = remote_user.get('first_name', local_user.first_name)
                    local_user.last_name = remote_user.get('last_name', local_user.last_name)
                    local_user.is_superuser = remote_user.get('is_superuser', local_user.is_superuser)
                    local_user.is_staff = remote_user.get('is_staff', local_user.is_staff)
                    local_user.is_active = remote_user.get('is_active', local_user.is_active)
                    
                    # Asignar empresa si existe
                    company_id = remote_user.get('company_id')
                    if company_id:
                        try:
                            company = Company.objects.get(id=company_id)
                            local_user.company = company
                        except Company.DoesNotExist:
                            self.stdout.write(f"⚠️  Empresa ID {company_id} no encontrada para usuario {username}")
                    
                    local_user.save()
                    synced_count += 1
                    self.stdout.write(f"✅ Usuario actualizado: {username}")
                    
                except User.DoesNotExist:
                    # Crear nuevo usuario
                    password = User.objects.make_random_password()  # Contraseña temporal
                    
                    new_user = User.objects.create_user(
                        username=username,
                        email=remote_user.get('email', ''),
                        password=password,
                        first_name=remote_user.get('first_name', ''),
                        last_name=remote_user.get('last_name', ''),
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
                            new_user.save()
                        except Company.DoesNotExist:
                            self.stdout.write(f"⚠️  Empresa ID {company_id} no encontrada para usuario {username}")
                    
                    created_count += 1
                    self.stdout.write(f"✅ Usuario creado: {username} (contraseña temporal: {password})")
            
            self.stdout.write(f"\\n🎉 Sincronización completada:")
            self.stdout.write(f"  📊 Usuarios actualizados: {synced_count}")
            self.stdout.write(f"  📊 Usuarios creados: {created_count}")
            self.stdout.write(f"  📊 Total procesados: {synced_count + created_count}")
            
            # Verificar resultado final
            total_local = User.objects.count()
            self.stdout.write(f"  📊 Total usuarios locales: {total_local}")
            
        except Exception as e:
            self.stdout.write(f"❌ Error en sincronización: {e}")
            logger.error(f"Error en sincronización de usuarios: {e}", exc_info=True)
    
    def get_remote_users_direct(self):
        """Obtener usuarios desde la base de datos remota directamente."""
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.id, u.username, u.email, u.first_name, u.last_name, 
                           u.is_superuser, u.is_staff, u.is_active, u.company_id
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
            self.stdout.write(f"❌ Error obteniendo usuarios remotos: {e}")
            logger.error(f"Error obteniendo usuarios remotos: {e}", exc_info=True)
            return []
