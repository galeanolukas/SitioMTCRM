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


UNLIMITED_LIMITS = {
    'plan_name': None,
    'max_products': None,      # None = ilimitado
    'max_users': None,         # None = ilimitado
    'allow_mp_qr': True,
    'allow_invoicing': True,
    'allow_catalog': True,
}


def get_company_limits(company_id):
    """Límites efectivos de la empresa según el plan de su suscripción.

    Empresa sin suscripción → todos los límites abiertos (instalaciones
    existentes sin plan no se ven afectadas).
    """
    limits = dict(UNLIMITED_LIMITS)
    if not company_id:
        return limits
    try:
        sub = (Subscription.objects
               .filter(company_id=company_id)
               .select_related('plan')
               .first())
    except Exception as e:
        logger.warning(f'get_company_limits falló para company {company_id}: {e}')
        return limits
    if not sub or not sub.plan:
        return limits

    plan = sub.plan
    limits.update({
        'plan_name': plan.name,
        'max_products': plan.max_products,
        'max_users': plan.max_users,
        'allow_mp_qr': plan.allow_mp_qr,
        'allow_invoicing': plan.allow_invoicing,
        'allow_catalog': plan.allow_catalog,
    })
    return limits


def check_product_limit(company_id):
    """Devuelve un mensaje de error si la empresa llegó al límite de
    productos de su plan, o None si puede seguir cargando."""
    limits = get_company_limits(company_id)
    max_products = limits.get('max_products')
    if not max_products:
        return None
    from core.erp.models import Product
    count = Product.objects.filter(company_id=company_id).count()
    if count >= max_products:
        return (
            f'Llegó al límite de {max_products} productos de su plan '
            f'({limits.get("plan_name")}). Amplíe su suscripción para cargar más.'
        )
    return None


def upsert_local_subscription(company, plan_name, plan_price, plan_duration_days,
                              start_date, end_date, grace_days, status, notes='',
                              plan_limits=None):
    """Crea/actualiza la suscripción local de una empresa (usado por sync remoto→local).

    plan_limits: dict opcional con los campos de límite del plan remoto
    (max_products, max_users, allow_mp_qr, allow_invoicing, allow_catalog).
    """
    from .models import SubscriptionPlan
    plan_fields = {'price': plan_price, 'duration_days': plan_duration_days}
    if plan_limits:
        plan_fields.update({k: v for k, v in plan_limits.items() if v is not None or k.startswith('max_')})
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name=plan_name,
        defaults=plan_fields,
    )
    changed = False
    updates = {}
    for field, value in plan_fields.items():
        if getattr(plan, field) != value:
            updates[field] = value
    if updates:
        for field, value in updates.items():
            setattr(plan, field, value)
        plan.save(update_fields=list(updates))
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
