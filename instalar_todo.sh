#!/bin/bash

# ===========================================================================
# Instalador completo (bootstrap) - SitioMTCRM / TechVentas (Linux)
# ===========================================================================
# Este script:
#   1. Verifica/instala git con el gestor de paquetes del sistema
#   2. Clona el repositorio desde GitHub
#   3. Verifica python3, python3-venv, python3-pip
#   4. Llama a instalador_pos.sh dentro del repositorio clonado
# ===========================================================================

set -e

REPO_URL="https://github.com/galeanolukas/SitioMTCRM.git"
REPO_DIR="SitioMTCRM"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}============================================"
echo "  Instalador Completo - TechVentas"
echo "  (Linux - Bootstrap)"
echo -e "============================================"
echo -e "${NC}"
echo "Este script:"
echo "  1. Verifica/instala git"
echo "  2. Clona el repositorio desde GitHub"
echo "  3. Verifica python3 y dependencias del sistema"
echo "  4. Ejecuta el instalador base del proyecto"
echo ""

# ---------------------------------------------------------------------------
# 1) Verificar / instalar git
# ---------------------------------------------------------------------------
if command -v git &> /dev/null; then
    echo -e "${GREEN}✓ Git detectado: $(git --version)${NC}"
else
    echo -e "${YELLOW}[ADVERTENCIA] Git no está instalado.${NC}"
    echo "Intentando instalar git..."

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
    elif command -v apk &> /dev/null; then
        sudo apk add git
    else
        echo -e "${RED}[ERROR] No se encontró un gestor de paquetes soportado.${NC}"
        echo "Instale git manualmente y vuelva a ejecutar este script."
        exit 1
    fi

    if ! command -v git &> /dev/null; then
        echo -e "${RED}[ERROR] No se pudo instalar git.${NC}"
        echo "Instálelo manualmente y vuelva a ejecutar este script."
        exit 1
    fi
    echo -e "${GREEN}✓ Git instalado: $(git --version)${NC}"
fi

# ---------------------------------------------------------------------------
# 2) Clonar repositorio (si no estamos ya dentro del repo)
# ---------------------------------------------------------------------------
if [ -f "instalador_pos.sh" ]; then
    echo -e "${GREEN}✓ Ya estamos dentro del repositorio. Se omite el clon.${NC}"
    REPO_DIR="."
elif [ -f "${REPO_DIR}/instalador_pos.sh" ]; then
    echo -e "${GREEN}✓ El repositorio ya existe en ${REPO_DIR}/. Se omite el clon.${NC}"
else
    echo ""
    echo "--- Clonando repositorio ---"
    echo "    URL: ${REPO_URL}"
    echo "    Dir: ${REPO_DIR}/"
    git clone "${REPO_URL}" "${REPO_DIR}"
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] No se pudo clonar el repositorio.${NC}"
        echo "  Verifique la conexión a internet."
        exit 1
    fi
    echo -e "${GREEN}✓ Repositorio clonado en ${REPO_DIR}/${NC}"
fi

# ---------------------------------------------------------------------------
# 3) Verificar python3 y dependencias del sistema
# ---------------------------------------------------------------------------
echo ""
echo "--- Verificando Python3 y dependencias ---"

NEED_INSTALL=false

if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}[ADVERTENCIA] Python3 no está instalado.${NC}"
    NEED_INSTALL=true
fi

# Verificar python3-venv y python3-pip (requeridos por instalador_pos.sh)
if command -v python3 &> /dev/null; then
    if ! python3 -m venv --help &> /dev/null; then
        echo -e "${YELLOW}[ADVERTENCIA] python3-venv no está disponible.${NC}"
        NEED_INSTALL=true
    fi
    if ! python3 -m pip --version &> /dev/null; then
        echo -e "${YELLOW}[ADVERTENCIA] python3-pip no está disponible.${NC}"
        NEED_INSTALL=true
    fi
fi

if [ "$NEED_INSTALL" = true ]; then
    echo "Instalando Python3 y dependencias..."

    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv python3-pip python3-dev
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3 python3-devel
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm python python-pip
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3 python3-devel
    elif command -v zypper &> /dev/null; then
        sudo zypper install -y python3 python3-devel
    elif command -v apk &> /dev/null; then
        sudo apk add python3 py3-pip
    else
        echo -e "${RED}[ERROR] No se encontró un gestor de paquetes soportado.${NC}"
        echo "Instale Python3, python3-venv y python3-pip manualmente."
        exit 1
    fi

    # Verificar nuevamente
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}[ERROR] No se pudo instalar Python3.${NC}"
        echo "Instálelo manualmente: sudo apt install python3 python3-venv python3-pip"
        exit 1
    fi
    echo -e "${GREEN}✓ Python3 instalado: $(python3 --version)${NC}"
else
    echo -e "${GREEN}✓ Python3 OK: $(python3 --version)${NC}"
fi

# Verificar que venv y pip funcionan
if ! python3 -m venv --help &> /dev/null; then
    echo -e "${RED}[ERROR] python3-venv no funciona. Instale con:${NC}"
    echo "  sudo apt install python3-venv"
    exit 1
fi

# ---------------------------------------------------------------------------
# 4) Llamar al instalador base del proyecto
# ---------------------------------------------------------------------------
echo ""
echo -e "${CYAN}============================================"
echo "  Llamando al instalador base del proyecto"
echo -e "============================================"
echo -e "${NC}"

cd "${REPO_DIR}"

if [ ! -f "instalador_pos.sh" ]; then
    echo -e "${RED}[ERROR] No se encontró instalador_pos.sh en el directorio actual.${NC}"
    echo "  Directorio: $(pwd)"
    exit 1
fi

chmod +x instalador_pos.sh
./instalador_pos.sh
INSTALL_RESULT=$?

if [ $INSTALL_RESULT -ne 0 ]; then
    echo ""
    echo -e "${RED}[ERROR] El instalador base finalizó con errores (código: $INSTALL_RESULT).${NC}"
    exit $INSTALL_RESULT
fi

echo ""
echo -e "${CYAN}============================================"
echo "  INSTALACIÓN COMPLETA"
echo -e "============================================"
echo -e "${NC}"
