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

### Ejecución de Scripts

### Linux/Mac:
```bash
./actualizar_pos.sh
```

### Windows (con Git instalado):
```cmd
actualizar_pos.bat
```

### Windows Portable (Thumbdrive Edition):
```cmd
# Primera vez - descargar Git Portable
setup_git_portable.bat

# Actualizaciones posteriores
actualizar_pos_portable.bat
```

### Verificación Manual:
```python
# En Django shell
from core.utils.version_utils import get_version_info, format_version_display
vi = get_version_info()
print(f"Versión actual: {format_version_display(vi['current_version'])}")
print(f"Última versión: {format_version_display(vi['latest_version'])}")
print(f"Actualización disponible: {vi['update_available']}")
```

### 🚀 **Git Portable (Thumbdrive Edition)**

Para entornos Windows donde no se puede instalar Git:

#### Características:
- **Sin instalación:** Git Portable funciona desde USB o carpeta local
- **Auto-configuración:** Descarga y configuración automática
- **Compatibilidad total:** Mismas funciones que Git instalado
- **Portabilidad:** Funciona en cualquier Windows sin permisos de admin

#### Opciones de Instalación:

##### Opción 1: Instalador Automático (Recomendado)
```cmd
# El instalador principal incluye Git Portable
instalador_pos_bat.bat
```
El instalador detectará si Git Portable está disponible y lo descargará automáticamente.

##### Opción 2: Configurador Manual
```cmd
# Configurar Git Portable manualmente
setup_git_portable_inline.bat
```
Ofrece múltiples métodos de descarga y configuración.

##### Opción 3: Paquete Portable Completo
```cmd
# Crear paquete con Git Portable incluido
preparar_paquete_portable.bat
```
Crea un paquete de distribución que ya incluye Git Portable.

#### Flujo de Instalación Automática:

1. **Ejecutar instalador:** `instalador_pos_bat.bat`
2. **Detección automática:** Verifica si Git Portable existe
3. **Descarga automática:** Si no existe, intenta descargarlo
4. **Configuración automática:** Configura Git para el proyecto
5. **Verificación:** Confirma que Git Portable está listo
6. **Finalización:** Completa instalación sin suspender si hay errores

#### Manejo de Errores Mejorado:

- **Sin curl:** Pregunta si continuar sin Git Portable
- **Error de descarga:** Ofrece reintentar o continuar sin Git Portable
- **Error en extracción:** Continúa con instalación normal
- **Error en superusuario:** Continúa y permite creación manual
- **Error en acceso directo:** Continúa y da instrucciones manuales

#### Métodos de Descarga Automática:

1. **curl:** Si está disponible en el sistema
2. **PowerShell:** Como alternativa a curl
3. **Manual:** Instrucciones detalladas si fallan los métodos automáticos

#### Estructura de Directorios:
```
SitioMTCRM/
├── tools/
│   └── PortableGit/
│       ├── bin/
│       │   ├── git.exe
│       │   └── git-bash.exe
│       ├── etc/
│       └── ...
├── instalador_pos_bat.bat      # Con Git Portable integrado
├── setup_git_portable_inline.bat
├── actualizar_pos_portable.bat
└── ... (archivos del proyecto)
```

#### Ventajas del Integrado:

- **Una sola instalación:** Todo en un solo script
- **Sin dependencias:** No necesita descargas adicionales
- **Detección automática:** El sistema sabe cuándo usar Git Portable
- **Fallback inteligente:** Si Git Portable falla, usa Git del sistema
- **Distribución sencilla:** Un solo archivo para enviar a usuarios

#### Uso en Actualizaciones:

```cmd
# Actualización con Git Portable
actualizar_pos_portable.bat

# O desde la interfaz web
# Botón: "Actualizar (Portable)"
```

#### Diagnóstico de Git Portable:

El sistema incluye diagnóstico automático:
```cmd
# Verificar estado
python manage.py shell -c "
from core.erp.api.updates import check_git_portable
# ... o usar la interfaz web
"
```

### � **Correcciones de Problemas**

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
