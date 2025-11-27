#!/bin/bash

# Ir siempre a la carpeta donde está este script
cd "$(dirname "$0")"

echo "============================================"
echo "Instalador POS Local - SitioMTCRM (Linux)"
echo "============================================"
echo

# Verificar si Python3 está instalado
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 no está instalado."
    echo "Instale Python3 con:"
    echo "  sudo apt update && sudo apt install python3 python3-pip python3-venv"
    echo "o para sistemas basados en Fedora/RHEL:"
    echo "  sudo dnf install python3 python3-pip"
    exit 1
fi

# Verificar si Git esta instalado (recomendado para futuras actualizaciones)
if ! command -v git &> /dev/null; then
    echo "[ADVERTENCIA] Git no está instalado."
    echo "Para usar el actualizador automático llamado actualizar_pos.sh debe tener Git instalado."
    echo "Puede instalar Git con:"
    echo "  sudo apt install git  # Debian/Ubuntu"
    echo "  sudo dnf install git  # Fedora/RHEL"
    echo
    echo "Este instalador continuará, pero las actualizaciones futuras deberán hacerse manualmente si no instala Git."
    echo
fi

# 1) Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "Error al crear el entorno virtual. Verifica que Python3 esté instalado."
        exit 1
    fi
else
    echo "Entorno virtual ya existe."
fi

# 2) Activar entorno virtual
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "No se pudo activar el entorno virtual."
    exit 1
fi

# 2.1) Actualizar pip en el entorno virtual
echo "Actualizando pip..."
python -m pip install --upgrade pip
if [ $? -ne 0 ]; then
    echo "No se pudo actualizar pip. Continuando con la instalación de dependencias..."
else
    echo "pip actualizado correctamente."
fi

# 3) Instalar dependencias (incluye pandas y openpyxl desde requirements.txt)
echo "Instalando dependencias desde requirements.txt..."

# Asegurar que no quede instalada la librería vieja pandas-openpyxl
pip uninstall -y pandas-openpyxl &> /dev/null

pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error instalando dependencias."
    exit 1
fi

# Verificación rápida de pandas y openpyxl en este entorno virtual
python -c "import pandas, openpyxl; print('pandas:', pandas.__version__)" &> /dev/null
if [ $? -ne 0 ]; then
    echo "[ADVERTENCIA] No se pudo importar pandas u openpyxl en el entorno virtual."
    echo "Verifique la instalación manualmente con:"
    echo "  source venv/bin/activate"
    echo "  pip install pandas openpyxl"
fi

# 4) Migraciones
echo "Creando migraciones si hacen falta (apps user y erp)..."
python manage.py makemigrations user erp
if [ $? -ne 0 ]; then
    echo "Error ejecutando makemigrations."
    exit 1
fi

echo "Ejecutando migraciones..."
python manage.py migrate
if [ $? -ne 0 ]; then
    echo "Error ejecutando migraciones."
    exit 1
fi

echo
echo "============================================"
echo "Instalación terminada."
echo "============================================"
echo "Si es la primera vez, crea un superusuario con:"
echo "  python manage.py createsuperuser"
echo
echo "Para iniciar el POS local:"
echo "  source venv/bin/activate"
echo "  python manage.py runserver 0.0.0.0:8000"
echo "y luego abre: http://localhost:8000/erp/sale/pos/"
echo
echo "Para futuras actualizaciones del POS (nueva versión desde GitHub):"
echo "  1) Cierre el POS."
echo "  2) Ejecute: ./actualizar_pos.sh"
echo "  3) Vuelva a iniciar con ./lanzar_pos.sh"
echo "============================================"

# Crear acceso directo (launcher) en el escritorio para el POS local
LAUNCHER_TARGET="$(pwd)/lanzar_pos.sh"
DESKTOP_DIR="$HOME/Desktop"
SHORTCUT_PATH="$DESKTOP_DIR/POS_Local.desktop"
ICON_FILE="$(pwd)/icon.png"  # Buscar icono PNG para Linux

echo "Creando acceso directo en el escritorio..."

if [ ! -f "$LAUNCHER_TARGET" ]; then
    echo "No se encontró el archivo lanzar_pos.sh en la carpeta del proyecto."
    echo "Crea el archivo lanzar_pos.sh y vuelve a ejecutar este instalador."
    exit 1
fi

# Crear directorio Desktop si no existe
if [ ! -d "$DESKTOP_DIR" ]; then
    mkdir -p "$DESKTOP_DIR"
fi

# Crear archivo .desktop
cat > "$SHORTCUT_PATH" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=POS Local SitioMTCRM
Comment=Iniciar el POS local de SitioMTCRM
Exec=$LAUNCHER_TARGET
Icon=$ICON_FILE
Path=$(pwd)
Terminal=true
Categories=Office;Business;
EOF

# Hacer ejecutable el acceso directo
chmod +x "$SHORTCUT_PATH"

if [ $? -ne 0 ]; then
    echo "No se pudo crear el acceso directo."
    echo "Puedes crear manualmente un acceso directo a lanzar_pos.sh en el escritorio."
else
    echo "Acceso directo creado en el escritorio: POS_Local.desktop"
fi

echo
echo "Presione Enter para continuar..."
read
