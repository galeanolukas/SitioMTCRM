#!/bin/bash

# Lanzar POS local de MultilideresCRM en Linux

# Ir siempre a la carpeta donde está este script
cd "$(dirname "$0")"

if [ ! -f "venv/bin/activate" ]; then
    echo "[ERROR] Entorno virtual venv no encontrado. Cree el venv primero:"
    echo "python3 -m venv venv"
    echo "Luego ejecute: ./instalador_pos.sh"
    exit 1
fi

source venv/bin/activate

# Asegurar entorno de POS (no production)
export ENVIRONMENT=development

echo "Iniciando servidor Django en http://localhost:8000 ..."
# Abrir el servidor en segundo plano para no bloquear este script
python manage.py runserver 0.0.0.0:8000 &
SERVER_PID=$!

# Esperar unos segundos a que levante el servidor (ajustado a 10s para equipos más lentos)
echo "Esperando a que el servidor se inicie..."
sleep 10

# Abrir el navegador en la URL del POS (launcher)
echo "Abriendo navegador en http://localhost:8000/erp/launcher/"
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:8000/erp/launcher/"
elif command -v gnome-open &> /dev/null; then
    gnome-open "http://localhost:8000/erp/launcher/"
elif command -v firefox &> /dev/null; then
    firefox "http://localhost:8000/erp/launcher/" &
elif command -v google-chrome &> /dev/null; then
    google-chrome "http://localhost:8000/erp/launcher/" &
elif command -v chromium &> /dev/null; then
    chromium "http://localhost:8000/erp/launcher/" &
else
    echo "No se pudo detectar un navegador. Abra manualmente:"
    echo "http://localhost:8000/erp/launcher/"
fi

echo
echo "El servidor Django está corriendo en segundo plano (PID: $SERVER_PID)"
echo "Para detenerlo, ejecute: kill $SERVER_PID"
echo "O presione Ctrl+C en esta terminal para detener todo."
echo

# Esperar a que el usuario presione Ctrl+C
trap "echo 'Deteniendo servidor...'; kill $SERVER_PID 2>/dev/null; exit" INT
wait $SERVER_PID
