#!/usr/bin/env python3
"""
Script para activar modo servidor - versión simplificada sin Django.

"""

import os
import sys

def check_current_env():
    """Verificar configuración actual."""
    print("🔍 VERIFICACIÓN ACTUAL")
    print("=" * 50)
    
    env_file = '.env'
    if os.path.exists(env_file):
        print(f"✅ Archivo .env encontrado: {env_file}")
        
        # Leer variables actuales
        with open(env_file, 'r') as f:
            content = f.read()
            
        environment = 'development'  # default
        for line in content.split('\n'):
            if line.startswith('ENVIRONMENT='):
                environment = line.split('=', 1)[1]
                break
            elif line.startswith('ENV='):  # compatibilidad con .env.example
                environment = line.split('=', 1)[1]
                break
        
        print(f"📍 ENVIRONMENT actual: {environment}")
        print(f"📍 Modo servidor: {'SÍ' if environment == 'production' else 'NO'}")
        
    else:
        print("❌ No se encuentra archivo .env")
        print("📝 Se usará .env.server como plantilla")
    
    return environment

def activate_server_mode():
    """Activar modo servidor."""
    print("\n🚀 ACTIVANDO MODO SERVIDOR")
    print("=" * 50)
    
    env_file = '.env'
    server_template = '.env.server'
    
    # Si no existe .env, crear desde plantilla
    if not os.path.exists(env_file):
        if os.path.exists(server_template):
            print("📋 Creando .env desde plantilla .env.server")
            with open(server_template, 'r') as f:
                content = f.read()
            with open(env_file, 'w') as f:
                f.write(content)
            print("✅ Archivo .env creado")
            print("⚠️  DEBES EDITAR LAS CREDENCIALES DE BASE DE DATOS")
        else:
            print("❌ No hay plantilla .env.server")
            return False
    else:
        # Modificar .env existente
        print("📝 Modificando .env existente")
        
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        modified = False
        new_lines = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('ENVIRONMENT='):
                new_lines.append('ENVIRONMENT=production\n')
                modified = True
                print("✅ ENVIRONMENT cambiado a production")
            elif line.startswith('ENV='):
                new_lines.append('ENV=production\n')
                modified = True
                print("✅ ENV cambiado a production")
            elif line.startswith('DEBUG='):
                new_lines.append('DEBUG=False\n')
                modified = True
                print("✅ DEBUG cambiado a False")
            else:
                new_lines.append(line + '\n')
        
        # Si no tenía ENVIRONMENT, agregarlo
        if not any(line.startswith('ENVIRONMENT=') for line in new_lines):
            new_lines.insert(0, 'ENVIRONMENT=production\n')
            modified = True
            print("✅ ENVIRONMENT=production agregado")
        
        if modified:
            with open(env_file, 'w') as f:
                f.writelines(new_lines)
            print("✅ Archivo .env actualizado")
        else:
            print("ℹ️  El archivo ya estaba configurado")
    
    return True

def show_next_steps():
    """Mostrar próximos pasos."""
    print("\n📋 PRÓXIMOS PASOS")
    print("=" * 50)
    
    print("1. 📝 EDITAR CREDENCIALES:")
    print("   Abre el archivo .env y configura:")
    print("   - DB_NAME, DB_USER, DB_PASSWORD, DB_HOST (BD local)")
    print("   - REMOTE_DB_NAME, REMOTE_DB_USER, etc. (BD remota)")
    print("   - SECRET_KEY (¡genera una nueva!)")
    print("   - ALLOWED_HOSTS (tu dominio)")
    
    print("\n2. 🗄️  CREAR BASES DE DATOS:")
    print("   - Base de datos local para el servidor")
    print("   - Base de datos remota para sincronización")
    
    print("\n3. 🔄 EJECUTAR MIGRACIONES:")
    print("   python3 manage.py makemigrations")
    print("   python3 manage.py migrate")
    
    print("\n4. 🚀 INICIAR SERVIDOR:")
    print("   python3 manage.py runserver 0.0.0.0:8000")
    
    print("\n5. ✅ VERIFICAR:")
    print("   python3 check_server_mode.py")
    
    print("\n🎯 Una vez configurado:")
    print("- Importa productos desde Excel/CSV")
    print("- Se sincronizarán automáticamente")
    print("- Usa /erp/sync/products/ para sincronización manual")

def generate_secret_key():
    """Generar clave secreta."""
    import secrets
    return secrets.token_urlsafe(50)

def main():
    """Función principal."""
    print("🔧 ACTIVADOR DE MODO SERVIDOR")
    print("=" * 60)
    
    # Verificar estado actual
    current_env = check_current_env()
    
    if current_env == 'production':
        print("\n✅ Ya está en modo servidor")
        show_next_steps()
        return
    
    # Preguntar si desea activar
    response = input("\n¿Deseas activar modo servidor? (s/N): ").lower().strip()
    
    if response in ['s', 'si', 'sí', 'y', 'yes']:
        if activate_server_mode():
            print("\n🎉 ¡MODO SERVIDOR ACTIVADO!")
            print("\n🔑 Clave secreta generada:")
            print(f"SECRET_KEY={generate_secret_key()}")
            print(f"DJANGO_SECRET_KEY={generate_secret_key()}")
            show_next_steps()
        else:
            print("\n❌ Error activando modo servidor")
    else:
        print("\n❌ Operación cancelada")

if __name__ == '__main__':
    main()
