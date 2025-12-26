#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.erp.models import Expense
from django.db import connections

def update_expense_permissions():
    """Actualizar permisos de gastos en la base de datos remota"""
    
    # Usar la base de datos remota
    using = 'remote'
    
    # Obtener o crear el grupo Usuarios
    group_name = 'Usuarios'
    group, _ = Group.objects.using(using).get_or_create(name=group_name)
    
    # Permisos de gastos
    ct_exp = ContentType.objects.get_for_model(Expense)
    exp_codenames = ['view_expense', 'add_expense', 'change_expense', 'delete_expense']
    exp_perms = list(Permission.objects.using(using).filter(content_type=ct_exp, codename__in=exp_codenames))
    
    # Asignar permisos al grupo
    group.permissions.add(*exp_perms)
    
    print(f'Permisos asignados al grupo {group_name}:')
    for perm in exp_perms:
        print(f'  - {perm.name} ({perm.codename})')
    
    print('¡Permisisos actualizados correctamente!')

if __name__ == '__main__':
    update_expense_permissions()
