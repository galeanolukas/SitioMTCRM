from django.core.management.base import BaseCommand
from django.db import DatabaseError

from core.erp.models import Category, Company


def retry_on_database_lock(max_retries=3, delay=0.1):
    """Decorador para reintentar operaciones cuando la base de datos está bloqueada (SQLite)."""
    import time
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except DatabaseError as e:
                    if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(delay)
                        continue
                    raise
        return wrapper
    return decorator


class Command(BaseCommand):
    help = "Sincroniza categorias/marcas desde la BD remota (remote) hacia la BD local (default)."

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, help='ID de la empresa a sincronizar')

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de categorias desde servidor remoto..."))

        company_id = options.get('company_id')
        active_company = None
        if company_id:
            active_company = Company.objects.using('default').filter(pk=company_id).first()
        if not active_company:
            active_company = Company.objects.using('default').first()
        if not active_company:
            self.stdout.write(self.style.ERROR("No se encontro ninguna empresa."))
            return

        try:
            remote_qs = Category.objects.using('remote').filter(company_id=active_company.id).order_by('id')
            total = remote_qs.count()
            if not total:
                self.stdout.write(self.style.WARNING(f"No hay categorias para la empresa {active_company.name} en la BD remota."))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error obteniendo categorias remotas: {e}"))
            return

        synced = 0
        updated = 0
        errors = 0

        for remote_cat in remote_qs:
            try:
                @retry_on_database_lock()
                def sync_cat():
                    nonlocal synced, updated, errors

                    try:
                        local_cat = None
                        if remote_cat.external_code:
                            local_cat = Category.objects.using('default').filter(
                                external_code=remote_cat.external_code,
                                company_id=active_company.id
                            ).first()
                        if not local_cat:
                            local_cat = Category.objects.using('default').filter(
                                name=remote_cat.name,
                                company_id=active_company.id
                            ).first()

                        if local_cat:
                            local_cat.name = remote_cat.name
                            local_cat.category_type = getattr(remote_cat, 'category_type', 'category') or 'category'
                            local_cat.external_code = getattr(remote_cat, 'external_code', None)
                            local_cat.desc = getattr(remote_cat, 'desc', None) or ''
                            local_cat.save(using='default')
                            updated += 1
                        else:
                            Category.objects.using('default').create(
                                company_id=active_company.id,
                                name=remote_cat.name,
                                category_type=getattr(remote_cat, 'category_type', 'category') or 'category',
                                external_code=getattr(remote_cat, 'external_code', None),
                                desc=getattr(remote_cat, 'desc', None) or '',
                                synced_to_server=True,
                            )
                            synced += 1

                    except DatabaseError as e:
                        if 'database is locked' in str(e).lower():
                            raise
                        errors += 1
                        self.stderr.write(f"Error sincronizando categoria {remote_cat.name}: {e}")

                sync_cat()
            except DatabaseError as e:
                if 'database is locked' in str(e).lower():
                    errors += 1
                    self.stderr.write(f"DB locked sincronizando categoria {remote_cat.name}")
                else:
                    errors += 1
                    self.stderr.write(f"Error sincronizando categoria {remote_cat.name}: {e}")
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando categoria {remote_cat.name}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de categorias finalizada. Categorias creadas: {synced}, actualizadas: {updated}. Errores: {errors}."
        ))
