from django.apps import AppConfig
from django.conf import settings
import threading
import time
import sys


class ErpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.erp'

    _sync_thread_started = False

    def ready(self):
        """Lanza una sincronización periódica solo en POS locales."""
        # No correr esto en producción (servidor central)
        if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
            return

        # Evitar múltiples hilos si ready() se llama más de una vez
        if ErpConfig._sync_thread_started:
            return
        ErpConfig._sync_thread_started = True

        # No correr durante comandos de mantenimiento
        blocked_cmds = {'makemigrations', 'migrate', 'collectstatic', 'shell', 'createsuperuser'}
        if any(cmd in sys.argv for cmd in blocked_cmds):
            return

        # IMPORTAR AQUÍ, no arriba, para evitar AppRegistryNotReady
        from core.erp.sync_utils import run_full_sync
        from core.erp.models import AutoSyncConfig

        # Intervalo base de sincronización (por defecto 10 min)
        base_interval = getattr(settings, 'POS_SYNC_INTERVAL_SECONDS', 600)

        def _worker():
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

        t = threading.Thread(target=_worker, daemon=True)
        t.start()