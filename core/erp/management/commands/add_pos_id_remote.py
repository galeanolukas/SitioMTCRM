from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = 'Agrega el campo pos_id a la tabla erp_sale en el servidor remoto usando SQL directo'

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
                # Verificar si el campo ya existe
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'erp_sale' 
                    AND column_name = 'pos_id'
                """)
                
                if cursor.fetchone():
                    self.stdout.write(self.style.WARNING('El campo pos_id ya existe en el servidor remoto'))
                    return
                
                # Agregar el campo pos_id
                self.stdout.write("\nAgregando campo pos_id a tabla erp_sale...")
                cursor.execute("""
                    ALTER TABLE erp_sale 
                    ADD COLUMN pos_id VARCHAR(50) NULL
                """)
                
                conn.commit()
                self.stdout.write(self.style.SUCCESS('Campo pos_id agregado exitosamente en servidor remoto'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error agregando campo pos_id en servidor remoto: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
