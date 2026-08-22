from django.core.management.base import BaseCommand
from core.erp.services.budget_service import send_pending_budgets_to_local_server
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envía presupuestos pendientes al servidor local (POS)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de empresa específica para filtrar presupuestos'
        )

    def handle(self, *args, **options):
        company_id = options.get('company_id')

        self.stdout.write('Enviando presupuestos pendientes al servidor local...')

        stats = send_pending_budgets_to_local_server(company_id=company_id)

        self.stdout.write(
            self.style.SUCCESS(
                f"Presupuestos enviados: {stats['sent']}, "
                f"omitidos: {stats['skipped']}, errores: {stats['errors']}"
            )
        )

        if stats['errors'] > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"{stats['errors']} presupuesto(s) no pudieron enviarse. "
                    "Verifique que el servidor local esté accesible."
                )
            )
