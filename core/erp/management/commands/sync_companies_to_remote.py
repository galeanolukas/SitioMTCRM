from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Company


class Command(BaseCommand):
    help = "Sincroniza empresas desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de empresas hacia servidor remoto..."))

        pending = Company.objects.using('default').filter(synced_to_server=False).order_by('id')
        total = pending.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay empresas pendientes de sincronizar."))
            return

        synced = 0
        errors = 0

        for comp in pending:
            try:
                with transaction.atomic(using='remote'):
                    # Usamos CUIT como clave natural si existe, sino ID
                    lookup = {}
                    if comp.cuit:
                        lookup['cuit'] = comp.cuit
                    else:
                        lookup['id'] = comp.id

                    remote_comp, created = Company.objects.using('remote').get_or_create(
                        **lookup,
                        defaults={
                            'name': comp.name,
                            'address': comp.address,
                            'iibb': comp.iibb,
                            'start': comp.start,
                            'pos': comp.pos,
                            'phone': comp.phone,
                            'email': comp.email,
                            'is_active': comp.is_active,
                        }
                    )
                    if not created:
                        remote_comp.name = comp.name
                        remote_comp.address = comp.address
                        remote_comp.iibb = comp.iibb
                        remote_comp.start = comp.start
                        remote_comp.pos = comp.pos
                        remote_comp.phone = comp.phone
                        remote_comp.email = comp.email
                        remote_comp.is_active = comp.is_active
                        remote_comp.save()

                Company.objects.using('default').filter(pk=comp.pk).update(synced_to_server=True)
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando empresa {comp.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de empresas finalizada. Empresas sincronizadas: {synced} / {total}. Errores: {errors}."
        ))
