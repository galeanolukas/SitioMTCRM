from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Sale, DetSale, QuickOrder, Expense


class Command(BaseCommand):
    help = "Limpia datos operativos del POS (ventas, detalles, órdenes rápidas, gastos) sin borrar usuarios ni configuración."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando limpieza de datos operativos del POS..."))

        with transaction.atomic():
            # Borrar en orden seguro: detalles antes que cabeceras
            DetSale.objects.all().delete()
            Sale.objects.all().delete()
            QuickOrder.objects.all().delete()
            Expense.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Limpieza completada: ventas, detalles, órdenes rápidas y gastos eliminados."))
