from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connections


class Command(BaseCommand):
    help = 'Aplica solo la migración del campo pos_id en el servidor remoto'

    def handle(self, *args, **options):
        if 'remote' not in connections:
            self.stdout.write(self.style.ERROR('No hay conexión a base de datos remota configurada'))
            return

        try:
            self.stdout.write("Verificando conexión a servidor remoto...")
            conn = connections['remote']
            conn.ensure_connection()
            self.stdout.write(self.style.SUCCESS('Conexión a servidor remoto establecida'))
            
            self.stdout.write("\nAplicando migración 0005_sale_pos_id en servidor remoto...")
            
            # Aplicar solo la migración específica
            call_command('migrate', 'erp', '0005', '--database=remote', verbosity=2)
            
            self.stdout.write(self.style.SUCCESS('\nMigración 0005 aplicada exitosamente en servidor remoto'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error aplicando migración en servidor remoto: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
