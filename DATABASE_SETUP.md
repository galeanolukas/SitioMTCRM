# Configuración de Base de Datos - SitioMTCRM

## Arquitectura de Bases de Datos

El sistema soporta múltiples configuraciones de bases de datos según el entorno:

### Entornos

1. **Producción (VPS)**
   - `default`: PostgreSQL local en el servidor
   - Sin base de datos remota (solo una BD)

2. **Desarrollo / POS Local**
   - **Opción A (SQLite local)**: `default` = SQLite, `remote` = PostgreSQL remoto
   - **Opción B (PostgreSQL local)**: `default` = PostgreSQL local, `remote` = PostgreSQL remoto

## Configuración Variables de Entorno

### Para Producción (VPS)

```bash
# Base de datos local PostgreSQL
DB_NAME=sitiomtcrm
DB_USER=postgres
DB_PASSWORD=tu_password_seguro
DB_HOST=localhost
DB_PORT=5432
```

### Para Desarrollo / POS Local con PostgreSQL Local

```bash
# Habilitar PostgreSQL local
USE_LOCAL_POSTGRES=true

# Base de datos local PostgreSQL
DB_NAME=sitiomtcrm
DB_USER=postgres
DB_PASSWORD=tu_password_seguro
DB_HOST=localhost
DB_PORT=5432

# Base de datos remota PostgreSQL (servidor central)
REMOTE_DB_NAME=sitiomtcrm
REMOTE_DB_USER=postgres
REMOTE_DB_PASSWORD=tu_password_remoto
REMOTE_DB_HOST=tu_servidor_remoto.com
REMOTE_DB_PORT=5432
REMOTE_DB_SSLMODE=require
```

### Para Desarrollo / POS Local con SQLite Local

```bash
# Deshabilitar PostgreSQL local (o no definir la variable)
USE_LOCAL_POSTGRES=false

# Base de datos remota PostgreSQL (servidor central)
REMOTE_DB_NAME=sitiomtcrm
REMOTE_DB_USER=postgres
REMOTE_DB_PASSWORD=tu_password_remoto
REMOTE_DB_HOST=tu_servidor_remoto.com
REMOTE_DB_PORT=5432
REMOTE_DB_SSLMODE=require
```

## Instalación de PostgreSQL Local

### Linux (Ubuntu/Debian)

```bash
# Instalar PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Iniciar servicio
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Crear usuario y base de datos
sudo -u postgres psql
```

En el prompt de PostgreSQL:
```sql
-- Crear usuario
CREATE USER sitiomtcrm WITH PASSWORD 'tu_password_seguro';

-- Crear base de datos
CREATE DATABASE sitiomtcrm OWNER sitiomtcrm;

-- Conceder privilegios
GRANT ALL PRIVILEGES ON DATABASE sitiomtcrm TO sitiomtcrm;

-- Salir
\q
```

### Linux (Arch Linux)

```bash
# Instalar PostgreSQL
sudo pacman -S postgresql

# Inicializar base de datos
sudo -u postgres initdb -D /var/lib/postgres/data

# Iniciar servicio
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Crear usuario y base de datos
sudo -u postgres createuser --interactive
sudo -u postgres createdb sitiomtcrm
```

### macOS

```bash
# Instalar con Homebrew
brew install postgresql@14

# Iniciar servicio
brew services start postgresql@14

# Crear usuario y base de datos
psql postgres
```

En el prompt de PostgreSQL:
```sql
-- Crear usuario
CREATE USER sitiomtcrm WITH PASSWORD 'tu_password_seguro';

-- Crear base de datos
CREATE DATABASE sitiomtcrm OWNER sitiomtcrm;

-- Salir
\q
```

### Windows

1. Descargar e instalar PostgreSQL desde https://www.postgresql.org/download/windows/
2. Usar pgAdmin para crear usuario y base de datos
3. Configurar variables de entorno

## Migración de SQLite a PostgreSQL Local

### 1. Exportar datos de SQLite

```bash
# Activar entorno virtual
source DJENV/bin/activate

# Crear archivo JSON con datos
python manage.py dumpdata > sqlite_backup.json
```

### 2. Configurar PostgreSQL Local

```bash
# Configurar variables de entorno
export USE_LOCAL_POSTGRES=true
export DB_NAME=sitiomtcrm
export DB_USER=postgres
export DB_PASSWORD=tu_password_seguro
export DB_HOST=localhost
export DB_PORT=5432
```

### 3. Crear base de datos PostgreSQL

```bash
# Crear base de datos
createdb -U postgres sitiomtcrm
```

### 4. Ejecutar migraciones

```bash
# Crear tablas en PostgreSQL
python manage.py migrate
```

### 5. Importar datos

```bash
# Importar datos desde JSON
python manage.py loaddata sqlite_backup.json
```

### 6. Verificar

```bash
# Verificar que todo funciona
python manage.py check
python manage.py runserver
```

## Ventajas de PostgreSQL Local vs SQLite

### PostgreSQL Local
- ✅ Mejor rendimiento en operaciones concurrentes
- ✅ Sin bloqueos de base de datos
- ✅ Soporte para transacciones complejas
- ✅ Mejor manejo de índices
- ✅ Compatible con producción
- ✅ Soporte para JSON avanzado
- ✅ Conexiones persistentes (CONN_MAX_AGE)

### SQLite Local
- ✅ Configuración cero (no requiere instalación)
- ✅ Archivo único portable
- ✅ Ideal para desarrollo simple
- ❌ Bloqueos en escritura concurrente
- ❌ Rendimiento limitado en operaciones complejas
- ❌ No soporta todas las características de PostgreSQL

## Configuración de Conexiones Persistentes

El sistema usa `CONN_MAX_AGE` para mantener conexiones persistentes:

- **PostgreSQL local**: 600 segundos (10 minutos)
- **PostgreSQL remoto**: 300 segundos (5 minutos)

Esto mejora el rendimiento reutilizando conexiones en lugar de crear nuevas en cada solicitud.

## Solución de Problemas

### Error: "database is locked" (SQLite)

**Causa**: SQLite bloquea el archivo completo en escritura.

**Solución**: Migrar a PostgreSQL local configurando `USE_LOCAL_POSTGRES=true`.

### Error: "could not connect to server" (PostgreSQL)

**Causa**: PostgreSQL no está corriendo o credenciales incorrectas.

**Solución**:
```bash
# Verificar que PostgreSQL está corriendo
sudo systemctl status postgresql

# Verificar credenciales en variables de entorno
echo $DB_NAME
echo $DB_USER
echo $DB_HOST
```

### Error: "peer authentication failed" (PostgreSQL)

**Causa**: Configuración de autenticación de PostgreSQL.

**Solución**: Cambiar a autenticación por contraseña en `pg_hba.conf`:
```
# Cambiar de:
local   all             all                                     peer
# A:
local   all             all                                     md5
```

Luego reiniciar PostgreSQL:
```bash
sudo systemctl restart postgresql
```

## Configuración en Archivo .env (Opcional)

Para facilitar la configuración, puedes crear un archivo `.env` en la raíz del proyecto:

```bash
# Entorno
ENVIRONMENT=development

# Base de datos local
USE_LOCAL_POSTGRES=true
DB_NAME=sitiomtcrm
DB_USER=postgres
DB_PASSWORD=tu_password_seguro
DB_HOST=localhost
DB_PORT=5432

# Base de datos remota
REMOTE_DB_NAME=sitiomtcrm
REMOTE_DB_USER=postgres
REMOTE_DB_PASSWORD=tu_password_remoto
REMOTE_DB_HOST=tu_servidor_remoto.com
REMOTE_DB_PORT=5432
REMOTE_DB_SSLMODE=require
```

Luego cargar las variables:
```bash
# Instalar python-dotenv
pip install python-dotenv

# Agregar en settings.py (al inicio)
from dotenv import load_dotenv
load_dotenv()
```

## Comandos Útiles

### Verificar configuración actual

```bash
python manage.py shell
```

```python
from django.conf import settings
print(settings.DATABASES)
```

### Migraciones específicas por base de datos

```bash
# Migrar base de datos default
python manage.py migrate

# Migrar base de datos remota
python manage.py migrate --database=remote
```

### Crear superusuario

```bash
# En base de datos default
python manage.py createsuperuser

# En base de datos remota (si es necesario)
python manage.py createsuperuser --database=remote
```

## Scripts de Cambio de Base de Datos

Para facilitar el cambio entre SQLite y PostgreSQL local, se proporcionan scripts automatizados:

### Linux/macOS

#### Cambiar a PostgreSQL Local

```bash
# Dar permisos de ejecución
chmod +x switch_to_postgres.sh

# Ejecutar script
./switch_to_postgres.sh
```

El script:
- Verifica que PostgreSQL esté instalado y corriendo
- Solicita credenciales de PostgreSQL
- Crea la base de datos si no existe
- Ofrece migrar datos de SQLite a PostgreSQL
- Configura variables de entorno en archivo `.env`
- Ejecuta migraciones
- Importa datos si se seleccionó migración

#### Cambiar a SQLite Local

```bash
# Dar permisos de ejecución
chmod +x switch_to_sqlite.sh

# Ejecutar script
./switch_to_sqlite.sh
```

El script:
- Ofrece migrar datos de PostgreSQL a SQLite
- Configura variables de entorno para usar SQLite
- Ejecuta migraciones en SQLite
- Importa datos si se seleccionó migración

### Windows

#### Cambiar a PostgreSQL Local

```cmd
switch_to_postgres.bat
```

El script:
- Verifica que PostgreSQL esté instalado y en el PATH
- Solicita credenciales de PostgreSQL
- Crea la base de datos si no existe
- Ofrece migrar datos de SQLite a PostgreSQL
- Configura variables de entorno en archivo `.env`
- Ejecuta migraciones
- Importa datos si se seleccionó migración

#### Cambiar a SQLite Local

```cmd
switch_to_sqlite.bat
```

El script:
- Ofrece migrar datos de PostgreSQL a SQLite
- Configura variables de entorno para usar SQLite
- Ejecuta migraciones en SQLite
- Importa datos si se seleccionó migración

### Notas sobre los Scripts

- Los scripts crean o actualizan un archivo `.env` en la raíz del proyecto
- Las migraciones de datos usan `dumpdata` y `loaddata` de Django
- Los archivos de backup temporales se eliminan automáticamente si la importación es exitosa
- Si hay errores en la importación, los archivos de backup se mantienen para revisión manual
- Los scripts requieren que el entorno virtual de Python esté activado

## Recomendaciones

1. **Para POS Local con alta concurrencia**: Usar PostgreSQL local (`USE_LOCAL_POSTGRES=true`)
2. **Para desarrollo simple**: Usar SQLite local (`USE_LOCAL_POSTGRES=false`)
3. **Para producción**: Siempre PostgreSQL local
4. **Mantener credenciales seguras**: Nunca commitear contraseñas en el código
5. **Usar variables de entorno**: Configurar credenciales vía variables de entorno o archivo .env
6. **Backups regulares**: Implementar backups automáticos de PostgreSQL
7. **Usar scripts automatizados**: Los scripts `switch_to_postgres.sh/bat` y `switch_to_sqlite.sh/bat` facilitan el cambio entre bases de datos
