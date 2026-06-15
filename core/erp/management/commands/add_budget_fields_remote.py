from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = 'Agrega los campos de presupuesto a la tabla erp_sale en el servidor remoto usando SQL directo'

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
                    ('status', "VARCHAR(20) DEFAULT 'confirmed'"),
                    ('is_budget', 'BOOLEAN DEFAULT FALSE'),
                    ('sent_to_local', 'BOOLEAN DEFAULT FALSE'),
                    ('local_server_response', 'TEXT NULL'),
                    ('budget_notes', 'TEXT NULL')
                ]
                
                for field_name, field_definition in fields_to_add:
                    # Verificar si el campo ya existe
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'erp_sale' 
                        AND column_name = %s
                    """, [field_name])
                    
                    if cursor.fetchone():
                        self.stdout.write(self.style.WARNING(f'El campo {field_name} ya existe en el servidor remoto'))
                        continue
                    
                    # Agregar el campo
                    self.stdout.write(f"\nAgregando campo {field_name} a tabla erp_sale...")
                    cursor.execute(f"""
                        ALTER TABLE erp_sale 
                        ADD COLUMN {field_name} {field_definition}
                    """)
                    
                    self.stdout.write(self.style.SUCCESS(f'Campo {field_name} agregado exitosamente'))
                
                conn.commit()
                self.stdout.write(self.style.SUCCESS('\nTodos los campos de presupuesto agregados exitosamente en servidor remoto'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error agregando campos de presupuesto en servidor remoto: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
