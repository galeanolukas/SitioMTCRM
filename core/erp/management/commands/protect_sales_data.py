from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import os

from core.erp.models import Sale


class Command(BaseCommand):
    help = "Protege los datos de ventas creando backup y verificando integridad"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Verificando protección de datos de ventas..."))
        
        # Contar ventas actuales
        total_sales = Sale.objects.count()
        self.stdout.write(f"Total de ventas actuales: {total_sales}")
        
        # Crear backup si hay ventas
        if total_sales > 0:
            backup_file = f"backups/ventas/emergency_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(backup_file), exist_ok=True)
            
            try:
                # Hacer backup de la base de datos completa
                import shutil
                shutil.copy2('db.sqlite3', backup_file)
                self.stdout.write(self.style.SUCCESS(f"✓ Backup de emergencia creado: {backup_file}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error creando backup: {e}"))
        
        # Verificar si hay ventas recientes (últimas 24 horas)
        recent_sales = Sale.objects.filter(
            date_joined__gte=timezone.now() - timezone.timedelta(hours=24)
        ).count()
        
        if recent_sales > 0:
            self.stdout.write(f"✓ Ventas recientes (24h): {recent_sales}")
        else:
            self.stdout.write(self.style.WARNING("⚠️ No hay ventas recientes (24h)"))
        
        # Verificar ventas sincronizadas
        synced_sales = Sale.objects.filter(synced_to_server=True).count()
        pending_sales = Sale.objects.filter(synced_to_server=False).count()
        
        self.stdout.write(f"Ventas sincronizadas: {synced_sales}")
        self.stdout.write(f"Ventas pendientes: {pending_sales}")
        
        self.stdout.write(self.style.SUCCESS("✓ Verificación de protección completada"))
