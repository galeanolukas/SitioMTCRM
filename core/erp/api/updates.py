"""
API endpoints para gestión de actualizaciones.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from core.utils.version_utils import get_version_info, get_latest_github_version
import json


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def check_updates_api(request):
    """
    API endpoint para verificar actualizaciones.
    Retorna JSON con información de versiones.
    """
    try:
        version_info = get_version_info()
        return JsonResponse({
            'success': True,
            'data': version_info
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def refresh_version_info(request):
    """
    Fuerza la actualización del cache de versiones desde GitHub.
    """
    try:
        from django.core.cache import cache
        cache.delete('github_latest_version')
        
        latest_version = get_latest_github_version()
        version_info = get_version_info()
        
        return JsonResponse({
            'success': True,
            'message': 'Información de versión actualizada',
            'data': version_info
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
