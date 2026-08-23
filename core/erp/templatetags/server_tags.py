from django import template
from core.erp.services.server_sync_service import ServerSyncService

register = template.Library()


@register.simple_tag
def is_server_mode():
    return ServerSyncService.is_server_mode()


@register.filter
def has_group(user, group_names):
    """Verifica si el usuario pertenece a alguno de los grupos especificados (separados por coma)."""
    if not user or not user.is_authenticated:
        return False
    names = [n.strip() for n in group_names.split(',')]
    return user.groups.filter(name__in=names).exists()
