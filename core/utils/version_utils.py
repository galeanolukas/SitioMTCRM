"""
Utilidades para manejo de versiones y actualizaciones.
"""
import json
import urllib.request
import urllib.error
from packaging import version
from django.conf import settings
from django.core.cache import cache


def parse_version(version_string):
    """
    Parsea una versión string a un objeto Version comparable.
    Maneja formatos como 'v1.0.1', '1.0.1', 'dev-abc123'.
    """
    if not version_string:
        return None
    
    # Remover prefijo 'v' si existe
    clean_version = version_string.lstrip('v')
    
    # Para versiones de desarrollo, devolver None para no comparar
    if clean_version.startswith('dev-'):
        return None
    
    try:
        return version.parse(clean_version)
    except Exception:
        return None


def is_newer_version(latest_version, current_version):
    """
    Compara dos versiones usando semver.
    Retorna True si latest_version > current_version.
    """
    latest_parsed = parse_version(latest_version)
    current_parsed = parse_version(current_version)
    
    if not latest_parsed or not current_parsed:
        return False
    
    return latest_parsed > current_parsed


def get_latest_github_version_fallback(timeout=10):
    """
    Método alternativo para obtener versión desde GitHub.
    Usa diferentes enfoques para máxima compatibilidad.
    """
    try:
        # Método 1: Usar subprocess con git command si está disponible
        import subprocess
        
        # Intentar obtener el último tag con git command
        try:
            result = subprocess.run(
                ['git', 'ls-remote', '--tags', 'https://github.com/galeanolukas/SitioMTCRM.git'],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    # Obtener el tag más reciente (última línea)
                    latest_line = lines[-1]
                    tag = latest_line.split('\t')[-1].replace('refs/tags/', '')
                    if tag.endswith('^{}'):
                        tag = tag[:-3]
                    
                    if tag.startswith('v'):
                        tag = tag[1:]
                    
                    return {
                        'version': tag,
                        'description': f'Versión {tag}',
                        'published_at': '',
                        'source': 'git-remote'
                    }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Método 2: Usar requests si urllib falla
        try:
            import requests
            response = requests.get(
                'https://api.github.com/repos/galeanolukas/SitioMTCRM/tags',
                headers={
                    'Accept': 'application/vnd.github+json',
                    'User-Agent': 'SitioMTCRM-Updater'
                },
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    tag = data[0]['name']
                    if tag.startswith('v'):
                        tag = tag[1:]
                    
                    return {
                        'version': tag,
                        'description': f'Versión {tag}',
                        'published_at': '',
                        'source': 'requests-api'
                    }
        except ImportError:
            pass
        except Exception:
            pass
        
        # Método 3: Versión hardcoded como último recurso
        return {
            'version': '1.2.0',
            'description': 'Última versión estable',
            'published_at': '',
            'source': 'fallback'
        }
        
    except Exception:
        return None


def get_latest_github_version(timeout=10):
    """
    Obtiene la última versión desde GitHub API.
    Intenta primero releases, si no hay usa tags como fallback.
    Retorna un diccionario con versión y descripción.
    Compatible con Linux y Windows.
    """
    cache_key = 'github_latest_version'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return cached_data
    
    # Primero intentar con releases/latest
    try:
        url = 'https://api.github.com/repos/galeanolukas/SitioMTCRM/releases/latest'
        req = urllib.request.Request(
            url, 
            headers={
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'SitioMTCRM-Updater'
            }
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        tag = data.get('tag_name', '')
        description = data.get('body', '')
        published_at = data.get('published_at', '')
        
        if tag.startswith('v'):
            tag = tag[1:]
        
        result = {
            'version': tag,
            'description': description,
            'published_at': published_at,
            'source': 'release'
        }
        
        # Cache por 1 hora (3600 segundos)
        cache.set(cache_key, result, 3600)
        return result
        
    except (urllib.error.URLError, json.JSONDecodeError, Exception) as e:
        print(f"Releases API failed, trying tags: {e}")
    
    # Fallback a tags si releases no funciona
    try:
        url = 'https://api.github.com/repos/galeanolukas/SitioMTCRM/tags'
        req = urllib.request.Request(
            url, 
            headers={
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'SitioMTCRM-Updater'
            }
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        # Obtener el tag más reciente (el primero de la lista)
        if data and len(data) > 0:
            tag_info = data[0]
            tag = tag_info.get('name', '')
            
            if tag.startswith('v'):
                tag = tag[1:]
            
            # Obtener información del commit para la descripción y fecha
            commit_sha = tag_info.get('commit', {}).get('sha', '')
            commit_url = tag_info.get('commit', {}).get('url', '')
            
            description = f'Tag {tag} creado'
            published_at = ''
            
            if commit_url:
                try:
                    # Obtener información detallada del commit
                    commit_req = urllib.request.Request(
                        commit_url,
                        headers={
                            'Accept': 'application/vnd.github+json',
                            'User-Agent': 'SitioMTCRM-Updater'
                        }
                    )
                    
                    with urllib.request.urlopen(commit_req, timeout=timeout) as commit_resp:
                        commit_data = json.loads(commit_resp.read().decode('utf-8'))
                    
                    # Extraer mensaje del commit
                    commit_message = commit_data.get('commit', {}).get('message', '')
                    if commit_message:
                        # Usar solo la primera línea del mensaje
                        description = commit_message.split('\n')[0]
                    
                    # Extraer fecha del commit
                    commit_date = commit_data.get('commit', {}).get('committer', {}).get('date', '')
                    if commit_date:
                        published_at = commit_date
                        
                except Exception as commit_error:
                    print(f"Could not fetch commit details: {commit_error}")
                    # Usar información básica del tag
                    description = f'Actualización {tag}'
                    published_at = tag_info.get('commit', {}).get('url', '').split('/')[-1][:8]  # Usar SHA como fallback
            
            result = {
                'version': tag,
                'description': description,
                'published_at': published_at,
                'source': 'tag'
            }
            
            # Cache por 1 hora (3600 segundos)
            cache.set(cache_key, result, 3600)
            return result
        
        return None
        
    except (urllib.error.URLError, json.JSONDecodeError, Exception) as e:
        print(f"Tags API also failed: {e}")
    
    # Fallback final si todos los métodos anteriores fallan
    print("Using fallback method for version detection...")
    return get_latest_github_version_fallback(timeout)


def get_version_info():
    """
    Retorna información completa de versiones.
    """
    current_version = getattr(settings, 'APP_VERSION', '1.0.0')
    latest_data = get_latest_github_version()
    
    if latest_data:
        latest_version = latest_data.get('version')
        latest_description = latest_data.get('description', '')
        latest_published = latest_data.get('published_at', '')
        source = latest_data.get('source', 'unknown')
    else:
        latest_version = None
        latest_description = ''
        latest_published = ''
        source = 'none'
    
    update_available = is_newer_version(latest_version, current_version)
    
    return {
        'current_version': current_version,
        'latest_version': latest_version,
        'latest_description': latest_description,
        'latest_published': latest_published,
        'source': source,
        'update_available': update_available,
        'is_dev_version': current_version.startswith('dev-')
    }


def format_version_display(version_string):
    """
    Formatea una versión para mostrar en la UI.
    """
    if not version_string:
        return 'Desconocida'
    
    if version_string.startswith('dev-'):
        return f'Desarrollo ({version_string})'
    
    return f'v{version_string.lstrip("v")}'
