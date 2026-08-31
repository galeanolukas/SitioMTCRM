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
    Ejecuta el script de actualización simplificado.
    """
    try:
        import platform
        system_os = platform.system().lower()
        
        # Obtener el directorio base del proyecto
        base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
        
        # Obtener parámetros del request
        data = json.loads(request.body) if request.body else {}
        force = data.get('force', False)
        
        # Script Python unificado
        script_path = os.path.join(base_dir, 'update_system.py')
        
        # Verificar que el script existe
        if not os.path.exists(script_path):
            return JsonResponse({
                'success': False,
                'error': f'No se encuentra el script de actualización: {script_path}'
            }, status=404)
        
        # Construir comando según el sistema operativo
        if system_os == 'windows':
            # En Windows, usar el script .bat que llama al Python
            update_type = data.get('type', 'auto')
            if update_type == 'portable':
                bat_script = os.path.join(base_dir, 'actualizar_pos_portable.bat')
            else:
                bat_script = os.path.join(base_dir, 'actualizar_pos_simple.bat')
            command = ['start', 'cmd', '/c', bat_script, '--force']
        elif system_os == 'linux':
            # En Linux, ejecutar directamente el script Python con --force (sin prompt interactivo)
            command = ['python3', script_path, '--force']
        else:
            return JsonResponse({
                'success': False,
                'error': f'Sistema operativo no soportado: {system_os}'
            }, status=400)
        
        # Ejecutar el script en segundo plano
        try:
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
                'message': 'Actualización iniciada en segundo plano',
                'data': {
                    'script': script_path,
                    'pid': process.pid if hasattr(process, 'pid') else None,
                    'os': system_os,
                    'force': force
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
        candidates = [
            os.path.join(base_dir, 'tools', 'PortableGit', 'cmd', 'git.exe'),
            os.path.join(base_dir, 'tools', 'PortableGit', 'mingw64', 'bin', 'git.exe'),
            os.path.join(base_dir, 'tools', 'PortableGit', 'mingw64', 'libexec', 'git-core', 'git.exe'),
            os.path.join(base_dir, 'tools', 'PortableGit', 'bin', 'git.exe'),
        ]
        git_portable_path = next((p for p in candidates if os.path.exists(p)), candidates[-1])
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
def check_update_status(request):
    """
    Verifica el estado del sistema para actualización.
    """
    try:
        import sys
        import platform
        
        # Obtener el directorio base del proyecto
        base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
        script_path = os.path.join(base_dir, 'update_system.py')
        
        # Ejecutar script para obtener estado
        if os.path.exists(script_path):
            result = subprocess.run([
                sys.executable, script_path, '--status', '--json'
            ], cwd=base_dir, capture_output=True, text=True)
            
            if result.returncode == 0:
                import json
                status = json.loads(result.stdout)
                return JsonResponse({
                    'success': True,
                    'status': status
                })
        
        # Fallback: verificación manual
        status = {
            'script_available': os.path.exists(script_path),
            'git_available': False,
            'git_repo': False,
            'has_changes': False,
            'system_os': platform.system().lower(),
            'base_dir': base_dir
        }
        
        # Verificar Git
        try:
            subprocess.run(['git', '--version'], capture_output=True, check=True)
            status['git_available'] = True
        except:
            pass
        
        # Verificar repositorio
        if os.path.exists(os.path.join(base_dir, '.git')):
            status['git_repo'] = True
            
            # Verificar cambios
            try:
                result = subprocess.run(
                    ['git', 'diff-index', '--quiet', 'HEAD', '--'],
                    cwd=base_dir,
                    capture_output=True
                )
                status['has_changes'] = result.returncode != 0
            except:
                pass
        
        return JsonResponse({
            'success': True,
            'status': status
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
