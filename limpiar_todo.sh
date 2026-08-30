#!/bin/bash
# Script para limpiar el proyecto y dejarlo listo para una instalación desde cero.
# Útil para resetear el POS local y volver a ejecutar el instalador.

set -euo pipefail

cd "$(dirname "$0")"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuración por defecto (coincide con instalador_pos.sh/bat)
DEFAULT_DB_NAME="mtcrm_pos"
DEFAULT_DB_USER="postgres"
DEFAULT_DB_PASS="postgres"
DEFAULT_DB_HOST="localhost"
DEFAULT_DB_PORT="5432"

clear
echo -e "${CYAN}============================================"
echo "  LIMPIEZA COMPLETA - SitioMTCRM / TechVentas"
echo "============================================"
echo -e "${NC}"
echo "Este script prepara el proyecto para una instalación desde cero."
echo "Se eliminarán:"
echo "  - Base de datos local (SQLite o PostgreSQL)"
echo "  - Entorno virtual DJENV"
echo "  - Configuración .env"
echo "  - Archivos estáticos recolectados"
echo "  - Caché, logs y archivos temporales"
echo "  - Archivos de media (imágenes subidas)"
echo
echo -e "${YELLOW}⚠️  ATENCIÓN: Se perderán TODOS los datos locales.${NC}"
echo
echo "Para continuar escriba:  BORRAR TODO"
read -rp "Confirmación: " confirm

if [ "$confirm" != "BORRAR TODO" ]; then
    echo "Operación cancelada."
    exit 0
fi

echo
echo -e "${CYAN}Iniciando limpieza...${NC}"
echo

# ---------------------------------------------------------------------------
# 1. Detener servidor Django si está corriendo
# ---------------------------------------------------------------------------
echo "[1/8] Verificando procesos del servidor..."
if pgrep -f "manage.py runserver" > /dev/null; then
    echo "  Deteniendo servidor Django..."
    pkill -f "manage.py runserver" || true
    sleep 2
fi

# ---------------------------------------------------------------------------
# 2. Leer credenciales de .env (si existe) para PostgreSQL
# ---------------------------------------------------------------------------
DB_NAME="$DEFAULT_DB_NAME"
DB_USER="$DEFAULT_DB_USER"
DB_PASS="$DEFAULT_DB_PASS"
DB_HOST="$DEFAULT_DB_HOST"
DB_PORT="$DEFAULT_DB_PORT"

if [ -f ".env" ]; then
    # Extraer valores del .env, ignorando comentarios y espacios
    while IFS='=' read -r key value; do
        # Limpiar espacios al inicio/final
        key=$(echo "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        case "$key" in
            DB_NAME) DB_NAME="$value" ;;
            DB_USER) DB_USER="$value" ;;
            DB_PASSWORD) DB_PASS="$value" ;;
            DB_HOST) DB_HOST="$value" ;;
            DB_PORT) DB_PORT="$value" ;;
        esac
    done < .env
fi

# ---------------------------------------------------------------------------
# 3. Eliminar base de datos
# ---------------------------------------------------------------------------
echo "[2/8] Eliminando base de datos..."

# SQLite
if [ -f "db.sqlite3" ]; then
    rm -f db.sqlite3
    echo -e "  ${GREEN}✓ Eliminada db.sqlite3${NC}"
fi

# PostgreSQL: intentar eliminar la BD si existe
if command -v psql &> /dev/null; then
    # Primer intento: peer auth con sudo
    if sudo -n -u postgres psql -c "SELECT 1;" &> /dev/null; then
        if sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME';" 2>/dev/null | grep -q 1; then
            sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME';" 2>/dev/null || true
            sudo -u postgres psql -c "DROP DATABASE $DB_NAME;" 2>/dev/null && \
                echo -e "  ${GREEN}✓ Base de datos PostgreSQL '$DB_NAME' eliminada (peer auth)${NC}" || \
                echo -e "  ${YELLOW}⚠ No se pudo eliminar la BD PostgreSQL '$DB_NAME'${NC}"
        fi
    else
        # Segundo intento: autenticación por red con PGPASSWORD
        export PGPASSWORD="$DB_PASS"
        psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -c "SELECT 1;" &> /dev/null && {
            if psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME';" 2>/dev/null | grep -q 1; then
                psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME';" 2>/dev/null || true
                psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -c "DROP DATABASE $DB_NAME;" 2>/dev/null && \
                    echo -e "  ${GREEN}✓ Base de datos PostgreSQL '$DB_NAME' eliminada${NC}" || \
                    echo -e "  ${YELLOW}⚠ No se pudo eliminar la BD PostgreSQL '$DB_NAME'${NC}"
            fi
        } || true
        unset PGPASSWORD
    fi
fi

# ---------------------------------------------------------------------------
# 4. Eliminar entorno virtual
# ---------------------------------------------------------------------------
echo "[3/8] Eliminando entorno virtual..."
if [ -d "DJENV" ]; then
    rm -rf DJENV
    echo -e "  ${GREEN}✓ DJENV eliminado${NC}"
fi

# ---------------------------------------------------------------------------
# 5. Eliminar configuración .env
# ---------------------------------------------------------------------------
echo "[4/8] Eliminando configuración .env..."
if [ -f ".env" ]; then
    rm -f .env
    echo -e "  ${GREEN}✓ .env eliminado${NC}"
fi

# ---------------------------------------------------------------------------
# 6. Eliminar archivos estáticos recolectados y caché
# ---------------------------------------------------------------------------
echo "[5/8] Eliminando archivos estáticos y caché..."
if [ -d "staticfiles" ]; then
    rm -rf staticfiles
    echo -e "  ${GREEN}✓ staticfiles eliminado${NC}"
fi

find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -not -path "./.git/*" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -not -path "./.git/*" -delete 2>/dev/null || true
find . -type d -name ".pytest_cache" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true

# Limpiar caché de Pillow o archivos temporales de weasyprint
find . -type d -name ".cache" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true

echo -e "  ${GREEN}✓ Caché de Python eliminada${NC}"

# ---------------------------------------------------------------------------
# 7. Eliminar logs, temporales y media
# ---------------------------------------------------------------------------
echo "[6/8] Eliminando logs, temporales y media..."
find . -type f -name "*.log" -not -path "./.git/*" -delete 2>/dev/null || true
find . -type f -name "*.tmp" -not -path "./.git/*" -delete 2>/dev/null || true
find . -type f -name ".DS_Store" -not -path "./.git/*" -delete 2>/dev/null || true

# Logs y cache en carpetas del proyecto
if [ -d "log" ]; then
    rm -rf log/*
    echo -e "  ${GREEN}✓ Carpeta log limpiada${NC}"
fi
if [ -d "cache" ]; then
    rm -rf cache/*
    echo -e "  ${GREEN}✓ Carpeta cache limpiada${NC}"
fi

# Media: imágenes subidas
if [ -d "media" ]; then
    rm -rf media/*
    echo -e "  ${GREEN}✓ Carpeta media limpiada${NC}"
fi

# ---------------------------------------------------------------------------
# 8. Eliminar accesos directos del escritorio (opcional)
# ---------------------------------------------------------------------------
echo "[7/8] Eliminando accesos directos antiguos..."
if [ -f "$HOME/Desktop/POS_Local.desktop" ]; then
    rm -f "$HOME/Desktop/POS_Local.desktop"
    echo -e "  ${GREEN}✓ Acceso directo POS_Local.desktop eliminado${NC}"
fi

# ---------------------------------------------------------------------------
# 9. Eliminar icono PNG generado (se regenerará en la instalación)
# ---------------------------------------------------------------------------
echo "[8/8] Eliminando iconos generados..."
if [ -f "icon.png" ]; then
    rm -f icon.png
    echo -e "  ${GREEN}✓ icon.png eliminado${NC}"
fi

echo
echo -e "${GREEN}============================================"
echo "  LIMPIEZA COMPLETADA"
echo "============================================"
echo -e "${NC}"
echo "El proyecto está listo para una instalación desde cero."
echo
echo "Ejecute ahora el instalador correspondiente:"
echo "  - Linux:   ./instalador_pos.sh"
echo "  - Windows: instalador_pos.bat"
echo
echo "Si PostgreSQL ya está instalado, el instalador creará la base de datos"
echo "'mtcrm_pos' con el usuario 'postgres' y contraseña 'postgres'."
echo
