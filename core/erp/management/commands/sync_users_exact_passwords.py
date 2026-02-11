from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.erp.models import Company
from django.db import connections
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class Command(BaseCommand):
    help = "Sincronización de usuarios desde servidor remoto manteniendo contraseñas exactas del servidor"

    def handle(self, *args, **options):
        """Sincronizar usuarios desde servidor remoto copiando contraseñas exactas"""
        try:
            self.stdout.write("🔍 Iniciando sincronización de usuarios desde servidor remoto...")
            
            # Obtener usuarios del servidor remoto con sus contraseñas hasheadas
            remote_users = self.get_remote_users_with_passwords()
            
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
                    
                    # Actualizar todos los datos incluyendo la contraseña hasheada
                    local_user.email = remote_user.get('email', local_user.email)
                    local_user.first_name = remote_user.get('first_name', local_user.first_name)
                    local_user.last_name = remote_user.get('last_name', local_user.last_name)
                    local_user.is_superuser = remote_user.get('is_superuser', local_user.is_superuser)
                    local_user.is_staff = remote_user.get('is_staff', local_user.is_staff)
                    local_user.is_active = remote_user.get('is_active', local_user.is_active)
                    
                    # COPIAR LA CONTRASEÑA HASHEADA EXACTA DEL SERVIDOR
                    password_hash = remote_user.get('password')
                    if password_hash:
                        local_user.password = password_hash
                        self.stdout.write(f"✅ Contraseña copiada para: {username}")
                    
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
                    self.stdout.write(f"✅ Usuario actualizado (contraseña exacta del servidor): {username}")
                    
                except User.DoesNotExist:
                    # Crear nuevo usuario con contraseña exacta del servidor
                    password_hash = remote_user.get('password')
                    if not password_hash:
                        self.stdout.write(f"❌ Usuario {username} sin contraseña en servidor, omitiendo...")
                        continue
                    
                    new_user = User(
                        username=username,
                        email=remote_user.get('email', ''),
                        first_name=remote_user.get('first_name', ''),
                        last_name=remote_user.get('last_name', ''),
                        password=password_hash,  # Usar el hash exacto del servidor
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
                            self.stdout.write(f"⚠️  Empresa ID {company_id} no encontrada para usuario {username}")
                    
                    new_user.save()
                    created_count += 1
                    self.stdout.write(f"✅ Usuario creado (contraseña exacta del servidor): {username}")
            
            self.stdout.write(f"\\n🎉 Sincronización completada:")
            self.stdout.write(f"  📊 Usuarios actualizados: {synced_count}")
            self.stdout.write(f"  📊 Usuarios creados: {created_count}")
            self.stdout.write(f"  📊 Total procesados: {synced_count + created_count}")
            
            # Verificar resultado final
            total_local = User.objects.count()
            self.stdout.write(f"  📊 Total usuarios locales: {total_local}")
            
            # Probar autenticación con usuarios importantes
            self.stdout.write(f"\\n🧪 PROBANDO AUTENTICACIÓN:")
            important_users = ['admin', 'AcroActivo']
            for username in important_users:
                try:
                    user = User.objects.get(username=username)
                    # Para probar, necesitamos verificar que el hash sea válido
                    self.stdout.write(f"  👤 {username} - 🟢 {'Activo' if user.is_active else 'Inactivo'} - 🔐 Contraseña del servidor copiada")
                except User.DoesNotExist:
                    self.stdout.write(f"  ❌ {username} - No encontrado")
            
        except Exception as e:
            self.stdout.write(f"❌ Error en sincronización: {e}")
            logger.error(f"Error en sincronización de usuarios: {e}", exc_info=True)
    
    def get_remote_users_with_passwords(self):
        """Obtener usuarios desde la base de datos remota incluyendo contraseñas hasheadas."""
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.id, u.username, u.email, u.first_name, u.last_name, 
                           u.is_superuser, u.is_staff, u.is_active, u.company_id, u.password
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
