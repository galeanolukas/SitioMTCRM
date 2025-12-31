-- Script para crear tablas de transferencias internas
-- Ejecutar en el servidor remoto con: sqlite3 tu_base_de_datos.db < create_transfer_tables.sql

-- Crear tabla InternalTransfer
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
);

-- Crear tabla InternalTransferDetail
CREATE TABLE IF NOT EXISTS erp_internaltransferdetail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quantity DECIMAL(10,2) NOT NULL,
    transfer_id INTEGER NOT NULL REFERENCES erp_internaltransfer(id),
    product_id INTEGER NOT NULL REFERENCES erp_product(id)
);

-- Verificar tablas creadas
SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%transfer%';
