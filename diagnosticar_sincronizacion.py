#!/usr/bin/env python3
"""
Script simple para probar sincronización sin dependencias
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
from django.utils import timezone
from django.db.models import Count
from core.erp.models import Sale, DetSale
from decimal import Decimal
import uuid


def verificar_estado_actual():
    """
    Verifica el estado actual de ventas y sincronización
    """
    print("📊 ESTADO ACTUAL DEL SISTEMA")
    print("-" * 40)
    
    # Ventas locales
    ventas_locales = Sale.objects.using('default').all()
    print(f"Ventas locales totales: {ventas_locales.count()}")
    print(f"Ventas sin sincronizar: {ventas_locales.filter(synced_to_server=False).count()}")
    print(f"Ventas con UUID: {ventas_locales.exclude(local_uuid__isnull=True).exclude(local_uuid__exact='').count()}")
    
    # Ventas en servidor
    try:
        ventas_servidor = Sale.objects.using('remote').all()
        print(f"Ventas en servidor: {ventas_servidor.count()}")
        print(f"Ventas con UUID en servidor: {ventas_servidor.exclude(local_uuid__isnull=True).exclude(local_uuid__exact='').count()}")
        
        # Verificar duplicados
        duplicados = ventas_servidor.exclude(
            local_uuid__isnull=True
        ).exclude(local_uuid__exact='').values('local_uuid').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if duplicados.exists():
            print(f"⚠️ DUPLICADOS ENCONTRADOS: {duplicados.count()} UUIDs")
            for dup in duplicados:
                print(f"   UUID {dup['local_uuid']}: {dup['count']} copias")
        else:
            print("✅ No hay duplicados en servidor")
            
    except Exception as e:
        print(f"❌ Error accediendo al servidor: {e}")
    
    print()


def simular_sincronizacion():
    """
    Simula el proceso de sincronización
    """
    print("🔄 SIMULANDO SINCRONIZACIÓN")
    print("-" * 40)
    
    # Ventas pendientes
    pendientes = Sale.objects.using('default').filter(
        synced_to_server=False
    ).exclude(local_uuid__isnull=True).exclude(local_uuid__exact='')
    
    print(f"Ventas pendientes de sincronizar: {pendientes.count()}")
    
    if pendientes.exists():
        print("Primeras 5 ventas pendientes:")
        for venta in pendientes[:5]:
            print(f"  ID: {venta.id}, UUID: {venta.local_uuid[:20]}..., Total: ${venta.total}")
        
        # Verificar si ya existen en servidor
        print("\nVerificando si ya existen en servidor...")
        ya_existentes = 0
        for venta in pendientes:
            try:
                existe = Sale.objects.using('remote').filter(
                    local_uuid=venta.local_uuid
                ).exists()
                if existe:
                    ya_existentes += 1
            except:
                pass
        
        print(f"Ventas que ya existen en servidor: {ya_existentes}")
        print(f"Ventas nuevas para sincronizar: {pendientes.count() - ya_existentes}")
    else:
        print("✅ No hay ventas pendientes de sincronizar")
    
    print()


def probar_creacion_uuid():
    """
    Prueba la creación de UUID para ventas sin UUID
    """
    print("🧪 PROBANDO CREACIÓN DE UUID")
    print("-" * 40)
    
    # Ventas sin UUID
    sin_uuid = Sale.objects.using('default').filter(
        local_uuid__isnull=True
    ).exclude(source='web')
    
    print(f"Ventas sin UUID: {sin_uuid.count()}")
    
    if sin_uuid.exists():
        print("Asignando UUID a primeras 3 ventas...")
        for venta in sin_uuid[:3]:
            venta.local_uuid = f"sale_{uuid.uuid4().hex}"
            venta.save()
            print(f"  ID {venta.id}: UUID asignado {venta.local_uuid[:20]}...")
    
    print()


def main():
    """
    Función principal
    """
    print("=" * 60)
    print("🔧 HERRAMIENTA DE DIAGNÓSTICO DE SINCRONIZACIÓN")
    print("=" * 60)
    print()
    
    try:
        # 1) Verificar estado actual
        verificar_estado_actual()
        
        # 2) Probar creación de UUID
        probar_creacion_uuid()
        
        # 3) Simular sincronización
        simular_sincronizacion()
        
        print("=" * 60)
        print("✅ DIAGNÓSTICO COMPLETADO")
        print("=" * 60)
        
        # Recomendaciones
        print("\n📋 RECOMENDACIONES:")
        print("1. Si hay ventas sin UUID, ejecutar: python migrar_uuid_ventas.py")
        print("2. Si hay duplicados, ejecutar: python limpiar_ventas_duplicadas.py")
        print("3. Para sincronizar manualmente: python manage.py sync_sales_to_remote")
        print("4. Para sincronización completa: python manage.py sync_smart")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error durante el diagnóstico: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
