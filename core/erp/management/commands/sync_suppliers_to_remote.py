from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Supplier


class Command(BaseCommand):
    help = "Sincroniza proveedores desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de proveedores hacia servidor remoto..."))

        pending = Supplier.objects.using('default').filter(synced_to_server=False).order_by('id')
        total = pending.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay proveedores pendientes de sincronizar."))
            return

        synced = 0
        errors = 0

        for sup in pending:
            try:
                with transaction.atomic(using='remote'):
                    lookup = {}
                    if sup.cuit:
                        lookup['cuit'] = sup.cuit
                    else:
                        lookup['name'] = sup.name

                    remote_sup, created = Supplier.objects.using('remote').get_or_create(
                        **lookup,
                        defaults={
                            'company_id': sup.company_id,
                            'address': sup.address,
                            'phone': sup.phone,
                            'email': sup.email,
                            'is_active': sup.is_active,
                        }
                    )
                    if not created:
                        remote_sup.company_id = sup.company_id
                        remote_sup.address = sup.address
                        remote_sup.phone = sup.phone
                        remote_sup.email = sup.email
                        remote_sup.is_active = sup.is_active
                        remote_sup.save()

                Supplier.objects.using('default').filter(pk=sup.pk).update(synced_to_server=True)
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando proveedor {sup.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de proveedores finalizada. Proveedores sincronizados: {synced} / {total}. Errores: {errors}."
        ))
