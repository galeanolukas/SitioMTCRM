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
                    # Buscar proveedor remoto por código, CUIT o nombre (los IDs no coinciden)
                    qs = Supplier.objects.using('remote')
                    remote_sup = None

                    if sup.code:
                        remote_sup = qs.filter(code=sup.code).first()
                    if not remote_sup and sup.cuit:
                        remote_sup = qs.filter(cuit=sup.cuit).first()
                    if not remote_sup:
                        remote_sup = qs.filter(name=sup.name).first()
                    if not remote_sup:
                        remote_sup = qs.filter(name__iexact=sup.name).first()

                    created = remote_sup is None

                    if created:
                        remote_sup = Supplier.objects.using('remote').create(
                            company_id=sup.company_id,
                            code=sup.code,
                            name=sup.name,
                            cuit=sup.cuit,
                            address=sup.address,
                            phone=sup.phone,
                            email=sup.email,
                            is_active=sup.is_active,
                        )
                    else:
                        remote_sup.company_id = sup.company_id
                        remote_sup.code = sup.code
                        remote_sup.name = sup.name
                        remote_sup.cuit = sup.cuit
                        remote_sup.address = sup.address
                        remote_sup.phone = sup.phone
                        remote_sup.email = sup.email
                        remote_sup.is_active = sup.is_active
                        remote_sup.save(using='remote')

                Supplier.objects.using('default').filter(pk=sup.pk).update(synced_to_server=True)
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando proveedor {sup.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de proveedores finalizada. Proveedores sincronizados: {synced} / {total}. Errores: {errors}."
        ))
