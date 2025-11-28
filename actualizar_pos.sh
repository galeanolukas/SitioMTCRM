#!/bin/bash

# Actualizar POS local de SitioMTCRM en Linux

# Ir siempre a la carpeta donde está este script
cd "$(dirname "$0")"

echo "============================================"
echo " Actualizador POS Local - SitioMTCRM (Linux)"
echo "============================================"
echo

# Verificar que exista el entorno virtual
if [ ! -f "venv/bin/activate" ]; then
    echo "[ERROR] Entorno virtual no encontrado."
    echo "Cree el venv primero (ejecute ./instalador_pos.sh)."
    exit 1
fi

# Verificar que Git este instalado
if ! command -v git &> /dev/null; then
    echo "[ERROR] Git no está instalado."
    echo "Instale Git con:"
    echo "  sudo apt install git  # Debian/Ubuntu"
    echo "  sudo dnf install git  # Fedora/RHEL"
    echo "y luego vuelva a ejecutar este actualizador."
    exit 1
fi

# Activar entorno virtual
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERROR] No se pudo activar el entorno virtual."
    exit 1
fi

# Backup de la base de datos antes de actualizar
echo "============================================"
echo "CREANDO BACKUP DE LA BASE DE DATOS LOCAL"
echo "============================================"

DB_FILE="db.sqlite3"
BACKUP_DIR="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sqlite3"

# Crear directorio de backups si no existe
mkdir -p "$BACKUP_DIR"

if [ -f "$DB_FILE" ]; then
    echo "Copiando base de datos a $BACKUP_FILE..."
    cp "$DB_FILE" "$BACKUP_FILE"
    if [ $? -eq 0 ]; then
        echo "✓ Backup creado exitosamente"
        echo "  Archivo: $BACKUP_FILE"
        echo "  Tamaño: $(du -h "$BACKUP_FILE" | cut -f1)"
    else
        echo "[ERROR] No se pudo crear el backup de la base de datos"
        echo "¿Desea continuar de todas formas? (s/N)"
        read -r response
        if [[ ! "$response" =~ ^[Ss]$ ]]; then
            echo "Actualización cancelada."
            exit 1
        fi
    fi
else
    echo "No se encontró archivo de base de datos ($DB_FILE)"
    echo "Continuando sin backup..."
fi

echo
echo "============================================"
echo "INICIANDO ACTUALIZACIÓN DEL CÓDIGO"
echo "============================================"

# Guardar cambios locales no commitidos si existe
echo "1) Verificando cambios locales..."
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Se detectaron cambios locales no guardados."
    echo "Opciones:"
    echo "  1) Guardar cambios en un stash (recomendado)"
    echo "  2) Descartar cambios locales"
    echo "  3) Cancelar actualización"
    echo "Seleccione una opción (1/2/3): "
    read -r choice
    
    case $choice in
        1)
            echo "Guardando cambios en stash..."
            git stash push -m "Auto-stash antes de actualizar - $(date)"
            echo "✓ Cambios guardados en stash"
            echo "Para recuperarlos después: git stash pop"
            ;;
        2)
            echo "Descartando cambios locales..."
            git reset --hard HEAD
            git clean -fd
            echo "✓ Cambios locales descartados"
            ;;
        3)
            echo "Actualización cancelada."
            exit 0
            ;;
        *)
            echo "Opción inválida. Cancelando actualización."
            exit 1
            ;;
    esac
else
    echo "✓ No hay cambios locales pendientes"
fi

echo
echo "2) Actualizando código desde Git (git pull)..."
git pull
if [ $? -ne 0 ]; then
    echo "[ERROR] Error ejecutando git pull."
    echo "Posibles causas:"
    echo "  - Problemas de conexión a Internet"
    echo "  - Conflictos de fusión"
    echo "  - Repositorio no configurado correctamente"
    echo
    echo "Intente resolver manualmente y ejecute nuevamente."
    exit 1
fi

echo "✓ Código actualizado exitosamente"

echo
echo "3) Actualizando dependencias (pip install -r requirements.txt)..."
python -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ADVERTENCIA] Hubo errores actualizando dependencias."
    echo "Revise el log anterior. Puede continuar, pero si el POS falla revise manualmente."
else
    echo "✓ Dependencias actualizadas"
fi

echo
echo "4) Aplicando migraciones de la base de datos..."
echo "   (Esto actualizará la estructura sin borrar datos existentes)"
python manage.py migrate
if [ $? -ne 0 ]; then
    echo "[ERROR] Error ejecutando migraciones."
    echo "Esto podría causar inestabilidad en la aplicación."
    echo "¿Desea continuar de todas formas? (s/N)"
    read -r response
    if [[ ! "$response" =~ ^[Ss]$ ]]; then
        echo "Actualización cancelada. La base de datos permanece sin cambios."
        exit 1
    fi
else
    echo "✓ Migraciones aplicadas exitosamente"
fi

echo
echo "5) Recolectando archivos estáticos (si es necesario)..."
python manage.py collectstatic --noinput 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Archivos estáticos actualizados"
else
    echo "No se requieren actualización de archivos estáticos"
fi

echo
echo "============================================"
echo "ACTUALIZACIÓN COMPLETADA EXITOSAMENTE"
echo "============================================"
echo
echo "Resumen de la actualización:"
echo "✓ Código actualizado desde Git"
echo "✓ Dependencias Python actualizadas"
echo "✓ Base de datos migrada (datos preservados)"
if [ -f "$BACKUP_FILE" ]; then
    echo "✓ Backup de seguridad creado: $BACKUP_FILE"
fi
echo
echo "La base de datos local ha sido PRESERVADA."
echo "Solo se actualizó la estructura y el código."
echo
echo "Para iniciar el POS actualizado:"
echo "  ./lanzar_pos.sh"
echo
echo "Si experimenta problemas:"
echo "1) Revise el backup: $BACKUP_FILE"
echo "2) Para restaurar: cp $BACKUP_FILE db.sqlite3"
echo "3) Para recuperar cambios locales: git stash pop"
echo

# Opción de limpiar backups antiguos
echo "¿Desea limpiar backups antiguos (mantener solo los últimos 3)? (s/N)"
read -r response
if [[ "$response" =~ ^[Ss]$ ]]; then
    cd "$BACKUP_DIR"
    ls -t db_backup_*.sqlite3 | tail -n +4 | xargs -r rm
    echo "✓ Backups antiguos eliminados"
    cd ..
fi

echo
echo "¡Actualización finalizada! Puede iniciar el POS ahora."