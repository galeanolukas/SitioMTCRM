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


GITHUB_REPO = 'galeanolukas/SitioMTCRM'


def get_latest_github_version(timeout=5):
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

    # Intentar releases primero
    data = _fetch_github_releases(timeout)
    if data:
        cache.set(cache_key, data, 300)  # cachear 5 minutos
        return data

    # Fallback: tags
    data = _fetch_github_tags(timeout)
    if data:
        cache.set(cache_key, data, 300)
        return data

    return None


def _fetch_github_releases(timeout=5):
    """Obtiene el release más reciente desde GitHub API."""
    url = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'SitioMTCRM-Update-Check',
            'Accept': 'application/vnd.github.v3+json',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return {
                'version': (data.get('tag_name') or '').lstrip('v'),
                'description': data.get('body') or data.get('name') or '',
                'published_at': data.get('published_at') or '',
                'source': 'github_release',
            }
    except Exception:
        return None


def _fetch_github_tags(timeout=5):
    """Obtiene el tag más reciente desde GitHub API como fallback."""
    url = f'https://api.github.com/repos/{GITHUB_REPO}/tags'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'SitioMTCRM-Update-Check',
            'Accept': 'application/vnd.github.v3+json',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            tags = json.loads(resp.read().decode('utf-8'))
            if tags and isinstance(tags, list) and len(tags) > 0:
                return {
                    'version': (tags[0].get('name') or '').lstrip('v'),
                    'description': '',
                    'published_at': '',
                    'source': 'github_tag',
                }
    except Exception:
        return None
    return None


def get_current_local_version():
    """Lee la versión local dinámicamente desde git (no cacheada al arranque)."""
    import subprocess
    import os
    base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
    try:
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True, text=True, cwd=base_dir, timeout=3
        )
        if result.returncode == 0:
            return result.stdout.strip().lstrip('v')
    except Exception:
        pass
    # Fallback a la versión de settings
    return getattr(settings, 'APP_VERSION', '1.0.0')


def get_version_info():
    """
    Retorna información completa de versiones.
    La versión local se lee dinámicamente desde git para reflejar updates recientes.
    """
    current_version = get_current_local_version()
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
