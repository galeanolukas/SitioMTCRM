"""Baja las suscripciones del servidor central al POS local.

El servidor es la fuente de verdad del estado de suscripción de cada empresa.
El POS local copia plan/vencimiento/estado para que el middleware de
suscripción pueda bloquear el acceso también sin conexión permanente.
"""
from django.core.management.base import BaseCommand
from django.db import connections

from core.erp.management.commands._restore_common import (
    get_local_company, resolve_remote_company,
)
from core.erp.models import Company
from core.subscriptions.models import Subscription, SubscriptionPlan


class Command(BaseCommand):
    help = 'Sincroniza suscripciones del servidor remoto al local (por CUIT de empresa)'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, default=None,
                            help='ID de empresa local (default: empresa del usuario activo)')

    def handle(self, *args, **options):
        local_company = get_local_company(options.get('company_id'))
        if not local_company:
            self.stdout.write(self.style.ERROR('No hay empresa local para sincronizar'))
            return

        remote_company = resolve_remote_company(local_company, self.stdout)
        if not remote_company:
            self.stdout.write(self.style.ERROR('No se encontró la empresa en el servidor'))
            return

        # Servidor aún sin la app de suscripciones (tabla no migrada)
        try:
            with connections['remote'].cursor() as cur:
                cur.execute("SELECT 1 FROM subscriptions_subscription LIMIT 1")
        except Exception:
            self.stdout.write('El servidor aún no tiene suscripciones (tabla no migrada) — omitido')
            return

        remote_sub = (Subscription.objects.using('remote')
                      .filter(company_id=remote_company.id)
                      .select_related('plan')
                      .first())
        if not remote_sub:
            self.stdout.write('La empresa no tiene suscripción en el servidor (nada que bajar)')
            return

        remote_plan = remote_sub.plan
        plan, _ = SubscriptionPlan.objects.update_or_create(
            name=remote_plan.name,
            defaults={
                'price': remote_plan.price,
                'duration_days': remote_plan.duration_days,
            },
        )

        sub, created = Subscription.objects.update_or_create(
            company=local_company,
            defaults={
                'plan': plan,
                'start_date': remote_sub.start_date,
                'end_date': remote_sub.end_date,
                'grace_days': remote_sub.grace_days,
                'status': remote_sub.status,
                'notes': remote_sub.notes or '',
            },
        )

        state = sub.effective_state()
        self.stdout.write(self.style.SUCCESS(
            f"Suscripción {'creada' if created else 'actualizada'} para {local_company.name}: "
            f"vence {sub.end_date} (estado: {state})"
        ))
