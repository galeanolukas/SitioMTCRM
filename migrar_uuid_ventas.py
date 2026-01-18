#!/usr/bin/env python3
"""
Migración para asignar UUID a ventas existentes sin UUID
"""
import os
import sys
import django

# Configurar Django
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django.setup()

from django.db import transaction
import uuid
from core.erp.models import Sale


def asignar_uuid_a_ventas_existentes():
    """
    Asigna UUID a todas las ventas existentes que no tienen
    """
    print("🔧 Asignando UUID a ventas existentes sin UUID...")
    
    with transaction.atomic():
        ventas_sin_uuid = Sale.objects.using('default').filter(
            local_uuid__isnull=True
        ).exclude(source='web')  # Excluir ventas web
        
        total = ventas_sin_uuid.count()
        
        if total == 0:
            print("✅ Todas las ventas ya tienen UUID")
            return 0
        
        print(f"📊 Se encontraron {total} ventas sin UUID")
        
        actualizadas = 0
        for venta in ventas_sin_uuid:
            venta.local_uuid = f"sale_{uuid.uuid4().hex}"
            venta.save(using='default')
            actualizadas += 1
            
            if actualizadas % 100 == 0:
                print(f"   Procesadas {actualizadas}/{total} ventas...")
        
        print(f"✅ Se asignaron UUID a {actualizadas} ventas")
        return actualizadas


def main():
    """
    Función principal
    """
    print("=" * 50)
    print("🔧 MIGRACIÓN: ASIGNAR UUID A VENTAS")
    print("=" * 50)
    print()
    
    try:
        actualizadas = asignar_uuid_a_ventas_existentes()
        print()
        print("=" * 50)
        print(f"✅ Migración completada: {actualizadas} ventas actualizadas")
        print("=" * 50)
        
        return 0
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
