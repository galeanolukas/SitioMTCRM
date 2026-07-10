from django.core.management.base import BaseCommand
from core.erp.models import AfipConfig, Company
from django.db import connections
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sincronizar configuraciones AFIP desde servidor remoto a POS locales'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se haría sin ejecutar cambios',
        )
        parser.add_argument(
            '--company-id',
            type=int,
            help='Sincronizar solo configuraciones de esta empresa (ID)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        company_id = options.get('company_id', None)

        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY-RUN: No se realizarán cambios reales"))

        if company_id:
            self.stdout.write(f"Sincronizando configuraciones AFIP solo para empresa ID: {company_id}")
        else:
            self.stdout.write("Sincronizando configuraciones AFIP para todas las empresas")

        self.stdout.write("Iniciando sincronización de configuraciones AFIP desde servidor remoto...")

        self.sync_afip_configs_from_server(dry_run, company_id)

        self.show_final_summary()

    def sync_afip_configs_from_server(self, dry_run=False, company_id=None):
        """Sincronizar configuraciones AFIP desde el servidor remoto

        Args:
            dry_run: Si es True, no ejecuta cambios reales
            company_id: Si se especifica, sincroniza solo configuraciones de esta empresa
        """
        try:
            remote_conn = connections['remote']

            with remote_conn.cursor() as cursor:
                # Obtener configuraciones AFIP del servidor
                if company_id:
                    cursor.execute('''
                        SELECT id, company_id, cuit, cert, key, access_token,
                               tipo_comprobante, concepto, moneda, cotizacion,
                               usar_contingencia, wsfe_authorized, wsfe_authorized_at,
                               wsfe_automation_id, clave_fiscal_username, clave_fiscal_password,
                               environment, is_active
                        FROM erp_afipconfig
                        WHERE company_id = %s
                        ORDER BY company_id
                    ''', [company_id])
                else:
                    cursor.execute('''
                        SELECT id, company_id, cuit, cert, key, access_token,
                               tipo_comprobante, concepto, moneda, cotizacion,
                               usar_contingencia, wsfe_authorized, wsfe_authorized_at,
                               wsfe_automation_id, clave_fiscal_username, clave_fiscal_password,
                               environment, is_active
                        FROM erp_afipconfig
                        ORDER BY company_id
                    ''')
                configs_servidor = cursor.fetchall()

                self.stdout.write(f"Configuraciones AFIP encontradas en servidor: {len(configs_servidor)}")

                synced_count = 0
                created_count = 0
                updated_count = 0

                for (config_id, company_id, cuit, cert, key, access_token,
                     tipo_comprobante, concepto, moneda, cotizacion,
                     usar_contingencia, wsfe_authorized, wsfe_authorized_at,
                     wsfe_automation_id, clave_fiscal_username, clave_fiscal_password,
                     environment, is_active) in configs_servidor:

                    try:
                        # Verificar si la empresa existe localmente
                        company = Company.objects.get(id=company_id)

                        # Si está en producción sin certificados, cambiar a desarrollo
                        if environment == 'prod' and (not cert or not key):
                            self.stdout.write(self.style.WARNING(f"  ! Config AFIP {config_id} en producción sin certificados. Cambiando a modo desarrollo."))
                            environment = 'dev'
                        
                        # Verificar si la configuración AFIP existe localmente
                        try:
                            config_local = AfipConfig.objects.get(id=config_id)
                            
                            # Verificar si necesita actualización
                            needs_update = (
                                config_local.cuit != cuit or
                                config_local.cert != cert or
                                config_local.key != key or
                                config_local.access_token != access_token or
                                config_local.tipo_comprobante != tipo_comprobante or
                                config_local.concepto != concepto or
                                config_local.moneda != moneda or
                                config_local.cotizacion != cotizacion or
                                config_local.usar_contingencia != usar_contingencia or
                                config_local.wsfe_authorized != wsfe_authorized or
                                config_local.clave_fiscal_username != clave_fiscal_username or
                                config_local.clave_fiscal_password != clave_fiscal_password or
                                config_local.environment != environment or
                                config_local.is_active != is_active
                            )

                            if needs_update:
                                if not dry_run:
                                    config_local.cuit = cuit
                                    config_local.cert = cert
                                    config_local.key = key
                                    config_local.access_token = access_token
                                    config_local.tipo_comprobante = tipo_comprobante
                                    config_local.concepto = concepto
                                    config_local.moneda = moneda
                                    config_local.cotizacion = cotizacion
                                    config_local.usar_contingencia = usar_contingencia
                                    config_local.wsfe_authorized = wsfe_authorized
                                    config_local.wsfe_authorized_at = wsfe_authorized_at
                                    config_local.wsfe_automation_id = wsfe_automation_id
                                    config_local.clave_fiscal_username = clave_fiscal_username
                                    config_local.clave_fiscal_password = clave_fiscal_password
                                    config_local.environment = environment
                                    config_local.is_active = is_active
                                    config_local.save()
                                updated_count += 1
                                synced_count += 1
                                self.stdout.write(f"  ✓ Actualizada config AFIP {config_id} para empresa {company.name}")

                        except AfipConfig.DoesNotExist:
                            # Crear configuración AFIP localmente
                            if not dry_run:
                                config_local = AfipConfig.objects.create(
                                    id=config_id,
                                    company=company,
                                    cuit=cuit,
                                    cert=cert,
                                    key=key,
                                    access_token=access_token,
                                    tipo_comprobante=tipo_comprobante,
                                    concepto=concepto,
                                    moneda=moneda,
                                    cotizacion=cotizacion,
                                    usar_contingencia=usar_contingencia,
                                    wsfe_authorized=wsfe_authorized,
                                    wsfe_authorized_at=wsfe_authorized_at,
                                    wsfe_automation_id=wsfe_automation_id,
                                    clave_fiscal_username=clave_fiscal_username,
                                    clave_fiscal_password=clave_fiscal_password,
                                    environment=environment,
                                    is_active=is_active
                                )
                            created_count += 1
                            synced_count += 1
                            self.stdout.write(f"  + Creada config AFIP {config_id} para empresa {company.name}")
                            
                    except Company.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"  ! Empresa {company_id} no existe localmente, omitiendo config AFIP {config_id}"))
                
                # Sincronización finalizada
                if configs_servidor:
                    self.stdout.write(self.style.SUCCESS(
                        f"Sincronización de configuraciones AFIP (servidor -> local) finalizada. "
                        f"Configuraciones sincronizadas: {synced_count} (Creadas: {created_count}, Actualizadas: {updated_count})."
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        "No se encontraron configuraciones AFIP para sincronizar."
                    ))
                
        except Exception as e:
            self.stderr.write(f"Error sincronizando configuraciones AFIP: {e}")
            logger.error(f"Error sincronizando configuraciones AFIP: {e}", exc_info=True)

    def show_final_summary(self):
        """Mostrar resumen final de la sincronización"""
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 RESUMEN DE SINCRONIZACIÓN DE CONFIGURACIONES AFIP"))
        self.stdout.write("=" * 80)
        
        try:
            total_configs = AfipConfig.objects.count()
            self.stdout.write(f"Total configuraciones AFIP en POS local: {total_configs}")
            
            # Mostrar por empresa
            for company in Company.objects.all():
                configs_count = AfipConfig.objects.filter(company=company).count()
                if configs_count > 0:
                    self.stdout.write(f"  - {company.name}: {configs_count} configuración(es)")
            
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"No se pudo generar resumen: {e}"))
        
        self.stdout.write("=" * 80)
