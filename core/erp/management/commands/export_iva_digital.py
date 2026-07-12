from django.core.management.base import BaseCommand
from django.db.models import Sum
from core.erp.models import Sale, SaleVatBreakdown
from django.contrib.auth import get_user_model
from crum import get_current_user
from datetime import datetime
import os


class Command(BaseCommand):
    help = "Exportar Libro IVA Digital (COMPROBANTES y ALÍCUOTAS) para ARCA/AFIP"

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de la empresa a exportar (opcional, usa empresa activa por defecto)'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Fecha inicio (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='Fecha fin (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='exports/iva_digital',
            help='Directorio de salida (default: exports/iva_digital)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando exportación de Libro IVA Digital..."))

        # Determinar empresa activa
        try:
            company_id = options.get('company_id')
            active_company = None
            
            if company_id:
                active_company = Sale.objects.filter(company_id=company_id).first()
                if active_company:
                    active_company = active_company.company
                    self.stdout.write(f"Empresa especificada: {active_company.name} (ID: {active_company.id})")
                else:
                    self.stdout.write(self.style.ERROR(f"No se encontró empresa con ID {company_id}"))
                    return
            else:
                User = get_user_model()
                current_user = get_current_user()
                
                if current_user and not current_user.is_anonymous and hasattr(current_user, 'company') and current_user.company:
                    active_company = current_user.company
                    self.stdout.write(f"Empresa del usuario logueado: {active_company.name} (ID: {active_company.id})")
                else:
                    # Si no hay usuario logueado, buscar usuario con último login más reciente
                    try:
                        user_with_last_login = User.objects.exclude(company__isnull=True).exclude(last_login__isnull=True).order_by('-last_login').first()
                        if user_with_last_login:
                            active_company = user_with_last_login.company
                            self.stdout.write(f"Usuario con último login: {user_with_last_login.username} ({user_with_last_login.last_login})")
                    except Exception:
                        # Último fallback: primer usuario con empresa
                        user_with_company = User.objects.exclude(company__isnull=True).first()
                        if user_with_company:
                            active_company = user_with_company.company
                            self.stdout.write(f"Usuario activo (fallback): {user_with_company.username}")
                
                if not active_company:
                    # Fallback: usar primera empresa disponible
                    first_sale = Sale.objects.first()
                    if first_sale:
                        active_company = first_sale.company
                        self.stdout.write("Fallback: usando empresa de primera venta disponible")
            
            if not active_company:
                self.stdout.write(self.style.ERROR("No se encontró ninguna empresa configurada."))
                return
                
            self.stdout.write(f"Empresa activa: {active_company.name} (ID: {active_company.id})")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error obteniendo empresa activa: {e}"))
            return

        # Filtrar ventas por fecha si se especificó
        start_date = options.get('start_date')
        end_date = options.get('end_date')
        
        sales_qs = Sale.objects.filter(company_id=active_company.id, status='confirmed')
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                sales_qs = sales_qs.filter(date_joined__date__gte=start_date_obj)
                self.stdout.write(f"Filtrando desde: {start_date}")
            except ValueError:
                self.stdout.write(self.style.ERROR(f"Formato de fecha inicio inválido: {start_date}. Use YYYY-MM-DD"))
                return
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                sales_qs = sales_qs.filter(date_joined__date__lte=end_date_obj)
                self.stdout.write(f"Filtrando hasta: {end_date}")
            except ValueError:
                self.stdout.write(self.style.ERROR(f"Formato de fecha fin inválido: {end_date}. Use YYYY-MM-DD"))
                return

        total_sales = sales_qs.count()
        if total_sales == 0:
            self.stdout.write(self.style.WARNING("No hay ventas para exportar en el período especificado."))
            return
        
        self.stdout.write(f"Total de ventas a exportar: {total_sales}")

        # Crear directorio de salida
        output_dir = options.get('output_dir')
        os.makedirs(output_dir, exist_ok=True)
        
        # Generar nombre de archivo con fecha
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        comprobantes_file = os.path.join(output_dir, f'COMPROBANTES_{active_company.id}_{timestamp}.txt')
        alicuotas_file = os.path.join(output_dir, f'ALICUOTAS_{active_company.id}_{timestamp}.txt')

        # Generar archivo COMPROBANTES
        self.generate_comprobantes_file(sales_qs, comprobantes_file)
        
        # Generar archivo ALÍCUOTAS
        self.generate_alicuotas_file(sales_qs, alicuotas_file)
        
        self.stdout.write(self.style.SUCCESS(
            f"Exportación completada.\n"
            f"Archivo COMPROBANTES: {comprobantes_file}\n"
            f"Archivo ALÍCUOTAS: {alicuotas_file}"
        ))

    def generate_comprobantes_file(self, sales_qs, output_file):
        """Generar archivo COMPROBANTES (cabecera) para Libro IVA Digital"""
        self.stdout.write("Generando archivo COMPROBANTES...")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # Cabecera del archivo
            f.write("FECHA;TIPO_COMPROBANTE;PUNTO_VENTA;NUMERO_COMPROBANTE;NUMERO_COMPROBANTE_HASTA;CODIGO_DOCUMENTO_COMPRADOR;NUMERO_IDENTIFICACION_COMPRADOR;APELLIDO_NOMBRE_COMPRADOR;IMPORTE_TOTAL_GRAVADO;IMPORTE_TOTAL_NO_GRAVADO;IMPORTE_EXENTO;IMPORTE_TOTAL_IMPUESTOS;IMPORTE_TOTAL_COMPROBANTE;MONEDA;TIPO_CAMBIO;CANTIDAD_ALICUOTAS_IVA;CODIGO_OPERACION;OTROS_TRIBUTOS;FECHA_VENCIMIENTO_PAGO\n")
            
            for sale in sales_qs:
                # Obtener totales de IVA desde aperturas
                vat_breakdowns = sale.vat_breakdowns.all()
                total_vat = vat_breakdowns.aggregate(total=Sum('vat_amount'))['total'] or 0
                total_taxable = vat_breakdowns.aggregate(total=Sum('taxable_base'))['total'] or 0
                
                # Datos del cliente
                client = sale.cli
                if client:
                    client_name = f"{client.names} {client.surnames or ''}".strip()
                    client_doc_type = self.get_doc_type(client.condicion_iva)
                    client_doc_number = client.cuit_cuil or client.dni or ''
                else:
                    client_name = 'Consumidor Final'
                    client_doc_type = '99'
                    client_doc_number = ''
                
                # Tipo de comprobante según invoice_type
                tipo_comprobante_map = {'A': '01', 'B': '06', 'C': '11', 'X': '99'}
                tipo_comprobante = tipo_comprobante_map.get(sale.invoice_type, '06')
                
                # Punto de venta y número
                punto_venta = sale.invoice_pos or '0001'
                numero_comprobante = sale.invoice_number or str(sale.id).zfill(8)
                
                # Fecha
                fecha = sale.date_joined.strftime('%d/%m/%Y')
                
                # Escribir línea
                line = f"{fecha};{tipo_comprobante};{punto_venta};{numero_comprobante};{numero_comprobante};{client_doc_type};{client_doc_number};{client_name};{total_taxable:.2f};0.00;0.00;{total_vat:.2f};{sale.total:.2f};PES;1.0000;{vat_breakdowns.count()};;;;;\n"
                f.write(line)
        
        self.stdout.write(self.style.SUCCESS(f"Archivo COMPROBANTES generado: {output_file}"))

    def generate_alicuotas_file(self, sales_qs, output_file):
        """Generar archivo ALÍCUOTAS (detalle) para Libro IVA Digital"""
        self.stdout.write("Generando archivo ALÍCUOTAS...")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # Cabecera del archivo
            f.write("FECHA;TIPO_COMPROBANTE;PUNTO_VENTA;NUMERO_COMPROBANTE;CODIGO_ALICUOTA_IVA;IMPORTE_BASE_IMponible;IMPORTE_IVA\n")
            
            for sale in sales_qs:
                # Tipo de comprobante según invoice_type
                tipo_comprobante_map = {'A': '01', 'B': '06', 'C': '11', 'X': '99'}
                tipo_comprobante = tipo_comprobante_map.get(sale.invoice_type, '06')
                
                # Punto de venta y número
                punto_venta = sale.invoice_pos or '0001'
                numero_comprobante = sale.invoice_number or str(sale.id).zfill(8)
                
                # Fecha
                fecha = sale.date_joined.strftime('%d/%m/%Y')
                
                # Escribir una línea por cada alícuota
                for vat_breakdown in sale.vat_breakdowns.all():
                    line = f"{fecha};{tipo_comprobante};{punto_venta};{numero_comprobante};{vat_breakdown.vat_code};{vat_breakdown.taxable_base:.2f};{vat_breakdown.vat_amount:.2f}\n"
                    f.write(line)
        
        self.stdout.write(self.style.SUCCESS(f"Archivo ALÍCUOTAS generado: {output_file}"))

    def get_doc_type(self, condicion_iva):
        """Mapear condición IVA a tipo de documento AFIP"""
        doc_type_map = {
            'RI': '80',  # CUIT
            'M': '80',   # CUIT
            'EX': '80',  # CUIT
            'CF': '99',  # Consumidor Final
            'NC': '99',  # No categorizado
        }
        return doc_type_map.get(condicion_iva, '99')
