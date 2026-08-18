#!/bin/bash

# Script para arreglar migraciones desincronizadas en servidor remoto
# Marca migraciones problemáticas como aplicadas y luego aplica las restantes

PROJECT_PATH="/media/lukas/ARCHIVOS/GitHub/SitioMTCRM"
VENV_PATH="$PROJECT_PATH/DJENV/bin/activate"

echo "Activando entorno virtual local..."
source $VENV_PATH

echo "Navegando al proyecto..."
cd $PROJECT_PATH

echo "Marcando migración problemática como aplicada en servidor remoto..."
python manage.py migrate --database=remote erp 0008 --fake

echo "Aplicando migraciones restantes en servidor remoto..."
python manage.py migrate --database=remote

echo "Migraciones aplicadas en servidor remoto"
