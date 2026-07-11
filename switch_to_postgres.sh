#!/bin/bash

# Script para cambiar de SQLite a PostgreSQL local
# SitioMTCRM - Sistema de Gestión

set -e

echo "=========================================="
echo "  Cambiar a PostgreSQL Local"
echo "  SitioMTCRM"
echo "=========================================="
echo

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar si PostgreSQL está instalado
if ! command -v psql &> /dev/null; then
    echo -e "${RED}ERROR: PostgreSQL no está instalado${NC}"
    echo
    echo "Instale PostgreSQL primero:"
    echo "  Ubuntu/Debian: sudo apt install postgresql postgresql-contrib"
    echo "  Arch Linux: sudo pacman -S postgresql"
    echo "  macOS: brew install postgresql@14"
    echo
    exit 1
fi

echo -e "${GREEN}✓ PostgreSQL encontrado${NC}"
echo

# Verificar si PostgreSQL está corriendo
if ! pg_isready &> /dev/null; then
    echo -e "${YELLOW}PostgreSQL no está corriendo. Intentando iniciarlo...${NC}"
    
    # Intentar iniciar según el sistema
    if command -v systemctl &> /dev/null; then
        sudo systemctl start postgresql
    elif command -v brew &> /dev/null; then
        brew services start postgresql@14
    else
        echo -e "${RED}ERROR: No se pudo iniciar PostgreSQL automáticamente${NC}"
        echo "Inicie PostgreSQL manualmente e intente nuevamente"
        exit 1
    fi
    
    # Esperar un momento
    sleep 2
    
    if ! pg_isready &> /dev/null; then
        echo -e "${RED}ERROR: PostgreSQL no se pudo iniciar${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ PostgreSQL iniciado${NC}"
    echo
fi

# Configuración de base de datos
echo "Configuración de PostgreSQL local:"
echo "-----------------------------------"
read -p "Nombre de la base de datos [sitiomtcrm]: " DB_NAME
DB_NAME=${DB_NAME:-sitiomtcrm}

read -p "Usuario de PostgreSQL [postgres]: " DB_USER
DB_USER=${DB_USER:-postgres}

read -s -p "Contraseña de PostgreSQL: " DB_PASSWORD
echo
echo

read -p "Host [localhost]: " DB_HOST
DB_HOST=${DB_HOST:-localhost}

read -p "Puerto [5432]: " DB_PORT
DB_PORT=${DB_PORT:-5432}

echo
echo -e "${YELLOW}Verificando conexión a PostgreSQL...${NC}"

# Verificar conexión (mostrar error si falla)
PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "SELECT 1;" > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: No se pudo conectar a PostgreSQL${NC}"
    echo
    echo "Detalles de la conexión:"
    echo "  Host: $DB_HOST"
    echo "  Puerto: $DB_PORT"
    echo "  Usuario: $DB_USER"
    echo "  Base de datos: postgres"
    echo
    echo "Verifique:"
    echo "  1. Que PostgreSQL esté corriendo: sudo systemctl status postgresql"
    echo "  2. Que el usuario y contraseña sean correctos"
    echo "  3. Que el host y puerto sean correctos"
    echo "  4. Que PostgreSQL acepte conexiones desde su dirección IP"
    echo
    echo "Pruebe manualmente:"
    echo "  PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres"
    exit 1
fi

echo -e "${GREEN}✓ Conexión exitosa${NC}"
echo

# Verificar si la base de datos existe
PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME';" | grep -q 1

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}La base de datos '$DB_NAME' no existe. Creándola...${NC}"
    PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
    echo -e "${GREEN}✓ Base de datos creada${NC}"
    echo
else
    echo -e "${GREEN}✓ Base de datos '$DB_NAME' ya existe${NC}"
    echo
fi

# Preguntar si desea migrar datos de SQLite
if [ -f "db.sqlite3" ]; then
    echo -e "${YELLOW}Se encontró base de datos SQLite (db.sqlite3)${NC}"
    read -p "¿Desea migrar los datos de SQLite a PostgreSQL? (s/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo -e "${YELLOW}Exportando datos de SQLite...${NC}"
        
        # Asegurar que usamos SQLite para el dumpdata
        unset USE_LOCAL_POSTGRES
        unset DB_NAME
        unset DB_USER
        unset DB_PASSWORD
        unset DB_HOST
        unset DB_PORT
        
        # Usar verbosity=0 para evitar salida de sincronización
        python manage.py dumpdata --verbosity=0 2>/dev/null > sqlite_backup.json
        
        if [ $? -eq 0 ]; then
            # Verificar que el archivo no esté vacío y sea JSON válido
            if [ -s "sqlite_backup.json" ]; then
                # Verificar que empiece con '[' (JSON array válido)
                if head -c 1 sqlite_backup.json | grep -q '\['; then
                    echo -e "${GREEN}✓ Datos exportados a sqlite_backup.json${NC}"
                else
                    echo -e "${RED}ERROR: El archivo exportado no contiene JSON válido${NC}"
                    echo "El archivo puede contener salida de sincronización en lugar de datos"
                    rm sqlite_backup.json
                    echo "Continuando sin migración de datos..."
                fi
            else
                echo -e "${YELLOW}ADVERTENCIA: El archivo exportado está vacío${NC}"
                echo "No hay datos para migrar"
                rm sqlite_backup.json
            fi
        else
            echo -e "${RED}ERROR al exportar datos de SQLite${NC}"
            echo "Continuando sin migración de datos..."
        fi
    fi
    echo
fi

# Configurar variables de entorno
echo "Configurando variables de entorno..."
echo

# Exportar variables de entorno para uso inmediato
export DB_NAME=$DB_NAME
export DB_USER=$DB_USER
export DB_PASSWORD=$DB_PASSWORD
export DB_HOST=$DB_HOST
export DB_PORT=$DB_PORT

# Crear archivo .env si no existe
if [ ! -f ".env" ]; then
    touch .env
fi

# Agregar o actualizar variables en .env
if grep -q "^DB_NAME=" .env; then
    sed -i "s/^DB_NAME=.*/DB_NAME=$DB_NAME/" .env
else
    echo "DB_NAME=$DB_NAME" >> .env
fi

if grep -q "^DB_USER=" .env; then
    sed -i "s/^DB_USER=.*/DB_USER=$DB_USER/" .env
else
    echo "DB_USER=$DB_USER" >> .env
fi

if grep -q "^DB_PASSWORD=" .env; then
    sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=$DB_PASSWORD/" .env
else
    echo "DB_PASSWORD=$DB_PASSWORD" >> .env
fi

if grep -q "^DB_HOST=" .env; then
    sed -i "s/^DB_HOST=.*/DB_HOST=$DB_HOST/" .env
else
    echo "DB_HOST=$DB_HOST" >> .env
fi

if grep -q "^DB_PORT=" .env; then
    sed -i "s/^DB_PORT=.*/DB_PORT=$DB_PORT/" .env
else
    echo "DB_PORT=$DB_PORT" >> .env
fi

echo -e "${GREEN}✓ Variables de entorno configuradas${NC}"
echo

# Ejecutar migraciones
echo -e "${YELLOW}Ejecutando migraciones en PostgreSQL...${NC}"

python manage.py migrate

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migraciones ejecutadas exitosamente${NC}"
else
    echo -e "${RED}ERROR al ejecutar migraciones${NC}"
    exit 1
fi
echo

# Importar datos si se exportaron
if [ -f "sqlite_backup.json" ]; then
    echo -e "${YELLOW}Importando datos a PostgreSQL...${NC}"
    python manage.py loaddata sqlite_backup.json
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Datos importados exitosamente${NC}"
        rm sqlite_backup.json
        echo -e "${GREEN}✓ Archivo de backup eliminado${NC}"
    else
        echo -e "${YELLOW}ADVERTENCIA: Algunos datos no pudieron importarse${NC}"
        echo "El archivo sqlite_backup.json se mantuvo para revisión manual"
    fi
    echo
fi

echo "=========================================="
echo -e "${GREEN}  ¡Cambio a PostgreSQL completado!${NC}"
echo "=========================================="
echo
echo "El sistema ahora usa PostgreSQL local."
echo "Puede iniciar el servidor con:"
echo "  ./lanzar_pos.sh"
echo
