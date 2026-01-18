#!/usr/bin/env python3
"""
Script para probar la sincronización de ventas y verificar duplicados
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
from django.db.models import Count, Q
from core.erp.models import Sale, DetSale, Company, Client, Product
from decimal import Decimal


def crear_venta_prueba():
    """
    Crea una venta de prueba para verificar sincronización
    """
    print("🧪 Creando venta de prueba...")
    
    try:
        with transaction.atomic(using='default'):
            # Obtener empresa y cliente de prueba
            company = Company.objects.using('default').first()
            client = Client.objects.using('default').first()
            product = Product.objects.using('default').first()
            
            if not all([company, client, product]):
                print("❌ No se encontraron datos de prueba (empresa, cliente, producto)")
                return None
            
            # Crear venta de prueba
            from core.erp.models import Sale
            import uuid
            
            sale = Sale.objects.using('default').create(
                company=company,
                cli=client,
                subtotal=Decimal('100.00'),
                iva=Decimal('21.00'),
                total=Decimal('121.00'),
                payment_method='cash',
                local_uuid=f"test_sale_{uuid.uuid4().hex}",
                source='test_sync',
                synced_to_server=False
            )
            
            # Crear detalle
            DetSale.objects.using('default').create(
                sale=sale,
                prod=product,
                price=Decimal('100.00'),
                cant=Decimal('1'),
                subtotal=Decimal('100.00')
            )
            
            print(f"✅ Venta de prueba creada: ID {sale.id}, UUID {sale.local_uuid}")
            return sale.id
            
    except Exception as e:
        print(f"❌ Error creando venta de prueba: {e}")
        return None


def verificar_venta_en_servidor(sale_id):
    """
    Verifica si una venta existe en el servidor
    """
    print(f"🔍 Verificando venta {sale_id} en servidor...")
    
    try:
        # Obtener venta local
        sale_local = Sale.objects.using('default').get(id=sale_id)
        
        # Buscar en servidor por UUID
        if sale_local.local_uuid:
            sale_remoto = Sale.objects.using('remote').filter(
                local_uuid=sale_local.local_uuid
            ).first()
            
            if sale_remoto:
                print(f"✅ Venta encontrada en servidor: ID {sale_remoto.id}")
                return True
            else:
                print("❌ Venta no encontrada en servidor")
                return False
        else:
            print("❌ Venta local no tiene UUID")
            return False
            
    except Exception as e:
        print(f"❌ Error verificando venta en servidor: {e}")
        return False


def verificar_duplicados_en_servidor():
    """
    Verifica si hay ventas duplicadas en el servidor
    """
    print("🔍 Buscando duplicados en servidor...")
    
    try:
        # Ventas con UUID en servidor
        ventas_con_uuid = Sale.objects.using('remote').exclude(
            local_uuid__isnull=True
        ).exclude(local_uuid__exact='')
        
        # Agrupar por UUID y contar
        duplicados = ventas_con_uuid.values('local_uuid').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if duplicados.exists():
            print(f"❌ Se encontraron {duplicados.count()} UUIDs duplicados:")
            for dup in duplicados:
                print(f"   UUID {dup['local_uuid']}: {dup['count']} copias")
            return False
        else:
            print("✅ No se encontraron duplicados en servidor")
            return True
            
    except Exception as e:
        print(f"❌ Error verificando duplicados: {e}")
        return False


def ejecutar_sincronizacion_manual():
    """
    Ejecuta sincronización manual de ventas
    """
    print("🔄 Ejecutando sincronización manual...")
    
    try:
        from django.core.management import call_command
        call_command('sync_sales_to_remote')
        print("✅ Sincronización completada")
        return True
        
    except Exception as e:
        print(f"❌ Error en sincronización: {e}")
        return False


def limpiar_venta_prueba(sale_id):
    """
    Elimina la venta de prueba
    """
    print(f"🗑️ Limpiando venta de prueba {sale_id}...")
    
    try:
        with transaction.atomic(using='default'):
            # Eliminar detalles
            DetSale.objects.using('default').filter(sale_id=sale_id).delete()
            
            # Eliminar venta
            Sale.objects.using('default').filter(id=sale_id).delete()
            
        with transaction.atomic(using='remote'):
            # Buscar y eliminar en servidor si existe
            sale_local = Sale.objects.using('default').filter(id=sale_id).first()
            if sale_local and sale_local.local_uuid:
                sale_remoto = Sale.objects.using('remote').filter(
                    local_uuid=sale_local.local_uuid
                ).first()
                if sale_remoto:
                    DetSale.objects.using('remote').filter(sale=sale_remoto).delete()
                    sale_remoto.delete()
                    print("✅ Venta eliminada también del servidor")
        
        print("✅ Venta de prueba eliminada")
        
    except Exception as e:
        print(f"❌ Error limpiando venta de prueba: {e}")


def main():
    """
    Función principal de prueba
    """
    print("=" * 60)
    print("🧪 PRUEBA DE SINCRONIZACIÓN DE VENTAS")
    print("=" * 60)
    print()
    
    venta_id = None
    
    try:
        # 1) Verificar estado actual
        print("1️⃣ Verificando estado actual...")
        verificar_duplicados_en_servidor()
        print()
        
        # 2) Crear venta de prueba
        print("2️⃣ Creando venta de prueba...")
        venta_id = crear_venta_prueba()
        if not venta_id:
            return 1
        print()
        
        # 3) Verificar que no existe en servidor
        print("3️⃣ Verificando que no existe en servidor...")
        verificar_venta_en_servidor(venta_id)
        print()
        
        # 4) Ejecutar sincronización
        print("4️⃣ Ejecutando sincronización...")
        if not ejecutar_sincronizacion_manual():
            return 1
        print()
        
        # 5) Verificar que ahora existe en servidor
        print("5️⃣ Verificando que existe en servidor...")
        if verificar_venta_en_servidor(venta_id):
            print("✅ Sincronización exitosa")
        else:
            print("❌ Sincronización fallida")
            return 1
        print()
        
        # 6) Verificar que no hay duplicados
        print("6️⃣ Verificando que no hay duplicados...")
        if verificar_duplicados_en_servidor():
            print("✅ No hay duplicados")
        else:
            print("❌ Se encontraron duplicados")
            return 1
        print()
        
        # 7) Sincronizar nuevamente (debería omitir)
        print("7️⃣ Sincronizando nuevamente (debería omitir)...")
        ejecutar_sincronizacion_manual()
        print()
        
        # 8) Verificar que sigue sin duplicados
        print("8️⃣ Verificando que sigue sin duplicados...")
        if verificar_duplicados_en_servidor():
            print("✅ No hay duplicados después de segunda sincronización")
        else:
            print("❌ Se crearon duplicados en segunda sincronización")
            return 1
        print()
        
        print("=" * 60)
        print("✅ PRUEBA COMPLETADA EXITOSAMENTE")
        print("✅ La sincronización funciona correctamente")
        print("✅ No se crean duplicados")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        # Limpiar siempre
        if venta_id:
            print()
            limpiar_venta_prueba(venta_id)


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
