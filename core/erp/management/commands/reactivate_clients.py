from django.core.management.base import BaseCommand
from core.erp.models import Client


class Command(BaseCommand):
    help = 'Reactiva todos los clientes inactivos en la base de datos local'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='Reactivar solo los clientes de una empresa específica',
        )

    def handle(self, *args, **options):
        company_id = options.get('company_id')
        qs = Client.objects.filter(is_active=False)
        if company_id:
            qs = qs.filter(company_id=company_id)

        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('No hay clientes inactivos para reactivar.'))
            return

        qs.update(is_active=True)
        self.stdout.write(self.style.SUCCESS(f'Se reactivaron {count} clientes.'))
