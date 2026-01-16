from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.erp.models import EmployeeAccountSale, DetEmployeeAccount, Company, Product


class Command(BaseCommand):
    help = "Sincroniza cuentas corrientes de empleados y sus detalles desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de cuentas corrientes de empleados hacia servidor remoto..."))

        # Cuentas corrientes locales que aún no se han sincronizado
        pending_accounts = EmployeeAccountSale.objects.using('default').filter(synced_to_server=False).order_by('id')
        total = pending_accounts.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay cuentas corrientes pendientes de sincronizar."))
            return

        synced = 0
        errors = 0

        for account in pending_accounts:
            try:
                # Resolver empresa remota a partir de la empresa local de la cuenta corriente
                remote_company = None
                if account.company_id:
                    local_company = Company.objects.using('default').filter(pk=account.company_id).first()
                    if local_company:
                        # 1) Intentar mapear por CUIT
                        if local_company.cuit:
                            remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
                        # 2) Si no hay CUIT o no se encontró, intentar por nombre exacto
                        if not remote_company:
                            remote_company = Company.objects.using('remote').filter(name=local_company.name).first()

                # Si la cuenta corriente tiene empresa local pero no existe equivalente remota,
                # no la sincronizamos para evitar error de FK.
                if account.company_id and not remote_company:
                    errors += 1
                    self.stderr.write(
                        f"Error sincronizando cuenta corriente {account.id}: empresa local {account.company_id} "
                        f"no tiene equivalente en servidor remoto (por CUIT/nombre)."
                    )
                    continue

                with transaction.atomic(using='remote'):
                    # Verificar si ya existe una cuenta corriente duplicada usando múltiples criterios
                    # Buscar por fecha, monto, empleado y notas
                    existing_account = EmployeeAccountSale.objects.using('remote').filter(
                        date_joined__year=account.date_joined.year,
                        date_joined__month=account.date_joined.month,
                        date_joined__day=account.date_joined.day,
                        total=account.total,
                        subtotal=account.subtotal,
                        employee_id=account.employee_id,
                        notes=account.notes
                    ).only(
                        'id', 'company_id', 'employee_id', 'date_joined', 'subtotal', 
                        'total', 'notes', 'is_paid', 'paid_date', 'local_timezone'
                    ).first()
                    
                    if existing_account:
                        # Ya existe una cuenta corriente muy similar, verificar si es la misma
                        # Comparar timestamp exacto (diferencia de menos de 5 segundos = misma cuenta)
                        time_diff = abs((existing_account.date_joined - account.date_joined).total_seconds())
                        if time_diff < 5:  # Si la diferencia es menor a 5 segundos, es la misma cuenta
                            # Ya existe, marcar como sincronizada y continuar
                            EmployeeAccountSale.objects.using('default').filter(pk=account.pk).update(synced_to_server=True)
                            synced += 1
                            self.stdout.write(
                                self.style.WARNING(f"Cuenta corriente {account.id} ya existe en servidor remoto (ID: {existing_account.id}), omitiendo...")
                            )
                            continue
                    
                    # Crear cabecera de cuenta corriente en remoto
                    # Para cuentas corrientes de empleados, el IVA siempre es 0
                    iva_amount = 0
                    
                    # Mantener el horario local original de la cuenta corriente
                    # Preservamos el date_joined tal como está para mantener la hora local del POS
                    remote_account = EmployeeAccountSale.objects.using('remote').create(
                        company_id=remote_company.id if remote_company else None,
                        employee_id=account.employee_id,
                        date_joined=account.date_joined,
                        local_timezone=account.local_timezone,
                        subtotal=account.subtotal,
                        iva=iva_amount,
                        total=account.total,
                        notes=account.notes,
                        is_paid=account.is_paid,
                        paid_date=account.paid_date,
                        synced_to_server=True,  # Marcar como sincronizada en servidor
                    )

                    # Crear detalles en remoto
                    for det in account.detemployeeaccount_set.all():
                        # Mapear producto local -> remoto
                        remote_prod = None
                        local_prod = Product.objects.using('default').filter(pk=det.prod_id).first()
                        if local_prod:
                            # 1) Buscar en remoto por code si existe
                            if local_prod.code:
                                remote_prod = Product.objects.using('remote').filter(code=local_prod.code).first()
                            # 2) Si no hay code o no matchea, intentar por nombre exacto
                            if not remote_prod:
                                remote_prod = Product.objects.using('remote').filter(name=local_prod.name).first()

                        if not remote_prod:
                            # Si no encontramos el producto remoto, registramos el error y abortamos
                            raise Exception(
                                f"Producto local {det.prod_id} ('{getattr(local_prod, 'name', '?')}') "
                                f"no tiene equivalente en servidor remoto (por code/nombre)."
                            )

                        DetEmployeeAccount.objects.using('remote').create(
                            employee_account=remote_account,
                            prod_id=remote_prod.id,
                            price=det.price,
                            cant=det.cant,
                            subtotal=det.subtotal,
                            iva_amount=det.iva_amount,
                        )

                # Marcar cuenta corriente local como sincronizada
                EmployeeAccountSale.objects.using('default').filter(pk=account.pk).update(
                    synced_to_server=True,
                )
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando cuenta corriente {account.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion finalizada. Cuentas corrientes sincronizadas: {synced} / {total}. Errores: {errors}."
        ))
