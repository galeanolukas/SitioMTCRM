from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Company


class Command(BaseCommand):
    help = "Sincroniza empresas desde la BD remota (remote) hacia la BD local (default). El servidor es la fuente de verdad."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de empresas desde servidor remoto hacia POS local..."))

        remote_qs = Company.objects.using('remote').all().order_by('id')
        total = remote_qs.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay empresas en la BD remota para sincronizar."))
            return

        synced = 0
        errors = 0

        for r in remote_qs:
            try:
                with transaction.atomic(using='default'):
                    # Intentar ubicar empresa local por CUIT si existe, si no por nombre
                    lookup = {}
                    local_obj = None

                    if r.cuit:
                        local_obj = Company.objects.using('default').filter(cuit=r.cuit).first()

                    if not local_obj:
                        local_obj = Company.objects.using('default').filter(name=r.name).first()

                    if local_obj is None:
                        # Crear nueva empresa local basada en la remota
                        local_obj = Company.objects.using('default').create(
                            name=r.name,
                            address=r.address,
                            cuit=r.cuit,
                            iibb=r.iibb,
                            start=r.start,
                            pos=r.pos,
                            phone=r.phone,
                            email=r.email,
                            is_active=r.is_active,
                            synced_to_server=True,
                        )
                    else:
                        # Actualizar datos principales desde servidor
                        local_obj.name = r.name
                        local_obj.address = r.address
                        local_obj.cuit = r.cuit
                        local_obj.iibb = r.iibb
                        local_obj.start = r.start
                        local_obj.pos = r.pos
                        local_obj.phone = r.phone
                        local_obj.email = r.email
                        local_obj.is_active = r.is_active
                        local_obj.synced_to_server = True
                        local_obj.save()

                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando empresa remota {r.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de empresas (remoto -> local) finalizada. Empresas sincronizadas: {synced} / {total}. Errores: {errors}."
        ))
