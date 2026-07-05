#!/usr/bin/env python
"""
Script para generar un comprobante PDF de ejemplo con datos AFIP SDK
Este script simula una respuesta de AFIP y genera un PDF con esos datos.
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datetime import datetime, timedelta
from decimal import Decimal
from core.erp.utils.pdf_utils import invoice_pdf_reportlab
from core.erp.models import Sale, DetSale, Client, Company, Product, Category


def create_example_sale():
    """
    Crea una venta de ejemplo con datos simulados de AFIP
    """
    # Obtener o crear empresa de ejemplo
    company, _ = Company.objects.get_or_create(
        cuit='20111222333',
        defaults={
            'name': 'Empresa Ejemplo S.A.',
            'address': 'Av. Corrientes 1234',
            'phone': '54-11-4444-5555',
            'email': 'contacto@ejemplo.com',
            'is_active': True
        }
    )

    # Obtener o crear cliente de ejemplo
    client, _ = Client.objects.get_or_create(
        dni='12345678',
        defaults={
            'names': 'Juan',
            'surnames': 'Pérez',
            'cuit_cuil': '20123456789',
            'address': 'Calle Falsa 123',
            'telefono': '54-11-5555-6666',
            'email': 'juan.perez@email.com',
            'company': company,
            'is_active': True
        }
    )

    # Obtener o crear categoría de ejemplo
    category, _ = Category.objects.get_or_create(
        name='General',
        defaults={'company': company}
    )

    # Obtener o crear producto de ejemplo
    product, _ = Product.objects.get_or_create(
        code='PROD001',
        defaults={
            'name': 'Producto de Ejemplo',
            'pvp': Decimal('1000.00'),
            'iva_rate': Decimal('21.00'),
            'company': company,
            'cat': category
        }
    )

    # Crear venta de ejemplo
    sale = Sale.objects.create(
        company=company,
        cli=client,
        date_joined=datetime.now(),
        subtotal=Decimal('1000.00'),
        iva=Decimal('210.00'),
        total=Decimal('1210.00'),
        payment_method='efectivo',
        is_invoiced=True,
        invoice_number='00001-00000001',
        invoice_pos=1,
        invoice_type='FACTURA B',
        synced_to_server=False
    )

    # Crear detalle de venta
    DetSale.objects.create(
        sale=sale,
        prod=product,
        cant=Decimal('1.00'),
        price=Decimal('1000.00'),
        subtotal=Decimal('1000.00')
    )

    return sale


def generate_afip_voucher_data():
    """
    Genera datos simulados de respuesta AFIP (CAE, CAEFchVto, etc.)
    """
    today = datetime.now()
    cae_vto = today + timedelta(days=10)

    return {
        'cae': '12345678901234',
        'cae_fch_vto': cae_vto.strftime('%Y%m%d'),
        'cbte_tipo': '6',  # Factura B
        'pto_vta': '1',
        'cbte_nro': '1',
        'fch_proceso': today.strftime('%Y%m%d'),
        'resultado': 'A',  # Aprobado
        'motivo': '',
        'reproceso': 'N'
    }


def main():
    """
    Función principal para generar el PDF de ejemplo
    """
    print("Generando comprobante PDF de ejemplo con datos AFIP...")

    # Crear venta de ejemplo
    sale = create_example_sale()
    print(f"Venta creada: ID {sale.id}")

    # Generar datos AFIP simulados
    afip_data = generate_afip_voucher_data()
    print(f"Datos AFIP simulados: CAE {afip_data['cae']}, Vto {afip_data['cae_fch_vto']}")

    # Generar PDF (usando la función existente)
    from django.test import RequestFactory
    factory = RequestFactory()
    request = factory.get('/')

    try:
        response = invoice_pdf_reportlab(request, sale)

        # Guardar PDF en archivo
        filename = f"comprobante_afip_ejemplo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(os.path.dirname(__file__), filename)

        with open(filepath, 'wb') as f:
            f.write(response.content)

        print(f"PDF generado exitosamente: {filepath}")
        print(f"Tamaño: {len(response.content)} bytes")

        # Mostrar datos del comprobante
        print("\n--- Datos del Comprobante ---")
        print(f"Empresa: {sale.company.name}")
        print(f"CUIT: {sale.company.cuit}")
        print(f"Cliente: {sale.cli.names} {sale.cli.surnames}")
        print(f"CUIT Cliente: {sale.cli.cuit_cuil}")
        print(f"Factura N°: {sale.invoice_number}")
        print(f"Fecha: {sale.date_joined.strftime('%d/%m/%Y %H:%M')}")
        print(f"Subtotal: ${sale.subtotal:.2f}")
        print(f"IVA: ${sale.iva:.2f}")
        print(f"TOTAL: ${sale.total:.2f}")
        print(f"\n--- Datos AFIP ---")
        print(f"CAE: {afip_data['cae']}")
        print(f"CAE Vto: {afip_data['cae_fch_vto']}")
        print(f"Tipo Comprobante: {afip_data['cbte_tipo']}")
        print(f"Punto Venta: {afip_data['pto_vta']}")
        print(f"Número: {afip_data['cbte_nro']}")
        print(f"Resultado: {afip_data['resultado']}")

    except Exception as e:
        print(f"Error generando PDF: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpiar datos de ejemplo
        print("\nLimpiando datos de ejemplo...")
        DetSale.objects.filter(sale=sale).delete()
        sale.delete()
        print("Datos de ejemplo eliminados")


if __name__ == '__main__':
    main()
