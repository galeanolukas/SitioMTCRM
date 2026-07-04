from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Client


class Command(BaseCommand):
    help = "Sincroniza clientes desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de clientes hacia servidor remoto..."))

        pending = Client.objects.using('default').filter(synced_to_server=False).order_by('id')
        total = pending.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay clientes pendientes de sincronizar."))
            return

        synced = 0
        errors = 0

        for cli in pending:
            try:
                with transaction.atomic(using='remote'):
                    # Buscar cliente remoto por DNI, CUIT/CUIL o nombre (los IDs no coinciden)
                    qs = Client.objects.using('remote')
                    remote_cli = None

                    if cli.dni:
                        remote_cli = qs.filter(dni=cli.dni).first()
                    if not remote_cli and cli.cuit_cuil:
                        remote_cli = qs.filter(cuit_cuil=cli.cuit_cuil).first()
                    if not remote_cli:
                        remote_cli = qs.filter(names=cli.names, company_id=cli.company_id).first()
                    if not remote_cli:
                        remote_cli = qs.filter(names__iexact=cli.names).first()

                    created = remote_cli is None

                    if created:
                        remote_cli = Client.objects.using('remote').create(
                            company_id=cli.company_id,
                            names=cli.names,
                            surnames=cli.surnames,
                            dni=cli.dni,
                            cuit_cuil=cli.cuit_cuil,
                            date_birthday=cli.date_birthday,
                            address=cli.address,
                            gender=cli.gender,
                            is_active=cli.is_active,
                        )
                    else:
                        remote_cli.company_id = cli.company_id
                        remote_cli.names = cli.names
                        remote_cli.surnames = cli.surnames
                        remote_cli.dni = cli.dni
                        remote_cli.cuit_cuil = cli.cuit_cuil
                        remote_cli.date_birthday = cli.date_birthday
                        remote_cli.address = cli.address
                        remote_cli.gender = cli.gender
                        remote_cli.is_active = cli.is_active
                        remote_cli.save(using='remote')

                Client.objects.using('default').filter(pk=cli.pk).update(synced_to_server=True)
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando cliente {cli.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de clientes finalizada. Clientes sincronizados: {synced} / {total}. Errores: {errors}."
        ))
