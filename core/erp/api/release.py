from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import subprocess
import os
import json
from django.conf import settings


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def execute_release(request):
    """
    Ejecuta el proceso de release automático
    """
    try:
        # Parsear datos del request
        data = json.loads(request.body)
        command = data.get('command', '')
        release_type = data.get('release_type', 'patch')
        commit_message = data.get('commit_message', '')
        
        # Validar comando
        if not command or 'release_manager.py' not in command:
            return JsonResponse({
                'success': False,
                'error': 'Comando inválido'
            })
        
        # Directorio base
        base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
        script_path = os.path.join(base_dir, 'release_manager.py')
        
        # Verificar si existe el script
        if not os.path.exists(script_path):
            return JsonResponse({
                'success': False,
                'error': 'No se encuentra el script release_manager.py'
            })
        
        # Construir comando completo
        full_command = f"python3 {script_path} {release_type}"
        if commit_message.strip():
            full_command += f' "{commit_message}"'
        
        # Ejecutar el comando
        try:
            result = subprocess.run(
                full_command,
                cwd=base_dir,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutos máximo
            )
            
            if result.returncode == 0:
                return JsonResponse({
                    'success': True,
                    'message': 'Release completado exitosamente',
                    'output': result.stdout
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Error en ejecución: {result.stderr}',
                    'output': result.stdout
                })
                
        except subprocess.TimeoutExpired:
            return JsonResponse({
                'success': False,
                'error': 'Tiempo de espera agotado (5 minutos)'
            })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Datos inválidos'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error inesperado: {str(e)}'
        })
