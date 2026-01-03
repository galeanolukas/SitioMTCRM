from django.core.management.base import BaseCommand
from django.db import transaction
from core.erp.models import InternalTransfer, InternalTransferDetail, Product, Company


class Command(BaseCommand):
    help = "Sincroniza transferencias internas desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronización de transferencias hacia servidor remoto..."))

        local_qs = InternalTransfer.objects.using('default').filter(synced_to_server=False).order_by('id')
        total = local_qs.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay transferencias para sincronizar."))
            return

        synced = 0
        errors = 0

        for transfer in local_qs:
            try:
                # Resolver empresa remota
                remote_company = None
                if transfer.company_id:
                    local_company = Company.objects.using('default').filter(pk=transfer.company_id).first()
                    if local_company:
                        # 1) Intentar mapear por CUIT
                        if local_company.cuit:
                            remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
                        # 2) Si no hay CUIT o no se encontró, intentar por nombre exacto
                        if not remote_company:
                            remote_company = Company.objects.using('remote').filter(name=local_company.name).first()

                if not remote_company:
                    errors += 1
                    self.stderr.write(
                        f"Error sincronizando transferencia {transfer.id}: empresa local {transfer.company_id} "
                        f"no tiene equivalente en servidor remoto."
                    )
                    continue

                with transaction.atomic(using='remote'):
                    # Crear o actualizar transferencia remota
                    remote_transfer, created = InternalTransfer.objects.using('remote').get_or_create(
                        transfer_number=transfer.transfer_number,
                        defaults={
                            'origin_pos': transfer.origin_pos,
                            'destination_pos': transfer.destination_pos,
                            'company_id': remote_company.id,
                            'created_by_id': transfer.created_by_id,
                            'status': transfer.status,
                            'observations': transfer.observations,
                            'synced_to_server': True,
                        },
                    )
                    
                    if not created:
                        # Actualizar transferencia existente
                        remote_transfer.origin_pos = transfer.origin_pos
                        remote_transfer.destination_pos = transfer.destination_pos
                        remote_transfer.company_id = remote_company.id
                        remote_transfer.created_by_id = transfer.created_by_id
                        remote_transfer.status = transfer.status
                        remote_transfer.observations = transfer.observations
                        remote_transfer.synced_to_server = True
                        remote_transfer.save()

                    # Sincronizar detalles de la transferencia
                    # Eliminar detalles antiguos y crear nuevos
                    InternalTransferDetail.objects.using('remote').filter(transfer=remote_transfer).delete()
                    
                    for detail in transfer.details.all():
                        # Buscar producto remoto
                        remote_product = None
                        if detail.product.code:
                            remote_product = Product.objects.using('remote').filter(code=detail.product.code).first()
                        if not remote_product:
                            remote_product = Product.objects.using('remote').filter(name=detail.product.name).first()
                        
                        if remote_product:
                            InternalTransferDetail.objects.using('remote').create(
                                transfer=remote_transfer,
                                product_id=remote_product.id,
                                quantity=detail.quantity,
                                unit_price=detail.unit_price,
                            )

                # Marcar transferencia local como sincronizada
                InternalTransfer.objects.using('default').filter(pk=transfer.pk).update(synced_to_server=True)
                synced += 1
                
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando transferencia {transfer.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización de transferencias finalizada. Transferencias sincronizadas: {synced} / {total}. Errores: {errors}."
        ))
