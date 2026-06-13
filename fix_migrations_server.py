#!/usr/bin/env python3
"""
Script para arreglar migraciones en el servidor remoto
"""
import os
import django
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command
from django.db import connection
import sys

print("=== ARREGLANDO MIGRACIONES EN SERVIDOR ===\n")

# 1. Verificar estado actual de migraciones
print("1. Verificando estado de migraciones...")
try:
    call_command('showmigrations', verbosity=1)
except Exception as e:
    print(f"Error al mostrar migraciones: {e}\n")

# 2. Aplicar migraciones de la app 'user' primero
print("\n2. Aplicando migraciones de la app 'user'...")
try:
    call_command('migrate', 'user', verbosity=2)
    print("✓ Migraciones de 'user' aplicadas\n")
except Exception as e:
    print(f"✗ Error aplicando migraciones de 'user': {e}\n")
    print("Intentando con --fake-initial...")
    try:
        call_command('migrate', 'user', '--fake-initial', verbosity=2)
        print("✓ Migraciones de 'user' aplicadas con --fake-initial\n")
    except Exception as e2:
        print(f"✗ Error con --fake-initial: {e2}\n")

# 3. Aplicar migraciones de auth
print("3. Aplicando migraciones de 'auth'...")
try:
    call_command('migrate', 'auth', verbosity=2)
    print("✓ Migraciones de 'auth' aplicadas\n")
except Exception as e:
    print(f"✗ Error aplicando migraciones de 'auth': {e}\n")

# 4. Aplicar migraciones de contenttypes
print("4. Aplicando migraciones de 'contenttypes'...")
try:
    call_command('migrate', 'contenttypes', verbosity=2)
    print("✓ Migraciones de 'contenttypes' aplicadas\n")
except Exception as e:
    print(f"✗ Error aplicando migraciones de 'contenttypes': {e}\n")

# 5. Aplicar migraciones de sessions
print("5. Aplicando migraciones de 'sessions'...")
try:
    call_command('migrate', 'sessions', verbosity=2)
    print("✓ Migraciones de 'sessions' aplicadas\n")
except Exception as e:
    print(f"✗ Error aplicando migraciones de 'sessions': {e}\n")

# 6. Aplicar migraciones de admin
print("6. Aplicando migraciones de 'admin'...")
try:
    call_command('migrate', 'admin', verbosity=2)
    print("✓ Migraciones de 'admin' aplicadas\n")
except Exception as e:
    print(f"✗ Error aplicando migraciones de 'admin': {e}\n")

# 7. Aplicar migraciones de erp
print("7. Aplicando migraciones de 'erp'...")
try:
    call_command('migrate', 'erp', verbosity=2)
    print("✓ Migraciones de 'erp' aplicadas\n")
except Exception as e:
    print(f"✗ Error aplicando migraciones de 'erp': {e}\n")
    print("Intentando con --fake si hay conflictos...")
    try:
        # Verificar qué migraciones están aplicadas
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM django_migrations WHERE app='erp' ORDER BY id")
            applied = [row[0] for row in cursor.fetchall()]
            print(f"Migraciones de 'erp' ya aplicadas: {applied}")
        
        # Intentar aplicar las faltantes
        call_command('migrate', 'erp', '--fake', verbosity=2)
        print("✓ Migraciones de 'erp' aplicadas con --fake\n")
    except Exception as e2:
        print(f"✗ Error con --fake: {e2}\n")

# 8. Aplicar migraciones de homepage
print("8. Aplicando migraciones de 'homepage'...")
try:
    call_command('migrate', 'homepage', verbosity=2)
    print("✓ Migraciones de 'homepage' aplicadas\n")
except Exception as e:
    print(f"✗ Error aplicando migraciones de 'homepage': {e}\n")

# 9. Aplicar migraciones de login
print("9. Aplicando migraciones de 'login'...")
try:
    call_command('migrate', 'login', verbosity=2)
    print("✓ Migraciones de 'login' aplicadas\n")
except Exception as e:
    print(f"✗ Error aplicando migraciones de 'login': {e}\n")

# 10. Verificar estado final
print("10. Verificando estado final de migraciones...")
try:
    call_command('showmigrations', verbosity=1)
except Exception as e:
    print(f"Error al mostrar migraciones: {e}\n")

print("\n=== PROCESO COMPLETADO ===")
print("Si hay errores, revisa los mensajes arriba.")
print("Si todo está bien, ejecuta: python3 manage.py migrate")
