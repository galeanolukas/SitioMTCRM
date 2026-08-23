from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.erp.models import Expense, Company, Supplier


class Command(BaseCommand):
    help = "Sincroniza gastos desde la BD local (default) hacia la BD remota (remote)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Eliminar gastos en servidor que fueron eliminados localmente',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se haría sin ejecutar cambios',
        )

    def handle(self, *args, **options):
        cleanup_mode = options.get('cleanup', False)
        dry_run = options.get('dry_run', False)

        if cleanup_mode:
            return self.cleanup_deleted_expenses(dry_run)

        # Ejecutar cleanup de eliminaciones antes de sync normal
        self.cleanup_deleted_expenses(dry_run)

        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de gastos hacia servidor remoto..."))

        pending = Expense.objects.using('default').filter(synced_to_server=False).order_by('id')
        total = pending.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay gastos pendientes de sincronizar."))
            return

        synced = 0
        updated = 0
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

                # Resolver proveedor remoto equivalente (por nombre)
                remote_supplier_id = None
                if exp.supplier_id:
                    local_supplier = Supplier.objects.using('default').filter(pk=exp.supplier_id).first()
                    if local_supplier:
                        remote_supplier = Supplier.objects.using('remote').filter(name=local_supplier.name).first()
                        if remote_supplier:
                            remote_supplier_id = remote_supplier.id

                with transaction.atomic(using='remote'):
                    # Buscar gasto existente por local_uuid
                    existing_exp = None
                    if exp.local_uuid:
                        existing_exp = Expense.objects.using('remote').filter(
                            local_uuid=exp.local_uuid
                        ).first()

                    # Si no hay UUID, buscar por local_expense_id + empresa
                    if not existing_exp and exp.local_expense_id:
                        existing_exp = Expense.objects.using('remote').filter(
                            local_expense_id=exp.local_expense_id,
                            company_id=remote_company_id
                        ).first()

                    expense_defaults = {
                        'company_id': remote_company_id,
                        'supplier_id': remote_supplier_id,
                        'date': exp.date,
                        'time': exp.time,
                        'description': exp.description,
                        'recurring_reason': exp.recurring_reason,
                        'amount': exp.amount,
                        'payment_method': exp.payment_method,
                        'payer': exp.payer,
                        'is_active': exp.is_active,
                        'synced_to_server': True,
                        'local_expense_id': exp.id,
                        'source': getattr(exp, 'source', 'local_pos'),
                        'synced_at': timezone.now(),
                    }

                    if existing_exp:
                        # Actualizar gasto existente
                        for field, value in expense_defaults.items():
                            setattr(existing_exp, field, value)
                        if not existing_exp.local_uuid and exp.local_uuid:
                            existing_exp.local_uuid = exp.local_uuid
                        existing_exp.save()
                        self.stdout.write(
                            self.style.WARNING(f"Gasto {exp.id} actualizado en servidor (ID remoto: {existing_exp.id})")
                        )
                        updated += 1
                    else:
                        # Crear nuevo gasto en remoto
                        Expense.objects.using('remote').create(
                            local_uuid=exp.local_uuid,
                            **expense_defaults,
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f"Gasto {exp.id} creado en servidor")
                        )
                        synced += 1

                # Marcar gasto local como sincronizado
                Expense.objects.using('default').filter(pk=exp.pk).update(
                    synced_to_server=True,
                    synced_at=timezone.now(),
                )
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando gasto {exp.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de gastos finalizada. Creados: {synced}, actualizados: {updated}, "
            f"errores: {errors}. Total procesado: {total}."
        ))

    def cleanup_deleted_expenses(self, dry_run=False):
        """Eliminar en servidor los gastos que fueron eliminados localmente"""
        self.stdout.write(self.style.NOTICE("Verificando gastos eliminados localmente..."))

        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY RUN - No se ejecutarán cambios reales"))

        try:
            from django.db import connections

            # Obtener todos los local_uuid y local_expense_id de gastos locales
            local_uuids = list(
                Expense.objects.using('default')
                .exclude(local_uuid__isnull=True)
                .exclude(local_uuid='')
                .values_list('local_uuid', flat=True)
            )
            local_expense_ids = list(
                Expense.objects.using('default')
                .exclude(local_expense_id__isnull=True)
                .values_list('local_expense_id', flat=True)
            )

            with connections['remote'].cursor() as cursor:
                orphaned = []

                if local_uuids:
                    placeholders = ','.join(['%s'] * len(local_uuids))
                    cursor.execute(f'''
                        SELECT id, local_uuid, local_expense_id, description, amount, date
                        FROM erp_expense
                        WHERE source = 'local_pos'
                          AND local_uuid IS NOT NULL
                          AND local_uuid != ''
                          AND local_uuid NOT IN ({placeholders})
                    ''', local_uuids)
                    orphaned.extend(cursor.fetchall())

                if local_expense_ids:
                    placeholders = ','.join(['%s'] * len(local_expense_ids))
                    cursor.execute(f'''
                        SELECT id, local_uuid, local_expense_id, description, amount, date
                        FROM erp_expense
                        WHERE source = 'local_pos'
                          AND (local_uuid IS NULL OR local_uuid = '')
                          AND local_expense_id IS NOT NULL
                          AND local_expense_id NOT IN ({placeholders})
                    ''', local_expense_ids)
                    orphaned.extend(cursor.fetchall())

                if not orphaned:
                    self.stdout.write(self.style.SUCCESS("No se encontraron gastos eliminados localmente pendientes de cleanup."))
                    return

                self.stdout.write(self.style.WARNING(
                    f"Se encontraron {len(orphaned)} gastos en servidor que fueron eliminados localmente:"
                ))

                for row in orphaned:
                    self.stdout.write(
                        f"  ID remoto: {row[0]}, UUID: {row[1]}, local_expense_id: {row[2]}, "
                        f"Descripción: {row[3]}, Importe: {row[4]}, Fecha: {row[5]}"
                    )

                if not dry_run:
                    orphaned_ids = [row[0] for row in orphaned]
                    placeholders = ','.join(['%s'] * len(orphaned_ids))

                    cursor.execute(f'''
                        DELETE FROM erp_expense
                        WHERE id IN ({placeholders})
                    ''', orphaned_ids)
                    deleted_count = cursor.rowcount

                    self.stdout.write(self.style.SUCCESS(
                        f"{deleted_count} gastos eliminados del servidor."
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"DRY RUN: Se eliminarían {len(orphaned)} gastos del servidor."
                    ))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error en cleanup de gastos eliminados: {e}"))
            import traceback
            traceback.print_exc()
