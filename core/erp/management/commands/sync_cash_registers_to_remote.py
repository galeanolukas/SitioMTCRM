from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from core.erp.models import CashRegister, CashMovement, Company

User = get_user_model()


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

                # Mapear usuario local a usuario remoto por username para evitar cruzado
                remote_user_id = None
                if cr.user_id:
                    local_user = User.objects.using('default').filter(pk=cr.user_id).first()
                    if local_user:
                        remote_user = User.objects.using('remote').filter(username=local_user.username).first()
                        if remote_user:
                            remote_user_id = remote_user.id
                        else:
                            # Si no se encuentra el usuario por username, intentar por email
                            if local_user.email:
                                remote_user = User.objects.using('remote').filter(email=local_user.email).first()
                                if remote_user:
                                    remote_user_id = remote_user.id

                if cr.user_id and not remote_user_id:
                    errors += 1
                    self.stderr.write(
                        f"Saltando cierre de caja {cr.id}: usuario local {cr.user_id} no tiene equivalente en remoto."
                    )
                    continue

                with transaction.atomic(using='remote'):
                    # Verificar si ya existe un cierre de caja con sync_id único
                    existing_cr = None
                    if cr.sync_id:
                        existing_cr = CashRegister.objects.using('remote').filter(sync_id=cr.sync_id).first()
                    
                    if existing_cr:
                        # Actualizar el registro existente en lugar de crear uno nuevo
                        existing_cr.company_id=remote_company_id
                        existing_cr.user_id=remote_user_id
                        existing_cr.date=cr.date
                        existing_cr.opening_balance=cr.opening_balance
                        existing_cr.closing_balance=cr.closing_balance
                        existing_cr.cash_sales=cr.cash_sales
                        existing_cr.card_sales=cr.card_sales
                        existing_cr.transfer_sales=cr.transfer_sales
                        existing_cr.mp_sales=cr.mp_sales
                        existing_cr.expenses=cr.expenses
                        existing_cr.notes=cr.notes
                        existing_cr.is_closed=cr.is_closed
                        existing_cr.save()
                        remote_cr = existing_cr
                    else:
                        # Crear nuevo cierre de caja en remoto con sync_id único
                        import uuid
                        sync_id = f"pos_{cr.id}_{uuid.uuid4().hex[:8]}"
                        
                        remote_cr = CashRegister.objects.using('remote').create(
                            company_id=remote_company_id,
                            user_id=remote_user_id,
                            date=cr.date,
                            opening_balance=cr.opening_balance,
                            closing_balance=cr.closing_balance,
                            cash_sales=cr.cash_sales,
                            card_sales=cr.card_sales,
                            transfer_sales=cr.transfer_sales,
                            mp_sales=cr.mp_sales,
                            expenses=cr.expenses,
                            notes=cr.notes,
                            is_closed=cr.is_closed,
                            sync_id=sync_id,
                        )
                        
                        # Guardar sync_id en el registro local
                        CashRegister.objects.using('default').filter(pk=cr.pk).update(sync_id=sync_id)

                    # Sincronizar movimientos asociados que aún no estén sincronizados
                    movements = CashMovement.objects.using('default').filter(cash_register=cr, is_synced=False)
                    for mv in movements:
                        # Mapear usuario del movimiento por username
                        remote_created_by_id = None
                        if mv.created_by_id:
                            local_creator = User.objects.using('default').filter(pk=mv.created_by_id).first()
                            if local_creator:
                                remote_creator = User.objects.using('remote').filter(username=local_creator.username).first()
                                if remote_creator:
                                    remote_created_by_id = remote_creator.id
                                else:
                                    # Intentar por email si no encuentra por username
                                    if local_creator.email:
                                        remote_creator = User.objects.using('remote').filter(email=local_creator.email).first()
                                        if remote_creator:
                                            remote_created_by_id = remote_creator.id
                        
                        # Si no se encuentra el usuario, usar el usuario mapeado de la caja
                        if not remote_created_by_id:
                            remote_created_by_id = remote_user_id

                        CashMovement.objects.using('remote').create(
                            cash_register=remote_cr,
                            movement_type=mv.movement_type,
                            amount=mv.amount,
                            description=mv.description,
                            payment_type=mv.payment_type,
                            created_by_id=remote_created_by_id,
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
