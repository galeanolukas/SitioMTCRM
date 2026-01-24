#!/usr/bin/env python3
"""
Script para probar la funcionalidad de pvp_final automático vs manual
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    print("Asegúrate de estar en el entorno virtual: source venv/bin/activate")
    sys.exit(1)

from decimal import Decimal
from core.erp.models import Product, Category

def test_pvp_final_logic():
    print("=== Prueba de lógica de pvp_final ===\n")
    
    # Obtener o crear una categoría de prueba
    cat, created = Category.objects.get_or_create(
        name="Categoría Prueba",
        defaults={'desc': 'Categoría para pruebas de pvp_final'}
    )
    
    print("1. Prueba: Producto nuevo con pvp_final vacío (debe calcular automáticamente)")
    try:
        product1 = Product.objects.create(
            name="Producto Prueba Auto",
            code="TEST001",
            cat=cat,
            pvp=Decimal('100.00'),
            iva_rate=Decimal('0.21'),
            stock=Decimal('10.00'),
            pvp_final=Decimal('0.00')  # Vacío/0
        )
        
        expected_final = Decimal('121.00')  # 100 * (1 + 0.21)
        print(f"   PVP: {product1.pvp}")
        print(f"   IVA: {product1.iva_rate}")
        print(f"   PVP Final guardado: {product1.pvp_final}")
        print(f"   PVP Final esperado: {expected_final}")
        print(f"   ✓ Correcto: {product1.pvp_final == expected_final}")
        product1.delete()
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n2. Prueba: Producto nuevo con pvp_final manual (debe conservar el valor)")
    try:
        product2 = Product.objects.create(
            name="Producto Prueba Manual",
            code="TEST002",
            cat=cat,
            pvp=Decimal('100.00'),
            iva_rate=Decimal('0.21'),
            stock=Decimal('10.00'),
            pvp_final=Decimal('150.00')  # Valor manual
        )
        
        print(f"   PVP: {product2.pvp}")
        print(f"   IVA: {product2.iva_rate}")
        print(f"   PVP Final guardado: {product2.pvp_final}")
        print(f"   PVP Final esperado: 150.00 (valor manual)")
        print(f"   ✓ Correcto: {product2.pvp_final == Decimal('150.00')}")
        product2.delete()
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n3. Prueba: Actualización con pvp_final vacío (debe calcular)")
    try:
        product3 = Product.objects.create(
            name="Producto Prueba Update",
            code="TEST003",
            cat=cat,
            pvp=Decimal('50.00'),
            iva_rate=Decimal('0.10'),
            stock=Decimal('5.00'),
            pvp_final=Decimal('55.00')
        )
        
        print(f"   Antes - PVP Final: {product3.pvp_final}")
        
        # Actualizar dejando pvp_final en 0
        product3.pvp = Decimal('100.00')
        product3.pvp_final = Decimal('0.00')
        product3.save()
        
        expected_final = Decimal('110.00')  # 100 * (1 + 0.10)
        print(f"   Después - PVP: {product3.pvp}")
        print(f"   Después - PVP Final: {product3.pvp_final}")
        print(f"   PVP Final esperado: {expected_final}")
        print(f"   ✓ Correcto: {product3.pvp_final == expected_final}")
        product3.delete()
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n4. Prueba: Actualización con pvp_final manual (debe conservar)")
    try:
        product4 = Product.objects.create(
            name="Producto Prueba Update Manual",
            code="TEST004",
            cat=cat,
            pvp=Decimal('50.00'),
            iva_rate=Decimal('0.10'),
            stock=Decimal('5.00'),
            pvp_final=Decimal('55.00')
        )
        
        print(f"   Antes - PVP Final: {product4.pvp_final}")
        
        # Actualizar manteniendo pvp_final manual
        product4.pvp = Decimal('100.00')
        product4.pvp_final = Decimal('200.00')  # Nuevo valor manual
        product4.save()
        
        print(f"   Después - PVP: {product4.pvp}")
        print(f"   Después - PVP Final: {product4.pvp_final}")
        print(f"   PVP Final esperado: 200.00 (valor manual)")
        print(f"   ✓ Correcto: {product4.pvp_final == Decimal('200.00')}")
        product4.delete()
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n=== Prueba completada ===")

if __name__ == '__main__':
    test_pvp_final_logic()
