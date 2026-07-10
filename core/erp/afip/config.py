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
    import logging
    logger = logging.getLogger(__name__)
    from core.erp.models import AfipConfig

    if company_id:
        try:
            config = AfipConfig.objects.filter(company_id=company_id, is_active=True).first()
            if config:
                logger.debug(f"[AFIP CONFIG] Configuración encontrada para empresa ID {company_id}: CUIT {config.cuit}")
                return {
                    'CUIT': config.cuit,
                    'access_token': config.access_token,
                    'cert': config.cert,
                    'key': config.key,
                    'environment': config.environment,
                    'is_active': config.is_active,
                    'company_id': config.company_id,
                    'usar_contingencia': config.usar_contingencia,
                    'tipo_comprobante': config.tipo_comprobante,
                    'concepto': config.concepto,
                    'moneda': config.moneda,
                    'cotizacion': config.cotizacion,
                }
            else:
                logger.warning(f"[AFIP CONFIG] No hay configuración AFIP activa para empresa ID {company_id}")
        except Exception as e:
            logger.error(f"[AFIP CONFIG] Error obteniendo configuración AFIP para empresa ID {company_id}: {e}")
            pass

    # Fallback a configuración global solo si tiene datos válidos
    if AFIP_CUIT and AFIP_ACCESS_TOKEN:
        logger.debug(f"[AFIP CONFIG] Usando configuración global")
        return {
            'CUIT': AFIP_CUIT,
            'access_token': AFIP_ACCESS_TOKEN,
            'cert': AFIP_CERT_PATH,
            'key': AFIP_KEY_PATH,
            'environment': AFIP_ENVIRONMENT,
            'is_active': True,  # Configuración global se considera activa
            'company_id': None,
            'usar_contingencia': False,
            'tipo_comprobante': 6,  # Default: Factura B
            'concepto': 1,  # Default: Productos
            'moneda': 'PES',
            'cotizacion': 1.0,
        }

    # No hay configuración válida
    logger.warning(f"[AFIP CONFIG] No hay configuración AFIP válida (ni específica ni global)")
    return None
