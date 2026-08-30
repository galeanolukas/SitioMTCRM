#!/bin/bash

# Instalador POS Local - SitioMTCRM (Linux)
# Crea entorno, dependencias, DB PostgreSQL por defecto y migraciones.

cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# Configuración por defecto de PostgreSQL
# ---------------------------------------------------------------------------
# Usuario y contraseña del SUPERUSUARIO postgresql (para crear el usuario app)
DEFAULT_POSTGRES_USER="postgres"
DEFAULT_POSTGRES_PASS="postgres"

# Usuario y contraseña DEDICADO para la aplicación (se creará en PostgreSQL)
DEFAULT_DB_NAME="mtcrm_pos"
DEFAULT_DB_USER="mtcrm_pos"
DEFAULT_DB_PASS="mtcrm_pos"
DEFAULT_DB_HOST="localhost"
DEFAULT_DB_PORT="5432"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================"
echo "  Instalador POS Local - TechVentas"
echo "  (Linux / macOS)"
echo "============================================"
echo -e "${NC}"

# ---------------------------------------------------------------------------
# 1) Verificar Python
# ---------------------------------------------------------------------------
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python3 no está instalado.${NC}"
    echo "Instale Python3 con:"
    echo "  sudo apt update && sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

# ---------------------------------------------------------------------------
# 2) Verificar / instalar PostgreSQL
# ---------------------------------------------------------------------------
PG_READY=false
if command -v psql &> /dev/null; then
    echo -e "${GREEN}✓ PostgreSQL detectado.${NC}"
    PG_READY=true
else
    echo -e "${YELLOW}[ADVERTENCIA] PostgreSQL (psql) no detectado.${NC}"
    echo "Intentando instalar PostgreSQL..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y postgresql postgresql-contrib || true
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y postgresql-server postgresql-contrib || true
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm postgresql || true
    else
        echo -e "${RED}[ERROR] No se encontró un gestor de paquetes soportado para instalar PostgreSQL.${NC}"
    fi
    if command -v psql &> /dev/null; then
        PG_READY=true
    else
        echo -e "${RED}[ERROR] No se pudo instalar PostgreSQL automáticamente.${NC}"
        echo "Instálelo manualmente y vuelva a ejecutar el instalador."
        exit 1
    fi
fi

# Asegurar que el servicio esté corriendo
if command -v systemctl &> /dev/null; then
    sudo systemctl start postgresql || true
    sudo systemctl enable postgresql || true
fi

# ---------------------------------------------------------------------------
# 3) Crear usuario / DB con superusuario PostgreSQL
# ---------------------------------------------------------------------------
# Esta función crea un usuario y DB dedicados para la app.
# Pide la contraseña del superusuario postgres si no puede conectarse.

setup_postgres() {
    local PG_USER="$1"
    local PG_PASS="$2"
    local DB_NAME="$3"
    local DB_USER="$4"
    local DB_PASS="$5"
    local PGSQL_SUPER_OK=false

    # Función auxiliar para ejecutar SQL como superusuario
    run_as_super() {
        local SQL="$1"
        if sudo -n -u postgres psql -c "$SQL" &> /dev/null; then
            return 0
        fi
        export PGPASSWORD="$PG_PASS"
        if psql -U "$PG_USER" -h "$DEFAULT_DB_HOST" -p "$DEFAULT_DB_PORT" -c "$SQL" &> /dev/null; then
            unset PGPASSWORD
            return 0
        fi
        unset PGPASSWORD
        return 1
    }

    # 3.1) Probar peer auth (sudo -u postgres)
    if sudo -n -u postgres psql -c "SELECT 1;" &> /dev/null; then
        PGSQL_SUPER_OK=true
        echo -e "${GREEN}✓ Conectado a PostgreSQL como superusuario (peer auth).${NC}"
    fi

    # 3.2) Probar conexión por red con contraseña por defecto
    if [ "$PGSQL_SUPER_OK" = false ]; then
        export PGPASSWORD="$PG_PASS"
        if psql -U "$PG_USER" -h "$DEFAULT_DB_HOST" -p "$DEFAULT_DB_PORT" -c "SELECT 1;" &> /dev/null; then
            PGSQL_SUPER_OK=true
            echo -e "${GREEN}✓ Conectado a PostgreSQL como superusuario (password auth).${NC}"
        fi
        unset PGPASSWORD
    fi

    # 3.3) Si nada funcionó, pedir contraseña del superusuario
    if [ "$PGSQL_SUPER_OK" = false ]; then
        echo -e "${YELLOW}No se pudo conectar al superusuario '$PG_USER' con la contraseña por defecto.${NC}"
        read -sp "Ingrese la contraseña del superusuario PostgreSQL [$PG_USER]: " PG_PASS_INPUT
        echo
        PG_PASS_INPUT="${PG_PASS_INPUT:-$PG_PASS}"
        export PGPASSWORD="$PG_PASS_INPUT"
        if psql -U "$PG_USER" -h "$DEFAULT_DB_HOST" -p "$DEFAULT_DB_PORT" -c "SELECT 1;" &> /dev/null; then
            PGSQL_SUPER_OK=true
            DEFAULT_POSTGRES_PASS="$PG_PASS_INPUT"
            echo -e "${GREEN}✓ Conectado con la contraseña ingresada.${NC}"
        else
            unset PGPASSWORD
            echo -e "${RED}[ERROR] No se pudo conectar a PostgreSQL. Verifique las credenciales.${NC}"
            return 1
        fi
    fi

    # 3.4) Ejecutar SQL: crear usuario app y base de datos
    # Eliminar DB si existe para evitar conflictos, luego crear nueva.
    local SUPER_SQL
    SUPER_SQL=$(cat << SQL
DO
\$do\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
        CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASS';
    ELSE
        ALTER ROLE $DB_USER WITH PASSWORD '$DB_PASS';
    END IF;
END
\$do\$;

SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME';
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME OWNER $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
SQL
)

    if sudo -n -u postgres psql -c "$SUPER_SQL" &> /dev/null; then
        echo -e "${GREEN}✓ Base de datos '$DB_NAME' y usuario '$DB_USER' creados.${NC}"
        return 0
    fi

    export PGPASSWORD="$DEFAULT_POSTGRES_PASS"
    if psql -U "$PG_USER" -h "$DEFAULT_DB_HOST" -p "$DEFAULT_DB_PORT" -c "$SUPER_SQL" &> /dev/null; then
        unset PGPASSWORD
        echo -e "${GREEN}✓ Base de datos '$DB_NAME' y usuario '$DB_USER' creados.${NC}"
        return 0
    fi
    unset PGPASSWORD

    echo -e "${RED}[ERROR] No se pudo crear la base de datos o el usuario de la aplicación.${NC}"
    return 1
}

setup_postgres "$DEFAULT_POSTGRES_USER" "$DEFAULT_POSTGRES_PASS" "$DEFAULT_DB_NAME" "$DEFAULT_DB_USER" "$DEFAULT_DB_PASS"
if [ $? -ne 0 ]; then
    exit 1
fi

# ---------------------------------------------------------------------------
# 4) Crear / actualizar .env con credenciales de la APP (no del superusuario)
# ---------------------------------------------------------------------------
echo "Configurando archivo .env..."
if [ ! -f ".env" ]; then
    cat > .env <<EOENV
# Entorno
ENVIRONMENT=development
APP_VERSION=1.0.0
POS_SYNC_INTERVAL_SECONDS=300

# Base de datos local (PostgreSQL) - usuario DEDICADO de la app
DB_NAME=$DEFAULT_DB_NAME
DB_USER=$DEFAULT_DB_USER
DB_PASSWORD=$DEFAULT_DB_PASS
DB_HOST=$DEFAULT_DB_HOST
DB_PORT=$DEFAULT_DB_PORT

# Base de datos remota (servidor central) - completar si aplica
REMOTE_DB_NAME=
REMOTE_DB_USER=
REMOTE_DB_PASSWORD=
REMOTE_DB_HOST=
REMOTE_DB_PORT=5432
REMOTE_DB_SSLMODE=require

# Configuración sincronización
POS_SYNC_PRODUCTS_MODE=safe

# AFIP
AFIP_ACCESS_TOKEN=
AFIP_CUIT=
AFIP_ENVIRONMENT=dev

# Catálogo
CATALOGO_URL=
CATALOGO_API_KEY=
EOENV
else
    python3 - <<'PY'
import re, os
env_file = '.env'
if not os.path.exists(env_file):
    open(env_file, 'w').close()
with open(env_file, 'r') as f:
    content = f.read()

def set_var(name, value, content):
    pattern = r'^{}=.*$'.format(re.escape(name))
    line = '{}={}'.format(name, value)
    if re.search(pattern, content, flags=re.MULTILINE):
        return re.sub(pattern, line, content, flags=re.MULTILINE)
    return content + '\n' + line

content = set_var('DB_NAME', 'mtcrm_pos', content)
content = set_var('DB_USER', 'mtcrm_pos', content)
content = set_var('DB_PASSWORD', 'mtcrm_pos', content)
content = set_var('DB_HOST', 'localhost', content)
content = set_var('DB_PORT', '5432', content)
with open(env_file, 'w') as f:
    f.write(content)
PY
fi

echo -e "${GREEN}✓ Archivo .env configurado para PostgreSQL local.${NC}"

# ---------------------------------------------------------------------------
# 5) Crear / verificar entorno virtual
# ---------------------------------------------------------------------------
RECREATE_VENV=false
if [ ! -d "DJENV" ]; then
    echo "Creando entorno virtual DJENV..."
    RECREATE_VENV=true
else
    if ! DJENV/bin/python -c "from django.db.migrations.migration import Migration" &>/dev/null; then
        echo "Entorno virtual DJENV dañado. Recreando..."
        rm -rf DJENV
        RECREATE_VENV=true
    else
        echo -e "${GREEN}✓ Entorno virtual DJENV existente.${NC}"
    fi
fi

if [ "$RECREATE_VENV" = true ]; then
    python3 -m venv DJENV || { echo -e "${RED}[ERROR] No se pudo crear el entorno virtual.${NC}"; exit 1; }
fi

source DJENV/bin/activate || { echo -e "${RED}[ERROR] No se pudo activar el entorno virtual.${NC}"; exit 1; }

# ---------------------------------------------------------------------------
# 6) Instalar dependencias
# ---------------------------------------------------------------------------
echo "Actualizando pip..."
python -m pip install --upgrade pip &> /dev/null

echo "Instalando dependencias desde requirements.txt..."
pip uninstall -y pandas-openpyxl &> /dev/null || true
pip install -r requirements.txt || { echo -e "${RED}[ERROR] Fallo instalando requerimientos.${NC}"; exit 1; }

echo -e "${GREEN}✓ Dependencias instaladas.${NC}"

# ---------------------------------------------------------------------------
# 7) Generar icono PNG si no existe
# ---------------------------------------------------------------------------
if [ -f "icon.ico" ] && [ ! -f "icon.png" ]; then
    echo "Generando icon.png desde icon.ico..."
    python - <<'PY'
try:
    from PIL import Image
    img = Image.open('icon.ico')
    # Guardar en un tamaño común
    for size in [(128, 128)]:
        ico = img.resize(size, Image.Resampling.LANCZOS)
        ico.save('icon.png')
    print('icon.png generado.')
except Exception as e:
    print('No se pudo generar icon.png:', e)
PY
fi

# ---------------------------------------------------------------------------
# 8) Migraciones y datos iniciales
# ---------------------------------------------------------------------------
echo "Creando migraciones..."
python manage.py makemigrations user erp || { echo -e "${RED}[ERROR] makemigrations falló.${NC}"; exit 1; }

echo "Aplicando migraciones..."
python manage.py migrate || { echo -e "${RED}[ERROR] migrate falló.${NC}"; exit 1; }

echo -e "${GREEN}✓ Migraciones aplicadas.${NC}"

# ---------------------------------------------------------------------------
# 9) Superusuario y roles
# ---------------------------------------------------------------------------
echo "Verificando superusuario..."
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('SUPERUSER_CREATED')
else:
    print('SUPERUSER_EXISTS')
" 2>/dev/null | grep -q 'SUPERUSER_CREATED' && \
    echo -e "${GREEN}✓ Superusuario creado: admin / admin123${NC}" || \
    echo -e "${GREEN}✓ Superusuario ya existe.${NC}"

echo "Configurando roles estándar..."
python manage.py setup_roles --migrate || \
    echo -e "${YELLOW}[ADVERTENCIA] setup_roles falló; ejecute manualmente: python manage.py setup_roles --migrate${NC}"

# ---------------------------------------------------------------------------
# 10) Acceso directo en escritorio
# ---------------------------------------------------------------------------
LAUNCHER_TARGET="$(pwd)/lanzar_pos.sh"
DESKTOP_DIR="$HOME/Desktop"
SHORTCUT_PATH="$DESKTOP_DIR/POS_Local.desktop"
ICON_FILE="$(pwd)/icon.png"
[ ! -f "$ICON_FILE" ] && ICON_FILE="$(pwd)/icon.ico"

if [ -f "$LAUNCHER_TARGET" ]; then
    mkdir -p "$DESKTOP_DIR"
    cat > "$SHORTCUT_PATH" << EOD
[Desktop Entry]
Version=1.0
Type=Application
Name=TechVentas POS Local
Comment=Iniciar el POS local de TechVentas
Exec=$LAUNCHER_TARGET
Icon=$ICON_FILE
Path=$(pwd)
Terminal=true
Categories=Office;Business;
EOD
    chmod +x "$SHORTCUT_PATH"
    echo -e "${GREEN}✓ Acceso directo creado: $SHORTCUT_PATH${NC}"
else
    echo -e "${YELLOW}[ADVERTENCIA] No se encontró lanzar_pos.sh. No se creó acceso directo.${NC}"
fi

# ---------------------------------------------------------------------------
# 11) Final
# ---------------------------------------------------------------------------
echo
echo -e "${CYAN}============================================"
echo "  INSTALACIÓN COMPLETADA"
echo "============================================"
echo -e "${NC}"
echo "Base de datos: $DEFAULT_DB_NAME ($DEFAULT_DB_HOST:$DEFAULT_DB_PORT)"
echo "Usuario DB:    $DEFAULT_DB_USER"
echo "Contraseña DB: $DEFAULT_DB_PASS"
echo
echo "Para iniciar el POS:"
echo "  ./lanzar_pos.sh"
echo "  o use el acceso directo del escritorio."
echo
echo "URL del sistema: http://localhost:8000/erp/launcher/"
echo "URL del POS:     http://localhost:8000/erp/sale/pos/"
echo

read -p "¿Desea iniciar el POS ahora? (s/n): " start_now
if [[ $start_now =~ ^[Ss]$ ]]; then
    exec ./lanzar_pos.sh
else
    read -p "Presione Enter para continuar..."
fi
