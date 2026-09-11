from django.core.management.base import BaseCommand
from django.db import transaction, connections
from core.erp.models import CardInstallmentPlan, Company


class Command(BaseCommand):
    help = "Sincroniza planes de cuotas de tarjeta desde la BD local hacia la BD remota."

    def handle(self, *args, **options):
        if 'remote' not in connections:
            self.stdout.write(self.style.ERROR('No hay conexión a base de datos remota configurada'))
            return

        # Verificar conectividad real antes de procesar
        try:
            connections['remote'].ensure_connection()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'No se puede conectar al servidor remoto: {e}'))
            return

        self.stdout.write(self.style.NOTICE("Iniciando sincronización de planes de cuotas hacia servidor remoto..."))

        local_plans = CardInstallmentPlan.objects.using('default').all().order_by('id')
        total = local_plans.count()

        if not total:
            self.stdout.write(self.style.WARNING("No hay planes de cuotas para sincronizar."))
            return

        synced = 0
        errors = 0

        for plan in local_plans:
            try:
                with transaction.atomic(using='remote'):
                    # Resolver empresa remota por CUIT o nombre
                    remote_company = None
                    if plan.company_id:
                        local_company = Company.objects.using('default').filter(pk=plan.company_id).first()
                        if local_company:
                            if local_company.cuit:
                                remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
                            if not remote_company:
                                remote_company = Company.objects.using('remote').filter(name=local_company.name).first()

                    # Buscar plan existente en remoto por nombre + empresa + marca + cuotas
                    remote_plan = None
                    lookup_fields = {
                        'name': plan.name,
                        'card_brand': plan.card_brand,
                        'installments': plan.installments,
                    }
                    if remote_company:
                        lookup_fields['company_id'] = remote_company.id
                        remote_plan = CardInstallmentPlan.objects.using('remote').filter(**lookup_fields).first()
                    if not remote_plan:
                        # Buscar solo por nombre + marca + cuotas (sin empresa)
                        remote_plan = CardInstallmentPlan.objects.using('remote').filter(
                            name=plan.name,
                            card_brand=plan.card_brand,
                            installments=plan.installments
                        ).first()

                    if remote_plan:
                        # Actualizar plan existente
                        if remote_company:
                            remote_plan.company_id = remote_company.id
                        remote_plan.name = plan.name
                        remote_plan.card_brand = plan.card_brand
                        remote_plan.installments = plan.installments
                        remote_plan.multiplier = plan.multiplier
                        remote_plan.afip_code = plan.afip_code
                        remote_plan.is_active = plan.is_active
                        remote_plan.save(using='remote')
                    else:
                        # Crear nuevo plan
                        CardInstallmentPlan.objects.using('remote').create(
                            company_id=remote_company.id if remote_company else None,
                            name=plan.name,
                            card_brand=plan.card_brand,
                            installments=plan.installments,
                            multiplier=plan.multiplier,
                            afip_code=plan.afip_code,
                            is_active=plan.is_active,
                        )

                    synced += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error sincronizando plan de cuotas {plan.id}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Sincronización de planes de cuotas finalizada. "
            f"Planes sincronizados: {synced} / {total}. Errores: {errors}."
        ))
