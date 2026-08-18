#!/bin/bash

# Script para aplicar migraciones en el servidor remoto
# Uso: ./scripts/migrate_remote_server.sh

SERVER="ubuntu@erp.multilideres.com"
PROJECT_PATH="/home/ubuntu/www/SitioMTCRM"
VENV_PATH="DJENV/bin/activate"

echo "Conectando al servidor remoto..."
ssh $SERVER "cd $PROJECT_PATH && source $VENV_PATH && python manage.py migrate"

echo "Migraciones aplicadas en servidor remoto"
