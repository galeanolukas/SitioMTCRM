#!/usr/bin/env python3
"""
Script para crear tablas de transferencias en servidor remoto
Ejecutar en el servidor: python create_transfer_tables.py
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

def create_transfer_tables():
    """Crear tablas de transferencias internas"""
    
    try:
        with connection.cursor() as cursor:
            # Crear tabla InternalTransfer
            cursor.execute('''
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
            ''')
            
            # Crear tabla InternalTransferDetail
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS erp_internaltransferdetail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quantity DECIMAL(10,2) NOT NULL,
                transfer_id INTEGER NOT NULL REFERENCES erp_internaltransfer(id),
                product_id INTEGER NOT NULL REFERENCES erp_product(id)
            )
            ''')
            
            # Verificar tablas creadas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%transfer%';")
            tables = cursor.fetchall()
            
            print("✅ Tablas creadas exitosamente:")
            for table in tables:
                print(f"   - {table[0]}")
                
            return True
            
    except Exception as e:
        print(f"❌ Error al crear tablas: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Creando tablas de transferencias internas...")
    if create_transfer_tables():
        print("✅ Proceso completado exitosamente")
    else:
        print("❌ Falló la creación de tablas")
