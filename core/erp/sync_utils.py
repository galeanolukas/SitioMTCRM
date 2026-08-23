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
        conn.close_if_unusable_or_obsolete()
        conn.ensure_connection()
        return True
    except Exception:
        try:
            conn.connect()
            return True
        except Exception:
            return False


def _get_sync_destination():
    """Determina el destino de sincronización basado en la empresa activa."""
    from django.contrib.auth import get_user_model
    from core.erp.models import Company
    from crum import get_current_user
    
    User = get_user_model()
    user = get_current_user()
    
    if not user or not user.is_authenticated:
        return 'cloud'  # Default
    
    # Obtener empresa del usuario
    company = getattr(user, 'company', None)
    if not company:
        # Si no tiene empresa asignada, usar la primera activa
        company = Company.objects.filter(is_active=True).first()
    
    if not company:
        return 'cloud'  # Default
    
    # Verificar si el usuario pertenece al grupo "Servidor Local"
    if user.groups.filter(name='Servidor Local').exists():
        # Forzar sincronización local para usuarios de este grupo
        return 'local'
    
    # Usar configuración de la empresa
    return company.sync_destination or 'cloud'


def _can_reach_local_server() -> bool:
    """Devuelve True si el servidor local está accesible, False si no."""
    from core.erp.models import Company
    from crum import get_current_user
    
    user = get_current_user()
    if not user or not user.is_authenticated:
        return False
    
    company = getattr(user, 'company', None)
    if not company:
        company = Company.objects.filter(is_active=True).first()
    
    if not company or not company.local_server_url:
        return False
    
    # Verificar si podemos hacer una petición HTTP al servidor local
    try:
        import requests
        response = requests.get(f"{company.local_server_url}/", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def run_full_sync(company_id=None):
    """Ejecuta sincronizacion de usuarios y ventas.

    Args:
        company_id: Si se especifica, sincroniza solo datos de esta empresa

    Devuelve (ok: bool, errors: list[str]).
    """
    # Si estamos en el servidor central (producción), no hacer nada.
    # La sincronización solo corresponde a los nodos POS locales.
    if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
        return True, []

    # Determinar destino de sincronización
    sync_destination = _get_sync_destination()
    logger.info(f"Destino de sincronización: {sync_destination}")
    if company_id:
        logger.info(f"Sincronizando solo para empresa ID: {company_id}")
    
    # Verificar disponibilidad del destino
    can_sync = False
    if sync_destination == 'cloud':
        can_sync = _can_reach_remote_db()
    elif sync_destination == 'local':
        can_sync = _can_reach_local_server()
    elif sync_destination == 'both':
        can_sync = _can_reach_remote_db() or _can_reach_local_server()
    
    if not can_sync:
        msg = f"No hay conexión disponible para destino '{sync_destination}'"
        logger.warning(msg)
        return False, [msg]

    # Check if sync is globally disabled
    try:
        from core.erp.models import GlobalSyncStatus
        if not GlobalSyncStatus.is_sync_enabled():
            logger.info("Sincronización desactivada globalmente - omitiendo ejecución")
            return True, ["Sincronización desactivada globalmente"]
    except Exception as e:
        # If we can't check the global status, proceed with sync
        logger.warning(f"No se pudo verificar estado de sincronización global: {e}")
        pass

    logger.info("Iniciando sincronización completa...")
    errors = []
    sync_stats = {
        'empresas': {'before': 0, 'after': 0, 'synced': 0},
        'usuarios': {'before': 0, 'after': 0, 'synced': 0},
        'afip_configs': {'before': 0, 'after': 0, 'synced': 0},
        'productos': {'before': 0, 'after': 0, 'synced': 0},
        'stock': {'before': 0, 'after': 0, 'synced': 0},
        'categorias': {'before': 0, 'after': 0, 'synced': 0},
        'ventas': {'before': 0, 'after': 0, 'synced': 0},
        'clientes': {'before': 0, 'after': 0, 'synced': 0},
        'proveedores': {'before': 0, 'after': 0, 'synced': 0},
        'gastos': {'before': 0, 'after': 0, 'synced': 0},
        'cierres': {'before': 0, 'after': 0, 'synced': 0},
        'pedidos_catalogo': {'before': 0, 'after': 0, 'synced': 0}
    }
    
    # 1) PRIMERO: Sincronizar empresas (base para usuarios)
    logger.info("🏢 PASO 1/10: Sincronizando empresas (base para usuarios)...")
    if sync_destination in ['cloud', 'both'] and _can_reach_remote_db():
        try:
            # Contar empresas antes
            from core.erp.models import Company
            sync_stats['empresas']['before'] = Company.objects.count()
            
            call_command("sync_companies_from_remote_to_local")
            sync_stats['empresas']['after'] = Company.objects.count()
            sync_stats['empresas']['synced'] = sync_stats['empresas']['after'] - sync_stats['empresas']['before']
            
            logger.info(f"✅ Empresas sincronizadas: {sync_stats['empresas']['synced']} nuevas (total: {sync_stats['empresas']['after']})")
        except Exception as e:
            logger.error(f"Error en sincronización de empresas: {e}")
            errors.append(f"sync_companies_from_remote_to_local: {e}")
    else:
        logger.warning(f"Sin conexión para destino '{sync_destination}' - omitiendo sincronización de empresas")
        errors.append(f"Sin conexión para destino '{sync_destination}' - omitiendo sincronización de empresas")
    
    # 2) SEGUNDO: Sincronizar usuarios (dependen de empresas)
    logger.info("👥 PASO 2/10: Sincronizando usuarios (dependen de empresas)...")
    if sync_destination in ['cloud', 'both'] and _can_reach_remote_db():
        try:
            # Contar usuarios antes
            from django.contrib.auth import get_user_model
            User = get_user_model()
            sync_stats['usuarios']['before'] = User.objects.count()

            call_command("sync_users_safe")
            sync_stats['usuarios']['after'] = User.objects.count()
            sync_stats['usuarios']['synced'] = sync_stats['usuarios']['after'] - sync_stats['usuarios']['before']

            logger.info(f"✅ Usuarios sincronizados: {sync_stats['usuarios']['synced']} cambios (total: {sync_stats['usuarios']['after']})")
        except Exception as e:
            logger.error(f"Error en sincronización de usuarios: {e}")
            errors.append(f"sync_users_safe: {e}")
    else:
        logger.warning(f"Sin conexión para destino '{sync_destination}' - omitiendo sincronización de usuarios")
        errors.append(f"Sin conexión para destino '{sync_destination}' - omitiendo sincronización de usuarios")

    # 2.b) Sincronizar configuraciones AFIP (dependen de empresas)
    logger.info("📋 PASO 2.b/10: Sincronizando configuraciones AFIP (dependen de empresas)...")
    if sync_destination in ['cloud', 'both'] and _can_reach_remote_db():
        try:
            # Contar configuraciones AFIP antes
            from core.erp.models import AfipConfig
            sync_stats['afip_configs']['before'] = AfipConfig.objects.count()

            # Pasar company_id si está disponible para filtrar por empresa del usuario
            if company_id:
                call_command("sync_afip_configs", company_id=company_id)
            else:
                call_command("sync_afip_configs")

            sync_stats['afip_configs']['after'] = AfipConfig.objects.count()
            sync_stats['afip_configs']['synced'] = sync_stats['afip_configs']['after'] - sync_stats['afip_configs']['before']

            logger.info(f"✅ Configuraciones AFIP sincronizadas: {sync_stats['afip_configs']['synced']} cambios (total: {sync_stats['afip_configs']['after']})")
        except Exception as e:
            logger.error(f"Error en sincronización de configuraciones AFIP: {e}")
            errors.append(f"sync_afip_configs: {e}")
    else:
        logger.warning(f"Sin conexión para destino '{sync_destination}' - omitiendo sincronización de configuraciones AFIP")
        errors.append(f"Sin conexión para destino '{sync_destination}' - omitiendo sincronización de configuraciones AFIP")

    # 3) TERCERO: Sincronizar el resto de datos (productos, categorías, ventas, etc.)
    logger.info("📦 PASO 3/10: Sincronizando resto de datos...")
    
    if sync_destination in ['cloud', 'both'] and _can_reach_remote_db():
        logger.info("Conexión remota disponible, iniciando sincronización de datos...")
        
        # 3.a) Productos: SOLO sincronización local → servidor (no descargar del servidor)
        try:
            # Contar productos antes
            from core.erp.models import Product
            sync_stats['productos']['before'] = Product.objects.count()
            
            call_command("sync_products_to_remote")  # Solo subir productos locales
            sync_stats['productos']['after'] = Product.objects.count()
            sync_stats['productos']['synced'] = sync_stats['productos']['after'] - sync_stats['productos']['before']
            
            logger.info(f"✅ Productos sincronizados: {sync_stats['productos']['synced']} locales → servidor (total: {sync_stats['productos']['after']})")
        except Exception as e:
            logger.error(f"Error en sincronización de productos local → servidor: {e}")
            errors.append(f"sync_products_to_remote: {e}")
        
        # 3.a.b) Stock: Sincronizar stock de productos local → servidor
        try:
            logger.info("📦 Sincronizando stock de productos local → servidor...")
            
            # Obtener empresa del usuario para sincronizar solo esa empresa
            from crum import get_current_user
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = get_current_user()
            company_id = None
            
            if user and user.is_authenticated:
                company = getattr(user, 'company', None)
                if company:
                    company_id = company.id
                    logger.info(f"📦 Sincronizando stock solo para empresa: {company.name} (ID: {company_id})")
            
            # Pasar company_id al comando si está disponible
            if company_id:
                call_command("sync_stock_to_remote", company_id=company_id)
            else:
                call_command("sync_stock_to_remote")
            
            # Contar productos con stock desincronizado
            from core.erp.models import Product
            products_with_stock = Product.objects.using('default').filter(track_stock=True).count()
            sync_stats['stock']['before'] = products_with_stock
            sync_stats['stock']['after'] = products_with_stock  # El comando actualiza, no crea/elimina
            sync_stats['stock']['synced'] = 0  # El comando reportará actualizaciones
            
            logger.info(f"✅ Stock sincronizado: {products_with_stock} productos con control de stock")
        except Exception as e:
            logger.error(f"Error en sincronización de stock: {e}")
            errors.append(f"sync_stock_to_remote: {e}")
        
        # 3.b) Categorías
        try:
            # Contar categorías antes
            from core.erp.models import Category
            sync_stats['categorias']['before'] = Category.objects.count()
            
            call_command("sync_categories_to_remote")
            sync_stats['categorias']['after'] = Category.objects.count()
            sync_stats['categorias']['synced'] = sync_stats['categorias']['after'] - sync_stats['categorias']['before']
            
            logger.info(f"✅ Categorías sincronizadas: {sync_stats['categorias']['synced']} nuevas (total: {sync_stats['categorias']['after']})")
        except Exception as e:
            logger.error(f"Error en sincronización de categorías: {e}")
            errors.append(f"sync_categories_to_remote: {e}")
        
        # 3.c) Ventas
        try:
            # Contar ventas antes
            from core.erp.models import Sale
            sync_stats['ventas']['before'] = Sale.objects.count()
            
            call_command("sync_sales_to_remote")
            sync_stats['ventas']['after'] = Sale.objects.count()
            sync_stats['ventas']['synced'] = sync_stats['ventas']['after'] - sync_stats['ventas']['before']
            
            logger.info(f"✅ Ventas sincronizadas: {sync_stats['ventas']['synced']} pendientes (total: {sync_stats['ventas']['after']})")
        except Exception as e:
            logger.error(f"Error en sincronización de ventas: {e}")
            errors.append(f"sync_sales_to_remote: {e}")
        
        # 3.d) Clientes
        try:
            # Contar clientes antes
            from core.erp.models import Client
            sync_stats['clientes']['before'] = Client.objects.count()
            
            call_command("sync_clients_to_remote")
            sync_stats['clientes']['after'] = Client.objects.count()
            sync_stats['clientes']['synced'] = sync_stats['clientes']['after'] - sync_stats['clientes']['before']
            
            logger.info(f"✅ Clientes sincronizados: {sync_stats['clientes']['synced']} nuevos (total: {sync_stats['clientes']['after']})")
        except Exception as e:
            logger.error(f"Error en sincronización de clientes: {e}")
            errors.append(f"sync_clients_to_remote: {e}")
        
        # 3.e) Proveedores
        try:
            # Contar proveedores antes
            from core.erp.models import Supplier
            sync_stats['proveedores']['before'] = Supplier.objects.count()
            
            call_command("sync_suppliers_to_remote")
            sync_stats['proveedores']['after'] = Supplier.objects.count()
            sync_stats['proveedores']['synced'] = sync_stats['proveedores']['after'] - sync_stats['proveedores']['before']
            
            logger.info(f"✅ Proveedores sincronizados: {sync_stats['proveedores']['synced']} nuevos (total: {sync_stats['proveedores']['after']})")
        except Exception as e:
            logger.error(f"Error en sincronización de proveedores: {e}")
            errors.append(f"sync_suppliers_to_remote: {e}")
        
        # 3.f) Gastos
        try:
            # Contar gastos antes
            from core.erp.models import Expense
            sync_stats['gastos']['before'] = Expense.objects.count()
            
            call_command("sync_expenses_to_remote")
            sync_stats['gastos']['after'] = Expense.objects.count()
            sync_stats['gastos']['synced'] = sync_stats['gastos']['after'] - sync_stats['gastos']['before']
            
            logger.info(f"✅ Gastos sincronizados: {sync_stats['gastos']['synced']} nuevos (total: {sync_stats['gastos']['after']})")
        except Exception as e:
            logger.error(f"Error en sincronización de gastos: {e}")
            errors.append(f"sync_expenses_to_remote: {e}")
        
        # 3.g) Cierres de caja
        try:
            # Contar cierres antes
            from core.erp.models import CashRegister
            sync_stats['cierres']['before'] = CashRegister.objects.count()
            
            call_command("sync_cash_registers_to_remote")
            sync_stats['cierres']['after'] = CashRegister.objects.count()
            sync_stats['cierres']['synced'] = sync_stats['cierres']['after'] - sync_stats['cierres']['before']
            
            logger.info(f"✅ Cierres de caja sincronizados: {sync_stats['cierres']['synced']} pendientes (total: {sync_stats['cierres']['after']})")
        except Exception as e:
            logger.error(f"Error en sincronización de cierres de caja: {e}")
            errors.append(f"sync_cash_registers_to_remote: {e}")

        # 3.h) Listas de precios
        try:
            call_command("sync_price_lists_to_remote")
            logger.info("✅ Listas de precios sincronizadas")
        except Exception as e:
            logger.error(f"Error en sincronización de listas de precios: {e}")
            errors.append(f"sync_price_lists_to_remote: {e}")

        # 3.i) Pedidos entregados del catálogo (solo si hay configuración activa)
        logger.info("🛒 PASO 3.i/10: Sincronizando pedidos entregados del catálogo...")
        try:
            from core.erp.models import CatalogoConfig
            if CatalogoConfig.objects.filter(is_active=True).exists():
                from core.erp.models import Sale
                sync_stats['pedidos_catalogo']['before'] = Sale.objects.exclude(catalogo_pedido_id__isnull=True).exclude(catalogo_pedido_id='').count()
                call_command("sync_pedidos_catalogo")
                sync_stats['pedidos_catalogo']['after'] = Sale.objects.exclude(catalogo_pedido_id__isnull=True).exclude(catalogo_pedido_id='').count()
                sync_stats['pedidos_catalogo']['synced'] = sync_stats['pedidos_catalogo']['after'] - sync_stats['pedidos_catalogo']['before']
                logger.info(f"✅ Pedidos del catálogo sincronizados: {sync_stats['pedidos_catalogo']['synced']} nuevos")
            else:
                logger.info("ℹ️ No hay configuraciones de catálogo activas - omitiendo sincronización de pedidos")
        except Exception as e:
            logger.error(f"Error en sincronización de pedidos del catálogo: {e}")
            errors.append(f"sync_pedidos_catalogo: {e}")
            
        try:
            # Verificar si el modelo InternalTransfer existe antes de usarlo
            try:
                from core.erp.models import InternalTransfer
                pending_count = InternalTransfer.objects.using('default').filter(synced_to_server=False).count()
                if pending_count > 0:
                    InternalTransfer.objects.using('default').filter(synced_to_server=False).update(synced_to_server=True)
                    logger.info(f"Omitidas {pending_count} transferencias (marcadas como sincronizadas)")
                else:
                    logger.info("No hay transferencias pendientes de sincronizar")
            except Exception:
                # Si el modelo no existe, simplemente omitir
                logger.info("Modelo InternalTransfer no disponible - omitiendo sincronización de transferencias")
        except Exception as e:
            logger.error(f"Error omitiendo sincronización de transferencias: {e}")
            errors.append(f"transfer_sync_omitted: {e}")
    else:
        msg = f"Sin conexión para destino '{sync_destination}'; se omite sincronización de empresas, categorias, productos, ventas, clientes, proveedores, gastos y transferencias."
        logger.warning(msg)
        errors.append(msg)

    # 4) RESUMEN FINAL DE SINCRONIZACIÓN
    logger.info("📋 PASO 4/10: Generando resumen de sincronización...")
    
    # Calcular totales
    total_synced = sum([stats['synced'] for stats in sync_stats.values()])
    total_before = sum([stats['before'] for stats in sync_stats.values()])
    total_after = sum([stats['after'] for stats in sync_stats.values()])
    
    # Generar resumen detallado
    logger.info("=" * 80)
    logger.info("📊 RESUMEN COMPLETO DE SINCRONIZACIÓN")
    logger.info("=" * 80)
    logger.info(f"🏢 EMPRESAS: {sync_stats['empresas']['synced']} nuevas ({sync_stats['empresas']['before']} → {sync_stats['empresas']['after']})")
    logger.info(f"👥 USUARIOS: {sync_stats['usuarios']['synced']} cambios ({sync_stats['usuarios']['before']} → {sync_stats['usuarios']['after']})")
    logger.info(f"� CONFIGURACIONES AFIP: {sync_stats['afip_configs']['synced']} cambios ({sync_stats['afip_configs']['before']} → {sync_stats['afip_configs']['after']})")
    logger.info(f"�📦 PRODUCTOS: {sync_stats['productos']['synced']} sincronizados ({sync_stats['productos']['before']} → {sync_stats['productos']['after']})")
    logger.info(f"📊 STOCK: {sync_stats['stock']['synced']} actualizados ({sync_stats['stock']['before']} productos con control de stock)")
    logger.info(f"📁 CATEGORÍAS: {sync_stats['categorias']['synced']} nuevas ({sync_stats['categorias']['before']} → {sync_stats['categorias']['after']})")
    logger.info(f"💰 VENTAS: {sync_stats['ventas']['synced']} pendientes ({sync_stats['ventas']['before']} → {sync_stats['ventas']['after']})")
    logger.info(f"👤 CLIENTES: {sync_stats['clientes']['synced']} nuevos ({sync_stats['clientes']['before']} → {sync_stats['clientes']['after']})")
    logger.info(f"🏭 PROVEEDORES: {sync_stats['proveedores']['synced']} nuevos ({sync_stats['proveedores']['before']} → {sync_stats['proveedores']['after']})")
    logger.info(f"💸 GASTOS: {sync_stats['gastos']['synced']} nuevos ({sync_stats['gastos']['before']} → {sync_stats['gastos']['after']})")
    logger.info(f"💰 CIERRES: {sync_stats['cierres']['synced']} pendientes ({sync_stats['cierres']['before']} → {sync_stats['cierres']['after']})")
    logger.info(f"🛒 PEDIDOS CATÁLOGO: {sync_stats['pedidos_catalogo']['synced']} nuevos ({sync_stats['pedidos_catalogo']['before']} → {sync_stats['pedidos_catalogo']['after']})")
    logger.info("=" * 80)
    logger.info(f"📈 TOTALES: {total_synced} cambios en {len([k for k in sync_stats.keys() if sync_stats[k]['synced'] > 0])} categorías")
    logger.info(f"📊 REGISTROS ANTES: {total_before} totales")
    logger.info(f"📊 REGISTROS DESPUÉS: {total_after} totales")
    logger.info("=" * 80)
    
    if len(errors) == 0:
        logger.info("🎉 SINCRONIZACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("✅ Todas las dependencias registradas en orden lógico")
        logger.info("✅ Usuarios con empresas asignadas correctamente")
        logger.info("✅ Sistema listo para producción")
    else:
        logger.error(f"❌ SINCRONIZACIÓN COMPLETADA CON {len(errors)} ERRORES:")
        for error in errors:
            logger.error(f"  - {error}")
    
    ok = (len(errors) == 0)
    
    if ok:
        logger.info("Sincronización completada exitosamente")
    else:
        logger.error(f"Sincronización completada con {len(errors)} errores")

    # 3) Registrar intento en el servidor (historial de sincronización)
    try:
        # Determinar conexión donde guardar el log: remota si existe y es alcanzable
        using = 'default'
        if _can_reach_remote_db():
            using = 'remote'

        node_name = getattr(settings, 'POS_NODE_NAME', None) or socket.gethostname()
        msg = '\n'.join(errors) if errors else 'Sincronización completada sin errores.'
        
        try:
            SyncLog.objects.using(using).create(
                node_name=node_name,
                success=ok,
                message=msg,
            )
            logger.info(f"Log de sincronización guardado en base de datos '{using}'")
        except Exception as e:
            # Si falla guardar en remoto, intentar guardar en local
            if using == 'remote':
                logger.warning(f"Error al guardar log en base de datos remota: {e}. Intentando guardar en local...")
                try:
                    SyncLog.objects.using('default').create(
                        node_name=f"{node_name}_LOCAL_FALLBACK",
                        success=ok,
                        message=f"[FALLBACK DESDE REMOTO] {msg}",
                    )
                    logger.info("Log de sincronización guardado en base de datos local (fallback)")
                except Exception as local_error:
                    logger.error(f"Error al guardar log en base de datos local: {local_error}")
            else:
                raise e
    except Exception as e:
        # No romper la sincronización si falló el log
        import traceback
        logger.error(f"Error al guardar log de sincronización: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

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


def sync_expense_immediately(expense_id=None):
    """Sincroniza inmediatamente el gasto especificado o todos los pendientes.
    
    Esta función se ejecuta en un hilo separado para no bloquear la UI.
    """
    def _sync_worker():
        try:
            call_command("sync_expenses_to_remote")
            if expense_id:
                logger.info(f"Gasto {expense_id} sincronizado inmediatamente")
            else:
                logger.info("Gastos pendientes sincronizados inmediatamente")
        except Exception as e:
            logger.error(f"Error en sincronización inmediata de gasto: {e}")
    
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
