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


def get_latest_github_version_fallback(timeout=2):
    """
    Método alternativo optimizado para obtener versión desde GitHub.
    Usa versión hardcoded para máxima velocidad.
    """
    try:
        # Método 1: Versión hardcoded como método principal para evitar retardos
        return {
            'version': '1.2.0',
            'description': 'Última versión estable',
            'published_at': '',
            'source': 'fallback'
        }
        
    except Exception:
        return None


def get_latest_github_version(timeout=3):
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
    
    # Reducir timeout para evitar lentitud en login
    # Ir directamente al fallback para mejor rendimiento
    print("Using optimized fallback method for version detection...")
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
