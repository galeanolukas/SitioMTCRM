"""
Herramientas de diagnóstico para el sistema de versiones.
"""
import platform
import urllib.request
import json
import subprocess
from django.conf import settings


def diagnose_version_system():
    """
    Diagnostica el sistema de detección de versiones.
    Retorna un reporte detallado del estado del sistema.
    """
    report = {
        'system_info': {},
        'network_tests': {},
        'git_tests': {},
        'api_tests': {},
        'recommendations': []
    }
    
    # Información del sistema
    report['system_info'] = {
        'platform': platform.system(),
        'platform_release': platform.release(),
        'platform_version': platform.version(),
        'python_version': platform.python_version(),
        'django_version': getattr(settings, 'VERSION', 'Unknown'),
        'app_version': getattr(settings, 'APP_VERSION', 'Unknown')
    }
    
    # Tests de red
    try:
        import urllib.request
        response = urllib.request.urlopen('https://api.github.com/rate_limit', timeout=5)
        rate_data = json.loads(response.read().decode('utf-8'))
        report['network_tests']['github_api'] = {
            'status': 'OK',
            'rate_limit': rate_data.get('rate', {}),
            'message': 'GitHub API accesible'
        }
    except Exception as e:
        report['network_tests']['github_api'] = {
            'status': 'ERROR',
            'error': str(e),
            'message': 'No se puede acceder a GitHub API'
        }
        report['recommendations'].append('Verifique la conexión a internet y firewall')
    
    # Tests de Git
    try:
        result = subprocess.run(['git', '--version'], capture_output=True, text=True, timeout=5)
        report['git_tests']['git_command'] = {
            'status': 'OK',
            'version': result.stdout.strip(),
            'message': 'Git command disponible'
        }
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
        report['git_tests']['git_command'] = {
            'status': 'ERROR',
            'error': str(e),
            'message': 'Git command no disponible'
        }
        report['recommendations'].append('Instale Git o use Git Portable')
    
    # Test de git ls-remote
    try:
        result = subprocess.run(
            ['git', 'ls-remote', '--tags', 'https://github.com/galeanolukas/SitioMTCRM.git'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            latest_tag = lines[-1].split('\t')[-1].replace('refs/tags/', '') if lines else 'None'
            report['git_tests']['git_ls_remote'] = {
                'status': 'OK',
                'tags_found': len(lines),
                'latest_tag': latest_tag,
                'message': 'git ls-remote funciona'
            }
        else:
            report['git_tests']['git_ls_remote'] = {
                'status': 'ERROR',
                'return_code': result.returncode,
                'stderr': result.stderr.strip(),
                'message': 'git ls-remote falló'
            }
    except Exception as e:
        report['git_tests']['git_ls_remote'] = {
            'status': 'ERROR',
            'error': str(e),
            'message': 'git ls-remote no disponible'
        }
    
    # Tests de API
    api_endpoints = [
        ('releases_latest', 'https://api.github.com/repos/galeanolukas/SitioMTCRM/releases/latest'),
        ('tags', 'https://api.github.com/repos/galeanolukas/SitioMTCRM/tags')
    ]
    
    for name, url in api_endpoints:
        try:
            req = urllib.request.Request(
                url,
                headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'SitioMTCRM-Updater'}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                
                if name == 'releases_latest':
                    report['api_tests'][name] = {
                        'status': 'OK' if data.get('tag_name') else 'NO_RELEASES',
                        'tag_name': data.get('tag_name', 'None'),
                        'message': 'Releases API disponible' if data.get('tag_name') else 'No hay releases'
                    }
                else:  # tags
                    report['api_tests'][name] = {
                        'status': 'OK',
                        'tags_count': len(data),
                        'latest_tag': data[0]['name'] if data else 'None',
                        'message': 'Tags API disponible'
                    }
        except Exception as e:
            report['api_tests'][name] = {
                'status': 'ERROR',
                'error': str(e),
                'message': f'Error en {name} API'
            }
    
    # Recomendaciones adicionales
    if report['git_tests'].get('git_command', {}).get('status') != 'OK':
        report['recommendations'].append('Use Git Portable para Windows sin instalación')
    
    if report['network_tests'].get('github_api', {}).get('status') != 'OK':
        report['recommendations'].append('Verifique proxy o configuración de red')
    
    if report['api_tests'].get('releases_latest', {}).get('status') == 'NO_RELEASES':
        report['recommendations'].append('Cree releases en GitHub para mejor información')
    
    return report


def print_diagnostic_report():
    """
    Imprime un reporte de diagnóstico legible.
    """
    report = diagnose_version_system()
    
    print("=" * 60)
    print("DIAGNÓSTICO DEL SISTEMA DE VERSIONES")
    print("=" * 60)
    
    print("\n📋 INFORMACIÓN DEL SISTEMA:")
    for key, value in report['system_info'].items():
        print(f"  {key}: {value}")
    
    print("\n🌐 TESTS DE RED:")
    for test, result in report['network_tests'].items():
        status_icon = "✅" if result['status'] == 'OK' else "❌"
        print(f"  {status_icon} {test}: {result['message']}")
        if result['status'] != 'OK':
            print(f"    Error: {result.get('error', 'Unknown')}")
    
    print("\n🔧 TESTS DE GIT:")
    for test, result in report['git_tests'].items():
        status_icon = "✅" if result['status'] == 'OK' else "❌"
        print(f"  {status_icon} {test}: {result['message']}")
        if result['status'] == 'OK' and 'version' in result:
            print(f"    Versión: {result['version']}")
        elif result['status'] == 'OK' and 'latest_tag' in result:
            print(f"    Último tag: {result['latest_tag']}")
        elif result['status'] != 'OK':
            print(f"    Error: {result.get('error', 'Unknown')}")
    
    print("\n🔌 TESTS DE API:")
    for test, result in report['api_tests'].items():
        status_icon = "✅" if result['status'] == 'OK' else "⚠️" if result['status'] == 'NO_RELEASES' else "❌"
        print(f"  {status_icon} {test}: {result['message']}")
        if 'tag_name' in result:
            print(f"    Tag: {result['tag_name']}")
        elif 'latest_tag' in result:
            print(f"    Último tag: {result['latest_tag']}")
        elif 'tags_count' in result:
            print(f"    Tags encontrados: {result['tags_count']}")
    
    if report['recommendations']:
        print("\n💡 RECOMENDACIONES:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"  {i}. {rec}")
    
    print("\n" + "=" * 60)
