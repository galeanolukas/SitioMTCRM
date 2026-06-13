#!/bin/bash
# Script para aplicar migraciones en servidor remoto
# Ejecutar en el servidor remoto: cd /home/ubuntu/www/SitioMTCRM && bash aplicar_migraciones_remoto.sh

echo "=== APLICANDO MIGRACIONES EN SERVIDOR REMOTO ==="
echo ""

# Activar entorno virtual
source DJENV/bin/activate

echo "1. Mostrando migraciones pendientes..."
python3 manage.py showmigrations

echo ""
echo "2. Aplicando migraciones pendientes..."
python3 manage.py migrate

echo ""
echo "3. Verificando estado final de migraciones..."
python3 manage.py showmigrations

echo ""
echo "=== PROCESO COMPLETADO ==="
