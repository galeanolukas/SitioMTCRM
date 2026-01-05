-- Agregar columna local_sale_id a la tabla erp_sale
ALTER TABLE erp_sale 
ADD COLUMN local_sale_id INTEGER NULL;

-- Agregar comentario a la columna
COMMENT ON COLUMN erp_sale.local_sale_id IS 'ID de la venta local para evitar duplicados';
