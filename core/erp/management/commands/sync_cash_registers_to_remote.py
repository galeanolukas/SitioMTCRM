from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import CashRegister, CashMovement, Company


class Command(BaseCommand):
    help = "Sincroniza cierres de caja y sus movimientos desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de cierres de caja hacia servidor remoto..."))

        # Solo sincronizamos cajas que aún no fueron marcadas como sincronizadas
        pending = CashRegister.objects.using('default').filter(is_synced=False).order_by('id')
        total = pending.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay cierres de caja pendientes de sincronizar."))
            return

        synced = 0
        errors = 0

        for cr in pending:
            try:
                # Resolver empresa remota equivalente (por CUIT o nombre), igual que en gastos/ventas
                remote_company_id = None
                if cr.company_id:
                    comp = Company.objects.using('default').filter(pk=cr.company_id).first()
                    if comp:
                        remote_comp = None
                        if comp.cuit:
                            remote_comp = Company.objects.using('remote').filter(cuit=comp.cuit).first()
                        if not remote_comp:
                            remote_comp = Company.objects.using('remote').filter(name=comp.name).first()
                        if remote_comp:
                            remote_company_id = remote_comp.id

                if cr.company_id and not remote_company_id:
                    errors += 1
                    self.stderr.write(
                        f"Saltando cierre de caja {cr.id}: empresa local {cr.company_id} no tiene equivalente en remoto."
                    )
                    continue

                with transaction.atomic(using='remote'):
                    # Crear cabecera de caja en remoto
                    remote_cr = CashRegister.objects.using('remote').create(
                        company_id=remote_company_id,
                        user_id=cr.user_id,
                        date=cr.date,
                        opening_balance=cr.opening_balance,
                        closing_balance=cr.closing_balance,
                        cash_sales=cr.cash_sales,
                        card_sales=cr.card_sales,
                        transfer_sales=cr.transfer_sales,
                        expenses=cr.expenses,
                        notes=cr.notes,
                        is_closed=cr.is_closed,
                    )

                    # Sincronizar movimientos asociados que aún no estén sincronizados
                    movements = CashMovement.objects.using('default').filter(cash_register=cr, is_synced=False)
                    for mv in movements:
                        CashMovement.objects.using('remote').create(
                            cash_register=remote_cr,
                            movement_type=mv.movement_type,
                            amount=mv.amount,
                            description=mv.description,
                            payment_type=mv.payment_type,
                            created_by_id=mv.created_by_id,
                            created_at=mv.created_at,
                        )

                        # Marcar movimiento local como sincronizado
                        CashMovement.objects.using('default').filter(pk=mv.pk).update(is_synced=True)

                # Marcar caja local como sincronizada
                CashRegister.objects.using('default').filter(pk=cr.pk).update(is_synced=True)
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando cierre de caja {cr.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de cierres de caja finalizada. Cierres sincronizados: {synced} / {total}. Errores: {errors}."
        ))
