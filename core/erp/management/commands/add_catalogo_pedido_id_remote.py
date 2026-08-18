from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "Agrega el campo catalogo_pedido_id a la tabla Sale en la base de datos remota"

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
                    WHERE table_name = 'erp_sale' AND column_name = 'catalogo_pedido_id'
                """)
                existing = cursor.fetchone()
                
                if existing:
                    self.stdout.write(self.style.WARNING('El campo catalogo_pedido_id ya existe en erp_sale'))
                    return
                
                # Agregar el campo
                self.stdout.write("Agregando campo catalogo_pedido_id a erp_sale...")
                cursor.execute("""
                    ALTER TABLE erp_sale 
                    ADD COLUMN catalogo_pedido_id VARCHAR(100) NULL
                """)
                
                self.stdout.write(self.style.SUCCESS('✓ Campo catalogo_pedido_id agregado exitosamente'))
                
                # Verificar que se agregó correctamente
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'erp_sale' AND column_name = 'catalogo_pedido_id'
                """)
                result = cursor.fetchone()
                
                if result:
                    self.stdout.write(self.style.SUCCESS(
                        f'Campo verificado: {result[0]} (tipo: {result[1]}, nullable: {result[2]})'
                    ))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            import traceback
            traceback.print_exc()
