#!/usr/bin/env python3
"""
Script universal para crear tablas de transferencias en servidor remoto
Compatible con PostgreSQL, MySQL y SQLite
Ejecutar en el servidor: python create_transfer_tables_universal.py
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from django.db.utils import ProgrammingError

def create_transfer_tables():
    """Crear tablas de transferencias internas (compatible con cualquier DB)"""
    
    try:
        with connection.cursor() as cursor:
            # Detectar tipo de base de datos
            db_vendor = connection.vendor
            print(f"🔧 Detectada base de datos: {db_vendor}")
            
            # SQL específico para cada base de datos
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
            
            # Ejecutar creación de tablas
            print("🔧 Creando tabla erp_internaltransfer...")
            cursor.execute(transfer_sql)
            
            print("🔧 Creando tabla erp_internaltransferdetail...")
            cursor.execute(detail_sql)
            
            # Verificar tablas creadas
            if db_vendor == 'sqlite':
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%transfer%';")
            elif db_vendor == 'postgresql':
                cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE '%transfer%';")
            elif db_vendor == 'mysql':
                cursor.execute("SHOW TABLES LIKE '%transfer%';")
            
            tables = cursor.fetchall()
            
            print("✅ Tablas creadas exitosamente:")
            for table in tables:
                table_name = table[0] if isinstance(table, (tuple, list)) else table
                print(f"   - {table_name}")
                
            return True
            
    except ProgrammingError as e:
        print(f"❌ Error de SQL: {e}")
        return False
    except Exception as e:
        print(f"❌ Error general: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Creando tablas de transferencias internas...")
    if create_transfer_tables():
        print("✅ Proceso completado exitosamente")
    else:
        print("❌ Falló la creación de tablas")
