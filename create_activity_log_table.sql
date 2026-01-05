-- SQL para crear tabla ActivityLog en PostgreSQL
-- Ejecutar solo en servidor de producción (ENVIRONMENT=production)

CREATE TABLE IF NOT EXISTS erp_activitylog (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES auth_user(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    description TEXT,
    model_name VARCHAR(50),
    object_id INTEGER,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    company_id INTEGER REFERENCES erp_company(id) ON DELETE SET NULL
);

-- Índices para mejor rendimiento
CREATE INDEX IF NOT EXISTS erp_activitylog_user_id_timestamp_idx ON erp_activitylog(user_id, timestamp);
CREATE INDEX IF NOT EXISTS erp_activitylog_action_timestamp_idx ON erp_activitylog(action, timestamp);
CREATE INDEX IF NOT EXISTS erp_activitylog_company_id_timestamp_idx ON erp_activitylog(company_id, timestamp);

-- Comentarios
COMMENT ON TABLE erp_activitylog IS 'Registro de actividades de usuarios para modo servidor';
COMMENT ON COLUMN erp_activitylog.user_id IS 'Usuario que realizó la acción';
COMMENT ON COLUMN erp_activitylog.action IS 'Tipo de acción realizada';
COMMENT ON COLUMN erp_activitylog.description IS 'Descripción detallada de la actividad';
COMMENT ON COLUMN erp_activitylog.model_name IS 'Nombre del modelo afectado';
COMMENT ON COLUMN erp_activitylog.object_id IS 'ID del objeto afectado';
COMMENT ON COLUMN erp_activitylog.ip_address IS 'Dirección IP del cliente';
COMMENT ON COLUMN erp_activitylog.user_agent IS 'Navegador/cliente del usuario';
COMMENT ON COLUMN erp_activitylog.timestamp IS 'Fecha y hora de la actividad';
COMMENT ON COLUMN erp_activitylog.company_id IS 'Empresa relacionada con la actividad';
