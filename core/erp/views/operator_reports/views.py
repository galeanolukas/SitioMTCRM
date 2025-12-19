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
                        'payment_method': sale.get_payment_method_display(),
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
    """Generate PDF report with printer-friendly formatting"""
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from io import BytesIO
    
    # Register fonts (if available)
    try:
        pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        font_name = 'Arial'
    except:
        font_name = 'Helvetica'
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ventas_{start_date}_al_{end_date}.pdf"'
    
    buffer = BytesIO()
    # Reduce margins for more space
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=12,
        spaceAfter=6,
        alignment=1,  # Center
        textColor=colors.black
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=10,
        spaceAfter=6,
        alignment=1,  # Center
        textColor=colors.black
    )
    
    normal_style = styles['Normal']
    
    # Get company info
    company_name = "Todas las Empresas"
    if company_id:
        try:
            company = Company.objects.get(id=company_id)
            company_name = company.name
        except Company.DoesNotExist:
            company_name = "Empresa Desconocida"
    
    user_name = user.get_full_name() or user.username
    
    # Build story
    story = []
    
    # Title
    story.append(Paragraph("REPORTE DE VENTAS", title_style))
    story.append(Paragraph(company_name, subtitle_style))
    story.append(Spacer(1, 4))
    
    # Report info in single row - more compact
    info_data = [[
        f"Por: {user_name[:15]}",
        f"Período: {start_date} al {end_date}",
        f"Fecha: {timezone.now().strftime('%d/%m %H:%M')}",
        f"Ventas: {len(sales)}"
    ]]
    
    info_table = Table(info_data, colWidths=[2*inch, 2.5*inch, 2*inch, 1.2*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 8))
    
    # Sales table - better spacing
    if sales:
        # Calculate totals
        total_amount = sum(float(sale.total) for sale in sales)
        
        # Table headers
        headers = ['Fecha', 'Ticket', 'Cliente', 'Total', 'Pago']
        
        # Table data
        table_data = [headers]
        for sale in sales[:80]:  # Adjusted for better spacing
            ticket_number = sale.invoice_number if sale.is_invoiced else f"TK-{sale.id:06d}"
            # Truncate client name for space
            client_name = sale.cli.names if sale.cli else 'Anónimo'
            if len(client_name) > 18:
                client_name = client_name[:15] + "..."
            
            table_data.append([
                sale.date_joined.strftime('%d/%m %H:%M'),
                ticket_number,
                client_name,
                f"${float(sale.total):.2f}",
                sale.get_payment_method_display()[:8]  # Truncate payment method
            ])
        
        # Add total row
        table_data.append(['', '', 'TOTAL:', f"${total_amount:.2f}", ''])
        
        # Better column widths for spacing - match info table width
        sales_table = Table(table_data, colWidths=[1.5*inch, 1.2*inch, 2.0*inch, 1.0*inch, 1.0*inch])
        sales_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
            ('TOPPADDING', (0, 0), (-1, 0), 5),
            ('BACKGROUND', (0, 1), (-2, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),  # Total column right-aligned
            ('FONTNAME', (-1, -1), (-1, -1), font_name),  # Total row bold
            ('FONTSIZE', (-1, -1), (-1, -1), 8),
            ('BACKGROUND', (-1, -1), (-1, -1), colors.lightgrey),  # Total row background
            ('BOTTOMPADDING', (-1, -1), (-1, -1), 5),
            ('TOPPADDING', (-1, -1), (-1, -1), 5),
            ('BOLD', (-1, -1), (-1, -1), True),  # Make total row bold
        ]))
        
        story.append(sales_table)
        
        if len(sales) > 80:
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"*Mostrando las primeras 80 ventas de {len(sales)} totales", ParagraphStyle('small', parent=normal_style, fontSize=7)))
    
    story.append(Spacer(1, 8))
    
    # Payment method breakdown - compact but readable
    payment_choices = {
        'cash': 'Efectivo',
        'card': 'Tarjeta',
        'transfer': 'Transfer',
        'mp': 'MP',
        'check': 'Cheque',
        'combined': 'Combin'
    }
    
    payment_data = [['Método', 'Total', 'Cant.']]
    for method_key, method_name in payment_choices.items():
        method_sales = sales.filter(payment_method=method_key)
        if method_sales.exists():
            method_total = method_sales.aggregate(total=Sum('total'))['total'] or 0
            method_count = method_sales.count()
            payment_data.append([method_name, f"${method_total:.2f}", str(method_count)])
    
    if len(payment_data) > 1:
        story.append(Paragraph("DESGLOSE POR MÉTODO DE PAGO", subtitle_style))
        payment_table = Table(payment_data, colWidths=[2.0*inch, 2.0*inch, 1.0*inch])
        payment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('TOPPADDING', (0, 0), (-1, 0), 4),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Total column right-aligned
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOLD', (0, 1), (-1, -1), True),  # Make payment totals bold
        ]))
        
        story.append(payment_table)
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    response.write(buffer.getvalue())
    buffer.close()
    
    return response
