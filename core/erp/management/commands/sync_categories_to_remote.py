from django.core.management.base import BaseCommand
from django.db import transaction

from core.erp.models import Category


class Command(BaseCommand):
    help = "Sincroniza categorias desde la BD local (default) hacia la BD remota (remote)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de categorias hacia servidor remoto..."))

        local_qs = Category.objects.using('default').all().order_by('id')
        total = local_qs.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay categorias para sincronizar."))
            return

        synced = 0
        errors = 0

        for cat in local_qs:
            try:
                with transaction.atomic(using='remote'):
                    # Usamos name como clave natural (es unique en el modelo)
                    remote_cat, created = Category.objects.using('remote').get_or_create(
                        name=cat.name,
                        defaults={
                            'desc': cat.desc,
                        },
                    )
                    if not created:
                        remote_cat.desc = cat.desc
                        remote_cat.save()
                synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando categoria {cat.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de categorias finalizada. Categorias sincronizadas: {synced} / {total}. Errores: {errors}."
        ))
