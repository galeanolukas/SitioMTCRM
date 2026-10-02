"""Helpers compartidos para los comandos de restauracion remoto -> local.

El servidor actua como backup: estos helpers resuelven la empresa local en la
BD remota (por CUIT, fallback nombre) y mapean entidades relacionadas
(productos, clientes, proveedores) sin depender de que los IDs coincidan
entre bases.
"""
from django.contrib.auth import get_user_model
from crum import get_current_user

from core.erp.models import Company, Product, Client, Supplier


def get_local_company(company_id=None):
    """Devuelve la empresa local a restaurar.

    Prioridad: --company-id > empresa del usuario actual (crum) >
    usuario con ultimo login > primera empresa.
    """
    if company_id:
        return Company.objects.filter(pk=company_id).first()

    current_user = get_current_user()
    if current_user and not current_user.is_anonymous and getattr(current_user, 'company_id', None):
        return current_user.company

    User = get_user_model()
    user = (User.objects.exclude(company__isnull=True)
            .exclude(last_login__isnull=True).order_by('-last_login').first()
            or User.objects.exclude(company__isnull=True).order_by('-date_joined').first())
    if user:
        return user.company
    return Company.objects.first()


def resolve_remote_company(local_company, stdout=None):
    """Resuelve la empresa remota equivalente a la local (por CUIT, fallback nombre)."""
    if not local_company:
        return None
    remote_company = None
    if local_company.cuit:
        remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
    if not remote_company and local_company.name:
        remote_company = Company.objects.using('remote').filter(name=local_company.name).first()
    if not remote_company and stdout:
        stdout.write(f"No se encontro empresa remota para '{local_company.name}' "
                     f"(CUIT: {local_company.cuit or '-'})")
    return remote_company


def map_remote_product(remote_prod, company_id):
    """Mapea un producto remoto al local: server_product_id -> code -> name."""
    local = Product.objects.using('default').filter(
        server_product_id=remote_prod.id
    ).first()
    if local:
        return local
    if remote_prod.code:
        local = Product.objects.using('default').filter(
            code=remote_prod.code, company_id=company_id
        ).first()
    if not local and remote_prod.name:
        local = Product.objects.using('default').filter(
            name=remote_prod.name, company_id=company_id
        ).first()
    return local


def map_remote_client(remote_cli, company_id, create=True):
    """Mapea un cliente remoto al local: cuit_cuil -> nombre. Crea si no existe."""
    if not remote_cli:
        return None
    local = None
    if remote_cli.cuit_cuil:
        local = Client.objects.using('default').filter(
            cuit_cuil=remote_cli.cuit_cuil, company_id=company_id
        ).first()
    if not local and remote_cli.names:
        local = Client.objects.using('default').filter(
            names=remote_cli.names, company_id=company_id
        ).first()
    if not local and create:
        local = Client.objects.using('default').create(
            company_id=company_id,
            names=remote_cli.names,
            surnames=getattr(remote_cli, 'surnames', None),
            dni=getattr(remote_cli, 'dni', None),
            cuit_cuil=getattr(remote_cli, 'cuit_cuil', None) or None,
            condicion_iva=getattr(remote_cli, 'condicion_iva', 'CF'),
            address=getattr(remote_cli, 'address', None),
            ciudad=getattr(remote_cli, 'ciudad', None),
            provincia=getattr(remote_cli, 'provincia', None),
            codigo_postal=getattr(remote_cli, 'codigo_postal', None),
            email=getattr(remote_cli, 'email', None) or None,
            telefono=getattr(remote_cli, 'telefono', None),
            synced_to_server=True,
        )
    return local


def map_remote_supplier(remote_supplier, company_id, create=True):
    """Mapea un proveedor remoto al local: cuit -> nombre. Crea si no existe."""
    if not remote_supplier:
        return None
    local = None
    if remote_supplier.cuit:
        local = Supplier.objects.using('default').filter(
            cuit=remote_supplier.cuit, company_id=company_id
        ).first()
    if not local and remote_supplier.name:
        local = Supplier.objects.using('default').filter(
            name=remote_supplier.name, company_id=company_id
        ).first()
    if not local and create:
        kwargs = {
            'company_id': company_id,
            'name': remote_supplier.name,
            'cuit': getattr(remote_supplier, 'cuit', None),
            'address': getattr(remote_supplier, 'address', None),
            'phone': getattr(remote_supplier, 'phone', None),
            'email': getattr(remote_supplier, 'email', None),
            'external_code': getattr(remote_supplier, 'external_code', None),
            'default_discount_percentage': getattr(remote_supplier, 'default_discount_percentage', 0),
            'synced_to_server': True,
        }
        # code es unique: solo copiarlo si no esta en uso
        remote_code = getattr(remote_supplier, 'code', None)
        if remote_code and not Supplier.objects.using('default').filter(code=remote_code).exists():
            kwargs['code'] = remote_code
        local = Supplier.objects.using('default').create(**kwargs)
    return local
