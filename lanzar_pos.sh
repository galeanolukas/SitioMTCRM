#!/bin/bash

# Lanzar POS local de MultilideresCRM en Linux

# Ir siempre a la carpeta donde está este script
cd "$(dirname "$0")"

if [ ! -f "DJENV/bin/activate" ]; then
    echo "[ERROR] Entorno virtual venv no encontrado. Cree el venv primero:"
    echo "python3 -m venv venv"
    echo "Luego ejecute: ./instalador_pos.sh"
    exit 1
fi

source DJENV/bin/activate

# Asegurar entorno de POS (no production)
export ENVIRONMENT=development

# Leer dominio local desde .env (si existe)
LOCAL_DOMAIN="localhost"
if [ -f ".env" ]; then
    LOCAL_DOMAIN=$(grep -E '^LOCAL_DOMAIN=' .env | cut -d'=' -f2 | tr -d '[:space:]')
    [ -z "$LOCAL_DOMAIN" ] && LOCAL_DOMAIN="localhost"
fi

ACCESS_HOST="$LOCAL_DOMAIN"
echo "Iniciando servidor Django en http://${ACCESS_HOST}:8000 ..."
# Abrir el servidor en segundo plano para no bloquear este script
python manage.py runserver 0.0.0.0:8000 &
SERVER_PID=$!

# Esperar unos segundos a que levante el servidor (ajustado a 10s para equipos más lentos)
echo "Esperando a que el servidor se inicie..."
sleep 10

# Abrir el navegador en la URL del POS (launcher)
echo "Abriendo navegador en http://${ACCESS_HOST}:8000/erp/launcher/"
LAUNCHER_URL="http://${ACCESS_HOST}:8000/erp/launcher/"
if command -v xdg-open &> /dev/null; then
    xdg-open "$LAUNCHER_URL"
elif command -v gnome-open &> /dev/null; then
    gnome-open "$LAUNCHER_URL"
elif command -v firefox &> /dev/null; then
    firefox "$LAUNCHER_URL" &
elif command -v google-chrome &> /dev/null; then
    google-chrome "$LAUNCHER_URL" &
elif command -v chromium &> /dev/null; then
    chromium "$LAUNCHER_URL" &
else
    echo "No se pudo detectar un navegador. Abra manualmente:"
    echo "$LAUNCHER_URL"
fi

echo
echo "El servidor Django está corriendo en segundo plano (PID: $SERVER_PID)"
echo "Para detenerlo, ejecute: kill $SERVER_PID"
echo "O presione Ctrl+C en esta terminal para detener todo."
echo

# Esperar a que el usuario presione Ctrl+C
trap "echo 'Deteniendo servidor...'; kill $SERVER_PID 2>/dev/null; exit" INT
wait $SERVER_PID
