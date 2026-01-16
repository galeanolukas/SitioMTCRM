# Instalación de SitioMTCRM POS

## Instrucciones para instalación en una computadora nueva

### Windows
1. **Ejecutar el instalador principal:**
   ```
   Doble clic en: instalador_pos_bat.bat
   ```

2. **Si necesita limpiar todo (instalación fresca):**
   ```
   Doble clic en: limpiar_todo.sh
   Luego ejecute: instalador_pos_bat.bat
   ```

### Linux
1. **Dar permisos de ejecución:**
   ```bash
   chmod +x install.sh
   chmod +x limpiar_todo.sh
   ```

2. **Ejecutar el instalador principal:**
   ```bash
   ./install.sh
   ```

3. **Si necesita limpiar todo (instalación fresca):**
   ```bash
   ./limpiar_todo.sh
   ./install.sh
   ```

## ¿Qué hacen los instaladores?

### instalador_pos_bat.bat (Windows)
- ✅ Crea entorno virtual venv
- ✅ Instala todas las dependencias Python
- ✅ Configura Git Portable (opcional, no detiene la instalación)
- ✅ **Crea todas las migraciones desde cero**
- ✅ **Aplica todas las migraciones y crea tablas**
- ✅ Crea superusuario por defecto (admin/admin)
- ✅ Crea acceso directo en el escritorio
- ✅ Recolecta archivos estáticos
- ✅ Verifica la instalación

### install.sh (Linux)
- ✅ Verifica e instala dependencias del sistema
- ✅ Crea entorno virtual venv
- ✅ Instala todas las dependencias Python
- ✅ Configura Git (opcional)
- ✅ **Crea todas las migraciones desde cero**
- ✅ **Aplica todas las migraciones y crea tablas**
- ✅ Crea superusuario por defecto (admin/admin)
- ✅ Recolecta archivos estáticos
- ✅ Verifica la instalación

### limpiar_todo.sh (Ambos sistemas)
- ⚠️  **Elimina completamente** la base de datos
- ⚠️  **Elimina todas las migraciones**
- ⚠️  **Elimina archivos estáticos**
- ⚠️  **Elimina caché y temporales**

## Características clave de la instalación

### ✅ Creación robusta de tablas
- Limpia migraciones anteriores automáticamente
- Crea migraciones iniciales para cada app
- Usa `--fake-initial` para evitar conflictos
- Verifica cada paso con manejo de errores

### ✅ Seguridad mejorada
- **No se crea superusuario automáticamente** (medida de seguridad)
- El usuario debe crear sus propias credenciales
- Evita accesos no autorizados por defecto

### ✅ Git Portable no detiene la instalación
- Es completamente opcional
- Si falla la descarga, continúa la instalación
- Se puede configurar más tarde manualmente
- No afecta el funcionamiento del POS

### ✅ Manejo de errores mejorado
- Cada paso verifica el código de salida
- Ofrece soluciones alternativas
- No detiene la instalación por errores no críticos
- Muestra instrucciones claras para resolver problemas

## Acceso al sistema

### Después de la instalación exitosa:

1. **Iniciar el servidor:**
   - Windows: Doble clic en el acceso directo del escritorio
   - Linux: `source venv/bin/activate && python manage.py runserver`

2. **Acceder al sistema:**
   - Panel de administración: http://127.0.0.1:8000/admin/
   - Sistema POS: http://127.0.0.1:8000/erp/pos/
   - Cuentas corrientes: http://127.0.0.1:8000/erp/employee-account/

3. **Credenciales:**
   - **Debe crear un superusuario manualmente**
   - Ejecute: `python manage.py createsuperuser`
   - Configure su propio usuario y contraseña

## Solución de problemas

### Si las migraciones fallan:
1. Ejecute `limpiar_todo.sh`
2. Vuelva a ejecutar el instalador principal
3. Si persiste, elimine manualmente `db.sqlite3`

### Si Git Portable falla:
- No afecta el funcionamiento del sistema
- Puede configurarlo más tarde con `setup_git_portable.bat`
- O usar Git instalado en el sistema

### Si el entorno virtual falla:
- Elimine la carpeta `venv`
- Ejecute nuevamente el instalador

## Estructura creada

```
SitioMTCRM/
├── venv/                    # Entorno virtual Python
├── db.sqlite3               # Base de datos SQLite
├── staticfiles/              # Archivos estáticos
├── tools/                   # Git Portable (opcional)
├── core/
│   ├── erp/migrations/      # Migraciones de ERP
│   └── user/migrations/     # Migraciones de Usuarios
└── MultilideresCRM POS.lnk  # Acceso directo (Windows)
```

## Actualizaciones futuras

El sistema está preparado para actualizaciones automáticas a través de:
- Interfaz web: http://localhost:8000/erp/updates/
- Scripts de actualización (si Git está disponible)

## Notas importantes

- **Base de datos:** SQLite (archivo único `db.sqlite3`)
- **Python:** Requiere Python 3.8+
- **Dependencias:** Se instalan automáticamente
- **Git:** Opcional, solo para actualizaciones
- **Multiplataforma:** Windows y Linux

## Soporte

Si encuentra problemas durante la instalación:
1. Revise los mensajes de error en la consola
2. Asegúrese de tener conexión a internet
3. Verifique los permisos en la carpeta de instalación
4. Ejecute `limpiar_todo.sh` antes de reintentar
