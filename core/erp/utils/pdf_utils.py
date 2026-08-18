from django.http import HttpResponse
from django.template.loader import get_template
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from decimal import Decimal
import os
from django.conf import settings
import base64
import io

def invoice_pdf_reportlab(request, sale):
    """
    Generar PDF de factura usando ReportLab como alternativa a WeasyPrint
    """
    response = HttpResponse(content_type='application/pdf')
    filename = f"factura_{sale.invoice_number or sale.id}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    # Crear documento PDF
    doc = SimpleDocTemplate(response, pagesize=A4)
    story = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Centrado
    )
    
    # Datos de la empresa
    company_obj = sale.company or None
    company_data = []
    if company_obj:
        company_data = [
            ['Empresa:', company_obj.name or ''],
            ['CUIT:', company_obj.cuit or ''],
            ['Dirección:', company_obj.address or ''],
            ['Teléfono:', company_obj.phone or ''],
            ['Email:', company_obj.email or ''],
        ]
    
    # Datos de la factura
    if sale.is_invoiced:
        invoice_display = sale.invoice_number
    else:
        # Usar siempre el ID local para mantener consistencia
        if hasattr(sale, 'local_sale_id') and sale.local_sale_id:
            invoice_display = f'TK-{sale.local_sale_id:06d}'
        else:
            invoice_display = f'TK-{sale.id:06d}'
    
    invoice_data = [
        ['Factura N°:', invoice_display],
        ['Fecha:', sale.date_joined.strftime('%d/%m/%Y %H:%M')],
        ['Tipo:', 'Factura' if sale.is_invoiced else 'Ticket'],
        ['Cliente:', sale.cli.names if sale.cli else 'Anónimo'],
    ]
    
    # Agregar título
    story.append(Paragraph("FACTURA", title_style))
    story.append(Spacer(1, 12))
    
    # Tabla de datos de empresa
    if company_data:
        company_table = Table(company_data, colWidths=[1.5*inch, 4*inch])
        company_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(company_table)
        story.append(Spacer(1, 12))
    
    # Tabla de datos de factura
    invoice_table = Table(invoice_data, colWidths=[1.5*inch, 4*inch])
    invoice_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(invoice_table)
    story.append(Spacer(1, 20))
    
    # Detalles de productos
    headers = ['Producto', 'Cantidad', 'Precio Unit.', 'Subtotal']
    data = [headers]
    
    for det in sale.detsale_set.all():
        product_name = det.prod.name if det.prod else 'Producto desconocido'
        quantity = f"{det.cant:.2f}"
        unit_price = f"${float(det.price):.2f}"
        subtotal = f"${float(det.subtotal):.2f}"
        data.append([product_name, quantity, unit_price, subtotal])
    
    # Tabla de productos
    products_table = Table(data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    products_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    story.append(products_table)
    story.append(Spacer(1, 20))
    
    # Totales
    totals_data = [
        ['Subtotal:', f"${float(sale.subtotal):.2f}"],
        ['IVA:', f"${float(sale.iva):.2f}"],
        ['TOTAL:', f"${float(sale.total):.2f}"],
    ]
    
    totals_table = Table(totals_data, colWidths=[4*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(totals_table)
    
    # Datos AFIP y QR
    if sale.afip_cae:
        story.append(Spacer(1, 12))
        afip_data = [
            ['CAE:', sale.afip_cae],
            ['Vto. CAE:', sale.afip_cae_vto.strftime('%d/%m/%Y') if sale.afip_cae_vto else '-'],
        ]
        afip_table = Table(afip_data, colWidths=[1.5*inch, 4*inch])
        afip_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(afip_table)

    if sale.afip_qr and sale.afip_qr.startswith('data:image'):
        try:
            b64 = sale.afip_qr.split('base64,')[1]
            img_bytes = base64.b64decode(b64)
            img_reader = ImageReader(io.BytesIO(img_bytes))
            story.append(Spacer(1, 12))
            story.append(Image(img_reader, width=1.5*inch, height=1.5*inch))
        except Exception:
            pass

    # Construir PDF
    doc.build(story)

    return response
