"""Lógica de estado de suscripciones compartida por middleware y verificación remota."""
import logging

from django.utils import timezone

from .models import Subscription

logger = logging.getLogger(__name__)

STATE_NONE = 'none'            # La empresa no tiene suscripción cargada (se permite el acceso)
STATE_ACTIVE = 'active'
STATE_GRACE = 'grace'
STATE_SUSPENDED = 'suspended'
STATE_CANCELLED = 'cancelled'

BLOCKED_STATES = (STATE_SUSPENDED, STATE_CANCELLED)


def get_company_access_state(company_id, today=None):
    """Estado de acceso de una empresa según su suscripción.

    Devuelve dict: {
        'state': 'none'|'active'|'grace'|'suspended'|'cancelled',
        'subscription': Subscription|None,
        'days_left': int|None,      # días hasta el vencimiento (negativo si venció)
        'days_overdue': int|None,   # días vencida (0 si no venció)
        'grace_left': int|None,     # días de gracia restantes (solo en 'grace')
    }
    Empresas sin suscripción devuelven state='none' (acceso permitido).
    """
    info = {
        'state': STATE_NONE, 'subscription': None,
        'days_left': None, 'days_overdue': None, 'grace_left': None,
    }
    if not company_id:
        return info
    try:
        sub = (Subscription.objects
               .filter(company_id=company_id)
               .select_related('plan', 'company')
               .first())
    except Exception as e:
        # Tabla aún no migrada u otro error: no bloquear por fallas.
        logger.warning(f'get_company_access_state falló para company {company_id}: {e}')
        return info
    if not sub:
        return info

    today = today or timezone.localdate()
    state = sub.effective_state(today)
    info.update({
        'state': state,
        'subscription': sub,
        'days_left': sub.days_left(today),
        'days_overdue': sub.days_overdue(today),
    })
    if state == STATE_GRACE:
        info['grace_left'] = sub.grace_days - info['days_overdue']
    return info


def upsert_local_subscription(company, plan_name, plan_price, plan_duration_days,
                              start_date, end_date, grace_days, status, notes=''):
    """Crea/actualiza la suscripción local de una empresa (usado por sync remoto→local)."""
    from .models import SubscriptionPlan
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name=plan_name,
        defaults={'price': plan_price, 'duration_days': plan_duration_days},
    )
    changed = False
    if plan.price != plan_price or plan.duration_days != plan_duration_days:
        plan.price = plan_price
        plan.duration_days = plan_duration_days
        plan.save(update_fields=['price', 'duration_days'])
        changed = True
    sub, created = Subscription.objects.update_or_create(
        company=company,
        defaults={
            'plan': plan,
            'start_date': start_date,
            'end_date': end_date,
            'grace_days': grace_days,
            'status': status,
            'notes': notes or '',
        },
    )
    return sub, created or changed
