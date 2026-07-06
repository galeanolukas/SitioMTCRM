from django.core.management.base import BaseCommand
from core.erp.models import Client, Company


class Command(BaseCommand):
    help = 'Diagnóstico de clientes en la base de datos local'

    def handle(self, *args, **options):
        total = Client.objects.count()
        active = Client.objects.filter(is_active=True).count()
        inactive = Client.objects.filter(is_active=False).count()

        self.stdout.write('=== Diagnóstico de Clientes ===')
        self.stdout.write(f'Total clientes: {total}')
        self.stdout.write(f'Activos: {active}')
        self.stdout.write(f'Inactivos: {inactive}')

        self.stdout.write('\n=== Clientes por empresa ===')
        companies = Company.objects.filter(is_active=True)
        for company in companies:
            count = Client.objects.filter(company=company, is_active=True).count()
            self.stdout.write(f'  Empresa {company.id} - {company.name}: {count} clientes activos')

        self.stdout.write(f'\nClientes sin empresa (company=None): {Client.objects.filter(company_id=None).count()}')

        self.stdout.write('\n=== Prueba toJSON() ===')
        errors = 0
        for client in Client.objects.all()[:10]:
            try:
                data = client.toJSON()
                self.stdout.write(f'  Cliente {client.id}: OK - {data.get("names")}')
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f'  Cliente {client.id}: ERROR - {e}'))

        if errors:
            self.stdout.write(self.style.ERROR(f'\n{errors} clientes con error en toJSON()'))
        else:
            self.stdout.write(self.style.SUCCESS('\nTodos los clientes probados tienen toJSON() OK'))
