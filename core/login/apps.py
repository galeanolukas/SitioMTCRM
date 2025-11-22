from django.apps import AppConfig

class ErpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'erp'
    default = False

    def ready(self):
        # Importa las señales para post_migrate
        try:
            import core.erp.signals  # noqa: F401
        except Exception:
            # Evitar romper el arranque si aún no existen migraciones/tablas
            pass
        
class LoginConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'login'
    default = False
