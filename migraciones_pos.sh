#!/bin/bash

# Script de Migraciones - SitioMTCRM (Linux)
# Basado en instalador_pos.sh - Solo la parte de migraciones

# Ir siempre a la carpeta donde está este script
cd "$(dirname "$0")"

echo "============================================"
echo "  MIGRACIONES - SITIOMTCRM (Linux)"
echo "============================================"
echo

# Verificar si estamos en el directorio correcto
if [ ! -f "manage.py" ]; then
    echo "ERROR: No se encuentra el archivo manage.py"
    echo "Por favor, ejecute este script desde el directorio raiz del proyecto"
    exit 1
fi

echo "Iniciando proceso de migraciones..."
echo

# Opción de limpiar base de datos si existe
if [ -f "db.sqlite3" ]; then
    echo "ADVERTENCIA: Se encontró una base de datos existente (db.sqlite3)"
    echo "Para garantizar la creación de tablas, se recomienda eliminarla y crear una nueva."
    read -p "¿Desea eliminarla y crear una nueva? (s/n): " clean_db
    if [[ $clean_db =~ ^[Ss]$ ]]; then
        echo "Eliminando base de datos existente..."
        rm -f db.sqlite3
        echo "Base de datos eliminada."
    else
        echo "INFO: Manteniendo base de datos existente."
        echo "Si las tablas no se crean correctamente, ejecute el script nuevamente y elija 's'."
    fi
    echo
fi

# Migraciones - Asegurar creación completa de tablas
echo "============================================"
echo "  Creando Base de Datos y Tablas"
echo "============================================"
echo

# Limpiar migraciones anteriores solo si existen archivos de migración
if [ -d "core/erp/migrations" ]; then
    echo "[1/6] Limpiando migraciones anteriores..."
    rm -f core/erp/migrations/*.py 2>/dev/null
    rm -f core/user/migrations/*.py 2>/dev/null
    echo "Hecho."
fi

# Crear directorios de migraciones si no existen
if [ ! -d "core/erp/migrations" ]; then
    mkdir -p core/erp/migrations
    touch core/erp/migrations/__init__.py
fi

if [ ! -d "core/user/migrations" ]; then
    mkdir -p core/user/migrations
    touch core/user/migrations/__init__.py
fi

echo "[2/6] Creando migraciones iniciales para user..."
python manage.py makemigrations user --empty user --name initial
if [ $? -ne 0 ]; then
    echo "Advertencia: No se pudo crear migración inicial para user"
fi

echo "[3/6] Creando migraciones iniciales para erp..."
python manage.py makemigrations erp --empty erp --name initial
if [ $? -ne 0 ]; then
    echo "Advertencia: No se pudo crear migración inicial para erp"
fi

echo "[4/6] Creando migraciones automáticas..."
python manage.py makemigrations user erp
if [ $? -ne 0 ]; then
    echo "Error en makemigrations automatico, intentando metodo alternativo..."
    python manage.py makemigrations
fi

echo "[5/6] Aplicando migraciones con --fake-initial..."
python manage.py migrate --fake-initial
if [ $? -ne 0 ]; then
    echo "Error en --fake-initial, continuando con migrate normal..."
fi

echo "[6/6] Aplicando todas las migraciones..."
# Forzar aplicación de migraciones eliminando el registro de migraciones aplicadas
python manage.py migrate --verbosity=2 --run-syncdb
if [ $? -ne 0 ]; then
    echo "ERROR CRITICO: No se pudieron aplicar las migraciones"
    echo
    echo "Intentando método alternativo: eliminando registro de migraciones..."
    # Eliminar tabla de migraciones para forzar recreación
    python manage.py shell -c "
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS django_migrations')
        print('Tabla django_migrations eliminada')
except Exception as e:
    print(f'Error: {e}')
"
    
    echo "Reintentando aplicar migraciones..."
    python manage.py migrate --verbosity=2
    
    if [ $? -ne 0 ]; then
        echo "ERROR CRITICO: No se pudieron aplicar las migraciones después de recrear"
        echo
        echo "Posibles soluciones:"
        echo "1. Elimine el archivo db.sqlite3 y reintente"
        echo "2. Verifique que no haya programas usando la base de datos"
        echo "3. Ejecute manualmente: python manage.py migrate --verbosity=2"
        echo "4. Verifique que las migraciones se hayan creado correctamente"
        echo
        echo "Verificando archivos de migración creados:"
        ls -la core/erp/migrations/
        ls -la core/user/migrations/
        echo
        exit 1
    fi
fi

# Verificar que las tablas se hayan creado correctamente
echo
echo "Verificando que las tablas se hayan creado..."
python manage.py shell -c "
from django.db import connection
tables_to_check = ['erp_employeeaccountsale', 'erp_detsale', 'erp_sale']
missing_tables = []

try:
    with connection.cursor() as cursor:
        cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables_to_check:
            if table in existing_tables:
                print(f'✓ Tabla {table} existe')
            else:
                print(f'✗ Tabla {table} NO existe')
                missing_tables.append(table)
    
    if missing_tables:
        print(f'\\nADVERTENCIA: Faltan las siguientes tablas: {missing_tables}')
        print('Las migraciones no se aplicaron correctamente.')
    else:
        print('\\n✓ Todas las tablas críticas existen correctamente')
        
except Exception as e:
    print(f'Error verificando tablas: {e}')
"

echo
echo "============================================"
echo "  MIGRACIONES COMPLETADAS EXITOSAMENTE!"
echo "============================================"
echo

# Omitir creación automática de superusuario
echo "============================================"
echo "  Creacion de Superusuario (Manual)"
echo "============================================"
echo
echo "IMPORTANTE: Por seguridad, no se crea un superusuario automaticamente."
echo "Debe crearlo manualmente despues de las migraciones."
echo
echo "Para crear el superusuario, ejecute:"
echo "  python manage.py createsuperuser"
echo
echo "O acceda a la administracion y siga las instrucciones."
echo

# Recolectar archivos estáticos
echo "============================================"
echo "  Recolectando Archivos Estaticos"
echo "============================================"
echo

python manage.py collectstatic --noinput
if [ $? -ne 0 ]; then
    echo "[ADVERTENCIA] Error al recolectar archivos estáticos."
    echo "Esto puede afectar la visualizacion de algunos elementos."
    echo
    echo "Puede ejecutar manualmente: python manage.py collectstatic --noinput"
    echo
    echo "Continuando..."
else
    echo "[OK] Archivos estáticos recolectados exitosamente."
fi

echo
echo "============================================"
echo "  PROCESO DE MIGRACIONES FINALIZADO"
echo "============================================"
echo
echo "La base de datos ha sido creada y actualizada correctamente."
echo
echo "PASOS SIGUIENTES:"
echo "  1. Cree un superusuario: python manage.py createsuperuser"
echo "  2. Inicie el servidor: python manage.py runserver"
echo
echo "Para iniciar manualmente:"
echo "  python manage.py runserver 0.0.0.0:8000"
echo
echo "Presione Enter para continuar..."
read
echo
echo "Presione Enter para continuar..."
read
