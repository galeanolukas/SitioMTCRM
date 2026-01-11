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
        
        # Obtener el tipo de actualización desde el request
        data = json.loads(request.body) if request.body else {}
        update_type = data.get('type', 'auto')  # auto, portable
        
        if system_os == 'windows':
            if update_type == 'portable':
                script_path = os.path.join(base_dir, 'actualizar_pos_portable.bat')
                # Verificar si Git Portable está configurado
                git_portable_path = os.path.join(base_dir, 'tools', 'git-portable', 'bin', 'git.exe')
                if not os.path.exists(git_portable_path):
                    # Ejecutar setup primero
                    setup_script = os.path.join(base_dir, 'setup_git_portable.bat')
                    if os.path.exists(setup_script):
                        process = subprocess.Popen(
                            ['start', 'cmd', '/c', setup_script],
                            shell=True,
                            cwd=base_dir,
                            creationflags=subprocess.CREATE_NEW_CONSOLE
                        )
                        return JsonResponse({
                            'success': True,
                            'message': 'Configurando Git Portable...',
                            'data': {
                                'script': setup_script,
                                'pid': process.pid if hasattr(process, 'pid') else None,
                                'os': system_os,
                                'setup_required': True
                            }
                        })
                
                command = ['start', 'cmd', '/c', script_path]
            else:
                script_path = os.path.join(base_dir, 'actualizar_pos.bat')
                command = ['start', 'cmd', '/c', script_path]
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
                    command,
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
                    'os': system_os,
                    'type': update_type
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


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def check_git_portable(request):
    """
    Verifica si Git Portable está configurado.
    """
    try:
        base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
        git_portable_path = os.path.join(base_dir, 'tools', 'git-portable', 'bin', 'git.exe')
        
        git_portable_ready = os.path.exists(git_portable_path)
        
        return JsonResponse({
            'success': True,
            'git_portable_ready': git_portable_ready,
            'git_portable_path': git_portable_path
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def version_diagnostics(request):
    """
    Endpoint para diagnóstico del sistema de versiones.
    """
    try:
        from core.utils.version_diagnostics import diagnose_version_system
        report = diagnose_version_system()
        
        return JsonResponse({
            'success': True,
            'diagnostics': report
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
