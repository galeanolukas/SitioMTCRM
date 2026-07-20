"""
Fábrica para obtener controladores fiscales según configuración
"""
import logging
from typing import Optional
from .base import FiscalPrinterBase, FiscalPrinterError
from .hasar import HasarFiscalPrinter

logger = logging.getLogger(__name__)


class FiscalPrinterFactory:
    """Fábrica para crear instancias de impresoras fiscales"""
    
    @staticmethod
    def get_printer(printer_type: str, port: str, baudrate: int = 9600) -> Optional[FiscalPrinterBase]:
        """
        Obtener instancia de impresora fiscal según tipo
        
        Args:
            printer_type: Tipo de impresora ('hasar', 'epson', 'none')
            port: Puerto serial
            baudrate: Velocidad de comunicación
            
        Returns:
            Instancia de FiscalPrinterBase o None si no hay impresora
        """
        if printer_type == 'none' or not printer_type:
            logger.debug("[FISCAL] Sin impresora fiscal configurada")
            return None
        
        try:
            if printer_type == 'hasar':
                logger.info(f"[FISCAL] Creando impresora Hasar en puerto {port}")
                return HasarFiscalPrinter(port=port, baudrate=baudrate)
            elif printer_type == 'epson':
                logger.warning(f"[FISCAL] Epson no implementado aún")
                return None
            else:
                logger.warning(f"[FISCAL] Tipo de impresora desconocido: {printer_type}")
                return None
        except Exception as e:
            logger.error(f"[FISCAL] Error creando impresora fiscal: {e}")
            return None
    
    @staticmethod
    def get_printer_from_config(config: dict) -> Optional[FiscalPrinterBase]:
        """
        Obtener impresora fiscal desde configuración de AfipConfig
        
        Args:
            config: Diccionario con configuración AFIP
            
        Returns:
            Instancia de FiscalPrinterBase o None
        """
        if not config.get('fiscal_printer_enabled', False):
            logger.debug("[FISCAL] Impresora fiscal no habilitada en configuración")
            return None
        
        printer_type = config.get('fiscal_printer_type', 'none')
        port = config.get('fiscal_printer_port', '/dev/ttyUSB0')
        baudrate = config.get('fiscal_printer_baudrate', 9600)
        
        return FiscalPrinterFactory.get_printer(printer_type, port, baudrate)
