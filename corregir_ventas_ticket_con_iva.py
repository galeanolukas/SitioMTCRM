#!/usr/bin/env python
"""
Script para corregir ventas registradas incorrectamente con IVA cuando deberían ser tickets (sin IVA).

Este script identifica ventas que:
1. No tienen número de factura (invoice_number es NULL o vacío)
2. Tienen IVA mayor a 0
3. Corrige: IVA = 0 y Total = Subtotal
"""

import os
import sys
import django

# Configurar entorno Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from django.utils import timezone
from datetime import datetime
from core.erp.models import Sale

def corregir_ventas_ticket_con_iva():
    """
    Corrige ventas que fueron registradas como tickets pero tienen IVA incorrectamente.
    Solo corrige ventas desde el 15/01/2026.
    """
    print("🔍 Buscando ventas con errores de IVA en tickets desde 15/01/2026...")
    
    # Definir fecha límite (15/01/2026)
    fecha_limite = datetime(2026, 1, 15, 0, 0, 0)
    
    # Buscar ventas que no tienen factura (invoice_number es NULL o vacío) pero tienen IVA > 0
    # y que sean desde el 15/01/2026
    ventas_a_corregir = Sale.objects.filter(
        invoice_number__isnull=True
    ).filter(
        iva__gt=0
    ).filter(
        date_joined__gte=fecha_limite
    ).order_by('-date_joined')
    
    total_ventas = ventas_a_corregir.count()
    
    if total_ventas == 0:
        print("✅ No se encontraron ventas con errores de IVA en tickets.")
        return
    
    print(f"📊 Se encontraron {total_ventas} ventas para corregir:")
    print("-" * 80)
    
    # Mostrar detalles de las ventas a corregir
    for i, venta in enumerate(ventas_a_corregir, 1):
        print(f"{i:3d}. Venta #{venta.id:5d} | Fecha: {venta.date_joined.strftime('%d-%m-%Y %H:%M')} | "
              f"Cliente: {venta.cli.names if venta.cli else 'Anónimo'}")
        print(f"     Subtotal: ${venta.subtotal:10.2f} | IVA: ${venta.iva:10.2f} | "
              f"Total: ${venta.total:10.2f} | Método: {venta.get_payment_method_display()}")
    
    print("-" * 80)
    
    # Confirmación del usuario
    confirmacion = input(f"\n⚠️  ¿Desea corregir estas {total_ventas} ventas? (S/N): ").strip().upper()
    
    if confirmacion != 'S':
        print("❌ Operación cancelada.")
        return
    
    print("\n🔧 Corrigiendo ventas...")
    
    try:
        with transaction.atomic():
            corregidas = 0
            for venta in ventas_a_corregir:
                # Guardar valores originales para mostrar
                subtotal_original = venta.subtotal
                iva_original = venta.iva
                total_original = venta.total
                
                # Corregir valores
                venta.iva = 0.0
                venta.total = venta.subtotal
                venta.save()
                
                corregidas += 1
                print(f"✅ Venta #{venta.id:5d} corregida: "
                      f"IVA ${iva_original:.2f}→$0.00 | "
                      f"Total ${total_original:.2f}→${venta.total:.2f}")
            
            print(f"\n🎉 Se corrigieron exitosamente {corregidas} ventas.")
            
    except Exception as e:
        print(f"❌ Error durante la corrección: {str(e)}")
        print("💡 No se aplicaron cambios. Revise el error e intente nuevamente.")

def backup_ventas_a_corregir():
    """
    Crea un backup de las ventas que serán corregidas.
    Solo incluye ventas desde el 15/01/2026.
    """
    print("💾 Creando backup de ventas a corregir desde 15/01/2026...")
    
    # Definir fecha límite (15/01/2026)
    fecha_limite = datetime(2026, 1, 15, 0, 0, 0)
    
    ventas_a_corregir = Sale.objects.filter(
        invoice_number__isnull=True
    ).filter(
        iva__gt=0
    ).filter(
        date_joined__gte=fecha_limite
    ).order_by('-date_joined')
    
    if ventas_a_corregir.count() == 0:
        print("✅ No hay ventas para respaldar.")
        return
    
    backup_file = f"backup_ventas_con_iva_erroneo_{django.utils.timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write("id,date_joined,client,subtotal,iva,total,payment_method\n")
            for venta in ventas_a_corregir:
                cliente = venta.cli.names if venta.cli else 'Anónimo'
                f.write(f"{venta.id},"
                       f"{venta.date_joined.strftime('%Y-%m-%d %H:%M:%S')},"
                       f"\"{cliente}\","
                       f"{venta.subtotal},"
                       f"{venta.iva},"
                       f"{venta.total},"
                       f"{venta.payment_method}\n")
        
        print(f"✅ Backup creado: {backup_file}")
        
    except Exception as e:
        print(f"❌ Error creando backup: {str(e)}")

def main():
    """
    Función principal del script.
    """
    print("=" * 80)
    print("🔧 SCRIPT DE CORRECCIÓN DE VENTAS CON IVA ERRÓNEO")
    print("=" * 80)
    print("\nEste script corrige ventas que fueron registradas como tickets")
    print("pero incorrectamente incluyen IVA en el total.")
    print("\n⚠️  SOLO CORRIGE VENTAS DESDE EL 15/01/2026")
    print("\nLas ventas afectadas cumplieron:")
    print("• Fecha >= 15/01/2026")
    print("• No tienen número de factura (son tickets)")
    print("• Tienen IVA mayor a 0 (debería ser 0)")
    print("• El total incluye IVA (debería ser solo subtotal)")
    print("=" * 80)
    
    # Crear backup primero
    backup_ventas_a_corregir()
    
    print()
    
    # Corregir ventas
    corregir_ventas_ticket_con_iva()
    
    print("\n" + "=" * 80)
    print("🏁 Proceso finalizado")
    print("=" * 80)

if __name__ == "__main__":
    main()
