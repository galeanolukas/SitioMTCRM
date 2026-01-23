#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.erp.models import Product

# Buscar los productos problemáticos
product_names = ['Menudencia', 'Molida', 'Cogote']
found_products = []

for name in product_names:
    products = Product.objects.filter(name__icontains=name)
    for p in products:
        found_products.append(p)
        print(f"ID: {p.id}")
        print(f"Nombre: {p.name}")
        print(f"Stock actual: {p.stock}")
        print(f"Controlar stock: {p.track_stock}")
        print(f"Unidad: {p.unit}")
        print(f"Precio: ${p.pvp}")
        print("-" * 50)

if not found_products:
    print("No se encontraron productos con esos nombres")
else:
    print(f"\nSe encontraron {len(found_products)} productos")
    
    # Preguntar si desea corregir
    print("\nPara corregir el problema de stock, ejecute:")
    print("python3 corregir_stock_products.py")
