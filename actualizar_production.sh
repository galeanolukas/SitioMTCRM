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
if [ -f "uwsgi.pid" ]; then
    uwsgi --reload uwsgi.pid
    sleep 3
else
    echo "Iniciando uWSGI..."
    uwsgi --ini uwsgi11.ini
fi

# Verificar estado
sleep 5
if pgrep -f "uwsgi" > /dev/null; then
    echo "uWSGI está corriendo"
else
    echo "[ERROR] uWSGI no está corriendo"
    exit 1
fi

echo
echo "============================================"
echo "Actualización completada"
echo "============================================"
echo "Servicios reiniciados. Verifique el sitio web."
