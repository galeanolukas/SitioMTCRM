from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import requests
import logging
import urllib3
from datetime import datetime, timedelta
from decimal import Decimal

from core.erp.models import Sale, DetSale, Product, Client, CatalogoConfig

logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Command(BaseCommand):
    help = 'Sincroniza pedidos entregados desde el catálogo al ERP local'

    def add_arguments(self, parser):
        parser.add_argument(
            '--catalogo-id',
            type=int,
            help='ID específico de configuración de catálogo a sincronizar'
        )
        parser.add_argument(
            '--dias',
            type=int,
            default=7,
            help='Cantidad de días hacia atrás para sincronizar (default: 7)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sincronización sin crear ventas'
        )

    def handle(self, *args, **options):
        catalogo_id = options.get('catalogo_id')
        dias = options.get('dias', 7)
        dry_run = options.get('dry_run', False)

        self.stdout.write(f"Iniciando sincronización de pedidos del catálogo...")
        self.stdout.write(f"Días a sincronizar: {dias}")
        self.stdout.write(f"Modo simulación: {dry_run}")

        # Obtener configuraciones de catálogo
        if catalogo_id:
            catalogo_configs = CatalogoConfig.objects.filter(id=catalogo_id, is_active=True)
        else:
            catalogo_configs = CatalogoConfig.objects.filter(is_active=True)

        if not catalogo_configs.exists():
            self.stdout.write(self.style.WARNING("No hay configuraciones de catálogo activas"))
            return

        for catalogo_config in catalogo_configs:
            self.stdout.write(f"\nProcesando catálogo: {catalogo_config.catalogo_url}")
            self.sync_catalogo(catalogo_config, dias, dry_run)

        self.stdout.write(self.style.SUCCESS("\nSincronización completada"))

    def sync_catalogo(self, catalogo_config, dias, dry_run):
        """Sincroniza pedidos de un catálogo específico"""
        
        # Calcular fecha desde
        fecha_desde = (timezone.now() - timedelta(days=dias)).strftime('%Y-%m-%d')
        
        # URL del endpoint del catálogo
        catalogo_url = catalogo_config.catalogo_url.rstrip('/')
        sync_url = f"{catalogo_url}/api/pedidos-entregados/"
        
        # Parámetros de la consulta
        params = {
            'desde_fecha': fecha_desde,
            'api_key': catalogo_config.api_key
        }
        
        try:
            self.stdout.write(f"Consultando: {sync_url}")
            self.stdout.write(f"Parámetros: desde_fecha={fecha_desde}")
            
            response = requests.get(sync_url, params=params, timeout=30, verify=False)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('success', False):
                self.stdout.write(self.style.ERROR(f"Error en respuesta del catálogo: {data.get('error', 'Error desconocido')}"))
                return
            
            pedidos = data.get('pedidos', [])
            self.stdout.write(f"Pedidos recibidos: {len(pedidos)}")
            
            # Procesar cada pedido
            ventas_creadas = 0
            ventas_omitidas = 0
            errores = []
            
            for pedido in pedidos:
                try:
                    # Verificar si ya existe la venta
                    pedido_id = pedido.get('pedido_id')
                    if Sale.objects.filter(catalogo_pedido_id=str(pedido_id)).exists():
                        self.stdout.write(f"  Pedido {pedido_id} ya existe, omitiendo...")
                        ventas_omitidas += 1
                        continue
                    
                    if not dry_run:
                        self.crear_venta_desde_pedido(catalogo_config, pedido)
                        ventas_creadas += 1
                        self.stdout.write(f"  ✓ Venta creada para pedido {pedido_id}")
                    else:
                        self.stdout.write(f"  [DRY RUN] Crearía venta para pedido {pedido_id}")
                        ventas_creadas += 1
                        
                except Exception as e:
                    error_msg = f"Error procesando pedido {pedido.get('pedido_id')}: {str(e)}"
                    errores.append(error_msg)
                    self.stdout.write(self.style.ERROR(f"  ✗ {error_msg}"))
            
            # Resumen
            self.stdout.write(f"\nResumen:")
            self.stdout.write(f"  Ventas creadas: {ventas_creadas}")
            self.stdout.write(f"  Ventas omitidas (duplicadas): {ventas_omitidas}")
            if errores:
                self.stdout.write(f"  Errores: {len(errores)}")
                for error in errores:
                    self.stdout.write(self.style.ERROR(f"    - {error}"))
            
            # Actualizar last_sync
            if not dry_run and (ventas_creadas > 0 or ventas_omitidas > 0):
                catalogo_config.last_sync = timezone.now()
                catalogo_config.save()
                self.stdout.write(f"Última sincronización actualizada")
                
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Error de conexión con el catálogo: {str(e)}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error general: {str(e)}"))

    def crear_venta_desde_pedido(self, catalogo_config, pedido):
        """Crea una venta local desde un pedido del catálogo"""
        
        with transaction.atomic():
            # Buscar o crear cliente genérico
            cliente_generico, created = Client.objects.get_or_create(
                email='cliente_catalogo@catalogo.com',
                defaults={
                    'names': 'Cliente Catálogo',
                    'company': catalogo_config.company
                }
            )
            
            # Calcular subtotal
            productos = pedido.get('productos', [])
            subtotal = sum(p.get('subtotal', 0) for p in productos)
            
            # Mapear método de pago
            metodo_pago_map = {
                'mercado_pago': 'mp',
                'efectivo': 'cash',
                'transferencia': 'transfer',
                'tarjeta': 'card'
            }
            metodo_pago = metodo_pago_map.get(pedido.get('metodo_pago', 'mercado_pago'), 'mp')
            
            # Crear venta
            venta = Sale.objects.create(
                company=catalogo_config.company,
                cli=cliente_generico,
                subtotal=Decimal(str(subtotal)),
                total=Decimal(str(pedido.get('total', 0))),
                payment_method=metodo_pago,
                catalogo_pedido_id=str(pedido.get('pedido_id')),
                source='catalogo',
                budget_notes=pedido.get('observaciones', '')
            )
            
            # Crear detalles de productos
            for prod_data in productos:
                # Buscar producto por código (code) o código de proveedor
                producto = Product.objects.filter(
                    code=prod_data.get('sku')
                ).first()
                
                if not producto:
                    producto = Product.objects.filter(
                        codigo_proveedor=prod_data.get('sku')
                    ).first()
                
                if producto:
                    DetSale.objects.create(
                        sale=venta,
                        prod=producto,
                        cant=prod_data.get('cantidad', 1),
                        price=Decimal(str(prod_data.get('precio_unitario', 0))),
                        subtotal=Decimal(str(prod_data.get('subtotal', 0)))
                    )
                else:
                    logger.warning(f"Producto no encontrado: SKU={prod_data.get('sku')}")
            
            return venta
