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

# 1) Crear o recrear entorno virtual DJENV
# Verificar si DJENV existe y está funcional
RECREATE_VENV=false
if [ ! -d "DJENV" ]; then
    echo "Creando entorno virtual DJENV..."
    RECREATE_VENV=true
else
    # Verificar que DJENV tenga Django completo (incluido módulo de migraciones)
    if ! DJENV/bin/python -c "from django.db.migrations.migration import Migration" &>/dev/null; then
        echo "Entorno virtual DJENV está dañado o incompleto. Recreando..."
        rm -rf DJENV
        RECREATE_VENV=true
    else
        echo "Entorno virtual DJENV ya existe y funciona correctamente."
    fi
fi

if [ "$RECREATE_VENV" = true ]; then
    python3 -m venv DJENV
    if [ $? -ne 0 ]; then
        echo "Error al crear el entorno virtual DJENV. Verifica que Python3 esté instalado."
        exit 1
    fi
fi

# 2) Activar entorno virtual DJENV
source DJENV/bin/activate
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
    echo "[ADVERTENCIA] No se pudo importar pandas u openpyxl en el entorno virtual DJENV."
    echo "Verifique la instalación manualmente con:"
    echo "  source DJENV/bin/activate"
    echo "  pip install pandas openpyxl"
fi

# 4) Migraciones - Método mejorado con verificación de company_id
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

# 5) Crear superusuario automáticamente si no existe ninguno
echo "Verificando si existe un superusuario..."
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('SUPERUSER_CREATED')
else:
    print('SUPERUSER_EXISTS')
" 2>/dev/null | grep -q 'SUPERUSER_CREATED' && echo "✓ Superusuario creado: admin / admin123" || echo "✓ Superusuario ya existe"

echo
echo "============================================"
echo "Instalación terminada."
echo "============================================"
echo "Para iniciar el POS local:"
echo "  source DJENV/bin/activate"
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
echo "============================================"
echo "Instalación completada exitosamente."
echo "============================================"
echo
echo "El sistema ha sido instalado y configurado."
echo
echo "Componentes instalados:"
echo "  - Entorno virtual DJENV"
echo "  - Dependencias Python"
echo "  - Base de datos SQLite"
echo "  - Acceso directo en escritorio"
echo

# Preguntar si desea iniciar el programa automáticamente
read -p "¿Desea iniciar el programa automáticamente? (s/n): " start_program

if [[ $start_program =~ ^[Ss]$ ]]; then
    echo
    echo "Iniciando el programa..."
    echo "El servidor se iniciará en: http://127.0.0.1:8000/"
    echo "Presione Ctrl+C para detener el servidor."
    echo
    source DJENV/bin/activate
    python manage.py runserver 0.0.0.0:8000
else
    echo
    echo "Para iniciar manualmente:"
    echo "  source DJENV/bin/activate"
    echo "  python manage.py runserver 0.0.0.0:8000"
    echo "y luego abra: http://localhost:8000/erp/sale/pos/"
    echo
    echo "Presione Enter para continuar..."
    read
fi
