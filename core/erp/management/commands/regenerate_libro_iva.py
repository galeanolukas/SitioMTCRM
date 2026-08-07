from django.core.management.base import BaseCommand
from core.erp.models import Sale, LibroIvaRegistro


class Command(BaseCommand):
    help = 'Regenera los registros del Libro IVA para todas las ventas existentes'

    def handle(self, *args, **options):
        self.stdout.write('Regenerando registros del Libro IVA para ventas existentes...')
        
        # Eliminar registros existentes de ventas
        deleted_count = LibroIvaRegistro.objects.filter(tipo_registro='venta').delete()[0]
        self.stdout.write(f'Eliminados {deleted_count} registros existentes de ventas')
        
        # Obtener todas las ventas confirmadas que no son presupuestos
        sales = Sale.objects.filter(status='confirmed', is_budget=False)
        total_sales = sales.count()
        self.stdout.write(f'Procesando {total_sales} ventas...')
        
        created_count = 0
        error_count = 0
        
        for sale in sales:
            try:
                sale._crear_registro_libro_iva_simple()
                created_count += 1
                if created_count % 100 == 0:
                    self.stdout.write(f'Procesados {created_count}/{total_sales}...')
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f'Error procesando venta {sale.id}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'Regeneración completada: {created_count} registros creados, {error_count} errores'))
