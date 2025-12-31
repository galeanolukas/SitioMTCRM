# Pasos para Actualización del Servidor Remoto

## 1. Antes de Actualizar (Obligatorio)

### Verificar Base de Datos
```sql
-- Conectarse a la base de datos del servidor remoto y ejecutar:
PRAGMA table_info(erp_sale);
```

### Si la columna `payment_details` NO existe:
```bash
# Ejecutar el script de migración
sqlite3 tu_base_de_datos.db < asegurar_migracion_remota.sql
```

## 2. Archivos a Actualizar

### Frontend (Static Files)
- `core/erp/static/sale/js/pos.js` - Formato de pesos y pagos combinados
- `core/erp/static/sale/js/list.js` - Formato en lista de ventas

### Templates
- `core/erp/templates/sale/pos.html` - Modal de pagos combinados
- `templates/operator_reports/sales_report.html` - Reporte de operadores

### Backend
- `core/erp/views/operator_reports/views.py` - API de reportes
- `core/erp/views/sale/views.py` - Guardado de ventas

## 3. Después de Actualizar

### Recrear Static Files
```bash
python manage.py collectstatic --noinput
```

### Reiniciar Servidor
```bash
# Reiniciar el servidor web (Apache/Nginx/Gunicorn)
sudo systemctl restart nginx
# o
sudo systemctl restart gunicorn
```

### Verificar Funcionamiento
1. Probar formato de pesos en POS
2. Probar pagos combinados
3. Verificar reporte de operadores
4. Revisar lista de ventas

## 4. Comandos de Verificación

### Verificar Migraciones
```bash
python manage.py showmigrations erp
```

### Verificar Formato
```javascript
// En consola del navegador
fmt(1234.56); // Debe retornar "$1.234,56"
```

### Verificar Pagos Combinados
```javascript
// Crear una venta combinada y verificar que los payment_details se guarden
```

## 5. Problemas Comunes

### Error: "column erp_sale.payment_details does not exist"
**Solución:** Ejecutar el script `asegurar_migracion_remota.sql`

### Error: Formato incorrecto (muestra 2 dígitos)
**Solución:** Limpiar caché del navegador y reiniciar servidor

### Error: Pagos combinados no distribuyen montos
**Solución:** Verificar que el backend envíe `payment_details` en el API

## 6. Backup Antes de Actualizar

```bash
# Backup de la base de datos
cp tu_base_de_datos.db tu_base_de_datos_backup_$(date +%Y%m%d).db

# Backup de archivos clave
tar -czf backup_$(date +%Y%m%d).tar.gz core/erp/static/sale/js/ core/erp/templates/sale/ core/erp/views/
```
