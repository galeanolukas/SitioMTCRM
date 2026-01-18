#!/usr/bin/env python3
"""
Script para limpiar ventas duplicadas en el servidor y mejorar sincronización
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
from django.db.models import F
from core.erp.models import Sale, DetSale


def limpiar_ventas_duplicadas():
    """
    Elimina ventas duplicadas en el servidor remoto basándose en UUID local
    """
    print("🔍 Buscando ventas duplicadas en el servidor...")
    
    # Ventas en servidor que tienen UUID local
    ventas_con_uuid = Sale.objects.using('remote').exclude(local_uuid__isnull=True).exclude(local_uuid__exact='')
    
    duplicados = 0
    procesadas = set()
    
    for venta in ventas_con_uuid:
        if venta.local_uuid in procesadas:
            continue
            
        # Buscar duplicados por UUID
        duplicados_uuid = Sale.objects.using('remote').filter(
            local_uuid=venta.local_uuid
        ).exclude(id=venta.id)
        
        if duplicados_uuid.exists():
            # Mantener la más antigua (primer registro)
            venta_a_mantener = Sale.objects.using('remote').filter(
                local_uuid=venta.local_uuid
            ).order_by('id').first()
            
            # Eliminar las más nuevas
            ventas_a_eliminar = Sale.objects.using('remote').filter(
                local_uuid=venta.local_uuid
            ).exclude(id=venta_a_mantener.id)
            
            count = ventas_a_eliminar.count()
            if count > 0:
                print(f"   🗑️ Eliminando {count} duplicados del UUID {venta.local_uuid}")
                
                # Eliminar detalles primero
                for v_eliminar in ventas_a_eliminar:
                    DetSale.objects.using('remote').filter(sale=v_eliminar).delete()
                    v_eliminar.delete()
                
                duplicados += count
        
        procesadas.add(venta.local_uuid)
    
    print(f"✅ Se eliminaron {duplicados} ventas duplicadas")
    return duplicados


def corregir_ventas_sin_uuid():
    """
    Asigna UUID a ventas locales que no tienen
    """
    print("🔧 Corrigiendo ventas locales sin UUID...")
    
    import uuid
    
    ventas_sin_uuid = Sale.objects.using('default').filter(
        local_uuid__isnull=True
    ).exclude(source='web')  # Excluir ventas web
    
    count = 0
    for venta in ventas_sin_uuid:
        venta.local_uuid = f"sale_{uuid.uuid4().hex}"
        venta.save(using='default')
        count += 1
    
    print(f"✅ Se corrigieron {count} ventas sin UUID")
    return count


def marcar_ventas_pendientes():
    """
    Marca ventas que deben sincronizarse
    """
    print("📋 Marcando ventas pendientes de sincronización...")
    
    # Ventas locales no sincronizadas
    pendientes = Sale.objects.using('default').filter(
        synced_to_server=False
    ).exclude(source='web')
    
    count = pendientes.count()
    print(f"📊 Hay {count} ventas pendientes de sincronizar")
    return count


def verificar_integridad():
    """
    Verifica la integridad de los datos
    """
    print("🔍 Verificando integridad de datos...")
    
    problemas = []
    
    # 1) Ventas sin detalles
    from django.db.models import Count
    ventas_sin_detalles = Sale.objects.using('default').filter(
        synced_to_server=False
    ).annotate(
        num_detalles=Count('detsale')
    ).filter(num_detalles=0)
    
    if ventas_sin_detalles.exists():
        count = ventas_sin_detalles.count()
        problemas.append(f"Ventas sin detalles: {count}")
        print(f"   ⚠️ Se encontraron {count} ventas sin detalles")
    
    # 2) Ventas con totales inconsistentes
    ventas_inconsistentes = Sale.objects.using('default').filter(
        synced_to_server=False
    ).exclude(subtotal=F('total'))
    
    if ventas_inconsistentes.exists():
        count = ventas_inconsistentes.count()
        problemas.append(f"Ventas con totales inconsistentes: {count}")
        print(f"   ⚠️ Se encontraron {count} ventas con totales inconsistentes")
    
    if not problemas:
        print("✅ No se encontraron problemas de integridad")
    
    return problemas


def main():
    """
    Función principal
    """
    print("=" * 60)
    print("🔧 HERRAMIENTA DE MANTENIMIENTO DE VENTAS")
    print("=" * 60)
    print()
    
    try:
        with transaction.atomic(using='remote'):
            # 1) Limpiar ventas duplicadas
            duplicados = limpiar_ventas_duplicadas()
            print()
            
            # 2) Verificar integridad
            problemas = verificar_integridad()
            print()
            
        with transaction.atomic(using='default'):
            # 3) Corregir ventas sin UUID
            corregidas = corregir_ventas_sin_uuid()
            print()
            
            # 4) Marcar pendientes
            pendientes = marcar_ventas_pendientes()
            print()
        
        # Resumen
        print("=" * 60)
        print("📋 RESUMEN DE OPERACIONES")
        print("=" * 60)
        print(f"🗑️ Ventas duplicadas eliminadas: {duplicados}")
        print(f"🔧 Ventas sin UUID corregidas: {corregidas}")
        print(f"📊 Ventas pendientes de sincronizar: {pendientes}")
        print(f"⚠️ Problemas de integridad encontrados: {len(problemas)}")
        print()
        
        if duplicados > 0 or corregidas > 0:
            print("✅ Se recomienda reiniciar la sincronización automática")
            print("   para que los cambios se reflejen en el servidor.")
        else:
            print("✅ No se requieren acciones adicionales")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error durante el proceso: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
