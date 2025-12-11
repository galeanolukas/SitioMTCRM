#!/bin/bash

# Actualizador para Servidor de Producción - SitioMTCRM
# USAR CON MUCHO CUIDADO - NO INTERACTIVO
cd "$(dirname "$0")"

echo "============================================"
echo "Actualizador PRODUCCIÓN - SitioMTCRM"
echo "============================================"
echo "ADVERTENCIA: Este script reinicia servicios"
echo

# Verificar si estamos en producción
if [ ! -f "uwsgi11.ini" ]; then
    echo "[ERROR] No se encuentra uwsgi11.ini"
    echo "Este script es solo para servidor de producción"
    exit 1
fi

# Verificar Git
if ! command -v git &> /dev/null; then
    echo "[ERROR] Git no está instalado"
    exit 1
fi

# Verificar entorno virtual
if [ ! -d "/home/ubuntu/DJENV" ]; then
    echo "[ERROR] No se encuentra el entorno virtual /home/ubuntu/DJENV"
    exit 1
fi

# Backup de la base de datos PostgreSQL
echo "Haciendo backup de PostgreSQL..."
timestamp=$(date +%Y%m%d-%H%M%S)
backup_file="backups/postgres_backup_${timestamp}.sql"

mkdir -p backups
if command -v pg_dump &> /dev/null; then
    pg_dump SitioMTCRM > "$backup_file"
    echo "Backup guardado en: $backup_file"
else
    echo "[ADVERTENCIA] pg_dump no encontrado. No se puede hacer backup de PostgreSQL"
fi

# Actualizar código
echo "Actualizando código desde GitHub..."
git pull origin main
if [ $? -ne 0 ]; then
    echo "[ERROR] Falló git pull"
    exit 1
fi

# Activar entorno virtual
source /home/ubuntu/DJENV/bin/activate

# Configurar .env para producción (ANTES de migraciones)
echo "Configurando .env para producción..."
if [ -f ".env" ]; then
    # Backup de .env original
    cp .env .env.backup
    
    # Actualizar variables de producción
    sed -i 's/DEBUG=True/DEBUG=False/' .env
    sed -i 's/ENV=development/ENV=production/' .env
    
    # Verificar si ya está configurado PostgreSQL
    if ! grep -q "DB_NAME=" .env || grep -q "DB_NAME=sqlite3" .env; then
        echo "ADVERTENCIA: Configure manualmente las variables de PostgreSQL en .env:"
        echo "  DB_NAME=nombre_base_datos"
        echo "  DB_USER=usuario_postgres" 
        echo "  DB_PASSWORD=contraseña_segura"
        echo "  DB_HOST=localhost"
        echo "  DB_PORT=5432"
        echo ""
        echo "Presione Enter para continuar o Ctrl+C para cancelar..."
        read
        
        # Crear template vacío para que el usuario complete
        cat >> .env << EOF

# Base de Datos PostgreSQL (Producción) - COMPLETAR MANUALMENTE
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
EOF
    else
        echo "Variables de PostgreSQL ya configuradas en .env"
    fi
    
    echo ".env configurado para producción"
else
    echo "[ADVERTENCIA] No se encuentra .env"
    echo "Creando .env con configuración básica..."
    cat > .env << EOF
# Configuración de Producción
DEBUG=False
ENV=production

# Base de Datos PostgreSQL (Producción) - COMPLETAR MANUALMENTE
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
EOF
    echo "Configure las variables de DB_ en .env antes de continuar"
fi

# Configurar settings para producción (ANTES de migraciones)
echo "Configurando settings para producción..."
if [ -f "config/settings.py" ]; then
    # Backup de settings original
    cp config/settings.py config/settings.py.backup
    
    # Cambiar DEBUG=False en producción
    sed -i 's/DEBUG = True/DEBUG = False/' config/settings.py
    echo "DEBUG configurado en False"
    
    # Cambiar ENVIRONMENT a production
    sed -i "s/ENVIRONMENT = 'development'/ENVIRONMENT = 'production'/" config/settings.py
    echo "ENVIRONMENT configurado en production"
    
    # Verificar ALLOWED_HOSTS
    if grep -q "ALLOWED_HOSTS = \['127.0.0.1'\]" config/settings.py; then
        echo "ADVERTENCIA: ALLOWED_HOSTS está limitado a localhost. Debe configurarlo manualmente."
    fi
    
    # Configurar logging para producción (reducir verbosidad)
    if grep -q "'level': 'DEBUG'" config/settings.py; then
        echo "Configurando logging para producción..."
        sed -i "s/'level': 'DEBUG'/'level': 'INFO'/" config/settings.py
        echo "Logging configurado en INFO level"
    fi
else
    echo "[ADVERTENCIA] No se encuentra config/settings.py"
fi

# Actualizar dependencias
echo "Actualizando dependencias..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Falló instalación de dependencias"
    exit 1
fi

# Migraciones (con cuidado en producción)
echo "Ejecutando migraciones..."
python manage.py migrate --no-input
if [ $? -ne 0 ]; then
    echo "[ERROR] Falló migraciones"
    exit 1
fi

# Collect static
echo "Recolectando archivos estáticos..."
python manage.py collectstatic --no-input
if [ $? -ne 0 ]; then
    echo "[ERROR] Falló collectstatic"
    exit 1
fi

# Reiniciar uWSGI
echo "Reiniciando uWSGI..."
if [ -f "uwsgi11.ini" ]; then
    if [ -f "uwsgi.pid" ]; then
        uwsgi --reload uwsgi.pid
        sleep 3
    else
        echo "Iniciando uWSGI..."
        uwsgi --ini uwsgi11.ini --daemonize /var/log/uwsgi.log
    fi
else
    echo "[ERROR] No se encuentra uwsgi11.ini"
    exit 1
fi

# Reiniciar lighttpd
echo "Reiniciando lighttpd..."
if command -v lighttpd &> /dev/null; then
    sudo systemctl restart lighttpd
    if [ $? -eq 0 ]; then
        echo "lighttpd reiniciado correctamente"
    else
        echo "[ADVERTENCIA] Error al reiniciar lighttpd"
    fi
else
    echo "[ADVERTENCIA] lighttpd no está instalado"
fi

# Verificar estado
sleep 5
if pgrep -f "uwsgi" > /dev/null; then
    echo "uWSGI está corriendo"
else
    echo "[ERROR] uWSGI no está corriendo"
    exit 1
fi

if command -v lighttpd &> /dev/null; then
    if sudo systemctl is-active --quiet lighttpd; then
        echo "lighttpd está corriendo"
    else
        echo "[ADVERTENCIA] lighttpd no está corriendo"
    fi
fi

echo
echo "============================================"
echo "Actualización completada"
echo "============================================"
echo "Servicios reiniciados. Verifique el sitio web."
echo
echo "Configuraciones aplicadas:"
echo "  - DEBUG=False en settings.py"
echo "  - ENVIRONMENT=production en settings.py"
echo "  - Logging level=INFO en settings.py"
echo "  - ENV=production en .env"
echo "  - Template PostgreSQL agregado a .env (completar manualmente)"
echo
echo "IMPORTANTE:"
echo "  - Configure DB_PASSWORD en .env"
echo "  - Verifique ALLOWED_HOSTS en settings.py"
echo "  - Backups guardados: .backup files"
echo
echo "Logs para depuración:"
echo "  - uWSGI: /var/log/uwsgi.log"
echo "  - lighttpd: /var/log/lighttpd/error.log"
