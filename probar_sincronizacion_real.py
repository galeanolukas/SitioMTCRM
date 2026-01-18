#!/usr/bin/env python3
"""
Script para probar sincronización marcando ventas como pendientes
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


def marcar_ventas_para_prueba():
    """
    Marca algunas ventas como no sincronizadas para prueba
    """
    print("🧪 MARCANDO VENTAS PARA PRUEBA")
    print("-" * 40)
    
    # Obtener ventas ya sincronizadas con UUID
    ventas_sincronizadas = Sale.objects.using('default').filter(
        synced_to_server=True,
        local_uuid__isnull=False
    ).exclude(local_uuid__exact='')
    
    print(f"Ventas sincronizadas disponibles: {ventas_sincronizadas.count()}")
    
    if ventas_sincronizadas.count() < 3:
        print("❌ No hay suficientes ventas sincronizadas para la prueba")
        return []
    
    # Marcar 3 ventas como no sincronizadas
    ventas_prueba = ventas_sincronizadas[:3]
    ids_prueba = []
    
    for venta in ventas_prueba:
        venta.synced_to_server = False
        venta.save()
        ids_prueba.append(venta.id)
        print(f"  Venta {venta.id} marcada como pendiente (UUID: {venta.local_uuid[:20]}...)")
    
    print(f"✅ Marcadas {len(ids_prueba)} ventas para prueba")
    return ids_prueba


def ejecutar_sincronizacion_y_verificar():
    """
    Ejecuta sincronización y verifica resultados
    """
    print("\n🔄 EJECUTANDO SINCRONIZACIÓN")
    print("-" * 40)
    
    try:
        from django.core.management import call_command
        
        # Ejecutar sincronización de ventas
        print("Ejecutando sync_sales_to_remote...")
        call_command('sync_sales_to_remote')
        
        # Verificar resultados
        print("\n📊 VERIFICANDO RESULTADOS")
        print("-" * 40)
        
        pendientes = Sale.objects.using('default').filter(synced_to_server=False)
        print(f"Ventas pendientes después de sincronización: {pendientes.count()}")
        
        # Verificar duplicados
        try:
            ventas_servidor = Sale.objects.using('remote').exclude(
                local_uuid__isnull=True
            ).exclude(local_uuid__exact='')
            
            duplicados = ventas_servidor.values('local_uuid').annotate(
                count=Count('id')
            ).filter(count__gt=1)
            
            if duplicados.exists():
                print(f"❌ DUPLICADOS ENCONTRADOS: {duplicados.count()}")
                for dup in duplicados:
                    print(f"   UUID {dup['local_uuid']}: {dup['count']} copias")
                return False
            else:
                print("✅ No se crearon duplicados")
                return True
                
        except Exception as e:
            print(f"❌ Error verificando duplicados: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error en sincronización: {e}")
        return False


def restaurar_estado_original(ids_prueba):
    """
    Restaura las ventas de prueba a su estado original
    """
    print(f"\n🔄 RESTAURANDO ESTADO ORIGINAL")
    print("-" * 40)
    
    for venta_id in ids_prueba:
        try:
            venta = Sale.objects.using('default').get(id=venta_id)
            venta.synced_to_server = True
            venta.save()
            print(f"  Venta {venta_id} restaurada como sincronizada")
        except Exception as e:
            print(f"❌ Error restaurando venta {venta_id}: {e}")
    
    print("✅ Estado original restaurado")


def main():
    """
    Función principal
    """
    print("=" * 60)
    print("🧪 PRUEBA DE SINCRONIZACIÓN REAL")
    print("=" * 60)
    print()
    
    ids_prueba = []
    
    try:
        # 1) Marcar ventas para prueba
        ids_prueba = marcar_ventas_para_prueba()
        
        if not ids_prueba:
            print("❌ No se pudo realizar la prueba")
            return 1
        
        # 2) Ejecutar sincronización y verificar
        exito = ejecutar_sincronizacion_y_verificar()
        
        if exito:
            print("\n" + "=" * 60)
            print("✅ PRUEBA EXITOSA")
            print("✅ La sincronización funciona correctamente")
            print("✅ No se crean duplicados")
            print("=" * 60)
            resultado = 0
        else:
            print("\n" + "=" * 60)
            print("❌ PRUEBA FALLIDA")
            print("❌ Se encontraron problemas en la sincronización")
            print("=" * 60)
            resultado = 1
        
        return resultado
        
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        # Siempre restaurar estado original
        if ids_prueba:
            restaurar_estado_original(ids_prueba)


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
