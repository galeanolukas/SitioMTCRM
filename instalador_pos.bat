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
REM 1) Verificar Python 3.12
REM ---------------------------------------------------------------------------
set "TOOLS_DIR=%~dp0tools"
set "PYTHON_INSTALLER="
for %%f in ("%TOOLS_DIR%\python-3.12*-amd64.exe") do set "PYTHON_INSTALLER=%%f"
set "PYTHON_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"

python --version >nul 2>&1
if errorlevel 1 goto :py_missing

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VERSION=%%v"
for /f "tokens=1,2 delims=." %%a in ("!PY_VERSION!") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)
echo [INFO] Python detectado: !PY_VERSION!
if not "!PY_MAJOR!"=="3" goto :py_wrong
if not "!PY_MINOR!"=="12" goto :py_warn
goto :py_ok

:py_wrong
echo [ERROR] Se requiere Python 3.12.x. Version detectada: !PY_VERSION!
goto :py_install

:py_missing
echo [ADVERTENCIA] Python no esta instalado o no esta en el PATH.
goto :py_install

:py_install
echo.
echo   Puede instalar Python 3.12 desde:
if defined PYTHON_INSTALLER (
    echo   [1] Usar instalador en tools\: !PYTHON_INSTALLER!
) else (
    echo   [1] Descargar desde internet y instalar
)
echo   [2] Salir e instalar manualmente
echo.
set /p "PY_CHOICE=  Seleccione una opcion [1]: "
if "!PY_CHOICE!"=="" set "PY_CHOICE=1"
if "!PY_CHOICE!"=="2" (
    echo Descargue Python 3.12 desde https://www.python.org/downloads/release/python-3120/
    pause
    exit /b 1
)
if not "!PY_CHOICE!"=="1" goto :py_install

if not defined PYTHON_INSTALLER (
    echo Descargando Python 3.12...
    if not exist "%TOOLS_DIR%" mkdir "%TOOLS_DIR%"
    curl -L -o "%TOOLS_DIR%\python-3.12.10-amd64.exe" "%PYTHON_URL%"
    if errorlevel 1 (
        echo [ERROR] No se pudo descargar Python.
        echo         URL: %PYTHON_URL%
        pause
        exit /b 1
    )
    set "PYTHON_INSTALLER=%TOOLS_DIR%\python-3.12.10-amd64.exe"
)
echo Instalando Python 3.12 silenciosamente...
echo   (Requiere permisos de administrador. Si falla, ejecute como admin.)
"!PYTHON_INSTALLER!" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
if errorlevel 1 (
    echo [ERROR] No se pudo instalar Python 3.12.
    echo         Intente ejecutar este script como administrador.
    pause
    exit /b 1
)
echo [OK] Python 3.12 instalado.
REM Refrescar PATH de esta sesion
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%b"
set "PATH=!SYS_PATH!;%PATH%"
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python se instalo pero no se encuentra en el PATH.
    echo         Abra una nueva terminal y vuelva a ejecutar este script.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VERSION=%%v"
echo [INFO] Python detectado: !PY_VERSION!
goto :py_ok

:py_warn
echo [ADVERTENCIA] Version detectada: !PY_VERSION!. Se recomienda Python 3.12.x.
echo   requirements.txt usa Pillow 10.4.0 y psycopg2-binary 2.9.9, que solo
echo   tienen wheels precompilados hasta Python 3.12. Con !PY_VERSION! es
echo   probable que pip intente compilar desde source y falle.
set /p "CONT_PY=  Desea continuar de todas formas? (s/n) [n]: "
if /I not "!CONT_PY!"=="s" (
    echo Instalacion cancelada. Instale Python 3.12.x e intente nuevamente.
    pause
    exit /b 1
)
echo.

:py_ok

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

if not defined PGSQL_BIN goto :pg_missing
goto :pg_found

:pg_missing
echo.
echo [ADVERTENCIA] PostgreSQL no esta instalado o psql no esta en el PATH.
set "PG_INSTALLER="
for %%f in ("%TOOLS_DIR%\postgresql-*-windows-x64.exe") do set "PG_INSTALLER=%%f"
set "PG_URL=https://get.enterprisedb.com/postgresql/postgresql-16.15-1-windows-x64.exe"
echo.
echo   Puede instalar PostgreSQL desde:
if defined PG_INSTALLER (
    echo   [1] Usar instalador en tools\: !PG_INSTALLER!
) else (
    echo   [1] Descargar desde internet y instalar (~350 MB)
)
echo   [2] Ingresar ruta manualmente a psql.exe
echo   [3] Salir e instalar manualmente
echo.
set /p "PG_CHOICE=  Seleccione una opcion [1]: "
if "!PG_CHOICE!"=="" set "PG_CHOICE=1"

if "!PG_CHOICE!"=="3" (
    echo Descargue PostgreSQL desde https://www.postgresql.org/download/windows/
    pause
    exit /b 1
)
if "!PG_CHOICE!"=="2" goto :pg_manual
if not "!PG_CHOICE!"=="1" goto :pg_invalid

REM Opcion 1: instalar desde tools/ o descargar
if not defined PG_INSTALLER (
    echo Descargando PostgreSQL 16 (~350 MB, puede tardar varios minutos)...
    if not exist "%TOOLS_DIR%" mkdir "%TOOLS_DIR%"
    curl -L -o "%TOOLS_DIR%\postgresql-16.15-1-windows-x64.exe" "%PG_URL%"
    if errorlevel 1 (
        echo [ERROR] No se pudo descargar PostgreSQL.
        echo         URL: %PG_URL%
        pause
        exit /b 1
    )
    set "PG_INSTALLER=%TOOLS_DIR%\postgresql-16.15-1-windows-x64.exe"
)
echo Instalando PostgreSQL silenciosamente...
echo   (Requiere permisos de administrador. Si falla, ejecute como admin.)
"!PG_INSTALLER!" --mode unattended --unattendedmodeui none --superpassword %DEFAULT_POSTGRES_PASS% --serverport %DEFAULT_DB_PORT%
if errorlevel 1 (
    echo [ERROR] No se pudo instalar PostgreSQL.
    pause
    exit /b 1
)
echo [OK] PostgreSQL instalado.
REM Buscar psql recien instalado
for %%v in (18 17 16 15 14 13) do (
    if exist "C:\Program Files\PostgreSQL\%%v\bin\psql.exe" (
        set "PGSQL_BIN=C:\Program Files\PostgreSQL\%%v\bin\psql.exe"
    )
)
if not defined PGSQL_BIN (
    echo [ERROR] PostgreSQL se instalo pero no se encontro psql.exe.
    echo         Abra una nueva terminal y vuelva a ejecutar este script.
    pause
    exit /b 1
)
goto :pg_found

:pg_manual
set /p "PSQL_PATH= Ingrese la ruta completa a psql.exe: "
if not "!PSQL_PATH!"=="" if exist "!PSQL_PATH!" (
    set "PGSQL_BIN=!PSQL_PATH!"
    goto :pg_found
)
echo [ERROR] La ruta ingresada no existe.
pause
exit /b 1

:pg_invalid
echo [ERROR] Opcion invalida.
pause
exit /b 1

:pg_found
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
REM 4.5) Configurar dominio local (DNS local)
REM ---------------------------------------------------------------------------
set "LOCAL_DOMAIN="
echo.
echo ------------------------------------------------------------
echo   Configuracion de dominio local ^(DNS local^)
echo ------------------------------------------------------------
echo   Permite acceder al sistema usando un nombre personalizado
echo   en lugar de localhost ^(ej: techventas.app^)
set /p "CONFIG_DOMAIN=  Desea configurar un dominio local? (s/n) [n]: "
if /I not "%CONFIG_DOMAIN%"=="s" goto :dns_skip

set /p "INPUT_DOMAIN=  Ingrese el dominio local [techventas.app]: "
if "!INPUT_DOMAIN!"=="" (
    set "LOCAL_DOMAIN=techventas.app"
) else (
    set "LOCAL_DOMAIN=!INPUT_DOMAIN!"
)

REM Verificar si ya existe en hosts
findstr /C:"!LOCAL_DOMAIN!" "%SystemRoot%\System32\drivers\etc\hosts" >nul 2>&1
if not errorlevel 1 (
    echo [OK] El dominio '!LOCAL_DOMAIN!' ya existe en el archivo hosts.
    goto :dns_done
)

REM Intentar agregar al archivo hosts
REM Usar archivo temporal + type para evitar errores de redirect en consola
set "HOSTS_FILE=%SystemRoot%\System32\drivers\etc\hosts"
set "HOSTS_TMP=%TEMP%\hosts_append.txt"
(echo 127.0.0.1 !LOCAL_DOMAIN!) > "%HOSTS_TMP%" 2>nul
if errorlevel 1 goto :dns_fail
type "%HOSTS_TMP%" >> "%HOSTS_FILE%" 2>nul
if errorlevel 1 goto :dns_fail
del "%HOSTS_TMP%" 2>nul
echo [OK] Dominio '!LOCAL_DOMAIN!' agregado al archivo hosts.
goto :dns_done

:dns_fail
del "%HOSTS_TMP%" 2>nul
echo [ADVERTENCIA] No se pudo modificar el archivo hosts.
echo   Ejecute como administrador o agregue manualmente:
echo   127.0.0.1 !LOCAL_DOMAIN!
echo   en: C:\Windows\System32\drivers\etc\hosts
set "LOCAL_DOMAIN="
goto :dns_done

:dns_skip
echo   Dominio local no configurado. Se usara localhost.

:dns_done

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
        echo # Base de datos local PostgreSQL - usuario DEDICADO de la app
        echo DB_NAME=%DEFAULT_DB_NAME%
        echo DB_USER=%DEFAULT_DB_USER%
        echo DB_PASSWORD=%DEFAULT_DB_PASS%
        echo DB_HOST=%DEFAULT_DB_HOST%
        echo DB_PORT=%DEFAULT_DB_PORT%
        echo.
        echo # Base de datos remota servidor central
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
        echo.
        echo # Dominio local DNS local
        echo LOCAL_DOMAIN=!LOCAL_DOMAIN!
    ) > .env
) else (
    echo Actualizando variables de base de datos en .env...
    call :UpdateEnvVar DB_NAME %DEFAULT_DB_NAME%
    call :UpdateEnvVar DB_USER %DEFAULT_DB_USER%
    call :UpdateEnvVar DB_PASSWORD %DEFAULT_DB_PASS%
    call :UpdateEnvVar DB_HOST %DEFAULT_DB_HOST%
    call :UpdateEnvVar DB_PORT %DEFAULT_DB_PORT%
    call :UpdateEnvVar LOCAL_DOMAIN !LOCAL_DOMAIN!
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
REM 4.6) Verificar GTK3 Runtime (requerido por WeasyPrint)
REM ---------------------------------------------------------------------------
set "GTK_FOUND="
for %%p in (
    "C:\Program Files\GTK3-Runtime Win64\bin"
    "C:\GTK3-Runtime Win64\bin"
    "C:\Program Files\GTK3-Runtime\bin"
) do (
    if exist "%%~p\libgobject-2.0-0.dll" set "GTK_FOUND=%%~p"
)

if defined GTK_FOUND (
    echo [OK] GTK3 Runtime detectado: !GTK_FOUND!
) else (
    echo [ADVERTENCIA] GTK3 Runtime no encontrado (requerido por WeasyPrint).
    set "GTK_INSTALLER="
    for %%f in ("%TOOLS_DIR%\gtk3-runtime-*-ts-win64.exe") do set "GTK_INSTALLER=%%f"
    set "GTK_URL=https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/download/2022-01-04/gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe"
    echo.
    echo   Puede instalar GTK3 Runtime desde:
    if defined GTK_INSTALLER (
        echo   [1] Usar instalador en tools\: !GTK_INSTALLER!
    ) else (
        echo   [1] Descargar desde internet y instalar (~47 MB)
    )
    echo   [2] Continuar sin instalar (WeasyPrint no funcionara)
    echo   [3] Salir
    echo.
    set /p "GTK_CHOICE=  Seleccione una opcion [1]: "
    if "!GTK_CHOICE!"=="" set "GTK_CHOICE=1"

    if "!GTK_CHOICE!"=="3" (
        pause
        exit /b 1
    )
    if "!GTK_CHOICE!"=="2" (
        echo   Continuando sin GTK3. WeasyPrint puede fallar al generar PDFs.
        goto :gtk_done
    )
    if not "!GTK_CHOICE!"=="1" goto :gtk_done

    if not defined GTK_INSTALLER (
        echo Descargando GTK3 Runtime...
        if not exist "%TOOLS_DIR%" mkdir "%TOOLS_DIR%"
        curl -L -o "%TOOLS_DIR%\gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe" "%GTK_URL%"
        if errorlevel 1 (
            echo [ERROR] No se pudo descargar GTK3 Runtime.
            echo         Continuando sin GTK3...
            goto :gtk_done
        )
        set "GTK_INSTALLER=%TOOLS_DIR%\gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe"
    )
    echo Instalando GTK3 Runtime silenciosamente...
    "!GTK_INSTALLER!" /S
    if errorlevel 1 (
        echo [ADVERTENCIA] No se pudo instalar GTK3 Runtime.
        echo           Continuando sin GTK3...
    ) else (
        echo [OK] GTK3 Runtime instalado.
    )
)
:gtk_done

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
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ============================================
    echo   [ERROR] Fallo la instalacion de dependencias.
    echo ============================================
    echo.
    echo Posibles causas:
    echo   - Algun paquete no tiene wheel para su version de Python.
    echo   - Sin conexion a internet / PyPI no responde.
    echo   - pip desactualizado (ya se intento actualizar).
    echo.
    echo Sugerencias:
    echo   - Verifique su version de Python: python --version
    echo     Si es muy nueva (ej. 3.14), asegurese de que requirements.txt
    echo     use versiones de paquetes con wheels para esa version.
    echo   - Reintente: active DJENV y ejecute manualmente:
    echo       call DJENV\Scripts\activate
    echo       pip install -r requirements.txt
    echo   - Si un paquete especifico falla, instale primero esa dependencia
    echo     por separado para ver el error completo.
    echo.
    pause
    exit /b 1
)
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
        echo timeout /t 7 /nobreak ^^>nul
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
if not "!LOCAL_DOMAIN!"=="" (
    echo URL del sistema: http://!LOCAL_DOMAIN!:8000/erp/launcher/
    echo URL del POS:     http://!LOCAL_DOMAIN!:8000/erp/sale/pos/
) else (
    echo URL del sistema: http://localhost:8000/erp/launcher/
    echo URL del POS:     http://localhost:8000/erp/sale/pos/
)
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
