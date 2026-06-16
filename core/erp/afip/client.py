"""
Cliente AFIP SDK para interactuar con los Web Services de ARCA
"""
from afip import Afip
from .config import get_afip_config


class AfipClient:
    """
    Wrapper para Afip SDK con manejo de configuración por empresa
    """
    
    def __init__(self, company_id=None):
        """
        Inicializa el cliente AFIP
        
        Args:
            company_id: ID de la empresa para obtener configuración específica
        """
        self.config = get_afip_config(company_id)
        self.afip = None
        self._initialize_client()
    
    def _initialize_client(self):
        """
        Inicializa la instancia de Afip SDK con la configuración
        """
        params = {
            'CUIT': self.config['CUIT'],
            'access_token': self.config['access_token'],
        }
        
        # Agregar certificado y key si están disponibles (producción)
        if self.config['cert'] and self.config['key']:
            params['cert'] = self.config['cert']
            params['key'] = self.config['key']
        
        # Configurar ambiente
        if self.config['environment'] == 'prod':
            params['production'] = True
        
        self.afip = Afip(params)
    
    def get_web_service(self, service_name):
        """
        Obtiene un Web Service específico
        
        Args:
            service_name: Nombre del web service (ej: 'wsfe', 'wsmtxca')
        
        Returns:
            Instancia del web service solicitado
        """
        return self.afip.webService(service_name)
    
    def get_server_status(self):
        """
        Verifica el estado del servidor de AFIP usando FEDummy
        
        Returns:
            Dict con el estado del servidor
        """
        try:
            # Usar Web Service WSFE para verificar estado con FEDummy
            ws = self.get_web_service('wsfe')
            # FEDummy es un método simple para verificar estado del servidor
            result = ws.executeRequest("FEDummy", {})
            return {'status': 'ok', 'data': result}
        except Exception as e:
            return {'error': str(e)}
    
    def get_taxpayer_info(self, cuit):
        """
        Obtiene información de un contribuyente
        
        Args:
            cuit: CUIT del contribuyente
        
        Returns:
            Dict con información del contribuyente
        """
        try:
            # Usar Web Service WSFE para obtener información de contribuyente
            ws = self.get_web_service('wsfe')
            # Obtener Token Authorization
            ta = ws.getTokenAuthorization()
            # Preparar datos con formato authRequest según documentación AFIP SDK
            data = {
                "authRequest": {
                    "token": ta["token"],
                    "sign": ta["sign"],
                    "cuitRepresentada": self.config['CUIT']
                }
            }
            # Ejecutar request para obtener datos del contribuyente
            result = ws.executeRequest("FEParamGetTiposCbte", data)
            return {'taxpayer': cuit, 'data': result}
        except Exception as e:
            return {'error': str(e)}
    
    def create_voucher(self, voucher_data, full_response=False):
        """
        Crea y asigna CAE a un comprobante electrónico
        
        Args:
            voucher_data: Dict con los datos del comprobante
            full_response: Si es True, devuelve la respuesta completa del WS
        
        Returns:
            Dict con CAE, CAEFchVto y otros datos del comprobante
        """
        try:
            # Usar Web Service WSFE para facturación electrónica
            ws = self.get_web_service('wsfe')
            # Crear voucher usando el método de AFIP SDK
            result = ws.createVoucher(voucher_data, full_response)
            return result
        except Exception as e:
            return {'error': str(e)}
    
    def get_invoice_types(self):
        """
        Obtiene los tipos de comprobantes disponibles
        
        Returns:
            Dict con los tipos de comprobantes
        """
        try:
            ws = self.get_web_service('wsfe')
            ta = ws.getTokenAuthorization()
            data = {
                "authRequest": {
                    "token": ta["token"],
                    "sign": ta["sign"],
                    "cuitRepresentada": self.config['CUIT']
                }
            }
            result = ws.executeRequest("FEParamGetTiposCbte", data)
            return {'types': result}
        except Exception as e:
            return {'error': str(e)}
    
    def get_concept_types(self):
        """
        Obtiene los tipos de conceptos disponibles
        
        Returns:
            Dict con los tipos de conceptos
        """
        try:
            ws = self.get_web_service('wsfe')
            ta = ws.getTokenAuthorization()
            data = {
                "authRequest": {
                    "token": ta["token"],
                    "sign": ta["sign"],
                    "cuitRepresentada": self.config['CUIT']
                }
            }
            result = ws.executeRequest("FEParamGetTiposConcepto", data)
            return {'types': result}
        except Exception as e:
            return {'error': str(e)}
    
    def get_document_types(self):
        """
        Obtiene los tipos de documentos disponibles
        
        Returns:
            Dict con los tipos de documentos
        """
        try:
            ws = self.get_web_service('wsfe')
            ta = ws.getTokenAuthorization()
            data = {
                "authRequest": {
                    "token": ta["token"],
                    "sign": ta["sign"],
                    "cuitRepresentada": self.config['CUIT']
                }
            }
            result = ws.executeRequest("FEParamGetTiposDoc", data)
            return {'types': result}
        except Exception as e:
            return {'error': str(e)}
    
    def get_aliquote_types(self):
        """
        Obtiene los tipos de alícuotas de IVA disponibles
        
        Returns:
            Dict con los tipos de alícuotas
        """
        try:
            ws = self.get_web_service('wsfe')
            ta = ws.getTokenAuthorization()
            data = {
                "authRequest": {
                    "token": ta["token"],
                    "sign": ta["sign"],
                    "cuitRepresentada": self.config['CUIT']
                }
            }
            result = ws.executeRequest("FEParamGetTiposIva", data)
            return {'types': result}
        except Exception as e:
            return {'error': str(e)}
    
    def get_currency_types(self):
        """
        Obtiene los tipos de monedas disponibles
        
        Returns:
            Dict con los tipos de monedas
        """
        try:
            ws = self.get_web_service('wsfe')
            ta = ws.getTokenAuthorization()
            data = {
                "authRequest": {
                    "token": ta["token"],
                    "sign": ta["sign"],
                    "cuitRepresentada": self.config['CUIT']
                }
            }
            result = ws.executeRequest("FEParamGetTiposMonedas", data)
            return {'types': result}
        except Exception as e:
            return {'error': str(e)}
