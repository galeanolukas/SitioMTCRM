-- Script para crear tablas de transferencias internas (PostgreSQL/MySQL)
-- Ejecutar en el servidor con: psql -d tu_base_de_datos < create_transfer_tables_postgres.sql

-- Crear tabla InternalTransfer
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
);

-- Crear tabla InternalTransferDetail
CREATE TABLE IF NOT EXISTS erp_internaltransferdetail (
    id SERIAL PRIMARY KEY,
    quantity DECIMAL(10,2) NOT NULL,
    transfer_id INTEGER NOT NULL REFERENCES erp_internaltransfer(id),
    product_id INTEGER NOT NULL REFERENCES erp_product(id)
);

-- Verificar tablas creadas
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name LIKE '%transfer%';
