#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append('/media/lukas/ARCHIVOS/GitHub/SitioMTCRM')
sys.path.append('/media/lukas/ARCHIVOS/GitHub')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from core.erp.models import Sale, Company
from django.contrib.auth.models import User
from core.erp.views.operator_reports.views import generate_pdf_report
from datetime import datetime, timedelta

def test_pdf_report():
    print("=== Probando Reporte PDF de Operador ===")
    
    # Obtener datos de prueba
    user = User.objects.first()
    company = Company.objects.first()
    
    end_date = datetime.now().date()
    start_date = (end_date - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    print(f"Usuario: {user}")
    print(f"Empresa: {company}")
    print(f"Período: {start_date} al {end_date_str}")
    
    # Obtener ventas recientes
    sales = Sale.objects.filter(date_joined__date__range=[start_date, end_date_str]).order_by('-date_joined')[:10]
    
    print(f'\nVentas encontradas: {sales.count()}')
    for sale in sales:
        ticket_number = sale.invoice_number if sale.is_invoiced else f"TK-{sale.id}"
        print(f'- {ticket_number} | Total: ${sale.total} | Método: {sale.payment_method} | Factura: {sale.is_invoiced}')
    
    # Generar PDF
    if sales.exists():
        try:
            response = generate_pdf_report(sales, start_date, end_date_str, company.id if company else None, user)
            print('\n✅ PDF generado exitosamente')
            print(f'Tamaño del PDF: {len(response.content)} bytes')
            
            # Guardar PDF para revisión
            with open('/tmp/test_reporte_ventas.pdf', 'wb') as f:
                f.write(response.content)
            print('PDF guardado en /tmp/test_reporte_ventas.pdf')
            
        except Exception as e:
            print(f'\n❌ Error al generar PDF: {e}')
            import traceback
            traceback.print_exc()
    else:
        print('\n⚠️ No hay ventas para probar')

if __name__ == '__main__':
    test_pdf_report()
