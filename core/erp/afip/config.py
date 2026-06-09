"""
Configuración para integración con AFIP SDK
"""
from django.conf import settings
import os

# Configuración base de AFIP SDK
AFIP_ACCESS_TOKEN = getattr(settings, 'AFIP_ACCESS_TOKEN', None)
AFIP_CUIT = getattr(settings, 'AFIP_CUIT', None)
AFIP_ENVIRONMENT = getattr(settings, 'AFIP_ENVIRONMENT', 'dev')  # 'dev' o 'prod'

# Rutas a certificados (solo para producción)
AFIP_CERT_PATH = getattr(settings, 'AFIP_CERT_PATH', None)
AFIP_KEY_PATH = getattr(settings, 'AFIP_KEY_PATH', None)

# Web Services disponibles
AFIP_WEBSERVICES = {
    'wsfe': 'Facturación Electrónica',
    'wsmtxca': 'Facturación Electrónica de Exportación',
    'wscdc': 'Constatación de Comprobantes',
    'wsct': 'Ticket de Acceso',
}


def get_afip_config(company_id=None):
    """
    Obtiene la configuración de AFIP para una empresa específica
    o la configuración global si no se especifica empresa
    """
    from core.erp.models import AfipConfig
    
    if company_id:
        try:
            config = AfipConfig.objects.get(company_id=company_id, is_active=True)
            return {
                'CUIT': config.cuit,
                'access_token': config.access_token,
                'cert': config.cert,
                'key': config.key,
                'environment': config.environment,
            }
        except AfipConfig.DoesNotExist:
            pass
    
    # Fallback a configuración global
    return {
        'CUIT': AFIP_CUIT,
        'access_token': AFIP_ACCESS_TOKEN,
        'cert': AFIP_CERT_PATH,
        'key': AFIP_KEY_PATH,
        'environment': AFIP_ENVIRONMENT,
    }
