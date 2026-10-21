import threading

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Remito, DetalleRemito, Company, Product, Supplier

# Lock global para prevenir ejecución concurrente del comando
_sync_lock = threading.Lock()


def _resolve_remote_company(local_company):
    """Empresa local -> remota: por CUIT, fallback nombre."""
    if not local_company:
        return None
    remote_company = None
    if local_company.cuit:
        remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
    if not remote_company:
        remote_company = Company.objects.using('remote').filter(name=local_company.name).first()
    return remote_company


def _resolve_remote_supplier(local_sup, remote_company_id, create=True):
    """Proveedor local -> remoto: por CUIT -> nombre (scoped a empresa). Crea si no existe."""
    if not local_sup:
        return None
    remote_sup = None
    if local_sup.cuit:
        remote_sup = Supplier.objects.using('remote').filter(
            cuit=local_sup.cuit, company_id=remote_company_id
        ).first()
    if not remote_sup and local_sup.name:
        remote_sup = Supplier.objects.using('remote').filter(
            name=local_sup.name, company_id=remote_company_id
        ).first()
    if not remote_sup and create:
        kwargs = {
            'company_id': remote_company_id,
            'name': local_sup.name,
            'cuit': getattr(local_sup, 'cuit', None),
            'address': getattr(local_sup, 'address', None),
            'phone': getattr(local_sup, 'phone', None),
            'email': getattr(local_sup, 'email', None),
            'external_code': getattr(local_sup, 'external_code', None),
            'default_discount_percentage': getattr(local_sup, 'default_discount_percentage', 0),
            'synced_to_server': True,
        }
        # code es unique: solo copiarlo si no esta en uso en el remoto
        local_code = getattr(local_sup, 'code', None)
        if local_code and not Supplier.objects.using('remote').filter(code=local_code).exists():
            kwargs['code'] = local_code
        remote_sup = Supplier.objects.using('remote').create(**kwargs)
    return remote_sup


def _resolve_remote_product(local_prod, remote_company_id):
    """Producto local -> remoto: por code -> nombre (scoped a empresa). No crea productos."""
    if not local_prod:
        return None
    remote_prod = None
    if local_prod.code:
        remote_prod = Product.objects.using('remote').filter(
            code=local_prod.code, company_id=remote_company_id
        ).first()
    if not remote_prod and local_prod.name:
        remote_prod = Product.objects.using('remote').filter(
            name=local_prod.name, company_id=remote_company_id
        ).first()
    return remote_prod


class Command(BaseCommand):
    help = ("Sube remitos locales (default) hacia el servidor (remote) con sus detalles. "
            "Dedup por numero+fecha+tipo+proveedor+empresa. No mueve stock en el servidor "
            "(el stock remoto se sincroniza via sync_stock_to_remote).")

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=None,
                            help='Solo remitos de esta empresa local')
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo muestra que se subiria, sin escribir')

    def handle(self, *args, **options):
        if not _sync_lock.acquire(blocking=False):
            self.stdout.write(self.style.WARNING(
                "Otra sincronizacion de remitos ya esta en curso. Omitiendo."
            ))
            return
        try:
            self._run_sync(options)
        finally:
            _sync_lock.release()

    def _run_sync(self, options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de remitos local -> servidor..."))

        pending = Remito.objects.using('default').filter(synced_to_server=False).order_by('id')
        if options.get('company_id'):
            pending = pending.filter(company_id=options['company_id'])
        total = pending.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay remitos pendientes de sincronizar."))
            return

        dry_run = options.get('dry_run')
        created = skipped = errors = 0
        User = get_user_model()

        for lr in pending.iterator():
            try:
                local_company = Company.objects.using('default').filter(pk=lr.company_id).first() if lr.company_id else None
                remote_company = _resolve_remote_company(local_company)
                if lr.company_id and not remote_company:
                    errors += 1
                    self.stderr.write(
                        f"Remito {lr.id} ({lr.numero}): empresa local {lr.company_id} "
                        f"sin equivalente remota (CUIT/nombre). Omitido."
                    )
                    continue

                local_sup = Supplier.objects.using('default').filter(pk=lr.supplier_id).first() if lr.supplier_id else None
                remote_sup = _resolve_remote_supplier(
                    local_sup, remote_company.id if remote_company else None,
                    create=not dry_run,
                )

                # Dedup: mismo numero+fecha+tipo+proveedor+empresa ya existe en remoto
                exists = Remito.objects.using('remote').filter(
                    numero=lr.numero,
                    fecha=lr.fecha,
                    tipo=lr.tipo,
                    supplier_id=remote_sup.id if remote_sup else None,
                    company_id=remote_company.id if remote_company else None,
                ).exists()
                if exists:
                    skipped += 1
                    if not dry_run:
                        Remito.objects.using('default').filter(pk=lr.pk).update(synced_to_server=True)
                    self.stdout.write(f"Remito {lr.numero} ya existia en servidor - marcado como sincronizado")
                    continue

                if dry_run:
                    self.stdout.write(f"[dry-run] Subiria remito {lr.numero} ({lr.fecha}, {lr.detalleremito_set.count()} lineas)")
                    created += 1
                    continue

                # Mapear usuario local -> remoto por username
                remote_user_id = None
                if lr.created_by_id:
                    local_user = User.objects.using('default').filter(pk=lr.created_by_id).first()
                    if local_user:
                        remote_user = User.objects.using('remote').filter(username=local_user.username).first()
                        remote_user_id = remote_user.id if remote_user else None

                with transaction.atomic(using='remote'):
                    remito = Remito.objects.using('remote').create(
                        company_id=remote_company.id if remote_company else None,
                        tipo=lr.tipo,
                        supplier=remote_sup,
                        numero=lr.numero,
                        fecha=lr.fecha,
                        estado=lr.estado,
                        observaciones=lr.observaciones,
                        iva_porcentaje=lr.iva_porcentaje,
                        iva_modo=getattr(lr, 'iva_modo', 'incluido') or 'incluido',
                        ajuste_costo_pct=getattr(lr, 'ajuste_costo_pct', 0) or 0,
                        stock_applied=getattr(lr, 'stock_applied', False),
                        created_by_id=remote_user_id,
                        synced_to_server=True,
                    )
                    missing = 0
                    for ld in DetalleRemito.objects.using('default').filter(remito_id=lr.id):
                        local_prod = Product.objects.using('default').filter(pk=ld.prod_id).first() if ld.prod_id else None
                        remote_prod = _resolve_remote_product(
                            local_prod, remote_company.id if remote_company else None
                        ) if local_prod else None
                        if ld.prod_id and not remote_prod:
                            raise Exception(
                                f"Producto local {ld.prod_id} "
                                f"('{getattr(local_prod, 'name', '?')}') sin equivalente remoto. "
                                f"Correr sync_products_to_remote primero."
                            )
                        DetalleRemito.objects.using('remote').create(
                            remito=remito,
                            prod=remote_prod,
                            cantidad=ld.cantidad,
                            precio_unitario=ld.precio_unitario,
                        )
                    msg = f"Remito {lr.numero} subido al servidor (ID remoto: {remito.id}, estado: {lr.estado})"
                    self.stdout.write(self.style.SUCCESS(msg))
                    created += 1

                Remito.objects.using('default').filter(pk=lr.pk).update(synced_to_server=True)
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando remito {lr.id} ({lr.numero}): {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de remitos finalizada. Subidos: {created}, "
            f"ya existian: {skipped}, errores: {errors}, total pendientes: {total}"
        ))
