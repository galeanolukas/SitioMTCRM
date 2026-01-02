#!/usr/bin/env python3
import os
import sys
import django

# Agregar el path del proyecto
sys.path.append('/media/lukas/ARCHIVOS/GitHub/SitioMTCRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Inicializar Django
django.setup()

from core.erp.models import Product

print("=== Verificación de sincronización de productos ===")

# 1. Verificar productos pendientes de sincronizar
pending = Product.objects.using('default').filter(synced_to_server=False).count()
print(f"Productos pendientes de sincronizar (local): {pending}")

# 2. Mostrar algunos productos pendientes
if pending > 0:
    print("\nProductos pendientes:")
    for p in Product.objects.using('default').filter(synced_to_server=False)[:5]:
        print(f"  - ID:{p.id} | {p.name} | Stock:{p.stock} | synced_to_server:{p.synced_to_server}")

# 3. Verificar si podemos conectar a la BD remota
try:
    from django.db import connections
    conn = connections['remote']
    conn.ensure_connection()
    print("\n✅ Conexión a BD remota: OK")
    
    # Verificar productos en servidor remoto
    remote_count = Product.objects.using('remote').count()
    print(f"Productos totales en servidor remoto: {remote_count}")
    
except Exception as e:
    print(f"\n❌ Error conectando a BD remota: {e}")

# 4. Probar manualmente marcar un producto para sincronizar
print("\n=== Prueba manual ===")
try:
    # Tomar el primer producto y cambiar su stock
    product = Product.objects.using('default').first()
    if product:
        old_stock = product.stock
        product.stock = old_stock + 1
        product.save()
        print(f"✅ Producto '{product.name}' actualizado: stock {old_stock} → {product.stock}")
        print(f"   synced_to_server: {product.synced_to_server}")
        
        # Verificar si quedó marcado para sincronizar
        updated = Product.objects.using('default').get(pk=product.pk)
        print(f"   synced_to_server después de save: {updated.synced_to_server}")
    else:
        print("❌ No hay productos para probar")
        
except Exception as e:
    print(f"❌ Error en prueba manual: {e}")

print("\n=== Fin de verificación ===")
