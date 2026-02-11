from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import os

from core.erp.models import Sale, DetSale, QuickOrder, Expense


class Command(BaseCommand):
    help = "Versión segura de limpieza de datos operativos del POS CON CONFIRMACIÓN Y BACKUP"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("⚠️  ADVERTENCIA: ESTE COMANDO ELIMINARÁ DATOS OPERATIVOS"))
        self.stdout.write(self.style.WARNING("   - Ventas y detalles de ventas"))
        self.stdout.write(self.style.WARNING("   - Órdenes rápidas"))
        self.stdout.write(self.style.WARNING("   - Gastos"))
        
        # Contar datos actuales
        sales_count = Sale.objects.count()
        detsales_count = DetSale.objects.count()
        quickorders_count = QuickOrder.objects.count()
        expenses_count = Expense.objects.count()
        
        self.stdout.write(f"\n📊 DATOS ACTUALES:")
        self.stdout.write(f"   - Ventas: {sales_count}")
        self.stdout.write(f"   - Detalles de venta: {detsales_count}")
        self.stdout.write(f"   - Órdenes rápidas: {quickorders_count}")
        self.stdout.write(f"   - Gastos: {expenses_count}")
        
        # Si hay ventas, crear backup
        if sales_count > 0:
            backup_file = f"backups/ventas/pre_clean_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
            os.makedirs(os.path.dirname(backup_file), exist_ok=True)
            
            try:
                import shutil
                shutil.copy2('db.sqlite3', backup_file)
                self.stdout.write(self.style.SUCCESS(f"✅ Backup creado: {backup_file}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error creando backup: {e}"))
                self.stdout.write(self.style.ERROR("❌ Operación cancelada por seguridad"))
                return
        
        # Preguntar confirmación
        self.stdout.write(self.style.ERROR(f"\n🚨 ¿ESTÁ SEGURO DE ELIMINAR ESTOS DATOS?"))
        self.stdout.write(self.style.ERROR(f"   Escriba 'ELIMINAR_DATOS' para confirmar: "))
        
        # En modo no interactivo, no permitir ejecución
        if not hasattr(self, '_interactive') or not self._interactive:
            self.stdout.write(self.style.ERROR("❌ Este comando requiere confirmación interactiva"))
            self.stdout.write(self.style.ERROR("   Use: python manage.py safe_clean_pos_data --confirm"))
            return
        
        # Aquí iría la lógica de confirmación interactiva
        # Por ahora, cancelamos por seguridad
        self.stdout.write(self.style.ERROR("❌ Operación cancelada. Use clean_pos_data solo si es absolutamente necesario."))
        
        self.stdout.write(self.style.NOTICE("\n💡 ALTERNATIVAS SEGURAS:"))
        self.stdout.write(self.style.NOTICE("   - Para eliminar solo ventas antiguas: use filtros de fecha"))
        self.stdout.write(self.style.NOTICE("   - Para resetear sincronización: use repair_sync"))
        self.stdout.write(self.style.NOTICE("   - Para backup: use backup_sqlite"))
