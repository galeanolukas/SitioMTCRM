from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.erp.models import EmployeeAccountSale, Company


class Command(BaseCommand):
    help = "Sincroniza actualizaciones de cuentas corrientes de empleados (pagos, cambios) hacia la BD remota."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronización de actualizaciones de cuentas corrientes..."))

        synced = 0
        errors = 0

        # Obtener todas las empresas
        companies = Company.objects.using('default').all()
        
        for company in companies:
            self.stdout.write(f"Procesando empresa: {company.name}")
            
            # Obtener cuentas corrientes locales de esta empresa
            local_accounts = EmployeeAccountSale.objects.using('default').filter(company=company)
            
            for local_account in local_accounts:
                try:
                    # Buscar cuenta remota correspondiente
                    remote_account = None
                    
                    # 1) Buscar por local_uuid si existe
                    if hasattr(local_account, 'local_uuid') and local_account.local_uuid:
                        remote_account = EmployeeAccountSale.objects.using('remote').filter(
                            local_uuid=local_account.local_uuid
                        ).first()
                    
                    # 2) Si no hay local_uuid o no se encontró, buscar por otros criterios
                    if not remote_account:
                        # Buscar por empleado, fecha y monto
                        remote_account = EmployeeAccountSale.objects.using('remote').filter(
                            employee_id=local_account.employee_id,
                            company_id=company.id,
                            date_joined=local_account.date_joined,
                            total=local_account.total
                        ).first()

                    if not remote_account:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Cuenta local {local_account.id} no tiene equivalente en servidor remoto"
                            )
                        )
                        continue

                    # Comparar estados
                    needs_update = False
                    update_fields = {}

                    # Verificar si el estado de pago cambió
                    if local_account.is_paid != remote_account.is_paid:
                        needs_update = True
                        update_fields['is_paid'] = local_account.is_paid
                        update_fields['paid_date'] = local_account.paid_date

                    # Verificar si las notas cambiaron
                    if local_account.notes != remote_account.notes:
                        needs_update = True
                        update_fields['notes'] = local_account.notes

                    # Verificar si el subtotal cambió
                    if local_account.subtotal != remote_account.subtotal:
                        needs_update = True
                        update_fields['subtotal'] = local_account.subtotal

                    # Verificar si el IVA cambió
                    if local_account.iva != remote_account.iva:
                        needs_update = True
                        update_fields['iva'] = local_account.iva

                    # Verificar si el total cambió
                    if local_account.total != remote_account.total:
                        needs_update = True
                        update_fields['total'] = local_account.total

                    if needs_update:
                        # Actualizar cuenta en servidor
                        with transaction.atomic(using='remote'):
                            EmployeeAccountSale.objects.using('remote').filter(
                                pk=remote_account.pk
                            ).update(**update_fields)
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  Cuenta actualizada - {local_account.employee.username}:"
                                )
                            )
                            
                            for field, value in update_fields.items():
                                self.stdout.write(
                                    f"    {field}: {value}"
                                )
                            
                            synced += 1
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  Cuenta sincronizada - {local_account.employee.username}"
                            )
                        )

                except Exception as e:
                    errors += 1
                    self.stderr.write(
                        f"Error sincronizando actualizaciones de cuenta {local_account.id}: {e}"
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización de actualizaciones finalizada. Cuentas actualizadas: {synced}. Errores: {errors}."
        ))
