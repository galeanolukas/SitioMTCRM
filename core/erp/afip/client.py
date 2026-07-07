"""
Cliente AFIP SDK para interactuar con los Web Services de ARCA
"""
import logging
from afip import Afip
import requests
from .config import get_afip_config

logger = logging.getLogger(__name__)


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
            # Si son paths de archivo, leer el contenido
            cert = self.config['cert']
            key = self.config['key']

            # Verificar si son paths (empiezan con / o son rutas relativas)
            if isinstance(cert, str) and (cert.startswith('/') or cert.startswith('./')):
                try:
                    with open(cert, 'r') as f:
                        cert = f.read()
                except Exception as e:
                    raise Exception(f"Error leyendo certificado: {e}")

            if isinstance(key, str) and (key.startswith('/') or key.startswith('./')):
                try:
                    with open(key, 'r') as f:
                        key = f.read()
                except Exception as e:
                    raise Exception(f"Error leyendo key: {e}")

            params['cert'] = cert
            params['key'] = key

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
            logger.debug(f"[AFIP] Verificando estado del servidor (FEDummy)")
            # Usar Web Service WSFE para verificar estado con FEDummy
            ws = self.get_web_service('wsfe')
            # FEDummy es un método simple para verificar estado del servidor
            result = ws.executeRequest("FEDummy", {})
            logger.debug(f"[AFIP] Respuesta FEDummy: {result}")
            return {'status': 'ok', 'data': result}
        except Exception as e:
            logger.error(f"[AFIP] Error en FEDummy: {e}")
            return {'error': str(e)}
    
    def get_taxpayer_info(self, cuit):
        """
        Obtiene información de un contribuyente usando el Padrón de AFIP

        Args:
            cuit: CUIT del contribuyente

        Returns:
            Dict con información del contribuyente
        """
        # Usar get_taxpayer_data que es el método correcto para consultar el Padrón
        return self.get_taxpayer_data(cuit)
    
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
            logger.debug(f"[AFIP] Creando voucher - PtoVta: {voucher_data.get('PtoVta')}, CbteTipo: {voucher_data.get('CbteTipo')}, Total: {voucher_data.get('ImpTotal')}")
            # Usar el método ElectronicBilling.createVoucher de AFIP SDK
            result = self.afip.ElectronicBilling.createVoucher(voucher_data)
            logger.debug(f"[AFIP] Respuesta createVoucher: {result}")
            return result
        except Exception as e:
            logger.error(f"[AFIP] Error en create_voucher: {e}")
            import traceback
            logger.error(f"[AFIP] Traceback: {traceback.format_exc()}")
            return {'error': str(e)}
    
    def get_last_voucher_number(self, pto_vta, cbte_tipo):
        """
        Obtiene el último número de comprobante autorizado para un punto de venta
        y tipo de comprobante, usando FECompUltimoAutorizado.

        Args:
            pto_vta: Punto de venta (int)
            cbte_tipo: Tipo de comprobante (int, ej: 6=Factura B)

        Returns:
            int: Último número autorizado, o 0 si no hay comprobantes previos
        """
        try:
            logger.debug(f"[AFIP] Obteniendo último comprobante - PtoVta: {pto_vta}, CbteTipo: {cbte_tipo}")
            ws = self.get_web_service('wsfe')
            ta = ws.getTokenAuthorization()
            data = {
                "authRequest": {
                    "token": ta["token"],
                    "sign": ta["sign"],
                    "cuitRepresentada": self.config['CUIT']
                },
                "PtoVta": pto_vta,
                "CbteTipo": cbte_tipo
            }
            result = ws.executeRequest("FECompUltimoAutorizado", data)
            logger.debug(f"[AFIP] Respuesta FECompUltimoAutorizado: {result}")
            logger.debug(f"[AFIP] Tipo de resultado: {type(result)}")
            # El resultado puede ser un entero directamente o un diccionario
            if isinstance(result, int):
                logger.debug(f"[AFIP] Último número de comprobante (directo): {result}")
                return result
            # El resultado trae FERespuestaConsulta con cbte_nro
            if isinstance(result, dict):
                # AFIP SDK puede devolver la respuesta en distintas claves
                cbte_nro = result.get('CbteNro') or result.get('cbte_nro')
                if cbte_nro is not None:
                    logger.debug(f"[AFIP] Último número de comprobante: {cbte_nro}")
                    return int(cbte_nro)
                # Buscar en respuestas anidadas
                for key in ('FERespuestaConsulta', 'response'):
                    if key in result and isinstance(result[key], dict):
                        cbte_nro = result[key].get('CbteNro') or result[key].get('cbte_nro')
                        if cbte_nro is not None:
                            logger.debug(f"[AFIP] Último número de comprobante (anidado): {cbte_nro}")
                            return int(cbte_nro)
            logger.debug(f"[AFIP] No se encontró número de comprobante previo, retornando 0")
            return 0
        except Exception as e:
            logger.error(f"[AFIP] Error en get_last_voucher_number: {e}")
            import traceback
            logger.error(f"[AFIP] Traceback: {traceback.format_exc()}")
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

    def get_taxpayer_data(self, cuit):
        """
        Consulta el Padrón de AFIP para obtener datos de un contribuyente.
        Usa RegisterScopeTen (Padrón Alcance 10) del AFIP SDK.

        Args:
            cuit: CUIT del contribuyente (con o sin guiones)

        Returns:
            Dict con datos del contribuyente: razon_social, domicilio, etc.
            o {'error': ...} si falla
        """
        try:
            cuit_clean = str(cuit).replace('-', '').strip()
            logger.debug(f"[AFIP] Consultando Padrón (RegisterScopeTen) para CUIT: {cuit_clean}")
            taxpayer = self.afip.RegisterScopeTen
            result = taxpayer.getTaxpayerDetails(int(cuit_clean))
            logger.debug(f"[AFIP] Respuesta RegisterScopeTen: {result}")

            if isinstance(result, dict) and 'persona' in result:
                persona = result['persona']
                data_dict = {
                    'cuit': cuit_clean,
                    'razon_social': '',
                    'domicilio': '',
                    'localidad': '',
                    'provincia': '',
                    'codigo_postal': '',
                    'telefono': '',
                    'email': '',
                    'impuestos': [],
                    'actividades': [],
                }

                if 'razonSocial' in persona:
                    data_dict['razon_social'] = persona.get('razonSocial', '')

                if 'domicilioFiscal' in persona:
                    dom = persona['domicilioFiscal']
                    calle = dom.get('calle', '')
                    numero = dom.get('numero', '')
                    data_dict['domicilio'] = f"{calle} {numero}".strip()
                    data_dict['localidad'] = dom.get('localidad', {}).get('nombre', '') if isinstance(dom.get('localidad'), dict) else dom.get('localidad', '')
                    data_dict['provincia'] = dom.get('provincia', {}).get('nombre', '') if isinstance(dom.get('provincia'), dict) else dom.get('provincia', '')
                    data_dict['codigo_postal'] = str(dom.get('codPostal', ''))

                if 'telefono' in persona:
                    data_dict['telefono'] = persona.get('telefono', '')

                if 'email' in persona:
                    data_dict['email'] = persona.get('email', '')

                if 'impuestos' in persona:
                    data_dict['impuestos'] = persona.get('impuestos', [])

                if 'actividades' in persona:
                    data_dict['actividades'] = persona.get('actividades', [])

                # Determinar condición IVA
                impuestos = data_dict['impuestos']
                if isinstance(impuestos, list):
                    imp_ids = [str(i.get('idImpuesto', '')) for i in impuestos if isinstance(i, dict)]
                else:
                    imp_ids = []

                # 32 = IVA Responsable Inscripto, 33 = Monotributo
                if '32' in imp_ids:
                    data_dict['condicion_iva'] = 'RI'
                elif '33' in imp_ids:
                    data_dict['condicion_iva'] = 'M'
                else:
                    data_dict['condicion_iva'] = 'CF'

                logger.debug(f"[AFIP] Datos del contribuyente procesados: {data_dict.get('razon_social', 'N/A')}, Condición IVA: {data_dict.get('condicion_iva', 'N/A')}")
                return {'success': True, 'data': data_dict}

            logger.warning(f"[AFIP] No se encontraron datos para CUIT {cuit_clean}")
            return {'error': 'No se encontraron datos para el CUIT ingresado'}

        except Exception as e:
            logger.error(f"[AFIP] Error en get_taxpayer_data: {e}")
            return {'error': str(e)}

    def create_pdf(self, pdf_data):
        """
        Genera un PDF de comprobante fiscal usando el método ElectronicBilling.createPDF() de AFIP SDK.

        Args:
            pdf_data: Dict con los datos para el template PDF de AFIP SDK.
                Debe incluir: file_name, template { name, params }, y opcional send_to.

        Returns:
            Dict con id, file (URL), file_expiration, file_name, created_at
            o {'error': ...} si falla.
        """
        try:
            template_name = pdf_data.get('template', {}).get('name', 'unknown')
            file_name = pdf_data.get('file_name', 'unknown')
            logger.debug(f"[AFIP PDF] Generando PDF - Template: {template_name}, Archivo: {file_name}")

            # Usar el método del SDK para crear PDFs
            result = self.afip.ElectronicBilling.createPDF(pdf_data)

            logger.debug(f"[AFIP PDF] Respuesta createPDF: {result}")
            return result
        except Exception as e:
            logger.error(f"[AFIP PDF] Error en createPDF: {e}")
            return {'error': str(e)}

    def get_supplier_vouchers(self, fecha_desde=None, fecha_hasta=None):
        """
        Obtiene comprobantes de proveedores desde AFIP (Mis Comprobantes).

        Args:
            fecha_desde: Fecha desde (formato YYYY-MM-DD)
            fecha_hasta: Fecha hasta (formato YYYY-MM-DD)

        Returns:
            Lista de comprobantes de proveedores o error
        """
        try:
            # Nota: El AFIP SDK puede no tener este método específico
            # Esta es una implementación placeholder que debería adaptarse
            # según la API específica del AFIP SDK que se esté usando

            if not hasattr(self.afip, 'get_supplier_vouchers'):
                return {'error': 'El AFIP SDK no soporta consulta de comprobantes de proveedores directamente. Use el portal de AFIP "Mis Comprobantes".'}

            result = self.afip.get_supplier_vouchers(
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta
            )
            return result
        except Exception as e:
            return {'error': str(e)}
    
    def create_automation(self, automation_name, data, wait=True):
        """
        Ejecuta una automatización de AFIP SDK usando la librería afip.py v1.2.0+
        
        Args:
            automation_name: Nombre de la automatización (ej: 'create-cert-dev', 'create-cert-prod')
            data: Dict con los parámetros de la automatización
            wait: Si True, espera a que la automatización termine (default: True)
        
        Returns:
            Dict con resultado de la automatización
        """
        try:
            # Crear instancia de Afip solo para automatizaciones (solo necesita access_token)
            from afip import Afip
            afip_auto = Afip({'access_token': self.config['access_token']})
            
            # Usar el método createAutomation de la librería
            result = afip_auto.createAutomation(automation_name, data, wait=wait)
            return result
        except Exception as e:
            return {'error': str(e)}
    
    def get_automation_details(self, automation_id, wait=False):
        """
        Obtiene detalles de una automatización usando la librería afip.py v1.2.0+
        
        Args:
            automation_id: ID de la automatización
            wait: Si True, espera a que la automatización termine
        
        Returns:
            Dict con detalles de la automatización
        """
        try:
            # Crear instancia de Afip solo para automatizaciones
            from afip import Afip
            afip_auto = Afip({'access_token': self.config['access_token']})
            
            # Usar el método getAutomationDetails de la librería
            result = afip_auto.getAutomationDetails(automation_id, wait=wait)
            return result
        except Exception as e:
            return {'error': str(e)}
    
    def create_dev_certificate(self, cuit, username, password, alias='afipsdk'):
        """
        Crea un certificado de desarrollo usando la automatización create-cert-dev
        
        Args:
            cuit: CUIT del contribuyente
            username: Usuario de Clave Fiscal
            password: Contraseña de Clave Fiscal
            alias: Alias para el certificado (default: 'afipsdk')
        
        Returns:
            Dict con cert y key generados o error
        """
        data = {
            'cuit': cuit,
            'username': username,
            'password': password,
            'alias': alias
        }
        
        result = self.create_automation('create-cert-dev', data)
        
        if 'error' in result:
            return result
        
        # Extraer cert y key de la respuesta
        if result.get('status') == 'complete' and 'data' in result:
            return {
                'success': True,
                'cert': result['data'].get('cert'),
                'key': result['data'].get('key'),
                'automation_id': result.get('id')
            }
        
        return {'error': 'La automatización no completó exitosamente'}
    
    def create_prod_certificate(self, cuit, username, password, alias='afipsdk'):
        """
        Crea un certificado de producción usando la automatización create-cert-prod

        Args:
            cuit: CUIT del contribuyente
            username: Usuario de Clave Fiscal
            password: Contraseña de Clave Fiscal
            alias: Alias para el certificado (default: 'afipsdk')

        Returns:
            Dict con cert y key generados o error
        """
        data = {
            'cuit': cuit,
            'username': username,
            'password': password,
            'alias': alias
        }

        result = self.create_automation('create-cert-prod', data)

        if 'error' in result:
            return result

        # Extraer cert y key de la respuesta
        if result.get('status') == 'complete' and 'data' in result:
            return {
                'success': True,
                'cert': result['data'].get('cert'),
                'key': result['data'].get('key'),
                'automation_id': result.get('id')
            }

        return {'error': 'La automatización no completó exitosamente'}

    def auth_web_service(self, cuit, username, password, alias='afipsdk', service='wsfe'):
        """
        Autoriza el uso de un Web Service de AFIP usando la automatización auth-web-service-dev o auth-web-service-prod

        Args:
            cuit: CUIT del contribuyente
            username: Usuario de Clave Fiscal
            password: Contraseña de Clave Fiscal
            alias: Alias del certificado (default: 'afipsdk')
            service: Web Service a autorizar (default: 'wsfe')

        Returns:
            Dict con resultado de la autorización o error
        """
        # Determinar la automatización según el ambiente
        if self.config['environment'] == 'prod':
            automation_name = 'auth-web-service-prod'
        else:
            automation_name = 'auth-web-service-dev'

        data = {
            'cuit': cuit,
            'username': username,
            'password': password,
            'alias': alias,
            'service': service
        }

        logger.debug(f"[AFIP] Autorizando Web Service {service} con automatización {automation_name}")

        result = self.create_automation(automation_name, data)

        if 'error' in result:
            logger.error(f"[AFIP] Error en autorización de Web Service: {result['error']}")
            return result

        logger.debug(f"[AFIP] Autorización de Web Service completada: {result}")
        return {
            'success': True,
            'automation_id': result.get('id'),
            'status': result.get('status'),
            'data': result.get('data')
        }
