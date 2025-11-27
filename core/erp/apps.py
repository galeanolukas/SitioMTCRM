from django.apps import AppConfig
from django.conf import settings
import threading
import time
import sys


class ErpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.erp'

    _sync_thread_started = False
    _backup_thread_started = False

    def ready(self):
        """Lanza una sincronización periódica solo en POS locales."""
        # No correr esto en producción (servidor central)
        if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
            return

        # Evitar múltiples hilos si ready() se llama más de una vez
        if ErpConfig._sync_thread_started and ErpConfig._backup_thread_started:
            return

        # Iniciar hilo de sincronización
        if not ErpConfig._sync_thread_started:
            ErpConfig._sync_thread_started = True
            self._start_sync_thread()

        # Iniciar hilo de respaldo
        if not ErpConfig._backup_thread_started:
            ErpConfig._backup_thread_started = True
            self._start_backup_thread()

    def _start_sync_thread(self):
        """Inicia el hilo de sincronización periódica."""
        # No correr durante comandos de mantenimiento
        blocked_cmds = {'makemigrations', 'migrate', 'collectstatic', 'shell', 'createsuperuser'}
        if any(cmd in sys.argv for cmd in blocked_cmds):
            return

        # IMPORTAR AQUÍ, no arriba, para evitar AppRegistryNotReady
        from core.erp.sync_utils import run_full_sync
        from core.erp.models import AutoSyncConfig

        # Intervalo base de sincronización (por defecto 10 min)
        base_interval = getattr(settings, 'POS_SYNC_INTERVAL_SECONDS', 600)

        def _sync_worker():
            while True:
                try:
                    run_full_sync()
                except Exception:
                    # No romper el hilo si hay errores de sync
                    pass

                # Leer configuración dinámica del intervalo en cada vuelta.
                interval_seconds = base_interval
                try:
                    cfg = AutoSyncConfig.objects.first()
                    if cfg and cfg.interval_seconds:
                        # Forzar rango seguro 120s (2 min) a 3600s (60 min)
                        interval_seconds = max(120, min(3600, int(cfg.interval_seconds)))
                except Exception:
                    # Ante cualquier error, usar el intervalo base
                    interval_seconds = base_interval

                time.sleep(interval_seconds)

        t = threading.Thread(target=_sync_worker, daemon=True)
        t.start()

    def _start_backup_thread(self):
        """Inicia el hilo de respaldo automático periódico."""
        # No correr durante comandos de mantenimiento
        blocked_cmds = {'makemigrations', 'migrate', 'collectstatic', 'shell', 'createsuperuser', 'backup_sqlite'}
        if any(cmd in sys.argv for cmd in blocked_cmds):
            return

        # IMPORTAR AQUÍ, no arriba, para evitar AppRegistryNotReady
        from django.core.management import call_command

        # Intervalo base de respaldo (por defecto 4 horas)
        base_interval = getattr(settings, 'POS_BACKUP_INTERVAL_SECONDS', 14400)

        def _backup_worker():
            while True:
                try:
                    call_command("backup_sqlite")
                except Exception:
                    # No romper el hilo si hay errores de backup
                    pass

                # Usar intervalo configurado (rango seguro 1h a 24h)
                interval_seconds = max(3600, min(86400, base_interval))
                time.sleep(interval_seconds)

        t = threading.Thread(target=_backup_worker, daemon=True)
        t.start()