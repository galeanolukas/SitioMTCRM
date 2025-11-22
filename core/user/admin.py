from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from .models import User
from core.erp import models as erp_models


def ensure_operator_group():
    # Nombre de grupo estándar en todo el proyecto
    group, _ = Group.objects.get_or_create(name='operadores')
    perms_to_add = []
    # Incluir permisos view/add/change/delete en entidades básicas
    for model in (erp_models.Category, erp_models.Product, erp_models.Client, erp_models.Sale):
        ct = ContentType.objects.get_for_model(model)
        for action in ('view', 'add', 'change', 'delete'):
            codename = f"{action}_{model._meta.model_name}"
            perm = Permission.objects.filter(content_type=ct, codename=codename).first()
            if perm:
                perms_to_add.append(perm)
    if perms_to_add:
        group.permissions.add(*perms_to_add)
    return group


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email", "image")}),
        (_("Company"), {"fields": ("company",)}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2"),
        }),
    )
    list_display = ("username", "email", "first_name", "last_name", "company", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)

    def save_model(self, request, obj, form, change):
        created = obj.pk is None
        super().save_model(request, obj, form, change)
        # Asignar grupo por defecto únicamente 'operadores' a nuevos usuarios no superusuario
        if created and not obj.is_superuser:
            group = ensure_operator_group()
            # Establecer solo este grupo (evita que queden otros grupos asignados por error)
            obj.groups.set([group])
            obj.save(update_fields=['last_login'])