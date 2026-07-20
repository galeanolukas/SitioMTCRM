"""
Clase base para controladores fiscales
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class FiscalPrinterError(Exception):
    """Excepción base para errores de impresora fiscal"""
    pass


class FiscalPrinterBase(ABC):
    """
    Clase base abstracta para controladores fiscales
    """
    
    def __init__(self, port: str, baudrate: int = 9600, timeout: int = 1):
        """
        Inicializar conexión con impresora fiscal
        
        Args:
            port: Puerto serial (ej: '/dev/ttyUSB0', 'COM1')
            baudrate: Velocidad de comunicación (default: 9600)
            timeout: Timeout en segundos (default: 1)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connected = False
        self._connection = None
        
    @abstractmethod
    def connect(self) -> bool:
        """Establecer conexión con la impresora fiscal"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Cerrar conexión con la impresora fiscal"""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict:
        """Obtener estado de la impresora fiscal"""
        pass
    
    @abstractmethod
    def open_fiscal_ticket(self, customer_data: Optional[Dict] = None) -> bool:
        """Abrir ticket fiscal"""
        pass
    
    @abstractmethod
    def print_item(self, description: str, quantity: float, price: float, 
                   iva_rate: float = 21.0, internal_tax: float = 0.0) -> bool:
        """Imprimir ítem en ticket fiscal"""
        pass
    
    @abstractmethod
    def print_payment(self, amount: float, payment_type: str, 
                     description: str = "") -> bool:
        """Imprimir forma de pago"""
        pass
    
    @abstractmethod
    def close_fiscal_ticket(self) -> Dict:
        """Cerrar ticket fiscal y devolver datos"""
        pass
    
    @abstractmethod
    def cancel_document(self) -> bool:
        """Cancelar documento actual"""
        pass
    
    @abstractmethod
    def daily_close(self) -> Dict:
        """Cierre diario (Z)"""
        pass
    
    @abstractmethod
    def get_last_number(self, document_type: str) -> int:
        """Obtener último número de comprobante"""
        pass
