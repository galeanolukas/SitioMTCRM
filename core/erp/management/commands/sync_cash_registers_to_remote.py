from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from core.erp.models import CashRegister, CashMovement, Company

User = get_user_model()


class Command(BaseCommand):
    help = "Sincroniza cierres de caja y sus movimientos desde la BD local (default) hacia la BD remota (remote)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Eliminar registros huérfanos en el servidor (cierres de caja no sincronizados)',
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
            return self.cleanup_orphaned_registers(dry_run)
        else:
            return self.sync_cash_registers(dry_run)

    def cleanup_orphaned_registers(self, dry_run=False):
        """Eliminar registros huérfanos en el servidor"""
        self.stdout.write(self.style.NOTICE("Iniciando limpieza de registros huérfanos..."))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY RUN - No se ejecutarán cambios reales"))
        
        try:
            from django.db import connections
            
            with connections['remote'].cursor() as cursor:
                # Buscar todos los cierres de caja en servidor que no están sincronizados
                cursor.execute('''
                    SELECT id, user_id, date, opening_balance, closing_balance, is_closed,
                           created_at, is_synced, sync_id
                    FROM erp_cashregister 
                    WHERE is_synced = False
                    ORDER BY created_at DESC
                ''')
                
                orphaned_registers = cursor.fetchall()
                
                if not orphaned_registers:
                    self.stdout.write(self.style.SUCCESS("No se encontraron registros huérfanos."))
                    return
                
                self.stdout.write(self.style.WARNING(f"Se encontraron {len(orphaned_registers)} registros huérfanos:"))
                
                for reg in orphaned_registers:
                    self.stdout.write(f"  ID: {reg[0]}, Usuario: {reg[1]}, Fecha: {reg[2]}, Cerrado: {reg[5]}, Sync ID: {reg[8]}")
                
                if not dry_run:
                    # Confirmar eliminación
                    confirm = input(f"\n¿Está seguro de eliminar estos {len(orphaned_registers)} registros? (s/N): ")
                    if confirm.lower() != 's':
                        self.stdout.write(self.style.WARNING("Operación cancelada."))
                        return
                    
                    # Eliminar registros huérfanos
                    cursor.execute('DELETE FROM erp_cashregister WHERE is_synced = False')
                    deleted_count = cursor.rowcount
                    
                    self.stdout.write(self.style.SUCCESS(f"✓ {deleted_count} registros huérfanos eliminados."))
                else:
                    self.stdout.write(self.style.WARNING(f"DRY RUN: Se eliminarían {len(orphaned_registers)} registros."))
                    
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error en limpieza: {e}"))
            import traceback
            traceback.print_exc()

    def sync_cash_registers(self, dry_run=False):
        """Sincronizar cierres de caja locales al servidor"""
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de cierres de caja hacia servidor remoto..."))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY RUN - No se ejecutarán cambios reales"))

        # 1) Detectar eliminaciones locales y eliminar del servidor
        self.detect_and_sync_deletions(dry_run)

        # 2) Sincronizar cierres pendientes
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

                if not dry_run:
                    with transaction.atomic(using='remote'):
                        # Verificar si ya existe un cierre de caja por local_uuid
                        existing_cr = None
                        if cr.local_uuid:
                            existing_cr = CashRegister.objects.using('remote').filter(local_uuid=cr.local_uuid).first()
                        
                        # Si no existe por UUID, verificar por clave natural (date, user, company)
                        if not existing_cr and remote_company_id and remote_user_id:
                            existing_cr = CashRegister.objects.using('remote').filter(
                                date=cr.date,
                                user_id=remote_user_id,
                                company_id=remote_company_id
                            ).first()
                        
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
                            existing_cr.cash_expenses=cr.cash_expenses
                            existing_cr.transfer_expenses=cr.transfer_expenses
                            existing_cr.mp_expenses=cr.mp_expenses
                            existing_cr.card_expenses=cr.card_expenses
                            existing_cr.cheque_expenses=cr.cheque_expenses
                            existing_cr.other_expenses=cr.other_expenses
                            existing_cr.notes=cr.notes
                            existing_cr.is_closed=cr.is_closed
                            # Mantener local_uuid si ya existe
                            if not existing_cr.local_uuid and cr.local_uuid:
                                existing_cr.local_uuid = cr.local_uuid
                            existing_cr.save()
                            remote_cr = existing_cr
                        else:
                            # Crear nuevo cierre de caja en remoto con sync_id basado en local_uuid
                            import uuid
                            sync_id = f"pos_{cr.local_uuid}" if cr.local_uuid else f"pos_{cr.id}_{uuid.uuid4().hex}"
                            
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
                                cash_expenses=cr.cash_expenses,
                                transfer_expenses=cr.transfer_expenses,
                                mp_expenses=cr.mp_expenses,
                                card_expenses=cr.card_expenses,
                                cheque_expenses=cr.cheque_expenses,
                                other_expenses=cr.other_expenses,
                                notes=cr.notes,
                                is_closed=cr.is_closed,
                                sync_id=sync_id,
                                local_uuid=cr.local_uuid,
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
                else:
                    self.stdout.write(f"[DRY RUN] Sincronizaría cierre de caja ID {cr.id}")
                
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando cierre de caja {cr.id}: {e}")

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"Sincronizacion de cierres de caja finalizada. Cierres sincronizados: {synced} / {total}. Errores: {errors}."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN: Se sincronizarían {synced} / {total} cierres de caja. Errores simulados: {errors}."
            ))

    def detect_and_sync_deletions(self, dry_run=False):
        """Detectar eliminaciones locales y eliminar registros correspondientes en servidor"""
        self.stdout.write(self.style.NOTICE("Verificando eliminaciones locales..."))
        
        try:
            from django.db import connections
            
            # Obtener todos los sync_ids de cierres locales
            local_sync_ids = list(CashRegister.objects.using('default').exclude(sync_id__isnull=True).exclude(sync_id='').values_list('sync_id', flat=True))
            
            with connections['remote'].cursor() as cursor:
                # Buscar registros en servidor que no existen localmente
                if local_sync_ids:
                    cursor.execute(f'''
                        SELECT id, sync_id, date, user_id
                        FROM erp_cashregister 
                        WHERE sync_id NOT IN ({','.join(['%s'] * len(local_sync_ids))})
                    ''', local_sync_ids)
                else:
                    # Si no hay sync_ids locales, eliminar todos los que tengan sync_id
                    cursor.execute('''
                        SELECT id, sync_id, date, user_id
                        FROM erp_cashregister 
                        WHERE sync_id IS NOT NULL AND sync_id != ''
                    ''')
                
                orphaned_server = cursor.fetchall()
                
                if orphaned_server:
                    self.stdout.write(self.style.WARNING(f"Se encontraron {len(orphaned_server)} registros en servidor que no existen localmente:"))
                    
                    for reg in orphaned_server:
                        self.stdout.write(f"  ID: {reg[0]}, Sync ID: {reg[1]}, Fecha: {reg[2]}, Usuario: {reg[3]}")
                    
                    if not dry_run:
                        # Eliminar registros huérfanos del servidor
                        sync_ids_to_delete = [reg[1] for reg in orphaned_server if reg[1]]
                        if sync_ids_to_delete:
                            cursor.execute(f'''
                                DELETE FROM erp_cashregister 
                                WHERE sync_id IN ({','.join(['%s'] * len(sync_ids_to_delete))})
                            ''', sync_ids_to_delete)
                            
                            deleted_count = cursor.rowcount
                            self.stdout.write(self.style.SUCCESS(f"✓ {deleted_count} registros eliminados del servidor."))
                    else:
                        self.stdout.write(self.style.WARNING(f"DRY RUN: Se eliminarían {len(orphaned_server)} registros del servidor."))
                else:
                    self.stdout.write(self.style.SUCCESS("✓ No se encontraron registros huérfanos en servidor."))
                    
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error detectando eliminaciones: {e}"))
            import traceback
            traceback.print_exc()
