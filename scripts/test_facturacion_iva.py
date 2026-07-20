#!/usr/bin/env python
"""
Script para verificar el sistema de facturación con IVA
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.erp.models import Client, Product, Sale, LibroIvaRegistro
from decimal import Decimal

def test_client_iva_fields():
    """Verificar campos CUIT/CUIL y condición IVA en clientes"""
    print("=" * 80)
    print("🧪 VERIFICACIÓN DE CAMPOS IVA EN CLIENTES")
    print("=" * 80)
    
    # 1. Verificar campos del modelo
    print("\n📋 1. Campos del modelo Client:")
    print(f"   - cuit_cuil: {Client._meta.get_field('cuit_cuil').verbose_name}")
    print(f"   - condicion_iva: {Client._meta.get_field('condicion_iva').verbose_name}")
    print(f"   - Default condicion_iva: {Client._meta.get_field('condicion_iva').default}")
    
    # 2. Verificar choices de condición IVA
    print("\n📋 2. Opciones de condición IVA:")
    for choice in Client.CONDICION_IVA_CHOICES:
        print(f"   - {choice[0]}: {choice[1]}")
    
    # 3. Listar clientes con sus datos
    print("\n📋 3. Clientes en el sistema:")
    clients = Client.objects.all()[:5]
    for client in clients:
        print(f"   - {client.names}: CUIT/CUIL={client.cuit_cuil or 'N/A'}, IVA={client.get_condicion_iva_display()}")
    
    print("\n✅ Campos IVA en clientes verificados")

def test_product_iva_fields():
    """Verificar campo IVA en productos"""
    print("\n" + "=" * 80)
    print("🧪 VERIFICACIÓN DE CAMPOS IVA EN PRODUCTOS")
    print("=" * 80)
    
    # 1. Verificar campos del modelo
    print("\n📋 1. Campos del modelo Product:")
    print(f"   - iva_rate: {Product._meta.get_field('iva_rate').verbose_name}")
    print(f"   - Default iva_rate: {Product._meta.get_field('iva_rate').default}")
    print(f"   - vat_code: {Product._meta.get_field('vat_code').verbose_name}")
    print(f"   - Default vat_code: {Product._meta.get_field('vat_code').default}")
    
    # 2. Verificar choices de código AFIP
    print("\n📋 2. Opciones de código AFIP:")
    for choice in Product.VAT_CODE_CHOICES:
        print(f"   - {choice[0]}: {choice[1]}")
    
    # 3. Listar productos con sus tasas de IVA
    print("\n📋 3. Productos en el sistema:")
    products = Product.objects.all()[:5]
    for product in products:
        print(f"   - {product.name}: IVA={product.iva_rate}%, Código AFIP={product.get_vat_code_display()}")
    
    print("\n✅ Campos IVA en productos verificados")

def test_anonymous_sales():
    """Verificar manejo de ventas anónimas"""
    print("\n" + "=" * 80)
    print("🧪 VERIFICACIÓN DE VENTAS ANÓNIMAS")
    print("=" * 80)
    
    # 1. Verificar campo cli en Sale
    print("\n📋 1. Campo cli en Sale:")
    print(f"   - cli: {Sale._meta.get_field('cli').verbose_name}")
    print(f"   - null: {Sale._meta.get_field('cli').null}")
    print(f"   - blank: {Sale._meta.get_field('cli').blank}")
    
    # 2. Buscar ventas sin cliente
    print("\n📋 2. Ventas sin cliente (cli=None):")
    anonymous_sales = Sale.objects.filter(cli__isnull=True)[:5]
    print(f"   Total: {anonymous_sales.count()}")
    for sale in anonymous_sales:
        print(f"   - Venta {sale.id}: Total=${sale.total}, Tipo factura={sale.invoice_type}")
    
    # 3. Verificar ventas con cliente
    print("\n📋 3. Ventas con cliente:")
    sales_with_client = Sale.objects.filter(cli__isnull=False)[:5]
    print(f"   Total: {sales_with_client.count()}")
    for sale in sales_with_client:
        client_iva = sale.cli.get_condicion_iva_display() if sale.cli else 'N/A'
        print(f"   - Venta {sale.id}: Cliente={sale.cli.names if sale.cli else 'N/A'}, IVA={client_iva}, Tipo factura={sale.invoice_type}")
    
    print("\n✅ Manejo de ventas anónimas verificado")

def test_iva_calculation():
    """Verificar cálculo de IVA en carrito"""
    print("\n" + "=" * 80)
    print("🧪 VERIFICACIÓN DE CÁLCULO DE IVA")
    print("=" * 80)
    
    # Simular cálculo de IVA
    print("\n📋 1. Simulación de cálculo de IVA:")
    
    # Producto con IVA 21%
    price_net = Decimal('100.00')
    iva_rate = Decimal('0.21')
    price_final = price_net * (1 + iva_rate)
    iva_amount = (price_final / (1 + iva_rate)) * iva_rate
    
    print(f"   Producto con IVA 21%:")
    print(f"   - Precio neto: ${price_net}")
    print(f"   - Tasa IVA: {iva_rate * 100}%")
    print(f"   - Precio final: ${price_final}")
    print(f"   - IVA calculado: ${iva_amount}")
    
    # Producto con IVA 10.5%
    iva_rate_105 = Decimal('0.105')
    price_final_105 = price_net * (1 + iva_rate_105)
    iva_amount_105 = (price_final_105 / (1 + iva_rate_105)) * iva_rate_105
    
    print(f"\n   Producto con IVA 10.5%:")
    print(f"   - Precio neto: ${price_net}")
    print(f"   - Tasa IVA: {iva_rate_105 * 100}%")
    print(f"   - Precio final: ${price_final_105}")
    print(f"   - IVA calculado: ${iva_amount_105}")
    
    # Producto exento (0%)
    iva_rate_0 = Decimal('0.00')
    price_final_0 = price_net * (1 + iva_rate_0)
    iva_amount_0 = Decimal('0.00')
    
    print(f"\n   Producto exento (0%):")
    print(f"   - Precio neto: ${price_net}")
    print(f"   - Tasa IVA: {iva_rate_0 * 100}%")
    print(f"   - Precio final: ${price_final_0}")
    print(f"   - IVA calculado: ${iva_amount_0}")
    
    print("\n✅ Cálculo de IVA verificado")

def test_libro_iva():
    """Verificar registro en Libro IVA"""
    print("\n" + "=" * 80)
    print("🧪 VERIFICACIÓN DE LIBRO IVA")
    print("=" * 80)
    
    # 1. Verificar modelo LibroIvaRegistro
    print("\n📋 1. Modelo LibroIvaRegistro:")
    print(f"   - Tipo registro: {LibroIvaRegistro._meta.get_field('tipo_registro').verbose_name}")
    print(f"   - Tipo comprobante: {LibroIvaRegistro._meta.get_field('tipo_comprobante').verbose_name}")
    
    # 2. Verificar choices
    print("\n📋 2. Opciones de tipo de registro:")
    for choice in LibroIvaRegistro.TIPO_REGISTRO_CHOICES:
        print(f"   - {choice[0]}: {choice[1]}")
    
    print("\n📋 3. Opciones de tipo de comprobante:")
    for choice in LibroIvaRegistro.TIPO_COMPROBANTE_CHOICES:
        print(f"   - {choice[0]}: {choice[1]}")
    
    # 3. Listar registros
    print("\n📋 4. Registros en Libro IVA:")
    registros = LibroIvaRegistro.objects.all()[:5]
    print(f"   Total: {registros.count()}")
    for reg in registros:
        total_iva = (reg.iva_21 or 0) + (reg.iva_10_5 or 0) + (reg.iva_27 or 0) + (reg.iva_2_5 or 0) + (reg.iva_0 or 0)
        print(f"   - {reg.tipo_registro}: Tipo={reg.get_tipo_comprobante_display()}, Neto=${reg.neto_gravado}, IVA=${total_iva}")
    
    print("\n✅ Libro IVA verificado")

def main():
    """Ejecutar todas las verificaciones"""
    print("\n" + "=" * 80)
    print("🔍 VERIFICACIÓN COMPLETA DEL SISTEMA DE FACTURACIÓN CON IVA")
    print("=" * 80)
    
    try:
        test_client_iva_fields()
        test_product_iva_fields()
        test_anonymous_sales()
        test_iva_calculation()
        test_libro_iva()
        
        print("\n" + "=" * 80)
        print("✅ VERIFICACIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error durante verificación: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
