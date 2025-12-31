#!/bin/bash
# Script completo para migración de tablas de transferencias
# Ejecutar en servidor remoto con: bash migrate_transfer_tables.sh

echo "🔧 Iniciando migración de tablas de transferencias..."

# Configuración (ajusta estos valores)
PROJECT_PATH="/ruta/a/tu/proyecto"  # ← CAMBIAR ESTO
VENV_NAME="venv"                    # ← CAMBIAR ESTO

# Navegar al proyecto
cd "$PROJECT_PATH" || {
    echo "❌ No se encontró el proyecto en: $PROJECT_PATH"
    exit 1
}

# Activar entorno virtual
if [ -d "$VENV_NAME" ]; then
    source "$VENV_NAME/bin/activate"
    echo "✅ Entorno virtual activado"
else
    echo "❌ No se encontró el entorno virtual: $VENV_NAME"
    exit 1
}

# Crear script Python para migración
cat > migrate_transfer.py << 'EOF'
#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from django.db.utils import ProgrammingError

def create_transfer_tables():
    try:
        with connection.cursor() as cursor:
            db_vendor = connection.vendor
            print(f"🔧 Base de datos detectada: {db_vendor}")
            
            if db_vendor == 'sqlite':
                transfer_sql = '''
                CREATE TABLE IF NOT EXISTS erp_internaltransfer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin_pos VARCHAR(100) NOT NULL,
                    destination_pos VARCHAR(100) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    observations TEXT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    company_id INTEGER NOT NULL REFERENCES erp_company(id),
                    created_by_id INTEGER NULL REFERENCES auth_user(id),
                    received_by_id INTEGER NULL REFERENCES auth_user(id)
                )
                '''
                detail_sql = '''
                CREATE TABLE IF NOT EXISTS erp_internaltransferdetail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quantity DECIMAL(10,2) NOT NULL,
                    transfer_id INTEGER NOT NULL REFERENCES erp_internaltransfer(id),
                    product_id INTEGER NOT NULL REFERENCES erp_product(id)
                )
                '''
            elif db_vendor == 'postgresql':
                transfer_sql = '''
                CREATE TABLE IF NOT EXISTS erp_internaltransfer (
                    id SERIAL PRIMARY KEY,
                    origin_pos VARCHAR(100) NOT NULL,
                    destination_pos VARCHAR(100) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    observations TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    company_id INTEGER NOT NULL REFERENCES erp_company(id),
                    created_by_id INTEGER REFERENCES auth_user(id),
                    received_by_id INTEGER REFERENCES auth_user(id)
                )
                '''
                detail_sql = '''
                CREATE TABLE IF NOT EXISTS erp_internaltransferdetail (
                    id SERIAL PRIMARY KEY,
                    quantity DECIMAL(10,2) NOT NULL,
                    transfer_id INTEGER NOT NULL REFERENCES erp_internaltransfer(id),
                    product_id INTEGER NOT NULL REFERENCES erp_product(id)
                )
                '''
            elif db_vendor == 'mysql':
                transfer_sql = '''
                CREATE TABLE IF NOT EXISTS erp_internaltransfer (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    origin_pos VARCHAR(100) NOT NULL,
                    destination_pos VARCHAR(100) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    observations TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    company_id INT NOT NULL,
                    created_by_id INT,
                    received_by_id INT,
                    FOREIGN KEY (company_id) REFERENCES erp_company(id),
                    FOREIGN KEY (created_by_id) REFERENCES auth_user(id),
                    FOREIGN KEY (received_by_id) REFERENCES auth_user(id)
                )
                '''
                detail_sql = '''
                CREATE TABLE IF NOT EXISTS erp_internaltransferdetail (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    quantity DECIMAL(10,2) NOT NULL,
                    transfer_id INT NOT NULL,
                    product_id INT NOT NULL,
                    FOREIGN KEY (transfer_id) REFERENCES erp_internaltransfer(id),
                    FOREIGN KEY (product_id) REFERENCES erp_product(id)
                )
                '''
            else:
                print(f"❌ Base de datos no soportada: {db_vendor}")
                return False
            
            cursor.execute(transfer_sql)
            cursor.execute(detail_sql)
            
            print("✅ Tablas creadas exitosamente")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    create_transfer_tables()
EOF

# Ejecutar migración
echo "🔧 Ejecutando migración..."
python migrate_transfer.py

# Verificar resultado
echo "🔧 Verificando tablas creadas..."
python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
if connection.vendor == 'sqlite':
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%transfer%';\")
elif connection.vendor == 'postgresql':
    cursor.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE '%transfer%';\")
elif connection.vendor == 'mysql':
    cursor.execute(\"SHOW TABLES LIKE '%transfer%';\")
tables = cursor.fetchall()
print('Tablas de transferencias:', tables)
"

# Limpiar
rm migrate_transfer.py

echo "✅ Migración completada"
