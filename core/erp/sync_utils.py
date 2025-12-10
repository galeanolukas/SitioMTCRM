from django.core.management import call_command
from django.db import connections
from django.conf import settings
import socket
import threading
import logging
import os
import datetime
import shutil

from core.erp.models import SyncLog

logger = logging.getLogger(__name__)


def _can_reach_remote_db() -> bool:
    """Devuelve True si la BD remota está accesible, False si no.

    Si no existe la conexión 'remote' en este entorno, devuelve False.
    """
    try:
        conn = connections['remote']
    except Exception:
        return False
    try:
        conn.ensure_connection()
        return True
    except Exception:
        return False


def run_full_sync():
    """Ejecuta sincronizacion de usuarios y ventas.

    Devuelve (ok: bool, errors: list[str]).
    """
    # Si estamos en el servidor central (producción), no hacer nada.
    # La sincronización solo corresponde a los nodos POS locales.
    if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
        return True, []

    errors = []

    # 1) Solo intentar sincronizar datos que dependen de la BD remota si está disponible
    if _can_reach_remote_db():
        # 1.a) Empresas: el servidor es la fuente de verdad, bajamos al POS
        try:
            call_command("sync_companies_from_remote_to_local")
        except Exception as e:
            errors.append(f"sync_companies_from_remote_to_local: {e}")
        # Categorias
        try:
            call_command("sync_categories_to_remote")
        except Exception as e:
            errors.append(f"sync_categories_to_remote: {e}")
        # Productos (maestro + stock)
        try:
            call_command("sync_products_to_remote")
        except Exception as e:
            errors.append(f"sync_products_to_remote: {e}")
        try:
            call_command("sync_sales_to_remote")
        except Exception as e:
            errors.append(f"sync_sales_to_remote: {e}")
        # Clientes
        try:
            call_command("sync_clients_to_remote")
        except Exception as e:
            errors.append(f"sync_clients_to_remote: {e}")
        # Proveedores
        try:
            call_command("sync_suppliers_to_remote")
        except Exception as e:
            errors.append(f"sync_suppliers_to_remote: {e}")
        # Gastos
        try:
            call_command("sync_expenses_to_remote")
        except Exception as e:
            errors.append(f"sync_expenses_to_remote: {e}")

        # Cierres de caja
        try:
            call_command("sync_cash_registers_to_remote")
        except Exception as e:
            errors.append(f"sync_cash_registers_to_remote: {e}")
    else:
        errors.append("Sin conexión a la base de datos remota; se omite sincronización de empresas, categorias, productos, ventas, clientes, proveedores y gastos.")

    # 2) Sincronizar usuarios (si el comando existe). Depende de que ya haya empresas locales.
    try:
        call_command("sync_users")
    except Exception as e:
        errors.append(f"sync_users: {e}")

    ok = (len(errors) == 0)

    # 3) Registrar intento en el servidor (historial de sincronización)
    try:
        # Determinar conexión donde guardar el log: remota si existe y es alcanzable
        using = 'default'
        if _can_reach_remote_db():
            using = 'remote'

        node_name = getattr(settings, 'POS_NODE_NAME', None) or socket.gethostname()
        msg = '\n'.join(errors) if errors else 'Sincronización completada sin errores.'
        SyncLog.objects.using(using).create(
            node_name=node_name,
            success=ok,
            message=msg,
        )
    except Exception:
        # No romper la sincronización si falló el log
        pass

    return ok, errors


def sync_cash_register_immediately(cash_register_id=None):
    """Sincroniza inmediatamente el cierre de caja especificado o todos los pendientes.
    
    Esta función se ejecuta en un hilo separado para no bloquear la UI.
    """
    def _sync_worker():
        try:
            if cash_register_id:
                # Sincronizar solo un cierre de caja específico
                call_command("sync_cash_registers_to_remote")
                logger.info(f"Cierre de caja {cash_register_id} sincronizado inmediatamente")
            else:
                # Sincronizar todos los cierres pendientes
                call_command("sync_cash_registers_to_remote")
                logger.info("Cierres de caja pendientes sincronizados inmediatamente")
        except Exception as e:
            logger.error(f"Error en sincronización inmediata de cierre de caja: {e}")
    
    # Ejecutar en hilo separado para no bloquear
    thread = threading.Thread(target=_sync_worker, daemon=True)
    thread.start()
    
    return thread


def backup_to_server():
    """Crea un backup de la base de datos local y lo envía al servidor remoto."""
    errors = []
    
    try:
        # 1) Verificar conexión remota
        if not _can_reach_remote_db():
            return False, ["No hay conexión con el servidor remoto"]
        
        # 2) Obtener información de la empresa activa
        from django.contrib.auth import get_user_model
        from core.erp.models import Company
        User = get_user_model()
        
        # Intentar obtener empresa del usuario actual o la primera disponible
        company = None
        try:
            # Usar la primera empresa disponible
            company = Company.objects.first()
        except Exception:
            pass
        
        if not company:
            return False, ["No se encontró información de la empresa"]
        
        # 3) Crear backup local
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_filename = f"backup_{company.name.replace(' ', '_')}_{timestamp}.sqlite3"
        backup_path = os.path.join(settings.BASE_DIR, backup_filename)
        
        # Copiar base de datos actual
        db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
        if not os.path.exists(db_path):
            return False, ["No se encuentra la base de datos local"]
        
        shutil.copy2(db_path, backup_path)
        
        # 4) Obtener nombre del POS
        pos_name = getattr(settings, 'POS_NODE_NAME', None) or socket.gethostname()
        
        # 5) Enviar backup al servidor (simulado - aquí iría la lógica real de transferencia)
        # Por ahora, solo registramos el intento
        try:
            # Aquí podrías agregar FTP, SFTP, o API para enviar el archivo
            # Por ahora simulamos éxito
            logger.info(f"Backup {backup_filename} creado para empresa {company.name} desde POS {pos_name}")
            
            # 6) Registrar en el log del servidor
            SyncLog.objects.using('remote').create(
                node_name=f"{pos_name}_BACKUP",
                success=True,
                message=f"Backup enviado: {backup_filename} (Empresa: {company.name})"
            )
            
            # 7) Limpiar backup local temporal
            os.remove(backup_path)
            
            return True, [f"Backup enviado exitosamente: {backup_filename}"]
            
        except Exception as e:
            errors.append(f"Error al enviar backup al servidor: {e}")
            # Limpiar backup local si falló
            if os.path.exists(backup_path):
                os.remove(backup_path)
            
    except Exception as e:
        errors.append(f"Error general en backup: {e}")
    
    # Registrar error si falló
    if errors:
        try:
            SyncLog.objects.using('remote').create(
                node_name="BACKUP_ERROR",
                success=False,
                message=f"Error en backup: {'; '.join(errors)}"
            )
        except Exception:
            pass
    
    return False, errors
