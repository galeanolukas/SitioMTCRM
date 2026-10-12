"""Middleware de control de acceso por suscripción.

Se gobierna con el setting SUBSCRIPTION_ENFORCEMENT (.env):
  - 'off'     → no hace nada
  - 'warn'    → muestra avisos pero nunca bloquea (default, rollout seguro)
  - 'enforce' → bloquea el acceso a empresas con suscripción vencida/cancelada

La empresa sin suscripción cargada siempre tiene acceso (state='none').
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.shortcuts import render
from django.utils import timezone

from .services import get_company_access_state, BLOCKED_STATES

logger = logging.getLogger(__name__)

# Prefijos que nunca se bloquean: login/logout, assets, gestión de
# suscripciones (solo superuser llega igual), APIs de sync (el backup de
# datos debe seguir funcionando aunque la UI quede bloqueada) y páginas
# públicas del catálogo.
EXEMPT_PREFIXES = (
    '/admin',
    '/login',
    '/logout',
    '/static',
    '/media',
    '/favicon',
    '/subscriptions',
    '/erp/api/',
    '/erp/sync',
    '/erp/public/',
    '/erp/quick-cart/',
)

SESSION_STATE_KEY = '_sub_state'
SESSION_CHECKED_KEY = '_sub_checked_at'
SESSION_WARNED_KEY = '_sub_warned'
CACHE_SECONDS = 300  # re-chequear como máximo cada 5 minutos


class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if (not user or not user.is_authenticated or user.is_superuser
                or self._is_exempt(request.path)):
            return self.get_response(request)

        enforcement = getattr(settings, 'SUBSCRIPTION_ENFORCEMENT', 'warn')
        if enforcement == 'off':
            return self.get_response(request)

        info = self._company_state(request)
        state = info.get('state')

        if state in BLOCKED_STATES:
            if enforcement == 'enforce':
                return self._render_suspended(request, info)
            self._warn_once(
                request,
                'Su suscripción está suspendida por falta de pago. '
                'Regularice la cuota para evitar el bloqueo del sistema.'
            )
        elif state == 'grace':
            self._warn_once(
                request,
                f"Su suscripción venció. Período de gracia: "
                f"{info.get('grace_left', 0)} día(s) restante(s)."
            )
        elif state == 'active' and info.get('days_left') is not None \
                and info['days_left'] <= 7:
            self._warn_once(
                request,
                f"Su suscripción vence en {info['days_left']} día(s). "
                f"Renueve la cuota para evitar interrupciones."
            )

        return self.get_response(request)

    def _is_exempt(self, path):
        return any(path.startswith(p) for p in EXEMPT_PREFIXES)

    def _company_state(self, request):
        """Estado de suscripción cacheado en sesión (máx. CACHE_SECONDS)."""
        now = timezone.now()
        checked_at = request.session.get(SESSION_CHECKED_KEY)
        if checked_at:
            try:
                checked_dt = timezone.datetime.fromisoformat(checked_at)
                if now - checked_dt < timedelta(seconds=CACHE_SECONDS):
                    return request.session.get(SESSION_STATE_KEY) or {'state': 'none'}
            except (ValueError, TypeError):
                pass

        try:
            from core.erp.mixins import get_active_company_id
            company_id = get_active_company_id(request)
            info = get_company_access_state(company_id)
        except Exception as e:
            logger.warning(f'SubscriptionMiddleware: error obteniendo estado: {e}')
            info = {'state': 'none'}

        # En sesión solo se guardan valores simples (no el objeto)
        request.session[SESSION_STATE_KEY] = {
            'state': info.get('state'),
            'days_left': info.get('days_left'),
            'days_overdue': info.get('days_overdue'),
            'grace_left': info.get('grace_left'),
        }
        request.session[SESSION_CHECKED_KEY] = now.isoformat()
        return info

    def _warn_once(self, request, message):
        if request.session.get(SESSION_WARNED_KEY) == message:
            return
        request.session[SESSION_WARNED_KEY] = message
        try:
            messages.warning(request, message)
        except Exception:
            pass

    def _render_suspended(self, request, info):
        try:
            from core.erp.mixins import get_active_company_id
            from core.erp.models import Company
            company = Company.objects.filter(pk=get_active_company_id(request)).first()
        except Exception:
            company = None
        return render(request, 'subscriptions/suspended.html', {
            'title': 'Suscripción suspendida',
            'company': company,
            'days_overdue': info.get('days_overdue'),
            'state': info.get('state'),
        }, status=403)
