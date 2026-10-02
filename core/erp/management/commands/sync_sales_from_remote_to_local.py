from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.erp.models import Sale, DetSale, Product
from core.erp.management.commands._restore_common import (
    get_local_company,
    resolve_remote_company,
    map_remote_product,
    map_remote_client,
)


class Command(BaseCommand):
    help = ("Restaura ventas desde el servidor (remote) hacia la BD local. "
            "El servidor funciona como backup: trae las ventas de la empresa "
            "que no existan localmente, con sus detalles. No modifica stock.")

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=None,
                            help='ID de la empresa local a restaurar')
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo muestra que se restauraria, sin escribir')

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando restauracion de ventas remoto -> local..."))

        local_company = get_local_company(options.get('company_id'))
        if not local_company:
            self.stdout.write(self.style.ERROR("No se encontro empresa local."))
            return
        self.stdout.write(f"Empresa local: {local_company.name} (ID: {local_company.id})")

        remote_company = resolve_remote_company(local_company, self.stdout)
        if not remote_company:
            self.stdout.write(self.style.ERROR("No se pudo resolver la empresa en el servidor."))
            return
        self.stdout.write(f"Empresa remota: {remote_company.name} (ID remoto: {remote_company.id})")

        remote_sales = (Sale.objects.using('remote')
                        .filter(company_id=remote_company.id)
                        .order_by('id'))
        total = remote_sales.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay ventas en el servidor para esta empresa."))
            return
        self.stdout.write(f"Ventas en servidor: {total}")

        dry_run = options.get('dry_run')
        created = skipped = errors = 0

        for rs in remote_sales.iterator():
            uuid = rs.local_uuid or f'srv-{rs.id}'
            exists = Sale.objects.using('default').filter(local_uuid=uuid).exists()
            if not exists and rs.local_sale_id:
                # Venta que se subio desde este u otro POS: el id local original
                exists = Sale.objects.using('default').filter(
                    pk=rs.local_sale_id, local_uuid=rs.local_uuid
                ).exists()
            if exists:
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"[dry-run] Restauraria venta remota {rs.id} ({rs.date_joined}, ${rs.total})")
                created += 1
                continue
            try:
                with transaction.atomic(using='default'):
                    self._restore_sale(rs, uuid, local_company.id)
                created += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error restaurando venta remota {rs.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Restauracion de ventas finalizada. Creadas: {created}, "
            f"ya existian: {skipped}, errores: {errors}, total remoto: {total}"
        ))

    def _restore_sale(self, rs, uuid, company_id):
        # Mapear cliente remoto -> local (se crea si no existe)
        remote_cli = None
        if rs.cli_id:
            from core.erp.models import Client
            remote_cli = Client.objects.using('remote').filter(pk=rs.cli_id).first()
        local_cli = map_remote_client(remote_cli, company_id)

        sale = Sale.objects.using('default').create(
            company_id=company_id,
            cli=local_cli,
            date_joined=rs.date_joined,
            local_timezone=rs.local_timezone,
            subtotal=rs.subtotal,
            iva=rs.iva,
            total=rs.total,
            payment_method=rs.payment_method,
            payment_details=rs.payment_details or {},
            card_type=getattr(rs, 'card_type', None),
            card_brand=getattr(rs, 'card_brand', None),
            card_installments=getattr(rs, 'card_installments', None),
            card_auth_code=getattr(rs, 'card_auth_code', None),
            invoice_number=rs.invoice_number,
            invoice_pos=rs.invoice_pos,
            invoice_type=rs.invoice_type,
            is_credit_note=rs.is_credit_note,
            is_invoiced=rs.is_invoiced,
            is_ticket_x=rs.is_ticket_x,
            afip_cae=rs.afip_cae,
            afip_cae_vto=rs.afip_cae_vto,
            afip_voucher_number=rs.afip_voucher_number,
            afip_result=getattr(rs, 'afip_result', {}),
            afip_error=getattr(rs, 'afip_error', None),
            afip_qr=getattr(rs, 'afip_qr', None),
            afip_pdf_url=getattr(rs, 'afip_pdf_url', None),
            afip_contingencia=rs.afip_contingencia,
            afip_contingencia_fecha=rs.afip_contingencia_fecha,
            afip_pendiente_autorizacion=rs.afip_pendiente_autorizacion,
            local_sale_id=rs.id,
            local_uuid=uuid,
            source=rs.source or 'server',
            pos_id=getattr(rs, 'pos_id', None),
            catalogo_pedido_id=getattr(rs, 'catalogo_pedido_id', None),
            status=rs.status,
            is_budget=rs.is_budget,
            sent_to_local=rs.sent_to_local,
            local_server_response=getattr(rs, 'local_server_response', {}),
            budget_notes=getattr(rs, 'budget_notes', None),
            subtotal_original=getattr(rs, 'subtotal_original', 0),
            discount_amount=getattr(rs, 'discount_amount', 0),
            synced_to_server=True,
            synced_at=rs.synced_at or timezone.now(),
        )

        # Detalles: mapear productos por server_product_id -> code -> name
        missing_products = 0
        remote_dets = DetSale.objects.using('remote').filter(sale_id=rs.id)
        for rd in remote_dets:
            remote_prod = Product.objects.using('remote').filter(pk=rd.prod_id).first()
            local_prod = map_remote_product(remote_prod, company_id) if remote_prod else None
            if not local_prod:
                missing_products += 1
                continue
            DetSale.objects.using('default').create(
                sale=sale,
                prod=local_prod,
                price=rd.price,
                cant=rd.cant,
                subtotal=rd.subtotal,
                iva_amount=getattr(rd, 'iva_amount', 0) or 0,
            )
        msg = f"Venta remota {rs.id} restaurada como local {sale.id}"
        if missing_products:
            msg += f" ({missing_products} detalle(s) omitidos: producto no encontrado localmente)"
        self.stdout.write(msg)
