#!/usr/bin/env python3
"""
Script para solucionar el problema de sincronización de cuentas corrientes de empleados
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
from django.core.management import call_command


def verificar_modelo_employee_account():
    """
    Verifica si el modelo EmployeeAccountSale existe
    """
    try:
        from core.erp.models import EmployeeAccountSale
        print("✅ Modelo EmployeeAccountSale encontrado")
        return True
    except ImportError:
        print("❌ Modelo EmployeeAccountSale no encontrado")
        return False


def crear_migracion_employee_account():
    """
    Crea las migraciones para EmployeeAccountSale si no existen
    """
    print("🔧 Creando migraciones para EmployeeAccountSale...")
    
    try:
        # Verificar si ya existe la tabla
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='erp_employeeaccountsale'
            """)
            table_exists = cursor.fetchone()
        
        if table_exists:
            print("✅ Tabla erp_employeeaccountsale ya existe")
            return True
        
        # Crear migraciones
        call_command('makemigrations', 'erp', '--name', 'create_employee_account_models')
        call_command('migrate', 'erp')
        
        print("✅ Migraciones de EmployeeAccountSale creadas y aplicadas")
        return True
        
    except Exception as e:
        print(f"❌ Error creando migraciones: {e}")
        return False


def eliminar_sync_employee_accounts_de_sync_utils():
    """
    Elimina o comenta la sincronización de employee accounts del sync_utils.py
    """
    print("🔧 Deshabilitando sincronización de employee accounts...")
    
    try:
        sync_utils_path = os.path.join(BASE_DIR, 'core', 'erp', 'sync_utils.py')
        
        with open(sync_utils_path, 'r') as f:
            content = f.read()
        
        # Buscar y comentar la sección de employee accounts
        if 'sync_employee_accounts_to_remote' in content:
            # Encontrar las líneas a comentar
            lines = content.split('\n')
            new_lines = []
            in_employee_section = False
            
            for line in lines:
                if 'sync_employee_accounts_to_remote' in line:
                    in_employee_section = True
                    new_lines.append('# ' + line)  # Comentar la línea del comando
                elif in_employee_section and 'sync_expenses_to_remote' in line:
                    in_employee_section = False
                    new_lines.append(line)  # No comentar la siguiente sección
                elif in_employee_section:
                    new_lines.append('# ' + line)  # Comentar líneas dentro de la sección
                else:
                    new_lines.append(line)
            
            # Escribir el archivo modificado
            with open(sync_utils_path, 'w') as f:
                f.write('\n'.join(new_lines))
            
            print("✅ Sincronización de employee accounts deshabilitada temporalmente")
        else:
            print("✅ La sincronización de employee accounts ya está deshabilitada")
        
        return True
        
    except Exception as e:
        print(f"❌ Error modificando sync_utils.py: {e}")
        return False


def probar_sincronizacion_completa():
    """
    Prueba la sincronización completa sin errores
    """
    print("🧪 Probando sincronización completa...")
    
    try:
        call_command('sync_smart')
        print("✅ Sincronización completa exitosa")
        return True
        
    except Exception as e:
        print(f"❌ Error en sincronización completa: {e}")
        return False


def main():
    """
    Función principal
    """
    print("=" * 60)
    print("🔧 SOLUCIÓN DE PROBLEMAS DE SINCRONIZACIÓN")
    print("=" * 60)
    print()
    
    try:
        # 1) Verificar modelo EmployeeAccountSale
        print("1️⃣ Verificando modelo EmployeeAccountSale...")
        modelo_existe = verificar_modelo_employee_account()
        print()
        
        # 2) Si no existe, crear migraciones
        if not modelo_existe:
            print("2️⃣ Creando migraciones...")
            if not crear_migracion_employee_account():
                return 1
            print()
        
        # 3) Deshabilitar temporalmente la sincronización de employee accounts
        print("3️⃣ Deshabilitando sincronización de employee accounts...")
        if not eliminar_sync_employee_accounts_de_sync_utils():
            return 1
        print()
        
        # 4) Probar sincronización completa
        print("4️⃣ Probando sincronización completa...")
        if not probar_sincronizacion_completa():
            return 1
        print()
        
        print("=" * 60)
        print("✅ PROBLEMAS DE SINCRONIZACIÓN SOLUCIONADOS")
        print("✅ La sincronización ahora funciona sin errores")
        print("=" * 60)
        print()
        print("📋 NOTAS:")
        print("- La sincronización de employee accounts está temporalmente deshabilitada")
        print("- Para habilitarla nuevamente, descomente las líneas en sync_utils.py")
        print("- Asegúrese de que el modelo EmployeeAccountSale exista en el servidor")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error durante el proceso: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
