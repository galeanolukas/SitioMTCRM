from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = 'Agrega los campos sync_destination y local_server_url al servidor remoto usando SQL directo'

    def handle(self, *args, **options):
        if 'remote' not in connections:
            self.stdout.write(self.style.ERROR('No hay conexión a base de datos remota configurada'))
            return

        try:
            self.stdout.write("Verificando conexión a servidor remoto...")
            conn = connections['remote']
            conn.ensure_connection()
            self.stdout.write(self.style.SUCCESS('Conexión a servidor remoto establecida'))
            
            with conn.cursor() as cursor:
                # Verificar si la columna sync_destination ya existe
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'erp_company' 
                    AND column_name = 'sync_destination'
                """)
                
                if cursor.fetchone():
                    self.stdout.write(self.style.WARNING('La columna sync_destination ya existe en el servidor remoto'))
                else:
                    # Agregar columna sync_destination
                    self.stdout.write("Agregando columna sync_destination...")
                    cursor.execute("""
                        ALTER TABLE erp_company 
                        ADD COLUMN sync_destination VARCHAR(10) DEFAULT 'cloud'
                    """)
                    self.stdout.write(self.style.SUCCESS('Columna sync_destination agregada'))
                
                # Verificar si la columna local_server_url ya existe
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'erp_company' 
                    AND column_name = 'local_server_url'
                """)
                
                if cursor.fetchone():
                    self.stdout.write(self.style.WARNING('La columna local_server_url ya existe en el servidor remoto'))
                else:
                    # Agregar columna local_server_url
                    self.stdout.write("Agregando columna local_server_url...")
                    cursor.execute("""
                        ALTER TABLE erp_company 
                        ADD COLUMN local_server_url VARCHAR(255) NULL
                    """)
                    self.stdout.write(self.style.SUCCESS('Columna local_server_url agregada'))
            
            self.stdout.write(self.style.SUCCESS('\nCampos de sincronización agregados exitosamente en servidor remoto'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error agregando campos en servidor remoto: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
