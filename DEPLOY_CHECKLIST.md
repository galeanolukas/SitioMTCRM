# CHECKLIST DE DEPLOY - SitioMTCRM
# ===================================

## 📋 VERIFICACIÓN PRE-DEPLOY

### ✅ 1. Estado del Repositorio
- [ ] Todos los cambios están commiteados
- [ ] Branch actual: main/master
- [ ] Sin archivos sin seguimiento críticos
- [ ] Tags de versión actualizados si corresponde

### ✅ 2. Dependencias y Entorno
- [ ] requirements.txt actualizado
- [ ] Versiones de Python y Django compatibles
- [ ] Variables de entorno configuradas
- [ ] Base de datos accesible

### ✅ 3. Migraciones
- [ ] Migraciones locales aplicadas
- [ ] Migraciones pendientes identificadas
- [ ] SQL de respaldo disponible

### ✅ 4. Configuración
- [ ] ENVIRONMENT=production
- [ ] DEBUG=False
- [ ] ALLOWED_HOSTS configurado
- [ ] SECRET_KEY seguro
- [ ] Base de datos de producción configurada

## 🔧 MODIFICACIONES RECIENTES A VERIFICAR

### 1. Modelo Sale (local_sale_id)
```sql
-- Verificar si la columna existe en producción
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'erp_sale' AND column_name = 'local_sale_id';
```

### 2. Sincronización de Ventas
- [ ] sync_sales_to_remote.py actualizado
- [ ] Manejo de local_sale_id solo en BD local
- [ ] synced_to_server=True en servidor remoto

### 3. Reportes Financieros
- [ ] profit_report.html con mejoras visuales
- [ ] Redondeo de porcentajes (1 decimal)
- [ ] Estilos CSS mejorados

### 4. Reportes Unificados
- [ ] Empresa por defecto del usuario
- [ ] UnifiedReportsView actualizado

## 🚀 COMANDOS DE DEPLOY

### 1. Backup (si es posible)
```bash
# Backup de base de datos
pg_dump nombre_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup de archivos
tar -czf backup_files_$(date +%Y%m%d_%H%M%S).tar.gz /ruta/al/proyecto
```

### 2. Actualización
```bash
# Pull de cambios
git pull origin main

# Instalar dependencias (si cambiaron)
pip install -r requirements.txt

# Aplicar migraciones
python manage.py migrate

# Recolectar archivos estáticos
python manage.py collectstatic --noinput

# Reiniciar servicios
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

### 3. Verificación Post-Deploy
```bash
# Verificar estado de servicios
systemctl status gunicorn
systemctl status nginx

# Verificar logs
tail -f /var/log/gunicorn/error.log
tail -f /var/log/nginx/error.log
```

## ⚠️ PUNTOS CRÍTICOS

### 1. Base de Datos
- **local_sale_id**: Solo debe existir en BD local, NO en servidor remoto
- **Migración 0004**: Aplicar solo en POS locales

### 2. Configuración
- **ENVIRONMENT**: Debe ser 'production' en servidor
- **DEBUG**: Debe ser False en producción
- **Base de datos**: Sin conexión 'remote' en producción

### 3. Sincronización
- El comando sync_sales_to_remote.py debe manejar gracefully
- la ausencia de local_sale_id en servidor

## 📊 ESTADO ACTUAL

### Cambios Pendientes:
- [x] sync_sales_to_remote.py: Fix local_sale_id
- [x] profit_report.html: Mejoras visuales  
- [x] UnifiedReportsView: Empresa por defecto
- [x] Modal detalle venta: Fix productos

### Archivos Modificados:
- core/erp/management/commands/sync_sales_to_remote.py
- core/erp/templates/reports/profit_report.html
- core/erp/views/reports/views.py
- core/erp/views/sale/views.py

### Compatibilidad:
- ✅ Django 4.2.5
- ✅ PostgreSQL/SQLite
- ✅ Python 3.10+
- ✅ Reportes PDF funcionales

## 🎯 ACCIÓN RECOMENDADA

1. **Aplicar migración local_sale_id** solo en POS locales:
   ```sql
   ALTER TABLE erp_sale ADD COLUMN local_sale_id INTEGER NULL;
   ```

2. **Deploy en servidor** con ENVIRONMENT=production

3. **Verificar sincronización** post-deploy

4. **Testear reportes** y mejoras visuales
