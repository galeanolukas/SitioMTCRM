@echo off
setlocal EnableDelayedExpansion

REM Instalador POS Local - TechVentas (Windows)
REM Crea entorno, dependencias, DB PostgreSQL por defecto y migraciones.

cd /d "%~dp0"

REM ---------------------------------------------------------------------------
REM Configuración por defecto de PostgreSQL
REM ---------------------------------------------------------------------------
set "DEFAULT_POSTGRES_USER=postgres"
set "DEFAULT_POSTGRES_PASS=postgres"
set "DEFAULT_DB_NAME=mtcrm_pos"
set "DEFAULT_DB_USER=mtcrm_pos"
set "DEFAULT_DB_PASS=mtcrm_pos"
set "DEFAULT_DB_HOST=localhost"
set "DEFAULT_DB_PORT=5432"

echo ============================================
echo   Instalador POS Local - TechVentas
echo   (Windows)
echo ============================================
echo.

REM ---------------------------------------------------------------------------
REM 1) Verificar Python
REM ---------------------------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo Descarguela desde https://www.python.org/downloads/
    pause
    exit /b 1
)

REM ---------------------------------------------------------------------------
REM 2) Verificar PostgreSQL
REM ---------------------------------------------------------------------------
set "PGSQL_BIN="
for /f "delims=" %%i in ('where psql 2^>nul') do set "PGSQL_BIN=%%i"

if not defined PGSQL_BIN (
    for %%p in (
        "C:\Program Files\PostgreSQL\15\bin\psql.exe"
        "C:\Program Files\PostgreSQL\16\bin\psql.exe"
        "C:\Program Files\PostgreSQL\14\bin\psql.exe"
        "C:\Program Files\PostgreSQL\17\bin\psql.exe"
        "C:\Program Files\PostgreSQL\13\bin\psql.exe"
        "C:\Program Files\PostgreSQL\12\bin\psql.exe"
        "C:\Program Files\PostgreSQL\18\bin\psql.exe"
        "C:\Program Files (x86)\PostgreSQL\15\bin\psql.exe"
        "C:\Program Files (x86)\PostgreSQL\16\bin\psql.exe"
        "C:\Program Files (x86)\PostgreSQL\18\bin\psql.exe"
        "C:\Program Files\pgAdmin 4\v7\runtime\psql.exe"
        "C:\Program Files\pgAdmin 4\v6\runtime\psql.exe"
        "C:\Program Files\pgAdmin 4\v8\runtime\psql.exe"
    ) do (
        if exist "%%~p" set "PGSQL_BIN=%%~p"
    )
)

if not defined PGSQL_BIN (
    echo.
    echo [ADVERTENCIA] No se encontro psql automaticamente.
    set /p "PSQL_PATH= Ingrese la ruta completa a psql.exe o deje en blanco para salir: "
    if not "!PSQL_PATH!"=="" if exist "!PSQL_PATH!" (
        set "PGSQL_BIN=!PSQL_PATH!"
    )
)

if not defined PGSQL_BIN (
    echo [ERROR] PostgreSQL no esta instalado o psql no esta en el PATH.
    echo Descargue e instale PostgreSQL desde https://www.postgresql.org/download/windows/
    echo.
    pause
    exit /b 1
)

for %%f in ("%PGSQL_BIN%") do set "PSQL_DIR=%%~dpf"
set "PATH=%PSQL_DIR%;%PATH%"
echo [OK] PostgreSQL detectado: %PGSQL_BIN%

REM ---------------------------------------------------------------------------
REM 3) Crear usuario y base de datos PostgreSQL
REM ---------------------------------------------------------------------------
echo.
echo Conectando a PostgreSQL con superusuario '%DEFAULT_POSTGRES_USER%'...

set "PGPASSWORD=%DEFAULT_POSTGRES_PASS%"

REM Verificar conexion con contrasena por defecto
psql -U %DEFAULT_POSTGRES_USER% -h %DEFAULT_DB_HOST% -p %DEFAULT_DB_PORT% -c "SELECT 1;" >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudo conectar con la contrasena por defecto '%DEFAULT_POSTGRES_PASS%'.
    set /p "PG_INPUT=Contrasena del superusuario PostgreSQL [%DEFAULT_POSTGRES_USER%]: "
    if not "!PG_INPUT!"=="" (
        set "DEFAULT_POSTGRES_PASS=!PG_INPUT!"
        set "PGPASSWORD=!PG_INPUT!"
    )
    psql -U %DEFAULT_POSTGRES_USER% -h %DEFAULT_DB_HOST% -p %DEFAULT_DB_PORT% -c "SELECT 1;" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se pudo conectar a PostgreSQL. Verifique las credenciales.
        pause
        exit /b 1
    )
    echo [OK] Conectado con la contrasena ingresada.
) else (
    echo [OK] Conectado a PostgreSQL.
)

REM Crear usuario dedicado y base de datos
set "SQL_TEMP=%TEMP%\create_mtcrm_db.sql"
(
    echo SELECT pg_terminate_backend^(pid^) FROM pg_stat_activity WHERE datname = '%DEFAULT_DB_NAME%';
    echo DROP DATABASE IF EXISTS %DEFAULT_DB_NAME%;
    echo DROP ROLE IF EXISTS %DEFAULT_DB_USER%;
    echo CREATE ROLE %DEFAULT_DB_USER% WITH LOGIN PASSWORD '%DEFAULT_DB_PASS%';
    echo CREATE DATABASE %DEFAULT_DB_NAME% OWNER %DEFAULT_DB_USER%;
    echo GRANT ALL PRIVILEGES ON DATABASE %DEFAULT_DB_NAME% TO %DEFAULT_DB_USER%;
) > "%SQL_TEMP%"

psql -U %DEFAULT_POSTGRES_USER% -h %DEFAULT_DB_HOST% -p %DEFAULT_DB_PORT% -f "%SQL_TEMP%" >nul
if errorlevel 1 (
    echo [ERROR] No se pudo crear la base de datos o el usuario de la aplicacion.
    del "%SQL_TEMP%" 2>nul
    pause
    exit /b 1
)
del "%SQL_TEMP%" 2>nul
echo [OK] Base de datos '%DEFAULT_DB_NAME%' y usuario '%DEFAULT_DB_USER%' creados.

REM ---------------------------------------------------------------------------
REM 4) Configuracion de base de datos remota (opcional)
REM ---------------------------------------------------------------------------
set "REMOTE_DB_NAME="
set "REMOTE_DB_USER="
set "REMOTE_DB_PASSWORD="
set "REMOTE_DB_HOST=erp.multiliderestech.online"
set "REMOTE_DB_PORT=5432"
set "REMOTE_DB_SSLMODE=require"

REM Leer .env.server si existe
if exist .env.server (
    for /f "tokens=1,* delims==" %%a in (.env.server) do (
        if /I "%%a"=="REMOTE_DB_NAME" set "REMOTE_DB_NAME=%%b"
        if /I "%%a"=="REMOTE_DB_USER" set "REMOTE_DB_USER=%%b"
        if /I "%%a"=="REMOTE_DB_PASSWORD" set "REMOTE_DB_PASSWORD=%%b"
        if /I "%%a"=="REMOTE_DB_HOST" set "REMOTE_DB_HOST=%%b"
        if /I "%%a"=="REMOTE_DB_PORT" set "REMOTE_DB_PORT=%%b"
        if /I "%%a"=="REMOTE_DB_SSLMODE" set "REMOTE_DB_SSLMODE=%%b"
    )
)

echo.
echo ------------------------------------------------------------
echo   Configuracion de base de datos remota (servidor central)
echo ------------------------------------------------------------
echo   Host por defecto: %REMOTE_DB_HOST%
set /p "CONFIG_REMOTE=  Desea configurar la conexion remota? (s/n): "
if /I "%CONFIG_REMOTE%"=="s" (
    set /p "INPUT=  Host remoto [%REMOTE_DB_HOST%]: "
    if not "!INPUT!"=="" set "REMOTE_DB_HOST=!INPUT!"
    set /p "INPUT=  Puerto remoto [%REMOTE_DB_PORT%]: "
    if not "!INPUT!"=="" set "REMOTE_DB_PORT=!INPUT!"
    set /p "INPUT=  Nombre de la BD remota [%REMOTE_DB_NAME%]: "
    if not "!INPUT!"=="" set "REMOTE_DB_NAME=!INPUT!"
    set /p "INPUT=  Usuario remoto [%REMOTE_DB_USER%]: "
    if not "!INPUT!"=="" set "REMOTE_DB_USER=!INPUT!"
    set /p "INPUT=  Contrasena remota: "
    if not "!INPUT!"=="" set "REMOTE_DB_PASSWORD=!INPUT!"
    set /p "INPUT=  SSL mode [%REMOTE_DB_SSLMODE%]: "
    if not "!INPUT!"=="" set "REMOTE_DB_SSLMODE=!INPUT!"
    echo [OK] Configuracion remota guardada.
) else (
    echo   Conexion remota no configurada. Se puede agregar luego editando .env
)

REM ---------------------------------------------------------------------------
REM 5) Crear / actualizar .env
REM ---------------------------------------------------------------------------
if not exist .env (
    echo Creando archivo .env con configuracion por defecto...
    (
        echo # Entorno
        echo ENVIRONMENT=development
        echo APP_VERSION=1.0.0
        echo POS_SYNC_INTERVAL_SECONDS=300
        echo.
        echo # Base de datos local ^(PostgreSQL^) - usuario DEDICADO de la app
        echo DB_NAME=%DEFAULT_DB_NAME%
        echo DB_USER=%DEFAULT_DB_USER%
        echo DB_PASSWORD=%DEFAULT_DB_PASS%
        echo DB_HOST=%DEFAULT_DB_HOST%
        echo DB_PORT=%DEFAULT_DB_PORT%
        echo.
        echo # Base de datos remota ^(servidor central^)
        echo REMOTE_DB_NAME=%REMOTE_DB_NAME%
        echo REMOTE_DB_USER=%REMOTE_DB_USER%
        echo REMOTE_DB_PASSWORD=%REMOTE_DB_PASSWORD%
        echo REMOTE_DB_HOST=%REMOTE_DB_HOST%
        echo REMOTE_DB_PORT=%REMOTE_DB_PORT%
        echo REMOTE_DB_SSLMODE=%REMOTE_DB_SSLMODE%
        echo.
        echo # Configuracion sincronizacion
        echo POS_SYNC_PRODUCTS_MODE=safe
        echo.
        echo # AFIP
        echo AFIP_ACCESS_TOKEN=
        echo AFIP_CUIT=
        echo AFIP_ENVIRONMENT=dev
        echo.
        echo # Catalogo
        echo CATALOGO_URL=
        echo CATALOGO_API_KEY=
    ) > .env
) else (
    echo Actualizando variables de base de datos en .env...
    call :UpdateEnvVar DB_NAME %DEFAULT_DB_NAME%
    call :UpdateEnvVar DB_USER %DEFAULT_DB_USER%
    call :UpdateEnvVar DB_PASSWORD %DEFAULT_DB_PASS%
    call :UpdateEnvVar DB_HOST %DEFAULT_DB_HOST%
    call :UpdateEnvVar DB_PORT %DEFAULT_DB_PORT%
    if /I "!CONFIG_REMOTE!"=="s" (
        call :UpdateEnvVar REMOTE_DB_NAME %REMOTE_DB_NAME%
        call :UpdateEnvVar REMOTE_DB_USER %REMOTE_DB_USER%
        call :UpdateEnvVar REMOTE_DB_PASSWORD %REMOTE_DB_PASSWORD%
        call :UpdateEnvVar REMOTE_DB_HOST %REMOTE_DB_HOST%
        call :UpdateEnvVar REMOTE_DB_PORT %REMOTE_DB_PORT%
        call :UpdateEnvVar REMOTE_DB_SSLMODE %REMOTE_DB_SSLMODE%
    )
)
echo [OK] Archivo .env configurado.

REM ---------------------------------------------------------------------------
REM 5) Crear entorno virtual
REM ---------------------------------------------------------------------------
if not exist DJENV (
    echo Creando entorno virtual DJENV...
    python -m venv DJENV || exit /b 1
) else (
    echo [OK] Entorno virtual DJENV ya existe.
)

echo Activando entorno virtual...
call DJENV\Scripts\activate || exit /b 1

REM ---------------------------------------------------------------------------
REM 6) Instalar dependencias
REM ---------------------------------------------------------------------------
echo Actualizando pip...
python -m pip install --upgrade pip >nul

echo Instalando dependencias desde requirements.txt...
pip install -r requirements.txt || exit /b 1
echo [OK] Dependencias instaladas.

REM ---------------------------------------------------------------------------
REM 7) Migraciones y datos iniciales
REM ---------------------------------------------------------------------------
echo Creando migraciones...
python manage.py makemigrations user erp
if errorlevel 1 (
    echo [ERROR] Fallo makemigrations.
    pause
    exit /b 1
)

echo Aplicando migraciones...
python manage.py migrate
if errorlevel 1 (
    echo [ERROR] Fallo migrate.
    pause
    exit /b 1
)
echo [OK] Migraciones aplicadas.

REM ---------------------------------------------------------------------------
REM 8) Superusuario y roles
REM ---------------------------------------------------------------------------
echo Verificando superusuario...
python manage.py shell -c "from django.contrib.auth.models import User; print('CREATED' if not User.objects.filter(is_superuser=True).exists() and (User.objects.create_superuser('admin', 'admin@example.com', 'admin123') or True) else 'EXISTS')" > "%TEMP%\superuser_check.txt" 2>nul
findstr "CREATED" "%TEMP%\superuser_check.txt" >nul && (
    echo [OK] Superusuario creado: admin / admin123
) || (
    echo [OK] Superusuario ya existe.
)
del "%TEMP%\superuser_check.txt" 2>nul

echo Configurando roles estandar...
python manage.py setup_roles --migrate
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudieron configurar los roles.
) else (
    echo [OK] Roles configurados.
)

REM ---------------------------------------------------------------------------
REM 9) Crear / verificar lanzador
REM ---------------------------------------------------------------------------
set "TARGET=%~dp0lanzar_pos.bat"
if not exist "%TARGET%" (
    echo Creando lanzador lanzar_pos.bat...
    (
        echo @echo off
        echo cd /d "%%~dp0"
        echo call DJENV\Scripts\activate
        echo set ENVIRONMENT=development
        echo echo Iniciando servidor Django en http://localhost:8000 ...
        echo start "POS_Local_Django" python manage.py runserver 0.0.0.0:8000
        echo timeout /t 7 /nobreak ^>nul
        echo start "" "http://localhost:8000/erp/launcher/"
        echo exit
    ) > "%TARGET%"
)

REM ---------------------------------------------------------------------------
REM 10) Acceso directo en el escritorio con icono
REM ---------------------------------------------------------------------------
echo Creando acceso directo en el escritorio...
set "SHORTCUT=%USERPROFILE%\Desktop\TechVentas POS Local.lnk"
set "ICON=%~dp0icon.ico"

set "VBS_SCRIPT=%TEMP%\CreateShortcut.vbs"
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo Set Shortcut = WshShell.CreateShortcut^("%SHORTCUT%"^)
    echo Shortcut.TargetPath = "%TARGET%"
    echo Shortcut.WorkingDirectory = "%~dp0"
    echo Shortcut.IconLocation = "%ICON%"
    echo Shortcut.Description = "Sistema POS TechVentas"
    echo Shortcut.Save
) > "%VBS_SCRIPT%"

cscript //nologo "%VBS_SCRIPT%"
del "%VBS_SCRIPT%" 2>nul
echo [OK] Acceso directo creado: %SHORTCUT%

REM ---------------------------------------------------------------------------
REM 11) Final
REM ---------------------------------------------------------------------------
echo.
echo ============================================
echo   INSTALACION COMPLETADA
echo ============================================
echo.
echo Base de datos: %DEFAULT_DB_NAME% (%DEFAULT_DB_HOST%:%DEFAULT_DB_PORT%)
echo Usuario DB:    %DEFAULT_DB_USER%
echo Contrasena DB: %DEFAULT_DB_PASS%
echo.
echo Para iniciar el POS:
echo   - Use el acceso directo del escritorio
echo   - O ejecute: lanzar_pos.bat
echo.
echo URL del sistema: http://localhost:8000/erp/launcher/
echo URL del POS:     http://localhost:8000/erp/sale/pos/
echo.

choice /c SN /M "Desea iniciar el POS ahora"
if errorlevel 2 (
    pause
    exit /b 0
)
call "%TARGET%"
exit /b 0

REM ---------------------------------------------------------------------------
REM Subrutinas
REM ---------------------------------------------------------------------------
:UpdateEnvVar
setlocal
set "VAR_NAME=%~1"
set "VAR_VALUE=%~2"
set "FILE=.env"
set "TEMP_FILE=%TEMP%\.env.tmp"
if not exist "%TEMP_FILE%" type nul > "%TEMP_FILE%"
(
    for /f "delims=" %%a in (%FILE%) do (
        set "LINE=%%a"
        for /f "tokens=1,* delims==" %%b in ("%%a") do (
            if /I "%%b"=="%VAR_NAME%" (
                echo %VAR_NAME%=%VAR_VALUE%
            ) else (
                echo %%a
            )
        )
    )
) > "%TEMP_FILE%"
move /y "%TEMP_FILE%" "%FILE%" >nul
endlocal
goto :eof
