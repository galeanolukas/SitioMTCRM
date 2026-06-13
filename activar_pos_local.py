#!/usr/bin/env python3
"""
Script para activar modo POS LOCAL - versión simplificada sin Django.

"""

import os
import sys
from borrar_migrations import borrar_migraciones_y_db

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
            
        environment = 'production'  # default
        for line in content.split('\n'):
            if line.startswith('ENVIRONMENT='):
                environment = line.split('=', 1)[1]
                break
            elif line.startswith('ENV='):  # compatibilidad con .env.example
                environment = line.split('=', 1)[1]
                break
        
        print(f"📍 ENVIRONMENT actual: {environment}")
        print(f"📍 Modo POS LOCAL: {'SÍ' if environment == 'development' else 'NO'}")
        
    else:
        print("❌ No se encuentra archivo .env")
        print("📝 Se usará .env.example como plantilla")
    
    return environment

def activate_pos_local_mode():
    """Activar modo POS LOCAL."""
    print("\n🏪 ACTIVANDO MODO POS LOCAL")
    print("=" * 50)
    
    env_file = '.env'
    local_template = '.env.example'
    
    # Si no existe .env, crear desde plantilla
    if not os.path.exists(env_file):
        if os.path.exists(local_template):
            print("📋 Creando .env desde plantilla .env.example")
            with open(local_template, 'r') as f:
                content = f.read()
            with open(env_file, 'w') as f:
                f.write(content)
            print("✅ Archivo .env creado")
            print("⚠️  DEBES EDITAR LAS CREDENCIALES DE BASE DE DATOS")
        else:
            print("❌ No hay plantilla .env.example")
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
                new_lines.append('ENVIRONMENT=development\n')
                modified = True
                print("✅ ENVIRONMENT cambiado a development")
            elif line.startswith('ENV='):
                new_lines.append('ENV=development\n')
                modified = True
                print("✅ ENV cambiado a development")
            elif line.startswith('DEBUG='):
                new_lines.append('DEBUG=True\n')
                modified = True
                print("✅ DEBUG cambiado a True")
            elif line.startswith('DB_NAME='):
                new_lines.append('DB_NAME=db.sqlite3\n')
                modified = True
                print("✅ DB_NAME cambiado a db.sqlite3 (SQLite)")
            elif line.startswith('DB_HOST='):
                new_lines.append('DB_HOST=\n')
                modified = True
                print("✅ DB_HOST vaciado (SQLite)")
            elif line.startswith('DB_PORT='):
                new_lines.append('DB_PORT=\n')
                modified = True
                print("✅ DB_PORT vaciado (SQLite)")
            elif line.startswith('DB_USER='):
                new_lines.append('DB_USER=\n')
                modified = True
                print("✅ DB_USER vaciado (SQLite)")
            elif line.startswith('DB_PASSWORD='):
                new_lines.append('DB_PASSWORD=\n')
                modified = True
                print("✅ DB_PASSWORD vaciado (SQLite)")
            elif line.startswith('REMOTE_DB_NAME='):
                new_lines.append('REMOTE_DB_NAME=gayozolibreria\n')
                modified = True
                print("✅ REMOTE_DB_NAME configurado")
            elif line.startswith('REMOTE_DB_USER='):
                new_lines.append('REMOTE_DB_USER=gallozo_admin\n')
                modified = True
                print("✅ REMOTE_DB_USER configurado")
            elif line.startswith('REMOTE_DB_PASSWORD='):
                new_lines.append('REMOTE_DB_PASSWORD=g4ll0z0lib$\n')
                modified = True
                print("✅ REMOTE_DB_PASSWORD configurado")
            elif line.startswith('REMOTE_DB_HOST='):
                new_lines.append('REMOTE_DB_HOST=www.multilideres.com\n')
                modified = True
                print("✅ REMOTE_DB_HOST configurado")
            elif line.startswith('REMOTE_DB_PORT='):
                new_lines.append('REMOTE_DB_PORT=5432\n')
                modified = True
                print("✅ REMOTE_DB_PORT configurado")
            else:
                new_lines.append(line + '\n')
        
        # Si no tenía ENVIRONMENT, agregarlo
        if not any(line.startswith('ENVIRONMENT=') for line in new_lines):
            new_lines.insert(0, 'ENVIRONMENT=development\n')
            modified = True
            print("✅ ENVIRONMENT=development agregado")
        
        # Si no tenía DB_NAME, agregarlo
        if not any(line.startswith('DB_NAME=') for line in new_lines):
            new_lines.append('DB_NAME=db.sqlite3\n')
            modified = True
            print("✅ DB_NAME=db.sqlite3 agregado")
        
        # Si no tenía configuración de BD remota, agregarla
        if not any(line.startswith('REMOTE_DB_NAME=') for line in new_lines):
            new_lines.append('REMOTE_DB_NAME=gayozolibreria\n')
            new_lines.append('REMOTE_DB_USER=gallozo_admin\n')
            new_lines.append('REMOTE_DB_PASSWORD=g4ll0z0lib$\n')
            new_lines.append('REMOTE_DB_HOST=www.multilideres.com\n')
            new_lines.append('REMOTE_DB_PORT=5432\n')
            new_lines.append('REMOTE_DB_SSLMODE=require\n')
            modified = True
            print("✅ Configuración de BD remota agregada")
        
        if modified:
            with open(env_file, 'w') as f:
                f.writelines(new_lines)
            print("✅ Archivo .env actualizado")
        else:
            print("ℹ️  El archivo ya estaba configurado")
    
    # Preguntar si desea borrar migraciones
    response = input("\n¿Deseas borrar las migraciones y la base de datos SQLite? (s/N): ").lower().strip()
    if response in ['s', 'si', 'sí', 'y', 'yes']:
        print("\n🗑️  BORRANDO MIGRACIONES Y BASE DE DATOS")
        print("=" * 50)
        proyecto_path = os.path.dirname(os.path.abspath(__file__))
        borrar_migraciones_y_db(proyecto_path)
        print("✅ Migraciones y base de datos eliminadas")
    
    return True

def show_next_steps():
    """Mostrar próximos pasos."""
    print("\n📋 PRÓXIMOS PASOS")
    print("=" * 50)
    
    print("1. 📝 EDITAR CREDENCIALES:")
    print("   Abre el archivo .env y configura:")
    print("   - SECRET_KEY (¡genera una nueva!)")
    print("   - ALLOWED_HOSTS (localhost, 127.0.0.1)")
    print("   - La base de datos ya está configurada para SQLite")
    
    print("\n2. 🗄️  BASE DE DATOS:")
    print("   - Se usará SQLite (db.sqlite3)")
    print("   - No requiere configuración de PostgreSQL")
    
    print("\n3. 🔄 EJECUTAR MIGRACIONES:")
    print("   python3 manage.py makemigrations")
    print("   python3 manage.py migrate")
    
    print("\n4. 🚀 INICIAR SERVIDOR:")
    print("   python3 manage.py runserver")
    
    print("\n5. ✅ VERIFICAR:")
    print("   python3 check_pos_local_mode.py")
    
    print("\n🎯 Una vez configurado:")
    print("- El POS funcionará en modo local con SQLite")
    print("- Se sincronizará con el servidor central")
    print("- Usa /erp/sync/ para sincronización manual")

def generate_secret_key():
    """Generar clave secreta."""
    import secrets
    return secrets.token_urlsafe(50)

def main():
    """Función principal."""
    print("🔧 ACTIVADOR DE MODO POS LOCAL")
    print("=" * 60)
    
    # Verificar estado actual
    current_env = check_current_env()
    
    if current_env == 'development':
        print("\n✅ Ya está en modo POS LOCAL")
        show_next_steps()
        return
    
    # Preguntar si desea activar
    response = input("\n¿Deseas activar modo POS LOCAL? (s/N): ").lower().strip()
    
    if response in ['s', 'si', 'sí', 'y', 'yes']:
        if activate_pos_local_mode():
            print("\n🎉 ¡MODO POS LOCAL ACTIVADO!")
            print("\n🔑 Clave secreta generada:")
            print(f"SECRET_KEY={generate_secret_key()}")
            print(f"DJANGO_SECRET_KEY={generate_secret_key()}")
            show_next_steps()
        else:
            print("\n❌ Error activando modo POS LOCAL")
    else:
        print("\n❌ Operación cancelada")

if __name__ == '__main__':
    main()
