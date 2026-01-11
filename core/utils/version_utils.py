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


def get_latest_github_version(timeout=5):
    """
    Obtiene la última versión desde GitHub API.
    Intenta primero releases, si no hay usa tags como fallback.
    Retorna un diccionario con versión y descripción.
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
            message = tag_info.get('message', '')
            
            if tag.startswith('v'):
                tag = tag[1:]
            
            result = {
                'version': tag,
                'description': message,
                'published_at': tag_info.get('commit', {}).get('committer', {}).get('date', ''),
                'source': 'tag'
            }
            
            # Cache por 1 hora (3600 segundos)
            cache.set(cache_key, result, 3600)
            return result
        
        return None
        
    except (urllib.error.URLError, json.JSONDecodeError, Exception) as e:
        print(f"Tags API also failed: {e}")
        return None


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
