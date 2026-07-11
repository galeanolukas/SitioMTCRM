"""
Cliente AFIP SDK para interactuar con los Web Services de ARCA
"""
import logging
from afip import Afip
import requests
from .config import get_afip_config

logger = logging.getLogger(__name__)


class AfipCompanyMismatchError(Exception):
    """
    Excepción lanzada cuando el usuario no pertenece a la misma empresa
    que tiene configurado el módulo fiscal AFIP.
    """
    pass


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
        logger.info(f"[AFIP CLIENT] Inicializando AfipClient con company_id: {company_id}")
        self.config = get_afip_config(company_id)
        if not self.config:
            logger.error(f"[AFIP CLIENT] No se pudo obtener configuración AFIP para company_id: {company_id}")
        else:
            logger.info(f"[AFIP CLIENT] Configuración obtenida - CUIT: {self.config.get('CUIT')}, Environment: {self.config.get('environment')}")
            logger.info(f"[AFIP CLIENT] Cert exists: {bool(self.config.get('cert'))}, Key exists: {bool(self.config.get('key'))}")
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

        # Configurar ambiente explícitamente
        if self.config['environment'] == 'prod':
            params['production'] = True
        else:
            # En modo desarrollo, asegurar que production sea False
            params['production'] = False

        # Agregar certificado y key si están disponibles (tanto en dev como prod)
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
            logger.info(f"[AFIP] Certificados configurados para CUIT {self.config['CUIT']} en ambiente {self.config['environment']}")
        elif self.config['environment'] == 'prod':
            # En producción sin certificados, loggear advertencia
            logger.warning(f"[AFIP] Configuración en producción sin certificados para CUIT {self.config['CUIT']}. Se usará modo contingencia si está habilitado.")
            if not self.config.get('usar_contingencia', False):
                logger.error(f"[AFIP] Configuración en producción sin certificados y modo contingencia deshabilitado. Las operaciones AFIP fallarán.")
        else:
            # En modo desarrollo, no se requieren certificados
            logger.debug(f"[AFIP] Configuración en modo desarrollo para CUIT {self.config['CUIT']}. No se requieren certificados.")

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

    def get_taxpayer_info(self, cuit, user=None):
        """
        Obtiene información de un contribuyente usando el Padrón de AFIP

        Args:
            cuit: CUIT del contribuyente
            user: Usuario que está realizando la consulta (opcional, para validación de empresa)

        Returns:
            Dict con información del contribuyente
        """
        # Validar que el usuario pertenece a la misma empresa que tiene configurado AFIP
        if user and hasattr(user, 'company') and user.company:
            config_company_id = self.config.get('company_id')
            if config_company_id and user.company.id != config_company_id:
                raise AfipCompanyMismatchError(
                    f"El usuario {user.username} pertenece a la empresa {user.company.name} "
                    f"pero la configuración AFIP pertenece a otra empresa. "
                    "No tiene permiso para consultar el Padrón AFIP de esta configuración."
                )

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
            logger.debug(f"[AFIP] Ambiente: {self.config.get('environment', 'unknown')}")

            # Usar el método ElectronicBilling.createVoucher de AFIP SDK
            result = self.afip.ElectronicBilling.createVoucher(voucher_data)
            logger.debug(f"[AFIP] Respuesta createVoucher: {result}")
            return result
        except Exception as e:
            logger.error(f"[AFIP] Error en create_voucher: {e}")
            import traceback
            logger.error(f"[AFIP] Traceback: {traceback.format_exc()}")
            return {'error': str(e)}

    def create_next_voucher(self, voucher_data, full_response=False):
        """
        Crea y asigna CAE al siguiente comprobante automáticamente
        Calcula el siguiente número de comprobante y lo asigna

        Args:
            voucher_data: Dict con los datos del comprobante (sin CbteDesde/CbteHasta)
            full_response: Si es True, devuelve la respuesta completa del WS

        Returns:
            Dict con CAE, CAEFchVto, voucher_number y otros datos del comprobante
        """
        try:
            logger.debug(f"[AFIP] Creando siguiente voucher - PtoVta: {voucher_data.get('PtoVta')}, CbteTipo: {voucher_data.get('CbteTipo')}, Total: {voucher_data.get('ImpTotal')}")
            logger.debug(f"[AFIP] Ambiente: {self.config.get('environment', 'unknown')}")

            # Usar el método ElectronicBilling.createNextVoucher de AFIP SDK
            result = self.afip.ElectronicBilling.createNextVoucher(voucher_data)
            logger.debug(f"[AFIP] Respuesta createNextVoucher: {result}")
            return result
        except Exception as e:
            logger.error(f"[AFIP] Error en create_next_voucher: {e}")
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
            # Usar el método específico de AFIP SDK para obtener el último número
            result = self.afip.ElectronicBilling.getLastVoucher(pto_vta, cbte_tipo)
            logger.debug(f"[AFIP] Respuesta getLastVoucher: {result}")
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

    def get_voucher_info(self, cbte_nro, pto_vta, cbte_tipo):
        """
        Obtiene información de un comprobante ya emitido usando FECompConsultar

        Args:
            cbte_nro: Número de comprobante (int)
            pto_vta: Punto de venta (int)
            cbte_tipo: Tipo de comprobante (int, ej: 6=Factura B)

        Returns:
            Dict con información del comprobante o {'error': ...} si falla
        """
        try:
            logger.debug(f"[AFIP] Consultando comprobante - CbteNro: {cbte_nro}, PtoVta: {pto_vta}, CbteTipo: {cbte_tipo}")
            # Usar el método getVoucherInfo de AFIP SDK
            result = self.afip.ElectronicBilling.getVoucherInfo(cbte_nro, pto_vta, cbte_tipo)
            logger.debug(f"[AFIP] Respuesta getVoucherInfo: {result}")

            if result is None:
                logger.warning(f"[AFIP] El comprobante no existe - CbteNro: {cbte_nro}, PtoVta: {pto_vta}, CbteTipo: {cbte_tipo}")
                return {'error': 'El comprobante no existe'}

            return {'success': True, 'data': result}
        except Exception as e:
            logger.error(f"[AFIP] Error en get_voucher_info: {e}")
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
            logger.debug(f"[AFIP] Obteniendo tipos de comprobantes")
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
            logger.error(f"[AFIP] Error en get_invoice_types: {e}")
            return {'error': str(e)}
    
    def get_concept_types(self):
        """
        Obtiene los tipos de conceptos disponibles

        Returns:
            Dict con los tipos de conceptos
        """
        try:
            logger.debug(f"[AFIP] Obteniendo tipos de conceptos")
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
            logger.error(f"[AFIP] Error en get_concept_types: {e}")
            return {'error': str(e)}
    
    def get_document_types(self):
        """
        Obtiene los tipos de documentos disponibles

        Returns:
            Dict con los tipos de documentos
        """
        try:
            logger.debug(f"[AFIP] Obteniendo tipos de documentos")
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
            logger.error(f"[AFIP] Error en get_document_types: {e}")
            return {'error': str(e)}
    
    def get_aliquote_types(self):
        """
        Obtiene los tipos de alícuotas de IVA disponibles

        Returns:
            Dict con los tipos de alícuotas
        """
        try:
            logger.debug(f"[AFIP] Obteniendo tipos de alícuotas de IVA")
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
            logger.error(f"[AFIP] Error en get_aliquote_types: {e}")
            return {'error': str(e)}
    
    def get_currency_types(self):
        """
        Obtiene los tipos de monedas disponibles

        Returns:
            Dict con los tipos de monedas
        """
        try:
            logger.debug(f"[AFIP] Obteniendo tipos de monedas")
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
            logger.error(f"[AFIP] Error en get_currency_types: {e}")
            return {'error': str(e)}

    def get_iva_conditions(self):
        """
        Obtiene los tipos de condiciones frente al IVA disponibles usando FEParamGetCondicionIvaReceptor

        Returns:
            Dict con las condiciones IVA disponibles o {'error': ...} si falla
        """
        try:
            logger.debug(f"[AFIP] Obteniendo condiciones IVA receptor")
            # Usar executeRequest directo como indica la documentación de AFIP SDK
            result = self.afip.ElectronicBilling.executeRequest('FEParamGetCondicionIvaReceptor')
            logger.debug(f"[AFIP] Respuesta FEParamGetCondicionIvaReceptor: {result}")
            return {'success': True, 'data': result}
        except Exception as e:
            logger.error(f"[AFIP] Error en get_iva_conditions: {e}")
            import traceback
            logger.error(f"[AFIP] Traceback: {traceback.format_exc()}")
            return {'error': str(e)}

    def get_sales_points(self):
        """
        Obtiene los puntos de venta habilitados desde AFIP

        Returns:
            Dict con los puntos de venta o error
        """
        try:
            logger.debug(f"[AFIP] Obteniendo puntos de venta")
            ws = self.get_web_service('wsfe')
            ta = ws.getTokenAuthorization()
            data = {
                "Auth": {
                    "Token": ta["token"],
                    "Sign": ta["sign"],
                    "Cuit": self.config['CUIT']
                }
            }
            result = ws.executeRequest("FEParamGetPtosVenta", data)
            logger.debug(f"[AFIP] Respuesta puntos de venta: {result}")

            # Verificar si hay errores en la respuesta
            if 'FEParamGetPtosVentaResult' in result:
                result_data = result['FEParamGetPtosVentaResult']
                if 'Errors' in result_data:
                    errors = result_data['Errors'].get('Err', [])
                    if errors:
                        error_msg = errors[0].get('Msg', 'Error desconocido')
                        error_code = errors[0].get('Code', 'N/A')
                        logger.warning(f"[AFIP] Error en respuesta FEParamGetPtosVenta: {error_code} - {error_msg}")
                        return {'error': f'Error AFIP {error_code}: {error_msg}'}

            return {'sales_points': result}
        except Exception as e:
            logger.error(f"[AFIP] Error en get_sales_points: {e}")
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

    def get_taxpayer_inscription_proof(self, cuit):
        """
        Consulta el Padrón de AFIP para obtener datos de un contribuyente.
        Usa RegisterInscriptionProof (Constancia de Inscripción) del AFIP SDK.
        Este método es más completo y actualizado que RegisterScopeTen.

        NOTA: Este método requiere autorización adicional del web service.
        Si recibe error "Debe autorizar el uso del web service", use get_taxpayer_data
        (RegisterScopeTen) que no requiere autorización adicional.
        Para autorizar RegisterInscriptionProof, siga la guía:
        https://afipsdk.com/docs/automations/auth-web-service-dev/nodejs/

        Args:
            cuit: CUIT del contribuyente (con o sin guiones)

        Returns:
            Dict con datos del contribuyente: razon_social, domicilio, etc.
            o {'error': ...} si falla
        """
        try:
            cuit_clean = str(cuit).replace('-', '').strip()
            logger.debug(f"[AFIP] Consultando Constancia de Inscripción (RegisterInscriptionProof) para CUIT: {cuit_clean}")
            taxpayer = self.afip.RegisterInscriptionProof
            result = taxpayer.getTaxpayerDetails(int(cuit_clean))
            logger.debug(f"[AFIP] Respuesta RegisterInscriptionProof: {result}")

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
            logger.error(f"[AFIP] Error en get_taxpayer_inscription_proof: {e}")
            return {'error': str(e)}

    def create_pdf(self, pdf_data, user=None):
        """
        Genera un PDF de comprobante fiscal usando el método ElectronicBilling.createPDF() de AFIP SDK.

        Args:
            pdf_data: Dict con los datos para el template PDF de AFIP SDK.
                Debe incluir: file_name, template { name, params }, y opcional send_to.
            user: Usuario que está generando el PDF (opcional, para validación de empresa)

        Returns:
            Dict con id, file (URL), file_expiration, file_name, created_at
            o {'error': ...} si falla.
        """
        # Validar que el usuario pertenece a la misma empresa que tiene configurado AFIP
        if user and hasattr(user, 'company') and user.company:
            config_company_id = self.config.get('company_id')
            if config_company_id and user.company.id != config_company_id:
                raise AfipCompanyMismatchError(
                    f"El usuario {user.username} pertenece a la empresa {user.company.name} "
                    f"pero la configuración AFIP pertenece a otra empresa. "
                    "No tiene permiso para generar PDFs de esta configuración."
                )

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
    
    def create_dev_certificate(self, cuit, username, password, alias='afipsdk', user=None):
        """
        Crea un certificado de desarrollo usando la automatización create-cert-dev

        Args:
            cuit: CUIT del contribuyente
            username: Usuario de Clave Fiscal
            password: Contraseña de Clave Fiscal
            alias: Alias para el certificado (default: 'afipsdk')
            user: Usuario que está creando el certificado (opcional, para validación de empresa)

        Returns:
            Dict con cert y key generados o error
        """
        # Validar que el usuario pertenece a la misma empresa que tiene configurado AFIP
        if user and hasattr(user, 'company') and user.company:
            config_company_id = self.config.get('company_id')
            if config_company_id and user.company.id != config_company_id:
                raise AfipCompanyMismatchError(
                    f"El usuario {user.username} pertenece a la empresa {user.company.name} "
                    f"pero la configuración AFIP pertenece a otra empresa. "
                    "No tiene permiso para crear certificados de esta configuración."
                )

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

    def create_prod_certificate(self, cuit, username, password, alias='afipsdk', user=None):
        """
        Crea un certificado de producción usando la automatización create-cert-prod

        Args:
            cuit: CUIT del contribuyente
            username: Usuario de Clave Fiscal
            password: Contraseña de Clave Fiscal
            alias: Alias para el certificado (default: 'afipsdk')
            user: Usuario que está creando el certificado (opcional, para validación de empresa)

        Returns:
            Dict con cert y key generados o error
        """
        # Validar que el usuario pertenece a la misma empresa que tiene configurado AFIP
        if user and hasattr(user, 'company') and user.company:
            config_company_id = self.config.get('company_id')
            if config_company_id and user.company.id != config_company_id:
                raise AfipCompanyMismatchError(
                    f"El usuario {user.username} pertenece a la empresa {user.company.name} "
                    f"pero la configuración AFIP pertenece a otra empresa. "
                    "No tiene permiso para crear certificados de esta configuración."
                )

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

    def auth_web_service(self, cuit, username, password, alias='afipsdk', service='wsfe', user=None):
        """
        Autoriza el uso de un Web Service de AFIP usando la automatización auth-web-service-dev o auth-web-service-prod

        Args:
            cuit: CUIT del contribuyente
            username: Usuario de Clave Fiscal
            password: Contraseña de Clave Fiscal
            alias: Alias del certificado (default: 'afipsdk')
            service: Web Service a autorizar (default: 'wsfe')
            user: Usuario que está autorizando el servicio (opcional, para validación de empresa)

        Returns:
            Dict con resultado de la autorización o error
        """
        # Validar que el usuario pertenece a la misma empresa que tiene configurado AFIP
        if user and hasattr(user, 'company') and user.company:
            config_company_id = self.config.get('company_id')
            if config_company_id and user.company.id != config_company_id:
                raise AfipCompanyMismatchError(
                    f"El usuario {user.username} pertenece a la empresa {user.company.name} "
                    f"pero la configuración AFIP pertenece a otra empresa. "
                    "No tiene permiso para autorizar servicios de esta configuración."
                )

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
