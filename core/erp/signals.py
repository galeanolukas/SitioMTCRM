from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.erp.models import Supplier, Expense

@receiver(post_migrate)
def ensure_supplier_permissions(sender, **kwargs):
    # Evita correr esto en otras apps
    app_label = getattr(sender, 'label', '')
    if app_label != 'erp':
        return

    # Grupo destino
    group_name = 'Usuarios'
    group, _ = Group.objects.get_or_create(name=group_name)

    # Permisos de proveedores
    ct_sup = ContentType.objects.get_for_model(Supplier)
    sup_codenames = ['view_supplier', 'add_supplier', 'change_supplier', 'delete_supplier']
    sup_perms = list(Permission.objects.filter(content_type=ct_sup, codename__in=sup_codenames))

    # Permisos de gastos (al menos ver, opcionalmente CRUD)
    ct_exp = ContentType.objects.get_for_model(Expense)
    exp_codenames = ['view_expense']  # agrega 'add_expense', 'change_expense', 'delete_expense' si lo necesitas
    exp_perms = list(Permission.objects.filter(content_type=ct_exp, codename__in=exp_codenames))

    # Asignar al grupo
    group.permissions.add(*sup_perms, *exp_perms)