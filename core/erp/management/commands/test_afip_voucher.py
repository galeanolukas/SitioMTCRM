from django.core.management.base import BaseCommand
from core.erp.models import AfipConfig, AfipPuntoVenta, Company
from core.erp.afip.client import AfipClient
from decimal import Decimal
from datetime import datetime


class Command(BaseCommand):
    help = 'Prueba automatizada de emisión de comprobantes AFIP usando configuración de la DB'

    def add_arguments(self, parser):
        parser.add_argument(
            '--config-id',
            type=int,
            help='ID de la configuración AFIP a usar (si no se especifica, usa la primera activa)'
        )
        parser.add_argument(
            '--punto-venta',
            type=int,
            help='Número de punto de venta (si no se especifica, usa el primero activo)'
        )
        parser.add_argument(
            '--cuit-cliente',
            type=str,
            default='20409378472',
            help='CUIT del cliente para el comprobante de prueba (default: 20409378472)'
        )
        parser.add_argument(
            '--monto',
            type=float,
            default=100.0,
            help='Monto del comprobante de prueba (default: 100.0)'
        )

    def handle(self, *args, **options):
        config_id = options.get('config_id')
        punto_venta = options.get('punto_venta')
        cuit_cliente = options.get('cuit_cliente')
        monto = options.get('monto')

        self.stdout.write('=== Prueba de Emisión de Comprobante AFIP ===\n')

        # Obtener configuración AFIP
        if config_id:
            try:
                config = AfipConfig.objects.get(id=config_id, is_active=True)
                self.stdout.write(f'Usando configuración AFIP ID: {config_id}')
            except AfipConfig.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Configuración AFIP ID {config_id} no encontrada o inactiva'))
                return
        else:
            config = AfipConfig.objects.filter(is_active=True).first()
            if not config:
                self.stdout.write(self.style.ERROR('No hay configuraciones AFIP activas'))
                return
            self.stdout.write(f'Usando configuración AFIP ID: {config.id} (primera activa)')

        # Mostrar información de la configuración
        self.stdout.write(f'Empresa: {config.company.name if config.company else "Global"}')
        self.stdout.write(f'CUIT: {config.cuit}')
        self.stdout.write(f'Ambiente: {config.environment}')
        self.stdout.write(f'Tipo de comprobante: {config.tipo_comprobante}')
        self.stdout.write(f'WSFE Autorizado: {"Sí" if config.wsfe_authorized else "No"}')
        self.stdout.write('')

        # Obtener punto de venta
        if punto_venta:
            self.stdout.write(f'Usando punto de venta: {punto_venta}')
        else:
            punto_venta_obj = AfipPuntoVenta.objects.filter(company=config.company, is_active=True).first()
            if punto_venta_obj:
                punto_venta = punto_venta_obj.numero
                self.stdout.write(f'Usando punto de venta activo: {punto_venta}')
            else:
                punto_venta = 1
                self.stdout.write(f'Usando punto de venta default: {punto_venta}')

        self.stdout.write('')

        # Crear cliente AFIP
        try:
            self.stdout.write('Inicializando cliente AFIP...')
            client = AfipClient(company_id=config.company_id if config.company else None)
            self.stdout.write(self.style.SUCCESS('Cliente AFIP inicializado correctamente'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al inicializar cliente AFIP: {e}'))
            return

        # Probar conexión
        try:
            self.stdout.write('\nProbando conexión con AFIP...')
            server_status = client.get_server_status()
            if 'error' in server_status:
                self.stdout.write(self.style.ERROR(f'Error de conexión: {server_status["error"]}'))
                return
            self.stdout.write(self.style.SUCCESS('Conexión con AFIP exitosa'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al probar conexión: {e}'))
            return

        # Obtener último número de comprobante
        try:
            self.stdout.write('\nObteniendo último número de comprobante autorizado...')
            last_nro = client.get_last_voucher_number(punto_venta, config.tipo_comprobante)
            if isinstance(last_nro, dict) and 'error' in last_nro:
                self.stdout.write(self.style.ERROR(f'Error al obtener último número: {last_nro["error"]}'))
                return
            next_nro = last_nro + 1
            self.stdout.write(f'Último número autorizado: {last_nro}')
            self.stdout.write(f'Próximo número a usar: {next_nro}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al obtener último número: {e}'))
            return

        # Preparar datos del comprobante de prueba
        try:
            self.stdout.write('\nPreparando comprobante de prueba...')
            monto_neto = float(monto)
            monto_iva = float(monto * 0.21)
            monto_total = monto_neto + monto_iva
            voucher_data = {
                'CantReg': 1,
                'PtoVta': punto_venta,
                'CbteTipo': config.tipo_comprobante,
                'Concepto': config.concepto,
                'DocTipo': 99,  # Consumidor Final
                'DocNro': 0,  # Consumidor Final
                'CbteDesde': next_nro,
                'CbteHasta': next_nro,
                'CbteFch': datetime.now().strftime('%Y%m%d'),
                'ImpTotal': monto_total,
                'ImpTotConc': 0.0,
                'ImpNeto': monto_neto,
                'ImpOpEx': 0.0,
                'ImpIVA': monto_iva,
                'ImpTrib': 0.0,
                'MonId': 'PES',
                'MonCotiz': 1.0,
                'CondicionIVAReceptorId': 5,  # Consumidor Final
                'Iva': [
                    {
                        'Id': 5,  # 21%
                        'BaseImp': monto_neto,
                        'Importe': monto_iva
                    }
                ]
            }
            self.stdout.write(f'Tipo de comprobante: {config.tipo_comprobante}')
            self.stdout.write(f'Punto de venta: {punto_venta}')
            self.stdout.write(f'Número: {next_nro}')
            self.stdout.write(f'CUIT cliente: {cuit_cliente}')
            self.stdout.write(f'Monto neto: {monto_neto}')
            self.stdout.write(f'Monto IVA: {monto_iva}')
            self.stdout.write(f'Monto total: {monto_total}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al preparar datos: {e}'))
            return

        # Emitir comprobante
        try:
            self.stdout.write('\nEmitiendo comprobante...')
            result = client.create_voucher(voucher_data, full_response=True)
            
            if 'error' in result:
                self.stdout.write(self.style.ERROR(f'Error al emitir comprobante: {result["error"]}'))
                return

            self.stdout.write(self.style.SUCCESS('Comprobante emitido exitosamente'))
            self.stdout.write('\n=== Respuesta completa de AFIP ===')
            self.stdout.write(str(result))
            self.stdout.write('\n=== Datos extraídos ===')
            self.stdout.write(f'CAE: {result.get("CAE", "N/A")}')
            self.stdout.write(f'Vencimiento CAE: {result.get("CAEFchVto", "N/A")}')
            self.stdout.write(f'Resultado: {result.get("Resultado", "N/A")}')
            self.stdout.write(f'Número: {result.get("CbteDesde", "N/A")} - {result.get("CbteHasta", "N/A")}')

            if 'Observaciones' in result:
                self.stdout.write(f'Observaciones: {result["Observaciones"]}')

            self.stdout.write('\n' + self.style.SUCCESS('=== Prueba completada exitosamente ==='))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al emitir comprobante: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
