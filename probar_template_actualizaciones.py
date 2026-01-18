#!/usr/bin/env python3
"""
Script para probar la página de actualizaciones con diferentes SO
"""
import os
import sys
import django

# Configurar Django
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from core.erp.views.dashboard.views import UpdatesView


def probar_template_actualizaciones():
    """
    Prueba el template de actualizaciones con diferentes SO
    """
    print("🧪 PROBANDO TEMPLATE DE ACTUALIZACIONES")
    print("=" * 50)
    
    factory = RequestFactory()
    view = UpdatesView()
    
    # Simular diferentes sistemas operativos
    sistemas = [
        ('Windows', 'windows'),
        ('Linux', 'linux'), 
        ('macOS', 'darwin'),
        ('Desconocido', 'unknown')
    ]
    
    for nombre, so in sistemas:
        print(f"\n📱 Probando SO: {nombre}")
        print("-" * 30)
        
        # Crear request simulado
        request = factory.get('/erp/updates/')
        request.user = AnonymousUser()
        
        # Mockear platform.system
        import platform
        original_system = platform.system
        platform.system = lambda: so.upper()
        
        try:
            # Ejecutar la vista
            response = view.get(request)
            
            # Verificar contexto
            context = response.context_data
            
            print(f"  is_windows: {context.get('is_windows', False)}")
            print(f"  is_linux: {context.get('is_linux', False)}")
            print(f"  is_mac: {context.get('is_mac', False)}")
            
            # Verificar que el template se renderizó
            if response.status_code == 200:
                print(f"  ✅ Template renderizado correctamente")
            else:
                print(f"  ❌ Error en template: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
        finally:
            # Restaurar platform.system
            platform.system = original_system
    
    print("\n" + "=" * 50)
    print("✅ PRUEBA COMPLETADA")
    print("=" * 50)


def main():
    """
    Función principal
    """
    try:
        probar_template_actualizaciones()
        return 0
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
