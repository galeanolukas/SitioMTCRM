@echo off
REM Script para cambiar de SQLite a PostgreSQL local
REM SitioMTCRM - Sistema de Gestión

echo ==========================================
echo   Cambiar a PostgreSQL Local
echo   SitioMTCRM
echo ==========================================
echo.

REM Verificar si PostgreSQL está instalado
where psql >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: PostgreSQL no esta instalado o no esta en el PATH
    echo.
    echo Instale PostgreSQL desde: https://www.postgresql.org/download/windows/
    pause
    exit /b 1
)

echo [OK] PostgreSQL encontrado
echo.

REM Configuración de base de datos
echo Configuracion de PostgreSQL local:
echo -----------------------------------
set /p DB_NAME="Nombre de la base de datos [sitiomtcrm]: "
if "%DB_NAME%"=="" set DB_NAME=sitiomtcrm

set /p DB_USER="Usuario de PostgreSQL [postgres]: "
if "%DB_USER%"=="" set DB_USER=postgres

set /p DB_PASSWORD="Contraseña de PostgreSQL: "

set /p DB_HOST="Host [localhost]: "
if "%DB_HOST%"=="" set DB_HOST=localhost

set /p DB_PORT="Puerto [5432]: "
if "%DB_PORT%"=="" set DB_PORT=5432

echo.
echo Verificando conexion a PostgreSQL...

REM Verificar conexion
set PGPASSWORD=%DB_PASSWORD%
psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d postgres -c "SELECT 1;" >nul 2>&1

if %errorlevel% neq 0 (
    echo ERROR: No se pudo conectar a PostgreSQL
    echo Verifique las credenciales y que PostgreSQL este corriendo
    pause
    exit /b 1
)

echo [OK] Conexion exitosa
echo.

REM Verificar si la base de datos existe
psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d postgres -c "SELECT 1 FROM pg_database WHERE datname='%DB_NAME%';" | findstr "1" >nul 2>&1

if %errorlevel% neq 0 (
    echo La base de datos '%DB_NAME%' no existe. Creandola...
    psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d postgres -c "CREATE DATABASE %DB_NAME% OWNER %DB_USER%;"
    echo [OK] Base de datos creada
    echo.
) else (
    echo [OK] Base de datos '%DB_NAME%' ya existe
    echo.
)

REM Preguntar si desea migrar datos de SQLite
if exist db.sqlite3 (
    echo Se encontro base de datos SQLite (db.sqlite3)
    set /p MIGRATE="¿Desea migrar los datos de SQLite a PostgreSQL? (s/n): "
    if /i "%MIGRATE%"=="s" (
        echo Exportando datos de SQLite...
        python manage.py dumpdata > sqlite_backup.json
        
        if %errorlevel% equ 0 (
            echo [OK] Datos exportados a sqlite_backup.json
        ) else (
            echo ERROR al exportar datos de SQLite
            echo Continuando sin migracion de datos...
        )
    )
    echo.
)

REM Configurar variables de entorno
echo Configurando variables de entorno...
echo.

REM Exportar variables de entorno para uso inmediato
set DB_NAME=%DB_NAME%
set DB_USER=%DB_USER%
set DB_PASSWORD=%DB_PASSWORD%
set DB_HOST=%DB_HOST%
set DB_PORT=%DB_PORT%

REM Crear archivo .env si no existe
if not exist .env (
    echo. > .env
)

REM Función para agregar/actualizar variable en .env
set "ENV_FILE=.env"
set "TEMP_FILE=.env.tmp"

REM Copiar archivo existente excluyendo las variables a actualizar
findstr /v "^USE_LOCAL_POSTGRES=" "%ENV_FILE%" > "%TEMP_FILE%" 2>nul
findstr /v "^DB_NAME=" "%TEMP_FILE%" > "%ENV_FILE%" 2>nul
findstr /v "^DB_USER=" "%ENV_FILE%" > "%TEMP_FILE%" 2>nul
findstr /v "^DB_PASSWORD=" "%TEMP_FILE%" > "%ENV_FILE%" 2>nul
findstr /v "^DB_HOST=" "%TEMP_FILE%" > "%ENV_FILE%" 2>nul
findstr /v "^DB_PORT=" "%TEMP_FILE%" > "%ENV_FILE%" 2>nul

REM Agregar nuevas variables
echo USE_LOCAL_POSTGRES=true >> "%ENV_FILE%"
echo DB_NAME=%DB_NAME% >> "%ENV_FILE%"
echo DB_USER=%DB_USER% >> "%ENV_FILE%"
echo DB_PASSWORD=%DB_PASSWORD% >> "%ENV_FILE%"
echo DB_HOST=%DB_HOST% >> "%ENV_FILE%"
echo DB_PORT=%DB_PORT% >> "%ENV_FILE%"

REM Limpiar archivo temporal
if exist "%TEMP_FILE%" del "%TEMP_FILE%"

echo [OK] Variables de entorno configuradas
echo.

REM Ejecutar migraciones
echo Ejecutando migraciones en PostgreSQL...

python manage.py migrate

if %errorlevel% neq 0 (
    echo ERROR al ejecutar migraciones
    pause
    exit /b 1
)

echo [OK] Migraciones ejecutadas exitosamente
echo.

REM Importar datos si se exportaron
if exist sqlite_backup.json (
    echo Importando datos a PostgreSQL...
    python manage.py loaddata sqlite_backup.json
    
    if %errorlevel% equ 0 (
        echo [OK] Datos importados exitosamente
        del sqlite_backup.json
        echo [OK] Archivo de backup eliminado
    ) else (
        echo ADVERTENCIA: Algunos datos no pudieron importarse
        echo El archivo sqlite_backup.json se mantuvo para revision manual
    )
    echo.
)

echo ==========================================
echo   ¡Cambio a PostgreSQL completado!
echo ==========================================
echo.
echo El sistema ahora usa PostgreSQL local.
echo Puede iniciar el servidor con:
echo   lanzar_pos.bat
echo.
pause
