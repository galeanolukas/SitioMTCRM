#!/bin/bash

# Script para aplicar migraciones en el servidor remoto desde el local
# Usa el entorno DJENV local y la configuración de DB remota en .env

PROJECT_PATH="/media/lukas/ARCHIVOS/GitHub/SitioMTCRM"
VENV_PATH="$PROJECT_PATH/DJENV/bin/activate"

echo "Activando entorno virtual local..."
source $VENV_PATH

echo "Navegando al proyecto..."
cd $PROJECT_PATH

echo "Aplicando migraciones en servidor remoto usando conexión configurada..."
python manage.py migrate_remote

echo "Migraciones aplicadas en servidor remoto"
