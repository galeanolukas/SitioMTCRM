"""
Servicio de integración con AFIP para facturación electrónica.

Este servicio encapsula toda la lógica de comunicación con AFIP,
separándola del modelo Sale para mejorar la mantenibilidad.
"""

import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)


class AfipService:
    """Servicio para manejar operaciones de facturación AFIP."""

    def __init__(self, company_id: int):
        """
        Inicializar el servicio AFIP para una empresa específica.

        Args:
            company_id: ID de la empresa para la cual se emitirán facturas
        """
        self.company_id = company_id
        self._client = None
        self._config = None

    @property
    def client(self):
        """Lazy load del cliente AFIP."""
        if self._client is None:
            try:
                from core.erp.afip.client import AfipClient
                self._client = AfipClient(company_id=self.company_id)
            except ImportError:
                logger.error("afip_client_not_available", extra={'company_id': self.company_id})
                raise RuntimeError("Módulo AFIP no disponible")
        return self._client

    @property
    def config(self) -> Dict:
        """Lazy load de la configuración AFIP."""
        if self._config is None:
            from core.erp.afip.config import get_afip_config
            self._config = get_afip_config(self.company_id)
        return self._config

    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """
        Validar que la configuración AFIP esté completa y activa.

        Returns:
            Tuple (is_valid, error_message)
        """
        if not self.config or not self.config.get('is_active'):
            return False, "No hay configuración AFIP activa"

        if not self.config.get('CUIT'):
            return False, "CUIT no configurado"

        return True, None

    def get_punto_venta(self) -> int:
        """
        Obtener el punto de venta activo para la empresa.

        Returns:
            Número de punto de venta (1 por defecto si no hay configurado)
        """
        from core.erp.models import Company

        company = Company.objects.get(pk=self.company_id)
        punto_venta_obj = company.afippuntoventa_set.filter(is_active=True).first()

        if not punto_venta_obj:
            logger.warning("afip_no_active_pos", extra={'company_id': self.company_id})
            return 1  # Fallback

        return punto_venta_obj.numero

    def get_afip_config_obj(self):
        """
        Obtener el objeto de configuración AFIP activo.

        Returns:
            AfipConfig object o None
        """
        from core.erp.models import Company

        company = Company.objects.get(pk=self.company_id)
        return company.afipconfig_set.filter(is_active=True).first()

    def calculate_iva_details(self, sale) -> list:
        """
        Calcular los detalles de IVA por alícuota para AFIP.

        Agrupa por alícuota y recalcula los importes para evitar
        inconsistencias de redondeo que rechazan AFIP (error 10051).

        Args:
            sale: Objeto Sale con detalles de venta

        Returns:
            Lista de diccionarios con detalles de IVA para AFIP
        """
        from decimal import Decimal, ROUND_HALF_UP

        # Tasa AFIP -> porcentaje real
        rate_map = {
            5: Decimal('0.21'),
            4: Decimal('0.105'),
            3: Decimal('0.00'),
            6: Decimal('0.27'),
            8: Decimal('0.05'),
            2: Decimal('0.025'),
        }

        iva_groups = {}
        for det in sale.detsale_set.all():
            if det.iva_amount > 0 and det.subtotal > 0:
                iva_rate = (Decimal(str(det.iva_amount)) / Decimal(str(det.subtotal)) * Decimal('100')).quantize(Decimal('0.1'))

                if iva_rate == Decimal('21.0'):
                    iva_id = 5
                elif iva_rate == Decimal('10.5'):
                    iva_id = 4
                elif iva_rate == Decimal('0.0'):
                    iva_id = 3
                else:
                    iva_id = 5  # Default 21%
            else:
                iva_id = 3  # No gravado/Exento

            if iva_id not in iva_groups:
                iva_groups[iva_id] = Decimal('0.00')
            iva_groups[iva_id] += Decimal(str(det.subtotal))

        iva_details = []
        for iva_id, base in iva_groups.items():
            rate = rate_map.get(iva_id, Decimal('0.00'))
            importe = (base * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            iva_details.append({
                'Id': iva_id,
                'BaseImp': float(base.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'Importe': float(importe)
            })

        # Si hay importe neto pero no hay detalles de IVA, agregar alícuota 0
        # AFIP requiere el objeto Iva cuando ImpNeto > 0 (error 10070)
        if sale.subtotal > 0 and not iva_details:
            iva_details.append({
                'Id': 3,  # No gravado/Exento
                'BaseImp': float(Decimal(str(sale.subtotal)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'Importe': 0.0
            })

        return iva_details

    def get_client_document_data(self, sale, config_obj) -> Tuple[int, int]:
        """
        Determinar el tipo y número de documento del cliente según normativa AFIP.

        Args:
            sale: Objeto Sale con datos del cliente
            config_obj: Objeto AfipConfig con tipo de comprobante

        Returns:
            Tuple (doc_tipo, doc_nro) según normativa AFIP
        """
        # Para facturas A (tipo_comprobante = 1), DocTipo debe ser 80 (CUIT) obligatoriamente
        if config_obj.tipo_comprobante == 1:  # Factura A
            if sale.cli and sale.cli.cuit_cuil:
                doc_tipo = 80  # CUIT
                doc_nro = int(sale.cli.cuit_cuil.replace('-', ''))
            else:
                # Si el cliente no tiene CUIT, usar CUIT de la empresa
                if config_obj.cuit:
                    doc_tipo = 80  # CUIT
                    doc_nro = int(config_obj.cuit.replace('-', ''))
                else:
                    raise ValueError("Factura A requiere CUIT del cliente o de la empresa")
        else:
            # Para otros tipos de comprobante (B, C, etc.), usar lógica normal
            if sale.cli and sale.cli.cuit_cuil:
                doc_tipo = 80  # CUIT
                doc_nro = int(sale.cli.cuit_cuil.replace('-', ''))
            elif sale.cli and sale.cli.dni:
                doc_tipo = 96  # DNI
                doc_nro = int(sale.cli.dni)
            else:
                doc_tipo = 99  # Consumidor Final sin datos
                doc_nro = 0

        return doc_tipo, doc_nro

    def get_client_iva_condition(self, sale) -> int:
        """
        Determinar la condición de IVA del receptor según normativa AFIP RG 5616/2024.

        Args:
            sale: Objeto Sale con datos del cliente

        Returns:
            Código de condición IVA según AFIP
        """
        condicion_iva_cliente = sale.cli.condicion_iva if sale.cli else 'CF'
        condicion_iva_map = {
            'RI': 1,  # Responsable Inscripto
            'M': 4,   # Monotributista
            'CF': 5,  # Consumidor Final
            'EX': 6,  # Exento
            'NC': 9,  # No Categorizado
        }
        return condicion_iva_map.get(condicion_iva_cliente, 5)  # Default CF

    def prepare_voucher_data(self, sale, config_obj) -> Dict:
        """
        Preparar los datos del voucher para enviar a AFIP.

        Args:
            sale: Objeto Sale con datos de la venta
            config_obj: Objeto AfipConfig con configuración

        Returns:
            Diccionario con datos del voucher para AFIP
        """
        from datetime import datetime

        iva_details = self.calculate_iva_details(sale)
        imp_neto = sum(float(detail['BaseImp']) for detail in iva_details) if iva_details else float(sale.subtotal)
        imp_iva = sum(float(detail['Importe']) for detail in iva_details) if iva_details else float(sale.iva)
        imp_total = imp_neto + imp_iva

        doc_tipo, doc_nro = self.get_client_document_data(sale, config_obj)
        condicion_iva_receptor = self.get_client_iva_condition(sale)

        fecha_afip = datetime.now().strftime('%Y%m%d')
        punto_venta = self.get_punto_venta()

        # Obtener el último número de comprobante autorizado desde AFIP
        last_voucher = self.client.get_last_voucher_number(punto_venta, config_obj.tipo_comprobante)
        if isinstance(last_voucher, dict) and 'error' in last_voucher:
            # Si hay error al obtener el último voucher, usar el valor local
            logger.warning("afip_get_last_voucher_failed", extra={
                'sale_id': sale.id,
                'error': last_voucher.get('error'),
                'fallback_to_local': True
            })
            next_voucher = config_obj.cbte_nro + 1
        else:
            next_voucher = last_voucher + 1 if last_voucher > 0 else 1

        return {
            'CbteFch': fecha_afip,
            'PtoVta': punto_venta,
            'CbteTipo': config_obj.tipo_comprobante,
            'Concepto': config_obj.concepto,
            'DocTipo': doc_tipo,
            'DocNro': doc_nro,
            'CbteDesde': next_voucher,
            'CbteHasta': next_voucher,
            'ImpTotal': imp_total,
            'ImpNeto': imp_neto,
            'ImpIVA': imp_iva,
            'ImpOpEx': 0.0,
            'ImpTrib': 0.0,
            'MonId': config_obj.moneda,
            'MonCotiz': 1.0,
            'Iva': iva_details,
            'CondicionIVAReceptorId': condicion_iva_receptor,
            'CantReg': sale.detsale_set.count(),
        }

    def emitir_factura(self, sale, user=None) -> Tuple[bool, Optional[Dict]]:
        """
        Emitir factura electrónica AFIP para una venta.

        Args:
            sale: Objeto Sale con datos de la venta
            user: Usuario que está emitiendo (opcional, para validación)

        Returns:
            Tuple (success, result) donde result contiene datos de la factura o error
        """
        try:
            # Validar configuración
            is_valid, error = self.validate_config()
            if not is_valid:
                logger.warning("afip_config_invalid", extra={
                    'sale_id': sale.id,
                    'error': error
                })
                return False, {'error': error}

            # Validar empresa
            if not sale.company:
                logger.warning("afip_no_company", extra={'sale_id': sale.id})
                return False, {'error': 'La venta no tiene empresa asignada'}

            # Validar usuario si se proporciona
            if user and hasattr(user, 'company') and user.company:
                if user.company.id != self.company_id:
                    from core.erp.afip.client import AfipCompanyMismatchError
                    raise AfipCompanyMismatchError(
                        f"El usuario {user.username} pertenece a la empresa {user.company.name} "
                        f"pero la venta pertenece a la empresa {sale.company.name}"
                    )

            # Obtener configuración AFIP
            config_obj = self.get_afip_config_obj()
            if not config_obj:
                return False, {'error': 'No hay configuración AfipConfig activa'}

            # Preparar datos del voucher
            voucher_data = self.prepare_voucher_data(sale, config_obj)

            logger.info("afip_invoice_start", extra={
                'sale_id': sale.id,
                'punto_venta': voucher_data['PtoVta'],
                'tipo_comprobante': voucher_data['CbteTipo'],
                'total': voucher_data['ImpTotal']
            })

            # Emitir factura usando el cliente AFIP
            result = self.client.emitir_factura(voucher_data)

            if result.get('success'):
                # Actualizar el número de comprobante en la configuración
                config_obj.cbte_nro = voucher_data['CbteDesde']
                config_obj.save(update_fields=['cbte_nro'])

                cae = result.get('cae')
                logger.info("afip_invoice_success", extra={
                    'sale_id': sale.id,
                    'cae': cae,
                    'cae_vto': result.get('cae_vto'),
                    'cbte_nro': config_obj.cbte_nro,
                    'voucher_number': voucher_data['CbteDesde']
                })

                return True, {'success': True, 'cae': cae, 'cae_vto': result.get('cae_vto'), 'voucher_number': voucher_data['CbteDesde']}
            else:
                error_msg = result.get('error') or result.get('message') or str(result)
                logger.error("afip_invoice_failed", extra={
                    'sale_id': sale.id,
                    'error': error_msg,
                    'result': result
                })
                return False, {'error': error_msg, 'raw_result': result}

        except Exception as e:
            logger.error("afip_invoice_exception", extra={
                'sale_id': sale.id,
                'error': str(e)
            })
            return False, {'error': str(e)}
