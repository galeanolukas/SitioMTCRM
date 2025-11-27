from django.core.management import call_command
from django.db import connections
from django.conf import settings
import socket

from core.erp.models import SyncLog


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
