#!/usr/bin/env python3
import os
import sys
import django

# Agregar el path del proyecto
sys.path.append('/media/lukas/ARCHIVOS/GitHub/SitioMTCRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Inicializar Django
django.setup()

from core.erp.models import Sale
from django.db import transaction
import json

print("=== DIAGNÓSTICO DE ERRORES EN PAGOS COMBINADOS ===")
print()

# 1. Verificar ventas con pagos combinados
print("1. 🔍 Buscando ventas con pagos combinados...")
combined_sales = Sale.objects.filter(payment_method__contains='+').order_by('-date_joined')[:10]

if combined_sales:
    print(f"   Se encontraron {len(combined_sales)} ventas con pagos combinados:")
    for sale in combined_sales:
        print(f"   📄 Venta #{sale.id} - {sale.date_joined.strftime('%Y-%m-%d %H:%M')}")
        print(f"      Método: {sale.payment_method}")
        print(f"      Total: ${sale.total}")
        if hasattr(sale, 'payment_details') and sale.payment_details:
            print(f"      Detalles: {sale.payment_details}")
        else:
            print(f"      ⚠️  No hay payment_details")
        print()
else:
    print("   ✅ No se encontraron ventas con pagos combinados")

# 2. Verificar estructura de payment_details
print("2. 🔍 Verificando estructura de payment_details...")
for sale in combined_sales[:3]:
    if hasattr(sale, 'payment_details') and sale.payment_details:
        print(f"   Venta #{sale.id}:")
        try:
            details = sale.payment_details
            if isinstance(details, (list, dict)):
                print(f"      ✅ Estructura válida: {type(details)}")
                if isinstance(details, list):
                    for i, payment in enumerate(details):
                        print(f"         Pago {i+1}: {payment}")
                else:
                    print(f"         Detalles: {details}")
            else:
                print(f"      ❌ Estructura inválida: {type(details)} = {details}")
        except Exception as e:
            print(f"      ❌ Error procesando payment_details: {e}")
    print()

# 3. Simular una venta con pagos combinados
print("3. 🔍 Simulando creación de venta con pagos combinados...")
try:
    with transaction.atomic():
        # Crear una venta de prueba con pagos combinados
        test_payment_details = [
            {'method': 'cash', 'amount': 50.0},
            {'method': 'transfer', 'amount': 25.0}
        ]
        
        print(f"   Detalles de prueba: {test_payment_details}")
        print(f"   Tipo: {type(test_payment_details)}")
        
        # Verificar si se puede asignar a una venta
        from decimal import Decimal
        test_sale = Sale()
        test_sale.payment_method = 'cash + transfer'
        test_sale.payment_details = test_payment_details
        test_sale.subtotal = Decimal('75.00')
        test_sale.total = Decimal('75.00')
        
        print(f"   ✅ Asignación exitosa")
        print(f"   payment_details guardados: {test_sale.payment_details}")
        
except Exception as e:
    print(f"   ❌ Error en simulación: {e}")
    import traceback
    traceback.print_exc()

print()
print("4. 💡 ANÁLISIS DEL PROBLEMA:")
print()

# 4. Análisis del problema
print("   Posibles causas de errores en pagos combinados:")
print("   1. payment_details no se está guardando correctamente")
print("   2. Estructura de datos inválida al recibir del frontend")
print("   3. Error al procesar el JSON en el backend")
print("   4. Problemas con la serialización/deserialización")
print()

print("5. 🔧 RECOMENDACIONES:")
print("   • Revisar el console.log del navegador para ver qué se envía")
print("   • Verificar los logs del servidor Django")
print("   • Probar con diferentes combinaciones de métodos de pago")
print("   • Verificar que el JSON sea válido antes de procesarlo")

print()
print("=== FIN DE DIAGNÓSTICO ===")
