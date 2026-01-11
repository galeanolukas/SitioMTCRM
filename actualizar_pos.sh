#!/bin/bash

# Ir siempre a la carpeta donde está este script
cd "$(dirname "$0")"

echo "============================================"
echo "Actualizador POS Local - SitioMTCRM (Linux)"
echo "============================================"
echo

# Verificar si Git esta instalado
if ! command -v git &> /dev/null; then
    echo "[ERROR] Git no está instalado."
    echo "Para usar este actualizador debe tener Git instalado."
    echo "Puede instalar Git con:"
    echo "  sudo apt install git  # Debian/Ubuntu"
    echo "  sudo dnf install git  # Fedora/RHEL"
    echo
    echo "Instale Git y vuelva a ejecutar este script."
    exit 1
fi

# Verificar si estamos en un repositorio git
if [ ! -d ".git" ]; then
    echo "[ERROR] No se encuentra el directorio .git en esta carpeta."
    echo "Este script debe ejecutarse desde la raíz del proyecto clonado desde GitHub."
    echo
    echo "Si descargó el proyecto como ZIP, por favor:"
    echo "1. Elimine la carpeta actual"
    echo "2. Clone el repositorio con: git clone https://github.com/galeanolukas/SitioMTCRM.git"
    echo "3. Vuelva a ejecutar este script desde la nueva carpeta"
    exit 1
fi

# Verificar si hay cambios sin commitear
if ! git diff-index --quiet HEAD --; then
    echo "[ADVERTENCIA] Se detectaron cambios locales sin guardar en Git."
    echo "Estos cambios podrían perderse al actualizar desde GitHub."
    echo
    echo "Opciones:"
    echo "1. Continuar con la actualización (los cambios locales se perderán)"
    echo "2. Cancelar para hacer backup manual de los cambios"
    echo
    read -p "¿Desea continuar con la actualización? (S/N): " continue
    if [[ ! "$continue" =~ ^[Ss]$ ]]; then
        echo "Actualización cancelada."
        exit 0
    fi
fi

# Backup de archivos importantes si existen
if [ -d "/media/lukas/ARCHIVOS/GitHub/DJENV" ]; then
    echo "Entorno virtual DJENV detectado externamente, no se requiere backup."
else
    if [ -d "DJENV" ]; then
        echo "Haciendo backup del entorno virtual local..."
        if [ -d "DJENV_backup" ]; then
            rm -rf DJENV_backup
        fi
        mv DJENV DJENV_backup
    fi
fi

# Backup de la base de datos local si existe
if [ -f "db.sqlite3" ]; then
    echo "Haciendo backup de la base de datos local..."
    if [ -f "db.sqlite3_backup" ]; then
        rm db.sqlite3_backup
    fi
    cp db.sqlite3 db.sqlite3_backup
fi

echo "Actualizando código desde GitHub..."
git pull origin main
if [ $? -ne 0 ]; then
    echo "[ERROR] Error al actualizar desde GitHub."
    echo "Verifique su conexión a internet o si hay conflictos de fusión."
    echo
    echo "Si hay conflictos, resuélvalos manualmente y vuelva a ejecutar."
    
    # Restaurar backup si falla
    if [ -d "/media/lukas/ARCHIVOS/GitHub/DJENV" ]; then
        echo "El entorno virtual DJENV es externo, no se requiere restauración."
    else
        if [ -d "DJENV_backup" ]; then
            echo "Restaurando entorno virtual desde backup..."
            mv DJENV_backup DJENV
        fi
    fi
    
    if [ -f "db.sqlite3_backup" ]; then
        echo "Restaurando base de datos desde backup..."
        mv db.sqlite3_backup db.sqlite3
    fi
    
    exit 1
fi

# 1) Activar entorno virtual DJENV (o crearlo si no existe)
if [ ! -d "DJENV" ] && [ ! -d "/media/lukas/ARCHIVOS/GitHub/DJENV" ]; then
    echo "[ERROR] Entorno virtual DJENV no encontrado."
    echo "Por favor, cree el entorno virtual DJENV en /media/lukas/ARCHIVOS/GitHub/"
    exit 1
fi

# Usar el entorno virtual DJENV externo
if [ -d "/media/lukas/ARCHIVOS/GitHub/DJENV" ]; then
    echo "Activando entorno virtual DJENV externo..."
    source /media/lukas/ARCHIVOS/GitHub/DJENV/bin/activate
else
    echo "Activando entorno virtual DJENV local..."
    source DJENV/bin/activate
fi
if [ $? -ne 0 ]; then
    echo "No se pudo activar el entorno virtual."
    exit 1
fi

# 2) Actualizar pip
echo "Actualizando pip..."
python -m pip install --upgrade pip
if [ $? -ne 0 ]; then
    echo "No se pudo actualizar pip. Continuando con la instalación de dependencias..."
fi

# 3) Instalar/actualizar dependencias
echo "Instalando/actualizando dependencias desde requirements.txt..."

# Asegurar que no quede instalada la librería vieja pandas-openpyxl
pip uninstall -y pandas-openpyxl &> /dev/null

pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error instalando dependencias."
    exit 1
fi

# Verificación rápida de pandas y openpyxl
python -c "import pandas, openpyxl; print('pandas:', pandas.__version__)" &> /dev/null
if [ $? -ne 0 ]; then
    echo "[ADVERTENCIA] No se pudo importar pandas u openpyxl en el entorno virtual."
    echo "Verifique la instalación manualmente."
fi

# 4) Migraciones
echo "Creando migraciones si hacen falta..."
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

# 5) Limpiar backup antiguo si la actualización fue exitosa
if [ -d "/media/lukas/ARCHIVOS/GitHub/DJENV" ]; then
    echo "Entorno virtual DJENV externo, no hay backup local que limpiar."
else
    if [ -d "DJENV_backup" ]; then
        echo "Limpiando backup antiguo..."
        rm -rf DJENV_backup
    fi
fi

if [ -f "db.sqlite3_backup" ]; then
    echo "Limpiando backup de base de datos..."
    rm db.sqlite3_backup
fi

echo
echo "============================================"
echo "Actualización completada exitosamente!"
echo "============================================"
echo
echo "El POS ha sido actualizado a la última versión desde GitHub."
echo
echo "Para iniciar el POS actualizado:"
echo "  1) Cierre esta ventana"
echo "  2) Ejecute: ./lanzar_pos.sh"
echo "  3) Abra su navegador y acceda al sistema"
echo
echo "Si experimenta problemas, puede verificar la versión"
echo "en el menú Actualizaciones del sistema."
echo "============================================"

echo
echo "Presione Enter para continuar..."
read
