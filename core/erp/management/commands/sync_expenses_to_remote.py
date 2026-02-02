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
                    # Verificar si ya existe gasto duplicado usando múltiples criterios
                    # PRIORIDAD 1: Buscar por local_uuid (método más confiable)
                    existing_expense = None
                    
                    if hasattr(exp, 'local_uuid') and exp.local_uuid:
                        existing_expense = Expense.objects.using('remote').filter(
                            local_uuid=exp.local_uuid
                        ).first()
                        
                        if existing_expense:
                            self.stdout.write(
                                self.style.WARNING(f"Gasto {exp.id} ya existe por UUID (ID: {existing_expense.id}), omitiendo...")
                            )
                            # Marcar como sincronizada y continuar
                            Expense.objects.using('default').filter(pk=exp.pk).update(synced_to_server=True)
                            synced += 1
                            continue
                    
                    # PRIORIDAD 2: Buscar por local_expense_id (método secundario)
                    if hasattr(exp, 'local_expense_id') and exp.local_expense_id:
                        existing_expense = Expense.objects.using('remote').filter(
                            local_expense_id=exp.id,
                            company_id=remote_company_id
                        ).first()
                        
                        if existing_expense:
                            self.stdout.write(
                                self.style.WARNING(f"Gasto {exp.id} ya existe por local_expense_id (ID: {existing_expense.id}), omitiendo...")
                            )
                            # Marcar como sincronizada y continuar
                            Expense.objects.using('default').filter(pk=exp.pk).update(synced_to_server=True)
                            synced += 1
                            continue
                    
                    # PRIORIDAD 3: Búsqueda estricta por fecha, monto y descripción (último recurso)
                    # Solo si todos los campos coinciden exactamente
                    existing_expense = Expense.objects.using('remote').filter(
                        date=exp.date,
                        amount=exp.amount,
                        description=exp.description,
                        company_id=remote_company_id
                    ).first()
                    
                    if existing_expense:
                        self.stdout.write(
                            self.style.WARNING(f"Gasto {exp.id} duplicado por criterios (ID: {existing_expense.id}), omitiendo...")
                        )
                        # Marcar como sincronizada y continuar
                        Expense.objects.using('default').filter(pk=exp.pk).update(synced_to_server=True)
                        synced += 1
                        continue
                    
                    # Crear gasto en remoto con identificadores
                    remote_expense = Expense.objects.using('remote').create(
                        company_id=remote_company_id,
                        supplier_id=exp.supplier_id,
                        date=exp.date,
                        time=exp.time,
                        description=exp.description,
                        amount=exp.amount,
                        payer=exp.payer,
                        is_active=exp.is_active,
                        # Importante: mantener identificadores únicos
                        local_uuid=exp.local_uuid,
                        local_expense_id=exp.id,
                        source=getattr(exp, 'source', 'local_pos'),
                        synced_to_server=True,  # Marcar como sincronizada en servidor
                    )

                Expense.objects.using('default').filter(pk=exp.pk).update(synced_to_server=True)
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando gasto {exp.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de gastos finalizada. Gastos sincronizados: {synced} / {total}. Errores: {errors}."
        ))
