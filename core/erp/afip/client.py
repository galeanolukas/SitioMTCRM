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
        return self.afip.WebService(service_name)
    
    def get_server_status(self):
        """
        Verifica el estado del servidor de AFIP
        
        Returns:
            Dict con el estado del servidor
        """
        try:
            return self.afip.GetServerStatus()
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
            return self.afip.GetTaxpayer(cuit)
        except Exception as e:
            return {'error': str(e)}
    
    def register_invoice(self, invoice_data):
        """
        Registra una factura electrónica
        
        Args:
            invoice_data: Dict con los datos de la factura
        
        Returns:
            Dict con el resultado del registro
        """
        try:
            ws = self.get_web_service('wsfe')
            return ws.CreateInvoice(invoice_data)
        except Exception as e:
            return {'error': str(e)}
    
    def get_invoice_types(self):
        """
        Obtiene los tipos de comprobantes disponibles
        
        Returns:
            List con los tipos de comprobantes
        """
        try:
            ws = self.get_web_service('wsfe')
            return ws.GetInvoiceTypes()
        except Exception as e:
            return {'error': str(e)}
    
    def get_concept_types(self):
        """
        Obtiene los tipos de conceptos disponibles
        
        Returns:
            List con los tipos de conceptos
        """
        try:
            ws = self.get_web_service('wsfe')
            return ws.GetConceptTypes()
        except Exception as e:
            return {'error': str(e)}
    
    def get_document_types(self):
        """
        Obtiene los tipos de documentos disponibles
        
        Returns:
            List con los tipos de documentos
        """
        try:
            ws = self.get_web_service('wsfe')
            return ws.GetDocumentTypes()
        except Exception as e:
            return {'error': str(e)}
    
    def get_aliquote_types(self):
        """
        Obtiene los tipos de alícuotas de IVA disponibles
        
        Returns:
            List con los tipos de alícuotas
        """
        try:
            ws = self.get_web_service('wsfe')
            return ws.GetAliquoteTypes()
        except Exception as e:
            return {'error': str(e)}
    
    def get_currency_types(self):
        """
        Obtiene los tipos de monedas disponibles
        
        Returns:
            List con los tipos de monedas
        """
        try:
            ws = self.get_web_service('wsfe')
            return ws.GetCurrencyTypes()
        except Exception as e:
            return {'error': str(e)}
