from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Agrega campos de impresora fiscal a la tabla AfipConfig en la base de datos remota"

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
                # Lista de campos a agregar
                fields_to_add = [
                    ('fiscal_printer_enabled', "BOOLEAN DEFAULT FALSE"),
                    ('fiscal_printer_type', "VARCHAR(20) DEFAULT 'none'"),
                    ('fiscal_printer_port', "VARCHAR(50) NULL"),
                    ('fiscal_printer_baudrate', "INTEGER DEFAULT 9600"),
                ]
                
                # Verificar qué campos ya existen
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'erp_afipconfig'
                """)
                existing_columns = {row[0] for row in cursor.fetchall()}
                
                self.stdout.write(f"Columnas existentes en erp_afipconfig: {len(existing_columns)}")
                
                # Agregar campos que faltan
                for field_name, field_definition in fields_to_add:
                    if field_name not in existing_columns:
                        sql = f"ALTER TABLE erp_afipconfig ADD COLUMN {field_name} {field_definition}"
                        self.stdout.write(f"Agregando campo {field_name}...")
                        cursor.execute(sql)
                        self.stdout.write(self.style.SUCCESS(f"✓ Campo {field_name} agregado"))
                    else:
                        self.stdout.write(self.style.WARNING(f"Campo {field_name} ya existe, omitiendo"))
                
                self.stdout.write(self.style.SUCCESS("Campos de impresora fiscal agregados exitosamente"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            import traceback
            traceback.print_exc()
