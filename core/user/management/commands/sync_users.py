from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import transaction

from core.erp.models import Company

User = get_user_model()


class Command(BaseCommand):
    help = "Sincroniza usuarios entre BD remota (PostgreSQL) y local (SQLite)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de usuarios..."))

        # Sincronizar permisos del grupo operadores (remoto -> local)
        self.sync_operator_group_permissions()

        # Sincronizar desde remoto -> local
        synced_down = self.sync_from_remote_to_local()

        # Sincronizar desde local -> remoto
        synced_up = self.sync_from_local_to_remote()

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion completada. Bajados: {synced_down}, Subidos: {synced_up}"
        ))

    def sync_operator_group_permissions(self) -> None:
        """Sincroniza los permisos del grupo 'operadores' desde la BD remota a la local.

        La fuente de la verdad de los permisos es el servidor (BD remota). El POS local
        solo replica esos permisos para el grupo 'operadores'.
        """
        # Obtener grupo operadores en remoto; si no existe, no hacemos nada
        try:
            remote_group = Group.objects.using('remote').get(name='operadores')
        except Group.DoesNotExist:
            return

        # Obtener/crear grupo operadores en local
        local_group, _ = Group.objects.using('default').get_or_create(name='operadores')

        # Buscar permisos remotos asociados al grupo y mapearlos por app_label+codename
        remote_perms = (
            Permission.objects.using('remote')
            .select_related('content_type')
            .filter(group=remote_group)
        )

        local_perms = []
        for rp in remote_perms:
            app_label = rp.content_type.app_label
            codename = rp.codename
            try:
                lp = Permission.objects.using('default').select_related('content_type').get(
                    codename=codename,
                    content_type__app_label=app_label,
                )
            except Permission.DoesNotExist:
                continue
            local_perms.append(lp)

        # Asignar exactamente el mismo conjunto de permisos al grupo local
        local_group.permissions.set(local_perms)

    def sync_from_remote_to_local(self) -> int:
        """Copia superusuarios y operadores desde la BD remota hacia la local."""
        remote_qs = User.objects.using('remote').filter(
            is_superuser=True
        ) | User.objects.using('remote').filter(
            groups__name='operadores'
        )

        count = 0
        for remote_user in remote_qs.distinct():
            # Resolver la empresa remota a una empresa local mediante CUIT (y como
            # fallback por nombre), ya que los IDs de ambas BD no tienen por qué coincidir.
            remote_company_id = getattr(remote_user, 'company_id', None)
            local_company_id = None
            if remote_company_id:
                remote_company = Company.objects.using('remote').filter(pk=remote_company_id).first()
                if remote_company:
                    # 1) Intentar mapear por CUIT
                    if remote_company.cuit:
                        local_company = Company.objects.using('default').filter(cuit=remote_company.cuit).first()
                    else:
                        local_company = None

                    # 2) Si no hay CUIT o no se encontró, intentar por nombre exacto
                    if not local_company:
                        local_company = Company.objects.using('default').filter(name=remote_company.name).first()

                    if local_company:
                        local_company_id = local_company.id

            with transaction.atomic(using='default'):
                local_user, created = User.objects.using('default').get_or_create(
                    username=remote_user.username,
                    defaults={
                        'email': remote_user.email,
                        'first_name': remote_user.first_name,
                        'last_name': remote_user.last_name,
                        'is_staff': remote_user.is_staff,
                        'is_superuser': remote_user.is_superuser,
                        'is_active': remote_user.is_active,
                        'password': remote_user.password,  # copia hash
                        'company_id': local_company_id,
                    }
                )
                if not created:
                    local_user.email = remote_user.email
                    local_user.first_name = remote_user.first_name
                    local_user.last_name = remote_user.last_name
                    local_user.is_staff = remote_user.is_staff
                    local_user.is_superuser = remote_user.is_superuser
                    local_user.is_active = remote_user.is_active
                    local_user.password = remote_user.password
                    local_user.company_id = local_company_id
                    local_user.save()

                if not remote_user.is_superuser:
                    op_group_local, _ = Group.objects.using('default').get_or_create(name='operadores')
                    local_user.groups.set([op_group_local])
                count += 1

        return count

    def sync_from_local_to_remote(self) -> int:
        """Copia operadores creados en la BD local hacia la BD remota.
        No crea superusuarios en remoto desde el POS.

        IMPORTANTE: la empresa (company) se considera verdad del servidor.
        Por eso NUNCA actualizamos company_id en remoto desde el POS, para evitar
        pisar cambios hechos en el ERP.
        """
        op_group_local, _ = Group.objects.using('default').get_or_create(name='operadores')

        local_ops = User.objects.using('default').filter(
            is_superuser=False,
            groups__in=[op_group_local],
        ).distinct()

        count = 0
        for local_user in local_ops:
            with transaction.atomic(using='remote'):
                remote_user, created = User.objects.using('remote').get_or_create(
                    username=local_user.username,
                    defaults={
                        'email': local_user.email,
                        'first_name': local_user.first_name,
                        'last_name': local_user.last_name,
                        'is_staff': local_user.is_staff,
                        'is_superuser': False,
                        'is_active': local_user.is_active,
                        'password': local_user.password,  # copia hash
                    }
                )
                if not created:
                    remote_user.email = local_user.email
                    remote_user.first_name = local_user.first_name
                    remote_user.last_name = local_user.last_name
                    remote_user.is_staff = local_user.is_staff
                    remote_user.is_active = local_user.is_active
                    remote_user.password = local_user.password
                    remote_user.save()

                op_group_remote, _ = Group.objects.using('remote').get_or_create(name='operadores')
                remote_user.groups.set([op_group_remote])
                count += 1

        return count
