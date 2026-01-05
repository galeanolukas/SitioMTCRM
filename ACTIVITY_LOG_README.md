# Registro de Actividades de Usuarios - SitioMTCRM

## 🎯 **Descripción**

Sistema de registro de actividades para modo servidor que captura automáticamente las acciones de los usuarios y solo es visible para superusuarios.

## 📋 **Características**

### ✅ **Funcionalidades**
- **Registro automático** de actividades mediante middleware
- **Solo visible** para superusuarios
- **Filtros avanzados** por usuario, acción, fecha, empresa
- **Dashboard** con estadísticas y gráficos
- **Paginación** para manejar grandes volúmenes de datos
- **Índices optimizados** para rendimiento

### ✅ **Información Capturada**
- Usuario que realiza la acción
- Tipo de acción (CREATE, UPDATE, DELETE, VIEW, EXPORT, SYNC, etc.)
- Descripción detallada
- Modelo y objeto afectado
- Dirección IP y User Agent
- Fecha y hora exacta
- Empresa relacionada

## 🚀 **Instalación**

### 1. **Base de Datos**
Ejecutar el SQL en el servidor de producción:
```bash
psql -d tu_base_de_datos -f create_activity_log_table.sql
```

### 2. **Middleware**
El middleware ya está configurado en `settings.py`:
```python
'core.erp.middleware.ActivityLogMiddleware'
```

### 3. **URLs**
Las URLs están agregadas a `core/erp/urls.py`:
- `/erp/activity/log/` - Registro completo
- `/erp/activity/dashboard/` - Dashboard de estadísticas

## 🔧 **Configuración**

### **Modo Servidor**
El middleware solo funciona en modo producción:
```python
ENVIRONMENT = 'production'  # Activa el registro
ENVIRONMENT = 'development'  # Desactiva el registro
```

### **Permisos**
- **Solo superusuarios** pueden ver los registros
- **Usuarios normales** no tienen acceso
- **Middleware** registra todas las acciones de usuarios autenticados

## 📊 **Uso**

### **Acceso a los Reportes**
1. Iniciar sesión como **superusuario**
2. Navegar a `/erp/activity/dashboard/` para estadísticas
3. O ir a `/erp/activity/log/` para registro completo

### **Filtros Disponibles**
- **Usuario**: Filtrar por usuario específico
- **Acción**: Filtrar por tipo de acción
- **Fecha**: Hoy, última semana, último mes
- **Empresa**: Filtrar por empresa

### **Estadísticas**
- Total de actividades
- Actividades por día (últimos 7 días)
- Top acciones más frecuentes
- Usuarios más activos
- Distribución porcentual

## 🛡️ **Seguridad**

### **Privacidad**
- Solo superusuarios pueden acceder
- No se registran contraseñas ni datos sensibles
- User Agent y IP para auditoría

### **Rendimiento**
- Índices en campos clave
- Middleware con manejo de errores silencioso
- Paginación para grandes volúmenes

### **Almacenamiento**
- Tabla separada `erp_activitylog`
- Configuración para retención (futura)
- Limpieza automática (futura implementación)

## 📁 **Archivos Modificados**

### **Nuevos**
- `core/erp/models.py` - Modelo ActivityLog
- `core/erp/middleware.py` - Middleware de registro
- `core/erp/views/activity_log.py` - Vistas del dashboard
- `templates/erp/activity_log.html` - Template del registro
- `templates/erp/activity_dashboard.html` - Template del dashboard
- `create_activity_log_table.sql` - SQL para crear tabla

### **Modificados**
- `config/settings.py` - Agregado middleware
- `core/erp/urls.py` - Agregadas URLs de actividad

## 🔍 **Monitoreo**

### **Actividades Registradas**
- Inicio/Cierre de sesión
- Creación/Actualización/Eliminación de objetos
- Ventas y facturación
- Exportación de reportes
- Sincronización de datos
- Navegación del sistema

### **No Registradas**
- Archivos estáticos
- Peticiones de admin de Django
- Usuarios no autenticados
- Paths ignorados configurados

## 🎯 **Beneficios**

1. **Auditoría completa** de actividades del sistema
2. **Detección de anomalías** en el uso
3. **Análisis de patrones** de usuario
4. **Cumplimiento normativo** (futuro)
5. **Optimización de rendimiento** basada en uso

## 🚨 **Consideraciones**

- **Espacio en BD**: El registro crece con el uso
- **Privacidad**: Cumplir con normativas de protección de datos
- **Rendimiento**: Monitorear impacto en aplicaciones grandes
- **Retención**: Implementar políticas de limpieza periódica

## 🔄 **Mantenimiento**

### **Limpieza (Futura)**
```sql
-- Eliminar registros anteriores a 90 días
DELETE FROM erp_activitylog 
WHERE timestamp < NOW() - INTERVAL '90 days';
```

### **Monitoreo de Rendimiento**
```sql
-- Verificar tamaño de la tabla
SELECT pg_size_pretty(pg_total_relation_size('erp_activitylog'));

-- Verificar uso de índices
SELECT schemaname, tablename, indexname, idx_scan 
FROM pg_stat_user_indexes 
WHERE tablename = 'activitylog';
```
