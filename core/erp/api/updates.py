"""
API endpoints para gestión de actualizaciones.
"""
import os
import subprocess
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings
from core.utils.version_utils import get_version_info, get_latest_github_version


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


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def execute_update_script(request):
    """
    Ejecuta el script de actualización según el sistema operativo.
    """
    try:
        import platform
        system_os = platform.system().lower()
        
        # Obtener el directorio base del proyecto
        base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
        
        if system_os == 'windows':
            script_path = os.path.join(base_dir, 'actualizar_pos.bat')
            command = ['cmd', '/c', script_path]
        elif system_os == 'linux':
            script_path = os.path.join(base_dir, 'actualizar_pos.sh')
            # Hacer el script ejecutable
            os.chmod(script_path, 0o755)
            command = ['bash', script_path]
        else:
            return JsonResponse({
                'success': False,
                'error': f'Sistema operativo no soportado: {system_os}'
            }, status=400)
        
        # Verificar que el script existe
        if not os.path.exists(script_path):
            return JsonResponse({
                'success': False,
                'error': f'No se encuentra el script de actualización: {script_path}'
            }, status=404)
        
        # Ejecutar el script en segundo plano
        try:
            # En Windows, usar START para abrir en nueva ventana
            if system_os == 'windows':
                process = subprocess.Popen(
                    ['start', 'cmd', '/c', script_path],
                    shell=True,
                    cwd=base_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # En Linux, ejecutar en segundo plano
                process = subprocess.Popen(
                    command,
                    cwd=base_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
            
            return JsonResponse({
                'success': True,
                'message': 'Script de actualización iniciado',
                'data': {
                    'script': script_path,
                    'pid': process.pid if hasattr(process, 'pid') else None,
                    'os': system_os
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error al ejecutar el script: {str(e)}'
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error general: {str(e)}'
        }, status=500)
