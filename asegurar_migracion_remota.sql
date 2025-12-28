-- Script para asegurar la migración de payment_details en servidor remoto
-- Ejecutar este script en la base de datos del servidor remoto antes de actualizar

-- Verificar si la columna payment_details existe
PRAGMA table_info(erp_sale);

-- Si no existe, aplicar la migración
-- Add field payment_details to sale
BEGIN;

-- Crear tabla nueva con la columna payment_details
CREATE TABLE "new__erp_sale" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
    "payment_details" text NOT NULL CHECK ((JSON_VALID("payment_details") OR "payment_details" IS NULL)), 
    "date_joined" datetime NOT NULL, 
    "local_timezone" varchar(50) NULL, 
    "subtotal" decimal NOT NULL, 
    "iva" decimal NOT NULL, 
    "total" decimal NOT NULL, 
    "payment_method" varchar(12) NOT NULL, 
    "invoice_number" varchar(20) NULL UNIQUE, 
    "invoice_pos" varchar(5) NOT NULL, 
    "invoice_type" varchar(1) NOT NULL, 
    "is_invoiced" bool NOT NULL, 
    "synced_to_server" bool NOT NULL, 
    "cli_id" bigint NULL REFERENCES "erp_client" ("id") DEFERRABLE INITIALLY DEFERRED, 
    "company_id" bigint NULL REFERENCES "erp_company" ("id") DEFERRABLE INITIALLY DEFERRED
);

-- Migrar datos existentes
INSERT INTO "new__erp_sale" (
    "id", "date_joined", "local_timezone", "subtotal", "iva", "total", 
    "payment_method", "invoice_number", "invoice_pos", "invoice_type", 
    "is_invoiced", "synced_to_server", "cli_id", "company_id", "payment_details"
) 
SELECT 
    "id", "date_joined", "local_timezone", "subtotal", "iva", "total", 
    "payment_method", "invoice_number", "invoice_pos", "invoice_type", 
    "is_invoiced", "synced_to_server", "cli_id", "company_id", '{}' 
FROM "erp_sale";

-- Reemplazar tabla vieja
DROP TABLE "erp_sale";
ALTER TABLE "new__erp_sale" RENAME TO "erp_sale";

-- Recrear índices
CREATE INDEX "erp_sale_cli_id_ffdb3bc4" ON "erp_sale" ("cli_id");
CREATE INDEX "erp_sale_company_id_2e2ff90e" ON "erp_sale" ("company_id");

COMMIT;

-- Verificar resultado
PRAGMA table_info(erp_sale);
