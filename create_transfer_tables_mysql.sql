-- Script para crear tablas de transferencias internas (MySQL)
-- Ejecutar en el servidor con: mysql -u usuario -p tu_base_de_datos < create_transfer_tables_mysql.sql

-- Crear tabla InternalTransfer
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
);

-- Crear tabla InternalTransferDetail
CREATE TABLE IF NOT EXISTS erp_internaltransferdetail (
    id INT AUTO_INCREMENT PRIMARY KEY,
    quantity DECIMAL(10,2) NOT NULL,
    transfer_id INT NOT NULL,
    product_id INT NOT NULL,
    FOREIGN KEY (transfer_id) REFERENCES erp_internaltransfer(id),
    FOREIGN KEY (product_id) REFERENCES erp_product(id)
);

-- Verificar tablas creadas
SHOW TABLES LIKE '%transfer%';
