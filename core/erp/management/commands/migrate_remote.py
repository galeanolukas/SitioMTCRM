from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connections
from django.conf import settings


class Command(BaseCommand):
    help = 'Aplica migraciones en el servidor remoto usando la conexión configurada'

    def handle(self, *args, **options):
        if 'remote' not in connections:
            self.stdout.write(self.style.ERROR('No hay conexión a base de datos remota configurada'))
            return

        try:
            self.stdout.write("Verificando conexión a servidor remoto...")
            conn = connections['remote']
            conn.ensure_connection()
            self.stdout.write(self.style.SUCCESS('Conexión a servidor remoto establecida'))
            
            self.stdout.write("\nAplicando migraciones en servidor remoto...")
            
            # Usar call_command con --database=remote
            call_command('migrate', '--database=remote', verbosity=2)
            
            self.stdout.write(self.style.SUCCESS('\nMigraciones aplicadas exitosamente en servidor remoto'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error aplicando migraciones en servidor remoto: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
