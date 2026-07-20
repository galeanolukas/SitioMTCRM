"""
Controlador fiscal Hasar (modelo 715/615)
"""
import logging
import serial
from typing import Dict, Optional
from .base import FiscalPrinterBase, FiscalPrinterError

logger = logging.getLogger(__name__)


class HasarFiscalPrinter(FiscalPrinterBase):
    """
    Controlador para impresoras fiscales Hasar (715/615)
    """
    
    # Comandos Hasar
    CMD_STATUS = '@'
    CMD_OPEN_TICKET = '\x02'
    CMD_PRINT_ITEM = '\x03'
    CMD_PRINT_PAYMENT = '\x04'
    CMD_CLOSE_TICKET = '\x05'
    CMD_CANCEL = '\x1B'
    CMD_DAILY_CLOSE = 'Z'
    CMD_GET_LAST_NUMBER = '\x06'
    
    def __init__(self, port: str, baudrate: int = 9600, timeout: int = 1):
        super().__init__(port, baudrate, timeout)
        self.model = None
        
    def connect(self) -> bool:
        """Establecer conexión con impresora Hasar"""
        try:
            self._connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=8,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            self.connected = True
            logger.info(f"[HASAR] Conectado al puerto {self.port}")
            
            # Obtener modelo
            status = self.get_status()
            if status:
                self.model = status.get('model', 'Hasar')
                logger.info(f"[HASAR] Modelo detectado: {self.model}")
            
            return True
        except serial.SerialException as e:
            logger.error(f"[HASAR] Error de conexión: {e}")
            raise FiscalPrinterError(f"No se pudo conectar al puerto {self.port}: {e}")
    
    def disconnect(self) -> bool:
        """Cerrar conexión con impresora Hasar"""
        try:
            if self._connection and self._connection.is_open:
                self._connection.close()
                self.connected = False
                logger.info("[HASAR] Desconectado")
                return True
            return False
        except Exception as e:
            logger.error(f"[HASAR] Error al desconectar: {e}")
            return False
    
    def _send_command(self, command: str, data: str = '') -> str:
        """
        Enviar comando a la impresora fiscal
        
        Args:
            command: Comando a enviar
            data: Datos adicionales
            
        Returns:
            Respuesta de la impresora
        """
        if not self.connected or not self._connection:
            raise FiscalPrinterError("No hay conexión con la impresora fiscal")
        
        try:
            # Formato: comando + datos + checksum + CR
            message = command + data
            checksum = self._calculate_checksum(message)
            full_message = message + checksum + '\r'
            
            self._connection.write(full_message.encode('ascii'))
            response = self._connection.readline().decode('ascii').strip()
            
            logger.debug(f"[HASAR] Enviado: {full_message}")
            logger.debug(f"[HASAR] Recibido: {response}")
            
            return response
        except Exception as e:
            logger.error(f"[HASAR] Error enviando comando: {e}")
            raise FiscalPrinterError(f"Error enviando comando: {e}")
    
    def _calculate_checksum(self, data: str) -> str:
        """Calcular checksum XOR para Hasar"""
        checksum = 0
        for char in data:
            checksum ^= ord(char)
        return chr(checksum)
    
    def get_status(self) -> Dict:
        """Obtener estado de la impresora fiscal"""
        try:
            response = self._send_command(self.CMD_STATUS)
            
            # Parsear respuesta (formato depende del modelo)
            status = {
                'connected': True,
                'model': self.model or 'Hasar',
                'response': response,
                'paper': True,  # Simplificado
                'fiscal_memory': True,  # Simplificado
            }
            
            return status
        except Exception as e:
            logger.error(f"[HASAR] Error obteniendo estado: {e}")
            return {'connected': False, 'error': str(e)}
    
    def open_fiscal_ticket(self, customer_data: Optional[Dict] = None) -> bool:
        """Abrir ticket fiscal"""
        try:
            # Formato: tipo_documento + numero_documento + nombre + IVA
            doc_type = 'D'  # DNI
            doc_number = customer_data.get('doc_number', '0') if customer_data else '0'
            name = customer_data.get('name', 'Consumidor Final')[:30] if customer_data else 'Consumidor Final'
            iva_type = customer_data.get('iva_type', '5') if customer_data else '5'  # Consumidor Final
            
            data = f"{doc_type}{doc_number}{name}{iva_type}"
            response = self._send_command(self.CMD_OPEN_TICKET, data)
            
            return 'A' in response  # 'A' indica aceptación
        except Exception as e:
            logger.error(f"[HASAR] Error abriendo ticket: {e}")
            raise FiscalPrinterError(f"Error abriendo ticket: {e}")
    
    def print_item(self, description: str, quantity: float, price: float, 
                   iva_rate: float = 21.0, internal_tax: float = 0.0) -> bool:
        """Imprimir ítem en ticket fiscal"""
        try:
            # Formato: cantidad + precio + IVA + impuesto_interno + descripción
            desc_short = description[:20]
            data = f"{quantity:.2f}{price:.2f}{iva_rate:.2f}{internal_tax:.2f}{desc_short}"
            response = self._send_command(self.CMD_PRINT_ITEM, data)
            
            return 'A' in response
        except Exception as e:
            logger.error(f"[HASAR] Error imprimiendo ítem: {e}")
            raise FiscalPrinterError(f"Error imprimiendo ítem: {e}")
    
    def print_payment(self, amount: float, payment_type: str, 
                     description: str = "") -> bool:
        """Imprimir forma de pago"""
        try:
            # Mapear tipos de pago a códigos Hasar
            payment_codes = {
                'cash': '1',
                'card': '2',
                'debit': '3',
                'check': '4',
                'transfer': '5',
            }
            code = payment_codes.get(payment_type.lower(), '1')
            
            data = f"{code}{amount:.2f}{description[:20]}"
            response = self._send_command(self.CMD_PRINT_PAYMENT, data)
            
            return 'A' in response
        except Exception as e:
            logger.error(f"[HASAR] Error imprimiendo pago: {e}")
            raise FiscalPrinterError(f"Error imprimiendo pago: {e}")
    
    def close_fiscal_ticket(self) -> Dict:
        """Cerrar ticket fiscal y devolver datos"""
        try:
            response = self._send_command(self.CMD_CLOSE_TICKET)
            
            # Parsear respuesta para obtener número de ticket
            ticket_data = {
                'success': 'A' in response,
                'response': response,
                'ticket_number': self._extract_ticket_number(response),
            }
            
            return ticket_data
        except Exception as e:
            logger.error(f"[HASAR] Error cerrando ticket: {e}")
            raise FiscalPrinterError(f"Error cerrando ticket: {e}")
    
    def _extract_ticket_number(self, response: str) -> Optional[int]:
        """Extraer número de ticket de la respuesta"""
        try:
            # Implementación simplificada - depende del formato real
            if response and len(response) > 4:
                return int(response[-8:])  # Últimos 8 caracteres suelen ser el número
            return None
        except:
            return None
    
    def cancel_document(self) -> bool:
        """Cancelar documento actual"""
        try:
            response = self._send_command(self.CMD_CANCEL)
            return 'A' in response
        except Exception as e:
            logger.error(f"[HASAR] Error cancelando documento: {e}")
            raise FiscalPrinterError(f"Error cancelando documento: {e}")
    
    def daily_close(self) -> Dict:
        """Cierre diario (Z)"""
        try:
            response = self._send_command(self.CMD_DAILY_CLOSE)
            
            return {
                'success': 'A' in response,
                'response': response,
            }
        except Exception as e:
            logger.error(f"[HASAR] Error en cierre diario: {e}")
            raise FiscalPrinterError(f"Error en cierre diario: {e}")
    
    def get_last_number(self, document_type: str) -> int:
        """Obtener último número de comprobante"""
        try:
            # document_type: 'A', 'B', 'C', 'X', etc.
            data = document_type
            response = self._send_command(self.CMD_GET_LAST_NUMBER, data)
            
            # Extraer número de la respuesta
            return self._extract_ticket_number(response) or 0
        except Exception as e:
            logger.error(f"[HASAR] Error obteniendo último número: {e}")
            return 0
