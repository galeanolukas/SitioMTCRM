#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.erp.models import Product

# Buscar y corregir los productos problemáticos
product_names = ['Menudencia', 'Molida', 'Cogote']
corrected_count = 0

print("Corrigiendo configuración de stock para productos...\n")

for name in product_names:
    products = Product.objects.filter(name__icontains=name)
    for p in products:
        print(f"Procesando: {p.name}")
        print(f"  - Stock actual: {p.stock}")
        print(f"  - Controlar stock ANTES: {p.track_stock}")
        
        if not p.track_stock:
            p.track_stock = True
            p.save()
            print(f"  - ✅ Corregido: Controlar stock AHORA: {p.track_stock}")
            corrected_count += 1
        else:
            print(f"  - ℹ️  Ya tenía control de stock activado")
        
        print("-" * 50)

print(f"\n✅ Se corrigieron {corrected_count} productos")
print("\nAhora estos productos deberían descontar stock correctamente en ventas por cuenta corriente.")
