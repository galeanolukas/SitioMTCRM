from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from core.erp.models import CashRegister, Company

User = get_user_model()


class Command(BaseCommand):
    help = "Resincroniza cajas cerradas localmente que aparecen abiertas en el servidor remoto"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando resincronización de cajas cerradas..."))

        # Buscar cajas que están cerradas localmente pero podrían estar abiertas en remoto
        # Buscamos por sync_id o por fecha/usuario/empresa
        resynced = 0
        errors = 0

        # Obtener todas las cajas cerradas localmente
        closed_local = CashRegister.objects.using('default').filter(is_closed=True)
        
        for local_cr in closed_local:
            try:
                # Resolver empresa remota
                remote_company_id = None
                if local_cr.company_id:
                    comp = Company.objects.using('default').filter(pk=local_cr.company_id).first()
                    if comp:
                        remote_comp = None
                        if comp.cuit:
                            remote_comp = Company.objects.using('remote').filter(cuit=comp.cuit).first()
                        if not remote_comp:
                            remote_comp = Company.objects.using('remote').filter(name=comp.name).first()
                        if remote_comp:
                            remote_company_id = remote_comp.id

                # Resolver usuario remoto
                remote_user_id = None
                if local_cr.user_id:
                    local_user = User.objects.using('default').filter(pk=local_cr.user_id).first()
                    if local_user:
                        remote_user = User.objects.using('remote').filter(username=local_user.username).first()
                        if remote_user:
                            remote_user_id = remote_user.id

                with transaction.atomic(using='remote'):
                    # Buscar caja correspondiente en remoto
                    remote_cr = None
                    
                    # Primero buscar por sync_id si existe
                    if local_cr.sync_id:
                        remote_cr = CashRegister.objects.using('remote').filter(sync_id=local_cr.sync_id).first()
                    
                    # Si no encuentra por sync_id, buscar por fecha y usuario
                    if not remote_cr and remote_company_id and remote_user_id:
                        remote_cr = CashRegister.objects.using('remote').filter(
                            date=local_cr.date,
                            company_id=remote_company_id,
                            user_id=remote_user_id
                        ).first()
                    
                    # Si aún no encuentra, buscar solo por fecha y empresa (menos preciso)
                    if not remote_cr and remote_company_id:
                        remote_cr = CashRegister.objects.using('remote').filter(
                            date=local_cr.date,
                            company_id=remote_company_id
                        ).first()

                    if remote_cr:
                        # Verificar si necesita actualización
                        needs_update = False
                        
                        if remote_cr.is_closed != local_cr.is_closed:
                            needs_update = True
                            self.stdout.write(f"Actualizando caja {local_cr.id}: is_closed {remote_cr.is_closed} -> {local_cr.is_closed}")
                        
                        if remote_cr.closing_balance != local_cr.closing_balance:
                            needs_update = True
                            self.stdout.write(f"Actualizando caja {local_cr.id}: closing_balance {remote_cr.closing_balance} -> {local_cr.closing_balance}")
                        
                        if remote_cr.cash_sales != local_cr.cash_sales:
                            needs_update = True
                            self.stdout.write(f"Actualizando caja {local_cr.id}: cash_sales {remote_cr.cash_sales} -> {local_cr.cash_sales}")
                        
                        if remote_cr.card_sales != local_cr.card_sales:
                            needs_update = True
                            self.stdout.write(f"Actualizando caja {local_cr.id}: card_sales {remote_cr.card_sales} -> {local_cr.card_sales}")
                        
                        if remote_cr.transfer_sales != local_cr.transfer_sales:
                            needs_update = True
                            self.stdout.write(f"Actualizando caja {local_cr.id}: transfer_sales {remote_cr.transfer_sales} -> {local_cr.transfer_sales}")
                        
                        if remote_cr.mp_sales != local_cr.mp_sales:
                            needs_update = True
                            self.stdout.write(f"Actualizando caja {local_cr.id}: mp_sales {remote_cr.mp_sales} -> {local_cr.mp_sales}")
                        
                        if remote_cr.expenses != local_cr.expenses:
                            needs_update = True
                            self.stdout.write(f"Actualizando caja {local_cr.id}: expenses {remote_cr.expenses} -> {local_cr.expenses}")

                        if needs_update:
                            # Actualizar todos los campos
                            remote_cr.company_id = remote_company_id
                            remote_cr.user_id = remote_user_id
                            remote_cr.date = local_cr.date
                            remote_cr.opening_balance = local_cr.opening_balance
                            remote_cr.closing_balance = local_cr.closing_balance
                            remote_cr.cash_sales = local_cr.cash_sales
                            remote_cr.card_sales = local_cr.card_sales
                            remote_cr.transfer_sales = local_cr.transfer_sales
                            remote_cr.mp_sales = local_cr.mp_sales
                            remote_cr.expenses = local_cr.expenses
                            remote_cr.notes = local_cr.notes
                            remote_cr.is_closed = local_cr.is_closed
                            remote_cr.save()
                            
                            resynced += 1
                            self.stdout.write(self.style.SUCCESS(f"Caja {local_cr.id} resincronizada correctamente"))
                        else:
                            self.stdout.write(f"Caja {local_cr.id} ya está actualizada")
                    else:
                        self.stdout.write(f"No se encontró caja remota correspondiente para la caja local {local_cr.id}")

            except Exception as e:
                errors += 1
                self.stderr.write(f"Error resincronizando caja {local_cr.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Resincronización finalizada. Cajas actualizadas: {resynced}. Errores: {errors}."
        ))
