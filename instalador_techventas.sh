#!/bin/bash

# Instalador TechVentas - Bootstrap Linux para TechVentas POS
# Verifica git, clona el repositorio y ejecuta instalador_pos.sh

set -e

REPO_URL="https://github.com/galeanolukas/SitioMTCRM.git"
REPO_DIR="SitioMTCRM"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

cd "$(dirname "$0")"

echo -e "${CYAN}============================================"
echo "  Instalador TechVentas - Bootstrap Linux"
echo "============================================"
echo -e "${NC}"

# ---------------------------------------------------------------------------
# 1) Verificar / instalar git
# ---------------------------------------------------------------------------
if command -v git &> /dev/null; then
    echo -e "${GREEN}✓ Git detectado: $(git --version)${NC}"
else
    echo -e "${YELLOW}[ADVERTENCIA] Git no está instalado.${NC}"
    echo "Intentando instalar Git..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y git
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y git
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm git
    elif command -v yum &> /dev/null; then
        sudo yum install -y git
    elif command -v zypper &> /dev/null; then
        sudo zypper install -y git
    else
        echo -e "${RED}[ERROR] No se encontró un gestor de paquetes soportado.${NC}"
        echo "Instale Git manualmente y vuelva a ejecutar este script."
        exit 1
    fi
    if ! command -v git &> /dev/null; then
        echo -e "${RED}[ERROR] No se pudo instalar Git automáticamente.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Git instalado: $(git --version)${NC}"
fi

# ---------------------------------------------------------------------------
# 2) Clonar repositorio
# ---------------------------------------------------------------------------
if [ -d "$REPO_DIR" ]; then
    echo -e "${YELLOW}La carpeta $REPO_DIR ya existe.${NC}"
    read -rp "¿Desea eliminarla y clonar de nuevo? (s/n) [n]: " reclone
    if [[ $reclone =~ ^[Ss]$ ]]; then
        echo "Eliminando $REPO_DIR..."
        rm -rf "$REPO_DIR"
    else
        echo "Continuando con la carpeta existente."
    fi
fi

if [ ! -d "$REPO_DIR" ]; then
    echo "Clonando repositorio desde $REPO_URL..."
    git clone "$REPO_URL" "$REPO_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] No se pudo clonar el repositorio.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Repositorio clonado en: $(pwd)/$REPO_DIR${NC}"
fi

# ---------------------------------------------------------------------------
# 3) Ejecutar instalador_pos.sh (maneja PostgreSQL, .env, venv, migraciones, .desktop)
# ---------------------------------------------------------------------------
cd "$REPO_DIR"
if [ ! -f "instalador_pos.sh" ]; then
    echo -e "${RED}[ERROR] No se encontró instalador_pos.sh en $REPO_DIR${NC}"
    exit 1
fi

chmod +x instalador_pos.sh
echo "Ejecutando instalador_pos.sh..."
./instalador_pos.sh
exit $?
