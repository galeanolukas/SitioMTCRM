from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from core.erp.mixins import ValidatePermissionRequiredMixin
from django.db.models import Sum, Count, F
from django.utils import timezone
from datetime import datetime, timedelta
from core.erp.models import Sale, Company
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json


class OperatorSalesReportView(LoginRequiredMixin, ValidatePermissionRequiredMixin, TemplateView):
    template_name = 'operator_reports/sales_report.html'
    permission_required = 'erp.view_sale'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Reporte de Ventas'
        context['companies'] = Company.objects.all()
        
        # Get company from session or user
        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)
        context['active_company_id'] = active_cid
        
        return context

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST.get('action')
            
            if action == 'get_report':
                report_type = request.POST.get('report_type', 'daily')
                company_id = request.POST.get('company', '')
                start_date = request.POST.get('start_date', '')
                end_date = request.POST.get('end_date', '')
                
                # Get company filter
                active_cid = self.request.session.get('company_id')
                if not self.request.user.is_superuser:
                    active_cid = active_cid or getattr(self.request.user, 'company_id', None)
                
                if company_id and (self.request.user.is_superuser or not active_cid):
                    active_cid = company_id if company_id else active_cid
                
                # Get dates
                if report_type == 'daily':
                    start_date = timezone.now().date().strftime('%Y-%m-%d')
                    end_date = start_date
                elif report_type == 'weekly':
                    end_date = timezone.now().date()
                    start_date = (end_date - timedelta(days=7)).strftime('%Y-%m-%d')
                elif report_type == 'monthly':
                    end_date = timezone.now().date()
                    start_date = (end_date - timedelta(days=30)).strftime('%Y-%m-%d')
                
                # Build filters
                filters = {}
                if active_cid:
                    filters['company_id'] = active_cid
                if start_date and end_date:
                    filters['date_joined__date__range'] = [start_date, end_date]
                
                # Get sales data
                sales = Sale.objects.filter(**filters).order_by('-date_joined')
                
                # Calculate totals
                total_sales = sales.aggregate(
                    total=Sum('total'),
                    count=Count('id')
                )
                
                # Calculate totals by payment method
                payment_totals = {}
                payment_choices = {
                    'cash': 'Efectivo',
                    'card': 'Tarjeta',
                    'transfer': 'Transferencia',
                    'mp': 'Mercado Pago',
                    'check': 'Cheque',
                    'combined': 'Combinada'
                }
                
                for method_key, method_name in payment_choices.items():
                    method_total = sales.filter(payment_method=method_key).aggregate(
                        total=Sum('total'),
                        count=Count('id')
                    )
                    payment_totals[method_key] = {
                        'name': method_name,
                        'total': float(method_total['total'] or 0),
                        'count': method_total['count'] or 0
                    }
                
                # Prepare data for response
                sales_data = []
                for sale in sales:
                    # Get invoice/ticket number
                    ticket_number = sale.invoice_number if sale.is_invoiced else f"TK-{sale.id:06d}"
                    
                    sales_data.append({
                        'id': sale.id,
                        'date': sale.date_joined.strftime('%d/%m/%Y %H:%M'),
                        'client': sale.cli.names if sale.cli else 'Anónimo',
                        'total': float(sale.total),
                        'payment_method': sale.payment_method,  # Enviar el código, no el display
                        'payment_details': getattr(sale, 'payment_details', []),  # Enviar detalles si existen
                        'company': sale.company.name if sale.company else 'N/A',
                        'ticket_number': ticket_number
                    })
                
                data = {
                    'success': True,
                    'sales': sales_data,
                    'total_amount': float(total_sales['total'] or 0),
                    'total_count': total_sales['count'] or 0,
                    'payment_totals': payment_totals,
                    'period_type': report_type,
                    'start_date': start_date,
                    'end_date': end_date
                }
                
            else:
                data['error'] = 'Acción no válida'
                
        except Exception as e:
            data['error'] = str(e)
            
        return JsonResponse(data, safe=False)


@login_required
def operator_sales_export(request):
    """Export sales data for operators"""
    if not request.user.has_perm('erp.view_sale'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    
    try:
        report_type = request.GET.get('report_type', 'daily')
        company_id = request.GET.get('company', '')
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        export_format = request.GET.get('format', 'csv')
        
        # Get company filter
        active_cid = request.session.get('company_id')
        if not request.user.is_superuser:
            active_cid = active_cid or getattr(request.user, 'company_id', None)
        
        if company_id and (request.user.is_superuser or not active_cid):
            active_cid = company_id if company_id else active_cid
        
        # Get dates
        if report_type == 'daily':
            start_date = timezone.now().date().strftime('%Y-%m-%d')
            end_date = start_date
        elif report_type == 'weekly':
            end_date = timezone.now().date()
            start_date = (end_date - timedelta(days=7)).strftime('%Y-%m-%d')
        elif report_type == 'monthly':
            end_date = timezone.now().date()
            start_date = (end_date - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Build filters
        filters = {}
        if active_cid:
            filters['company_id'] = active_cid
        if start_date and end_date:
            filters['date_joined__date__range'] = [start_date, end_date]
        
        # Get sales data
        sales = Sale.objects.filter(**filters).order_by('-date_joined')
        
        if export_format == 'pdf':
            return generate_pdf_report(sales, start_date, end_date, active_cid, request.user)
        
        elif export_format == 'csv':
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="ventas_{start_date}_al_{end_date}.csv"'
            
            writer = csv.writer(response)
            # Get company and user info for header
            company_name = "Todas las Empresas"
            if active_cid:
                try:
                    company = Company.objects.get(id=active_cid)
                    company_name = company.name
                except Company.DoesNotExist:
                    company_name = "Empresa Desconocida"
            
            user_name = request.user.get_full_name() or request.user.username
            
            # Add header information
            writer.writerow([f"REPORTE DE VENTAS - {company_name}"])
            writer.writerow([f"Generado por: {user_name}"])
            writer.writerow([f"Período: {start_date} al {end_date}"])
            writer.writerow([f"Fecha de generación: {timezone.now().strftime('%d/%m/%Y %H:%M')}"])
            writer.writerow([])
            
            writer.writerow(['Fecha', 'Ticket/Factura', 'Cliente', 'Total', 'Forma de Pago', 'Empresa'])
            
            total_amount = 0
            for sale in sales:
                # Get invoice/ticket number
                ticket_number = sale.invoice_number if sale.is_invoiced else f"TK-{sale.id:06d}"
                
                writer.writerow([
                    sale.date_joined.strftime('%d/%m/%Y %H:%M'),
                    ticket_number,
                    sale.cli.names if sale.cli else 'Anónimo',
                    sale.total,
                    sale.get_payment_method_display(),
                    sale.company.name if sale.company else 'N/A'
                ])
                total_amount += float(sale.total)
            
            # Add summary
            writer.writerow([])
            writer.writerow(['RESUMEN'])
            writer.writerow(['Total Ventas', total_amount])
            writer.writerow(['Cantidad de Ventas', len(sales)])
            writer.writerow(['Promedio por Venta', total_amount / len(sales) if sales else 0])
            
            # Add payment method breakdown
            writer.writerow([])
            writer.writerow(['DESGLOSE POR MÉTODO DE PAGO'])
            
            payment_choices = {
                'cash': 'Efectivo',
                'card': 'Tarjeta',
                'transfer': 'Transferencia',
                'mp': 'Mercado Pago',
                'check': 'Cheque',
                'combined': 'Combinada'
            }
            
            for method_key, method_name in payment_choices.items():
                method_sales = sales.filter(payment_method=method_key)
                if method_sales.exists():
                    method_total = method_sales.aggregate(total=Sum('total'))['total'] or 0
                    method_count = method_sales.count()
                    writer.writerow([method_name, f"${method_total:.2f}", f"({method_count} ventas)"])
            
            return response
        
        elif export_format == 'excel':
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from django.http import HttpResponse
            from io import BytesIO
            
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="ventas_{start_date}_al_{end_date}.xlsx"'
            
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = 'Reporte de Ventas'
            
            # Get company and user info for header
            company_name = "Todas las Empresas"
            if active_cid:
                try:
                    company = Company.objects.get(id=active_cid)
                    company_name = company.name
                except Company.DoesNotExist:
                    company_name = "Empresa Desconocida"
            
            user_name = request.user.get_full_name() or request.user.username
            
            # Add header information
            ws.append(['REPORTE DE VENTAS'])
            ws.merge_cells('A1:F1')
            ws['A1'].font = Font(bold=True, size=16)
            ws['A1'].alignment = Alignment(horizontal='center')
            
            ws.append([company_name])
            ws.merge_cells('A2:F2')
            ws['A2'].font = Font(bold=True, size=14)
            ws['A2'].alignment = Alignment(horizontal='center')
            
            ws.append([''])
            ws.append(['Generado por:', user_name])
            ws.append(['Período:', f'{start_date} al {end_date}'])
            ws.append(['Fecha de generación:', timezone.now().strftime('%d/%m/%Y %H:%M')])
            ws.append([''])
            
            # Headers
            headers = ['Fecha', 'Ticket/Factura', 'Cliente', 'Total', 'Forma de Pago', 'Empresa']
            ws.append(headers)
            
            # Style headers
            header_font = Font(bold=True, color='FFFFFF')
            header_alignment = Alignment(horizontal='center')
            header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                 top=Side(style='thin'), bottom=Side(style='thin'))
            
            # Style header information rows
            for row_num in range(4, 8):
                for col_num in range(1, 3):
                    cell = ws.cell(row=row_num, column=col_num)
                    cell.font = Font(bold=True)
            
            # Style column headers
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=9, column=col_num)
                cell.font = header_font
                cell.alignment = header_alignment
                cell.fill = header_fill
                cell.border = thin_border
            
            # Data
            total_amount = 0
            row_num = 10
            for sale in sales:
                # Get invoice/ticket number
                ticket_number = sale.invoice_number if sale.is_invoiced else f"TK-{sale.id:06d}"
                
                ws.append([
                    sale.date_joined.strftime('%d/%m/%Y %H:%M'),
                    ticket_number,
                    sale.cli.names if sale.cli else 'Anónimo',
                    float(sale.total),
                    sale.get_payment_method_display(),
                    sale.company.name if sale.company else 'N/A'
                ])
                
                # Style data rows
                for col_num in range(1, 7):
                    cell = ws.cell(row=row_num, column=col_num)
                    cell.border = thin_border
                    if col_num == 4:  # Total column
                        cell.alignment = Alignment(horizontal='right')
                
                total_amount += float(sale.total)
                row_num += 1
            
            # Summary section
            row_num += 2
            ws.append(['RESUMEN'])
            ws.merge_cells(f'A{row_num}:F{row_num}')
            ws.cell(row=row_num, column=1).font = Font(bold=True, size=12)
            ws.cell(row=row_num, column=1).alignment = Alignment(horizontal='center')
            ws.cell(row=row_num, column=1).fill = PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')
            
            row_num += 1
            ws.append(['Total Ventas', total_amount])
            ws.cell(row=row_num, column=1).font = Font(bold=True)
            ws.cell(row=row_num, column=2).font = Font(bold=True)
            ws.cell(row=row_num, column=2).alignment = Alignment(horizontal='right')
            
            row_num += 1
            ws.append(['Cantidad de Ventas', len(sales)])
            ws.cell(row=row_num, column=1).font = Font(bold=True)
            
            row_num += 1
            ws.append(['Promedio por Venta', total_amount / len(sales) if sales else 0])
            ws.cell(row=row_num, column=1).font = Font(bold=True)
            ws.cell(row=row_num, column=2).font = Font(bold=True)
            ws.cell(row=row_num, column=2).alignment = Alignment(horizontal='right')
            
            # Payment method breakdown
            row_num += 2
            ws.append(['DESGLOSE POR MÉTODO DE PAGO'])
            ws.merge_cells(f'A{row_num}:F{row_num}')
            ws.cell(row=row_num, column=1).font = Font(bold=True, size=12)
            ws.cell(row=row_num, column=1).alignment = Alignment(horizontal='center')
            ws.cell(row=row_num, column=1).fill = PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')
            
            payment_choices = {
                'cash': 'Efectivo',
                'card': 'Tarjeta',
                'transfer': 'Transferencia',
                'mp': 'Mercado Pago',
                'check': 'Cheque',
                'combined': 'Combinada'
            }
            
            row_num += 1
            for method_key, method_name in payment_choices.items():
                method_sales = sales.filter(payment_method=method_key)
                if method_sales.exists():
                    method_total = method_sales.aggregate(total=Sum('total'))['total'] or 0
                    method_count = method_sales.count()
                    ws.append([method_name, method_total, f"({method_count} ventas)"])
                    ws.cell(row=row_num, column=1).font = Font(bold=True)
                    ws.cell(row=row_num, column=2).font = Font(bold=True)
                    ws.cell(row=row_num, column=2).alignment = Alignment(horizontal='right')
                    row_num += 1
            
            # Adjust column widths
            column_widths = [20, 15, 25, 12, 15, 20]
            for col_num, width in enumerate(column_widths, 1):
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = width
            
            # Save to BytesIO
            excel_file = BytesIO()
            wb.save(excel_file)
            excel_file.seek(0)
            response.write(excel_file.read())
            
            return response
            
    except Exception as e:
        return HttpResponse(f"Error en exportación: {str(e)}", content_type='text/plain')


def generate_pdf_report(sales, start_date, end_date, company_id, user):
    """Generate PDF report matching the exact format from the image"""
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from io import BytesIO
    from django.db.models import Sum
    from core.erp.models import Company
    
    # Obtener nombre de la empresa
    company_name = "Empresa"
    try:
        if company_id:
            company = Company.objects.get(id=company_id)
            company_name = company.name
        else:
            # Si no hay company_id, intentar obtener de la sesión o usar la primera empresa
            company = Company.objects.filter(is_active=True).first()
            if company:
                company_name = company.name
    except:
        pass
    
    # Register fonts (if available)
    try:
        pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        font_name = 'Arial'
    except:
        font_name = 'Helvetica'
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="planilla_ventas_{start_date}_al_{end_date}.pdf"'
    
    buffer = BytesIO()
    # Use A4 with margins matching the image format
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=50, bottomMargin=50)
    
    styles = getSampleStyleSheet()
    
    # Custom styles for the exact format
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=12,
        alignment=1,  # Center
        textColor=colors.black,
        bold=True
    )
    
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=20,
        alignment=1,  # Center
        textColor=colors.black,
        bold=True
    )
    
    normal_style = styles['Normal']
    
    # Build story
    story = []
    
    # Header - Company name and Planilla de Ventas
    story.append(Paragraph(company_name, header_style))
    story.append(Paragraph("Planilla de Ventas", date_style))
    story.append(Spacer(1, 8))  # Reducido de 20 a 8
    
    # Date and Operator section - más compacto
    date_style_small = ParagraphStyle(
        'DateStyleSmall',
        parent=styles['Normal'],
        fontSize=10,  # Reducido de 12 a 10
        spaceAfter=6,  # Reducido espacio
        alignment=1,  # Center
        textColor=colors.black
    )
    
    # Fecha y operador en una sola línea
    operator_name = getattr(user, 'username', 'Operador')
    story.append(Paragraph(f"Fecha: {start_date.split('-')[0]} | Operador: {operator_name}", date_style_small))
    story.append(Spacer(1, 12))  # Reducido de 30 a 12
    
    # Calculate totals by payment method
    cash_total = 0
    transfer_total = 0
    mp_total = 0
    card_total = 0
    check_total = 0
    combined_total = 0
    grand_total = 0
    
    for sale in sales:
        sale_total = float(sale.total)
        grand_total += sale_total
        
        # Manejar diferentes métodos de pago
        if sale.payment_method == 'cash':
            cash_total += sale_total
        elif sale.payment_method == 'transfer':
            transfer_total += sale_total
        elif sale.payment_method == 'mp':
            mp_total += sale_total
        elif sale.payment_method == 'card':
            card_total += sale_total
        elif sale.payment_method == 'check':
            check_total += sale_total
        elif sale.payment_method == 'combined':
            # Para pagos combinados, usar los detalles guardados
            if hasattr(sale, 'payment_details') and sale.payment_details:
                # Distribuir montos según los detalles guardados
                for payment in sale.payment_details:
                    method = payment.get('method', '')
                    amount = float(payment.get('amount', 0))
                    if method == 'cash':
                        cash_total += amount
                    elif method == 'transfer':
                        transfer_total += amount
                    elif method == 'mp':
                        mp_total += amount
                    elif method == 'card':
                        card_total += amount
                    elif method == 'check':
                        check_total += amount
            else:
                # Si no hay detalles, poner en columna combinada
                combined_total += sale_total
    
    # Función para formatear con comas
    def format_currency(amount):
        if amount == 0:
            return ''
        return f"${amount:,.2f}"
    
    # Función para formatear pagos combinados con descripción
    def format_combined_payment(amount, payment_method):
        if amount == 0:
            return ''
        # Para pagos combinados, solo mostrar el monto sin descripción
        return f"${amount:,.2f}"
    
    # Sales table matching the image format - versión simplificada con abreviaturas
    headers = ['N° Comprob.', 'Efectivo', 'Transf.', 'MP', 'Otros', 'Total']
    
    # Table data with sales distributed by payment method
    table_data = [headers]
    
    # Group sales by payment method and create rows
    for sale in sales:
        sale_total = float(sale.total)
        cash_amount = 0
        transfer_amount = 0
        mp_amount = 0
        other_amount = 0  # Incluye tarjeta, cheque y combinado
        other_payment_method = ''  # Para guardar el método de pago
        
        # Asignar montos según método de pago
        if sale.payment_method == 'cash':
            cash_amount = sale_total
        elif sale.payment_method == 'transfer':
            transfer_amount = sale_total
        elif sale.payment_method == 'mp':
            mp_amount = sale_total
        elif sale.payment_method == 'combined':
            # Para pagos combinados, usar los detalles guardados
            if hasattr(sale, 'payment_details') and sale.payment_details:
                # Distribuir montos según los detalles guardados
                for payment in sale.payment_details:
                    method = payment.get('method', '')
                    amount = float(payment.get('amount', 0))
                    if method == 'cash':
                        cash_amount += amount
                    elif method == 'transfer':
                        transfer_amount += amount
                    elif method == 'mp':
                        mp_amount += amount
                    elif method == 'card':
                        card_amount += amount
                    elif method == 'check':
                        check_amount += amount
                # No poner nada en "Otros" ya que se distribuyó
                other_amount = 0
                other_payment_method = ''
            else:
                # Si no hay detalles, poner en columna combinada
                other_amount = sale_total
                other_payment_method = sale.payment_method
        else:
            # Tarjeta, Cheque van en "Otros"
            other_amount = sale_total
            other_payment_method = sale.payment_method
        
        ticket_number = sale.invoice_number if sale.is_invoiced else f"TK-{sale.id:06d}"
        
        table_data.append([
            ticket_number,
            format_currency(cash_amount),
            format_currency(transfer_amount),
            format_currency(mp_amount),
            format_combined_payment(other_amount, other_payment_method),
            format_currency(sale_total)
        ])
    
    # Add summary row
    table_data.append([
        'Resumen',
        format_currency(cash_total),
        format_currency(transfer_total),
        format_currency(mp_total),
        format_currency(card_total + check_total + combined_total),
        format_currency(grand_total)
    ])
    
    # Create table with adjusted column widths - más espacio para márgenes
    sales_table = Table(table_data, colWidths=[1.3*inch, 1.2*inch, 1.1*inch, 1.0*inch, 1.1*inch, 1.3*inch])
    sales_table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOLD', (0, 0), (-1, 0), True),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),  # Reducido de 8 a 6
        ('TOPPADDING', (0, 0), (-1, 0), 6),  # Reducido de 8 a 6
        
        # Data rows styling
        ('BACKGROUND', (0, 1), (-2, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-2, -1), colors.black),
        ('ALIGN', (0, 1), (-1, -2), 'CENTER'),
        ('FONTNAME', (0, 1), (-2, -1), font_name),
        ('FONTSIZE', (0, 1), (-2, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-2, -1), 4),  # Reducido de 6 a 4
        ('TOPPADDING', (0, 1), (-2, -1), 4),  # Reducido de 6 a 4
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        
        # Summary row styling
        ('BACKGROUND', (-1, -1), (-1, -1), colors.lightgrey),
        ('TEXTCOLOR', (-1, -1), (-1, -1), colors.black),
        ('ALIGN', (-1, -1), (-1, -1), 'CENTER'),
        ('FONTNAME', (-1, -1), (-1, -1), font_name),
        ('FONTSIZE', (-1, -1), (-1, -1), 10),
        ('BOLD', (-1, -1), (-1, -1), True),
        ('BOTTOMPADDING', (-1, -1), (-1, -1), 6),  # Reducido de 8 a 6
        ('TOPPADDING', (-1, -1), (-1, -1), 6),  # Reducido de 8 a 6
    ]))
    
    story.append(sales_table)
    story.append(Spacer(1, 20))  # Reducido de 40 a 20
    
    # Observations section
    obs_style = ParagraphStyle(
        'ObsStyle',
        parent=normal_style,
        fontSize=10,
        spaceAfter=10,
        leftIndent=20
    )
    
    story.append(Paragraph("Observaciones:", obs_style))
    story.append(Spacer(1, 20))
    
    # Conformity section
    conformity_style = ParagraphStyle(
        'ConformityStyle',
        parent=normal_style,
        fontSize=10,
        spaceAfter=10,
        leftIndent=20
    )
    
    story.append(Paragraph("Conformidad:", conformity_style))
    
    # Add signature line
    story.append(Spacer(1, 30))
    story.append(Paragraph("_________________________", conformity_style))
    story.append(Paragraph("Firma", conformity_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    response.write(buffer.getvalue())
    buffer.close()
    
    return response
