from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.erp import models as erp_models


class Command(BaseCommand):
    help = "Crea y configura los roles estándar del sistema: vendedor, admin_empresa, servidor_local."

    def add_arguments(self, parser):
        parser.add_argument(
            '--migrate',
            action='store_true',
            help='Migrar usuarios del grupo operadores a vendedor',
        )

    def handle(self, *args, **options):
        migrate = options.get('migrate', False)

        roles = self.get_roles_definition()

        for role_name, perms_config in roles.items():
            group, created = Group.objects.get_or_create(name=role_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Grupo creado: {role_name}"))
            else:
                self.stdout.write(f"Grupo existente: {role_name}")

            perm_objs = []
            for app_label, model_name, actions in perms_config:
                try:
                    ct = ContentType.objects.get(app_label=app_label, model=model_name)
                except ContentType.DoesNotExist:
                    self.stderr.write(f"  ContentType no encontrado: {app_label}.{model_name}")
                    continue
                for action in actions:
                    codename = f"{action}_{model_name}"
                    perm = Permission.objects.filter(content_type=ct, codename=codename).first()
                    if perm:
                        perm_objs.append(perm)
                    else:
                        self.stderr.write(f"  Permiso no encontrado: {app_label}.{codename}")

            group.permissions.set(perm_objs)
            self.stdout.write(f"  {len(perm_objs)} permisos asignados")

        # Migrar usuarios de operadores a vendedor
        if migrate:
            try:
                old_group = Group.objects.get(name='operadores')
                new_group = Group.objects.get(name='vendedor')
                users = old_group.user_set.all()
                count = users.count()
                if count:
                    for user in users:
                        user.groups.remove(old_group)
                        user.groups.add(new_group)
                    self.stdout.write(self.style.SUCCESS(
                        f"{count} usuarios migrados de 'operadores' a 'vendedor'"
                    ))
                else:
                    self.stdout.write("No hay usuarios en 'operadores' para migrar.")
            except Group.DoesNotExist:
                self.stdout.write("Grupo 'operadores' no existe, nada que migrar.")

        self.stdout.write(self.style.SUCCESS("Roles configurados correctamente."))

    def get_roles_definition(self):
        """
        Define los 3 roles estándar con sus permisos.
        Formato: { 'role_name': [(app_label, model_name, [actions]), ...] }
        """
        return {
            'vendedor': [
                # Ventas: crear y ver (no editar/eliminar)
                ('erp', 'sale', ['view', 'add']),
                # Productos: solo ver
                ('erp', 'product', ['view']),
                # Categorías: solo ver
                ('erp', 'category', ['view']),
                # Clientes: ver, crear, editar (para alta rápido en POS)
                ('erp', 'client', ['view', 'add', 'change']),
                # Cajas: ver, abrir, cerrar, movimientos
                ('erp', 'cashregister', ['view', 'add']),
                ('erp', 'cashmovement', ['view', 'add']),
                # Proveedores: solo ver
                ('erp', 'supplier', ['view']),
                # Planes de tarjeta: solo ver
                ('erp', 'cardinstallmentplan', ['view']),
            ],
            'admin_empresa': [
                # Todo lo de vendedor más:
                # Ventas: CRUD completo
                ('erp', 'sale', ['view', 'add', 'change', 'delete']),
                # Productos: CRUD completo
                ('erp', 'product', ['view', 'add', 'change', 'delete']),
                # Categorías: CRUD completo
                ('erp', 'category', ['view', 'add', 'change', 'delete']),
                # Clientes: CRUD completo
                ('erp', 'client', ['view', 'add', 'change', 'delete']),
                # Gastos: CRUD completo
                ('erp', 'expense', ['view', 'add', 'change', 'delete']),
                # Cajas: CRUD completo + movimientos
                ('erp', 'cashregister', ['view', 'add', 'change', 'delete']),
                ('erp', 'cashmovement', ['view', 'add', 'change', 'delete']),
                # Proveedores: CRUD completo
                ('erp', 'supplier', ['view', 'add', 'change', 'delete']),
                # Empresa: ver y editar
                ('erp', 'company', ['view', 'change']),
                # Libro IVA: ver
                ('erp', 'libroivaregistro', ['view']),
                # Planes de tarjeta: CRUD completo
                ('erp', 'cardinstallmentplan', ['view', 'add', 'change', 'delete']),
                # Cuentas de empleados
                ('erp', 'employeeaccountsale', ['view', 'add', 'change', 'delete']),
                # Listas de precios
                ('erp', 'pricelist', ['view', 'add', 'change', 'delete']),
            ],
            'servidor_local': [
                # Todo lo de admin_empresa más config global:
                # Ventas: CRUD completo
                ('erp', 'sale', ['view', 'add', 'change', 'delete']),
                # Productos: CRUD completo
                ('erp', 'product', ['view', 'add', 'change', 'delete']),
                # Categorías: CRUD completo
                ('erp', 'category', ['view', 'add', 'change', 'delete']),
                # Clientes: CRUD completo
                ('erp', 'client', ['view', 'add', 'change', 'delete']),
                # Gastos: CRUD completo
                ('erp', 'expense', ['view', 'add', 'change', 'delete']),
                # Cajas: CRUD completo + movimientos
                ('erp', 'cashregister', ['view', 'add', 'change', 'delete']),
                ('erp', 'cashmovement', ['view', 'add', 'change', 'delete']),
                # Proveedores: CRUD completo
                ('erp', 'supplier', ['view', 'add', 'change', 'delete']),
                # Empresa: CRUD completo
                ('erp', 'company', ['view', 'add', 'change', 'delete']),
                # Libro IVA: CRUD completo
                ('erp', 'libroivaregistro', ['view', 'add', 'change', 'delete']),
                # AFIP: CRUD completo
                ('erp', 'afipconfig', ['view', 'add', 'change', 'delete']),
                # Puntos de venta AFIP: CRUD completo
                ('erp', 'afippuntoventa', ['view', 'add', 'change', 'delete']),
                # Catálogo: CRUD completo
                ('erp', 'catalogoconfig', ['view', 'add', 'change', 'delete']),
                # Planes de tarjeta: CRUD completo
                ('erp', 'cardinstallmentplan', ['view', 'add', 'change', 'delete']),
                # Cuentas de empleados
                ('erp', 'employeeaccountsale', ['view', 'add', 'change', 'delete']),
                # Listas de precios
                ('erp', 'pricelist', ['view', 'add', 'change', 'delete']),
                # Remitos / transferencias
                ('erp', 'internaltransfer', ['view', 'add', 'change', 'delete']),
            ],
        }
