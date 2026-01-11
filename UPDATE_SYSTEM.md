# Sistema de Actualización Automática - SitioMTCRM v1.1.1

## Mejoras Implementadas

### 🚀 **Nuevas Funcionalidades**

1. **Soporte para Entorno Virtual DJENV Externo**
   - Scripts actualizados para detectar y usar el entorno virtual `DJENV` ubicado en `/media/lukas/ARCHIVOS/GitHub/DJENV/`
   - Compatibilidad con entornos virtuales locales y externos

2. **Comparación Semántica de Versiones**
   - Implementación de comparación correcta usando `packaging.version`
   - Manejo adecuado de versiones (ej: `1.0.1` vs `1.0.10`)
   - Detección de versiones de desarrollo (`dev-xxxx`)

3. **Cache de GitHub API**
   - Cache de 1 hora para reducir llamadas a la API de GitHub
   - Mejora de rendimiento y reducción de errores de red

4. **Sistema Robusto de Manejo de Errores**
   - Captura graceful de excepciones en llamadas a API
   - Mensajes informativos para el usuario
   - Continuidad operativa sin interrupciones

### 🔧 **Componentes Técnicos**

#### Nuevos Archivos:
- `core/utils/version_utils.py` - Utilidades de manejo de versiones
- `core/erp/api/updates.py` - Endpoints API para actualizaciones
- `core/utils/__init__.py` - Módulo utils
- `core/erp/api/__init__.py` - Módulo API

#### Scripts Actualizados:
- `actualizar_pos.sh` - Script Linux mejorado
- `actualizar_pos.bat` - Script Windows mejorado
- `requirements.txt` - Agregado paquete `packaging`

#### Vistas Mejoradas:
- `DashboardView` - Usa nuevo sistema de versiones
- `UpdatesView` - Usa nuevo sistema de versiones

### 📡 **Endpoints API**

#### Verificar Actualizaciones
```
GET /erp/api/updates/check/
```
Retorna JSON con información de versiones:
```json
{
  "success": true,
  "data": {
    "current_version": "1.1.1",
    "latest_version": "1.2.0",
    "update_available": true,
    "is_dev_version": false
  }
}
```

#### Refrescar Información de Versión
```
POST /erp/api/updates/refresh/
```
Fuerza la actualización del cache y retorna información actualizada.

### 🔄 **Flujo de Actualización**

1. **Detección de Entorno Virtual**
   - Busca `DJENV` en `/media/lukas/ARCHIVOS/GitHub/DJENV/`
   - Si no encuentra, usa entorno local `DJENV/`
   - Si no existe ninguno, muestra error

2. **Backup Automático**
   - Base de datos SQLite: `db.sqlite3` → `db.sqlite3_backup`
   - Entorno virtual local: `DJENV/` → `DJENV_backup/`
   - Entornos externos no requieren backup

3. **Actualización desde GitHub**
   - `git pull origin main`
   - Restauración automática si falla

4. **Instalación de Dependencias**
   - Actualización de pip
   - Instalación desde `requirements.txt`
   - Verificación de paquetes críticos

5. **Migraciones**
   - `python manage.py makemigrations user erp`
   - `python manage.py migrate`

6. **Limpieza**
   - Eliminación de backups si la actualización fue exitosa

### 🛠 **Uso**

#### Linux/Mac:
```bash
./actualizar_pos.sh
```

#### Windows:
```cmd
actualizar_pos.bat
```

#### Verificación Manual:
```python
# En Django shell
from core.utils.version_utils import get_version_info, format_version_display
vi = get_version_info()
print(f"Versión actual: {format_version_display(vi['current_version'])}")
print(f"Última versión: {format_version_display(vi['latest_version'])}")
print(f"Actualización disponible: {vi['update_available']}")
```

### 🐛 **Correcciones de Problemas**

1. **Problema:** Scripts usaban `venv` pero el entorno es `DJENV`
   **Solución:** Detección automática de `DJENV` local y externo

2. **Problema:** Comparación de versiones por string exacto
   **Solución:** Implementación de comparación semántica

3. **Problema:** Sin cache en llamadas a GitHub API
   **Solución:** Cache de 1 hora con Django cache framework

4. **Problema:** Manejo pobre de errores de red
   **Solución:** Try/catch específicos con fallback graceful

### 📋 **Requisitos**

- Python 3.8+
- Django 4.2.5
- Git instalado y configurado
- Entorno virtual `DJENV` (local o en `/media/lukas/ARCHIVOS/GitHub/DJENV/`)
- Paquete `packaging` (agregado a requirements.txt)

### 🎯 **Próximas Mejoras**

- [ ] Interfaz gráfica para actualizaciones
- [ ] Programación de actualizaciones automáticas
- [ ] Notificaciones por email de nuevas versiones
- [ ] Sistema de rollback automático
- [ ] Validación de integridad de archivos

---

**Versión:** 1.1.1  
**Fecha:** 2026-01-11  
**Autor:** Sistema de Actualización Automática
