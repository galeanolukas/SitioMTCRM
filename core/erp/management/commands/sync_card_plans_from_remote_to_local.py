from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import CardInstallmentPlan
from core.erp.management.commands._restore_common import (
    get_local_company,
    resolve_remote_company,
)


class Command(BaseCommand):
    help = ("Restaura planes de cuotas de tarjeta desde el servidor (remote) "
            "hacia la BD local. Dedup por empresa+marca+nombre+cuotas.")

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=None,
                            help='ID de la empresa local a restaurar')
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo muestra que se restauraria, sin escribir')

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando restauracion de planes de tarjeta remoto -> local..."))

        local_company = get_local_company(options.get('company_id'))
        if not local_company:
            self.stdout.write(self.style.ERROR("No se encontro empresa local."))
            return
        remote_company = resolve_remote_company(local_company, self.stdout)
        if not remote_company:
            self.stdout.write(self.style.ERROR("No se pudo resolver la empresa en el servidor."))
            return
        self.stdout.write(f"Empresa: {local_company.name} (local {local_company.id} -> remoto {remote_company.id})")

        remote_plans = (CardInstallmentPlan.objects.using('remote')
                        .filter(company_id=remote_company.id)
                        .order_by('id'))
        total = remote_plans.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay planes de tarjeta en el servidor para esta empresa."))
            return

        dry_run = options.get('dry_run')
        created = updated = errors = 0

        for rp in remote_plans.iterator():
            try:
                local_plan = CardInstallmentPlan.objects.using('default').filter(
                    company_id=local_company.id,
                    card_brand=rp.card_brand,
                    name=rp.name,
                    installments=rp.installments,
                ).first()

                if dry_run:
                    self.stdout.write(f"[dry-run] {'Actualizaria' if local_plan else 'Restauraria'} plan '{rp.name}'")
                    continue

                with transaction.atomic(using='default'):
                    if not local_plan:
                        CardInstallmentPlan.objects.using('default').create(
                            company_id=local_company.id,
                            card_brand=rp.card_brand,
                            name=rp.name,
                            installments=rp.installments,
                            multiplier=rp.multiplier,
                            afip_code=rp.afip_code,
                            is_active=rp.is_active,
                        )
                        created += 1
                        self.stdout.write(f"Plan '{rp.name}' restaurado")
                    else:
                        local_plan.multiplier = rp.multiplier
                        local_plan.afip_code = rp.afip_code
                        local_plan.is_active = rp.is_active
                        local_plan.save()
                        updated += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error restaurando plan remoto {rp.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Restauracion de planes finalizada. Creados: {created}, "
            f"actualizados: {updated}, errores: {errors}, total remoto: {total}"
        ))
