#!/bin/bash

# Script para cambiar de PostgreSQL a SQLite local
# SitioMTCRM - Sistema de Gestión

set -e

echo "=========================================="
echo "  Cambiar a SQLite Local"
echo "  SitioMTCRM"
echo "=========================================="
echo

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Preguntar si desea migrar datos de PostgreSQL
read -p "¿Desea migrar los datos de PostgreSQL a SQLite? (s/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    echo -e "${YELLOW}Verificando configuración de PostgreSQL...${NC}"
    
    # Leer configuración actual de .env si existe
    if [ -f ".env" ]; then
        DB_NAME=$(grep "^DB_NAME=" .env | cut -d '=' -f2)
        DB_USER=$(grep "^DB_USER=" .env | cut -d '=' -f2)
        DB_PASSWORD=$(grep "^DB_PASSWORD=" .env | cut -d '=' -f2)
        DB_HOST=$(grep "^DB_HOST=" .env | cut -d '=' -f2)
        DB_PORT=$(grep "^DB_PORT=" .env | cut -d '=' -f2)
        
        # Valores por defecto si no están en .env
        DB_NAME=${DB_NAME:-sitiomtcrm}
        DB_USER=${DB_USER:-postgres}
        DB_HOST=${DB_HOST:-localhost}
        DB_PORT=${DB_PORT:-5432}
    else
        echo -e "${YELLOW}No se encontró archivo .env${NC}"
        echo "Configuración de PostgreSQL:"
        read -p "Nombre de la base de datos [sitiomtcrm]: " DB_NAME
        DB_NAME=${DB_NAME:-sitiomtcrm}
        read -p "Usuario de PostgreSQL [postgres]: " DB_USER
        DB_USER=${DB_USER:-postgres}
        read -s -p "Contraseña de PostgreSQL: " DB_PASSWORD
        echo
        read -p "Host [localhost]: " DB_HOST
        DB_HOST=${DB_HOST:-localhost}
        read -p "Puerto [5432]: " DB_PORT
        DB_PORT=${DB_PORT:-5432}
    fi
    
    echo -e "${YELLOW}Verificando conexión a PostgreSQL...${NC}"
    
    # Verificar conexión
    PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: No se pudo conectar a PostgreSQL${NC}"
        echo "Verifique las credenciales y que PostgreSQL esté corriendo"
        echo "Continuando sin migración de datos..."
    else
        echo -e "${GREEN}✓ Conexión exitosa${NC}"
        echo
        echo -e "${YELLOW}Exportando datos de PostgreSQL...${NC}"
        
        # Exportar datos con variables de entorno de PostgreSQL
        export USE_LOCAL_POSTGRES=true
        export DB_NAME=$DB_NAME
        export DB_USER=$DB_USER
        export DB_PASSWORD=$DB_PASSWORD
        export DB_HOST=$DB_HOST
        export DB_PORT=$DB_PORT
        
        python manage.py dumpdata > postgres_backup.json
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Datos exportados a postgres_backup.json${NC}"
        else
            echo -e "${RED}ERROR al exportar datos de PostgreSQL${NC}"
            echo "Continuando sin migración de datos..."
        fi
    fi
    echo
fi

# Configurar variables de entorno para SQLite
echo "Configurando variables de entorno para SQLite..."
echo

# Crear archivo .env si no existe
if [ ! -f ".env" ]; then
    touch .env
fi

# Actualizar USE_LOCAL_POSTGRES a false
if grep -q "USE_LOCAL_POSTGRES" .env; then
    sed -i "s/USE_LOCAL_POSTGRES=.*/USE_LOCAL_POSTGRES=false/" .env
else
    echo "USE_LOCAL_POSTGRES=false" >> .env
fi

echo -e "${GREEN}✓ Variables de entorno configuradas${NC}"
echo

# Ejecutar migraciones en SQLite
echo -e "${YELLOW}Ejecutando migraciones en SQLite...${NC}"
unset USE_LOCAL_POSTGRES
unset DB_NAME
unset DB_USER
unset DB_PASSWORD
unset DB_HOST
unset DB_PORT

python manage.py migrate

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Migraciones ejecutadas exitosamente${NC}"
else
    echo -e "${RED}ERROR al ejecutar migraciones${NC}"
    exit 1
fi
echo

# Importar datos si se exportaron
if [ -f "postgres_backup.json" ]; then
    echo -e "${YELLOW}Importando datos a SQLite...${NC}"
    python manage.py loaddata postgres_backup.json
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Datos importados exitosamente${NC}"
        rm postgres_backup.json
        echo -e "${GREEN}✓ Archivo de backup eliminado${NC}"
    else
        echo -e "${YELLOW}ADVERTENCIA: Algunos datos no pudieron importarse${NC}"
        echo "El archivo postgres_backup.json se mantuvo para revisión manual"
    fi
    echo
fi

echo "=========================================="
echo -e "${GREEN}  ¡Cambio a SQLite completado!${NC}"
echo "=========================================="
echo
echo "El sistema ahora usa SQLite local."
echo "Puede iniciar el servidor con:"
echo "  ./lanzar_pos.sh"
echo
