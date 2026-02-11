from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.erp.models import Company
from django.db import connections
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class Command(BaseCommand):
    help = "Sincronización de usuarios desde servidor remoto manteniendo contraseñas existentes"

    def handle(self, *args, **options):
        """Sincronizar usuarios desde servidor remoto manteniendo contraseñas locales existentes"""
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
            password_reset_count = 0
            
            for remote_user in remote_users:
                username = remote_user.get('username')
                if not username:
                    continue
                
                # Buscar usuario local
                try:
                    local_user = User.objects.get(username=username)
                    
                    # Actualizar datos básicos pero MANTENER la contraseña existente
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
                    self.stdout.write(f"✅ Usuario actualizado (contraseña mantenida): {username}")
                    
                except User.DoesNotExist:
                    # Crear nuevo usuario - aquí sí necesitamos contraseña temporal
                    # Pero primero verificar si realmente no existe para evitar errores de constraint
                    if User.objects.filter(username=username).exists():
                        self.stdout.write(f"⚠️  Usuario {username} ya existe (duplicado), omitiendo...")
                        continue
                    
                    # Intentar usar una contraseña predecible basada en el usuario
                    password = self.generate_predictable_password(username, remote_user)
                    
                    try:
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
                        self.stdout.write(f"✅ Usuario creado: {username} (contraseña: {password})")
                        
                        # Para usuarios importantes, establecer contraseña conocida
                        if username in ['admin', 'AcroActivo']:
                            new_user.set_password('admin123')
                            new_user.save()
                            password_reset_count += 1
                            self.stdout.write(f"🔐 Contraseña establecida para {username}: admin123")
                    
                    except Exception as create_error:
                        self.stdout.write(f"❌ Error creando usuario {username}: {create_error}")
                        continue
            
            self.stdout.write(f"\\n🎉 Sincronización completada:")
            self.stdout.write(f"  📊 Usuarios actualizados (contraseñas mantenidas): {synced_count}")
            self.stdout.write(f"  📊 Usuarios creados (nuevos): {created_count}")
            self.stdout.write(f"  🔐 Contraseñas establecidas (usuarios importantes): {password_reset_count}")
            self.stdout.write(f"  📊 Total procesados: {synced_count + created_count}")
            
            # Verificar resultado final
            total_local = User.objects.count()
            self.stdout.write(f"  📊 Total usuarios locales: {total_local}")
            
            # Mostrar usuarios importantes y sus contraseñas
            self.stdout.write(f"\\n🔐 USUARIOS IMPORTANTES:")
            important_users = ['admin', 'AcroActivo']
            for username in important_users:
                try:
                    user = User.objects.get(username=username)
                    self.stdout.write(f"  👤 {username} - 🟢 {'Activo' if user.is_active else 'Inactivo'} - 🔑 admin123")
                except User.DoesNotExist:
                    self.stdout.write(f"  ❌ {username} - No encontrado")
            
        except Exception as e:
            self.stdout.write(f"❌ Error en sincronización: {e}")
            logger.error(f"Error en sincronización de usuarios: {e}", exc_info=True)
    
    def generate_predictable_password(self, username, remote_user):
        """Genera una contraseña predecible basada en el usuario"""
        # Para usuarios conocidos, usar contraseñas estándar
        if username.lower() in ['admin', 'acroactivo']:
            return 'admin123'
        
        # Para otros usuarios, generar basada en información disponible
        first_name = remote_user.get('first_name', '').lower()
        last_name = remote_user.get('last_name', '').lower()
        
        if first_name and last_name:
            return f"{first_name}{last_name}123"
        elif first_name:
            return f"{first_name}123"
        elif username:
            return f"{username}123"
        else:
            # Último recurso: contraseña temporal aleatoria
            import random
            import string
            return ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
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
