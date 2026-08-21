from django import template
from core.erp.services.server_sync_service import ServerSyncService

register = template.Library()


@register.simple_tag
def is_server_mode():
    return ServerSyncService.is_server_mode()
