from django.core.management.base import BaseCommand
from core.erp.models import CardInstallmentPlan


class Command(BaseCommand):
    help = 'Cargar planes de cuotas de tarjeta desde el Excel'

    def handle(self, *args, **options):
        # Datos extraídos del Excel PRECIOSTARJETA.xlsx
        plans_data = [
            # CUOTAS MI PYME
            {'name': 'CUOTAS MI PYME', 'installments': 3, 'multiplier': 1.14, 'afip_code': 13},
            {'name': 'CUOTAS MI PYME', 'installments': 6, 'multiplier': 1.24, 'afip_code': 16},
            # PLAN Z
            {'name': 'PLAN Z', 'installments': 1, 'multiplier': 1.1, 'afip_code': None},
            {'name': 'PLAN Z', 'installments': 6, 'multiplier': 1.2958, 'afip_code': None},
            {'name': 'PLAN Z', 'installments': 12, 'multiplier': 2.122, 'afip_code': None},
            # OTROS PLANES
            {'name': 'OTROS PLANES', 'installments': 3, 'multiplier': 1.29, 'afip_code': None},
            {'name': 'OTROS PLANES', 'installments': 6, 'multiplier': 1.55, 'afip_code': None},
            {'name': 'OTROS PLANES', 'installments': 12, 'multiplier': 2.1169, 'afip_code': None},
            {'name': 'OTROS PLANES', 'installments': 1, 'multiplier': 1.1, 'afip_code': None},
        ]

        created_count = 0
        updated_count = 0

        for plan_data in plans_data:
            plan, created = CardInstallmentPlan.objects.update_or_create(
                name=plan_data['name'],
                installments=plan_data['installments'],
                defaults={
                    'multiplier': plan_data['multiplier'],
                    'afip_code': plan_data['afip_code'],
                    'is_active': True
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Creado: {plan}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Actualizado: {plan}'))

        self.stdout.write(self.style.SUCCESS(f'\nResumen: {created_count} creados, {updated_count} actualizados'))
