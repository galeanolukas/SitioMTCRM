from django.core.management.base import BaseCommand
from django.db import transaction, OperationalError, connections
from django.contrib.auth import get_user_model
import time

from core.erp.models import CatalogoConfig


class Command(BaseCommand):
    help = "Sincroniza configuraciones de catálogo desde la BD remota (remote) hacia la BD local (default). El servidor es la fuente de verdad."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando sincronizacion de configs de catalogo desde servidor remoto hacia POS local..."))

        # Asegurar que la conexion remota este activa
        try:
            conn = connections['remote']
            conn.close_if_unusable_or_obsolete()
            conn.ensure_connection()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"No se pudo conectar a la BD remota: {e}"))
            return

        remote_qs = CatalogoConfig.objects.using('remote').all().order_by('id')
        total = remote_qs.count()
        if not total:
            self.stdout.write(self.style.WARNING("No hay configuraciones de catalogo en la BD remota para sincronizar."))
            return

        User = get_user_model()
        synced = 0
        errors = 0

        for r in remote_qs:
            max_retries = 3
            retry_count = 0
            success = False

            while retry_count < max_retries and not success:
                try:
                    with transaction.atomic(using='default'):
                        # Ubicar config local por ID remoto, luego por empresa+URL
                        local_obj = CatalogoConfig.objects.using('default').filter(pk=r.id).first()

                        if not local_obj and r.company_id:
                            local_obj = CatalogoConfig.objects.using('default').filter(
                                company_id=r.company_id,
                                catalogo_url=r.catalogo_url
                            ).first()

                        # created_by solo si el usuario existe en local
                        created_by = None
                        if r.created_by_id:
                            created_by = User.objects.using('default').filter(pk=r.created_by_id).first()

                        if local_obj is None:
                            local_obj = CatalogoConfig.objects.using('default').create(
                                id=r.id,
                                company_id=r.company_id,
                                catalogo_url=r.catalogo_url,
                                api_key=r.api_key,
                                erp_username=r.erp_username,
                                erp_password=r.erp_password,
                                created_by=created_by,
                                is_active=r.is_active,
                                auto_sync=r.auto_sync,
                                sync_interval_hours=r.sync_interval_hours,
                                last_sync=r.last_sync,
                            )
                        else:
                            local_obj.company_id = r.company_id
                            local_obj.catalogo_url = r.catalogo_url
                            local_obj.api_key = r.api_key
                            local_obj.erp_username = r.erp_username
                            local_obj.erp_password = r.erp_password
                            local_obj.created_by = created_by or local_obj.created_by
                            local_obj.is_active = r.is_active
                            local_obj.auto_sync = r.auto_sync
                            local_obj.sync_interval_hours = r.sync_interval_hours
                            local_obj.last_sync = r.last_sync
                            local_obj.save()

                    synced += 1
                    success = True
                except OperationalError as e:
                    if "database is locked" in str(e).lower():
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 1 * retry_count  # Esperar 1s, 2s, 3s
                            self.stdout.write(f"Base de datos bloqueada, reintentando en {wait_time}s... (intento {retry_count}/{max_retries})")
                            time.sleep(wait_time)
                        else:
                            errors += 1
                            self.stderr.write(f"Error sincronizando config remota {r.id} después de {max_retries} reintentos: {e}")
                    else:
                        errors += 1
                        self.stderr.write(f"Error sincronizando config remota {r.id}: {e}")
                        break
                except Exception as e:
                    errors += 1
                    self.stderr.write(f"Error sincronizando config remota {r.id}: {e}")
                    break

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacion de configs de catalogo (remoto -> local) finalizada. Configs sincronizadas: {synced} / {total}. Errores: {errors}."
        ))
