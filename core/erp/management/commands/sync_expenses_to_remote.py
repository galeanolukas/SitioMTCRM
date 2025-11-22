from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Expense, Company


class Command(BaseCommand):
    help = "Sincroniza gastos desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de gastos hacia servidor remoto..."))

        pending = Expense.objects.using('default').filter(synced_to_server=False).order_by('id')
        total = pending.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay gastos pendientes de sincronizar."))
            return

        synced = 0
        errors = 0

        for exp in pending:
            try:
                # Resolver empresa remota equivalente (por CUIT o nombre)
                remote_company_id = None
                if exp.company_id:
                    comp = Company.objects.using('default').filter(pk=exp.company_id).first()
                    if comp:
                        remote_comp = None
                        if comp.cuit:
                            remote_comp = Company.objects.using('remote').filter(cuit=comp.cuit).first()
                        if not remote_comp:
                            remote_comp = Company.objects.using('remote').filter(name=comp.name).first()
                        if remote_comp:
                            remote_company_id = remote_comp.id

                if exp.company_id and not remote_company_id:
                    errors += 1
                    self.stderr.write(
                        f"Saltando gasto {exp.id}: empresa local {exp.company_id} no tiene equivalente en remoto."
                    )
                    continue

                with transaction.atomic(using='remote'):
                    Expense.objects.using('remote').create(
                        company_id=remote_company_id,
                        supplier_id=exp.supplier_id,
                        date=exp.date,
                        description=exp.description,
                        amount=exp.amount,
                        payer=exp.payer,
                        is_active=exp.is_active,
                        # No sincronizamos archivo de comprobante en esta versión
                    )

                Expense.objects.using('default').filter(pk=exp.pk).update(synced_to_server=True)
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando gasto {exp.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de gastos finalizada. Gastos sincronizados: {synced} / {total}. Errores: {errors}."
        ))
