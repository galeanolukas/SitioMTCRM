@echo off
setlocal EnableDelayedExpansion

REM ===========================================================================
REM Instalador completo (bootstrap) - SitioMTCRM / TechVentas (Windows)
REM ===========================================================================
REM Este script:
REM   1. Clona el repositorio desde GitHub (usando git del sistema o PortableGit)
REM   2. Descarga e instala Python 3.12, PostgreSQL 16 y GTK3 runtime
REM   3. Llama a instalador_pos.bat dentro del repositorio clonado
REM
REM Uso: ejecutar como administrador (click derecho -> Ejecutar como administrador)
REM ===========================================================================

cd /d "%~dp0"

REM ---------------------------------------------------------------------------
REM URLs de descarga (manifest embebido - ver tools/manifest.txt en el repo)
REM ---------------------------------------------------------------------------
set "PYTHON_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
set "PYTHON_EXE=python-3.12.10-amd64.exe"

set "PG_URL=https://get.enterprisedb.com/postgresql/postgresql-16.15-1-windows-x64.exe"
set "PG_EXE=postgresql-16.15-1-windows-x64.exe"
set "PG_SUPERPASS=postgres"

set "GTK_URL=https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/download/2022-01-04/gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe"
set "GTK_EXE=gtk3-runtime-3.24.31-2022-01-04-ts-win64.exe"

set "PORTABLEGIT_URL=https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.5/PortableGit-2.55.0.5-64-bit.7z.exe"
set "PORTABLEGIT_EXE=PortableGit-2.55.0.5-64-bit.7z.exe"

set "REPO_URL=https://github.com/galeanolukas/SitioMTCRM.git"
set "REPO_DIR=SitioMTCRM"

set "DOWNLOAD_DIR=%TEMP%\mtcrm_installer"

echo ============================================
echo   Instalador Completo - TechVentas
echo   (Windows - Bootstrap)
echo ============================================
echo.
echo Este script:
echo   1. Clona el repositorio desde GitHub
echo   2. Instala Python 3.12, PostgreSQL 16 y GTK3
echo   3. Ejecuta el instalador base del proyecto
echo.

REM ---------------------------------------------------------------------------
REM 0) Verificar permisos de administrador
REM ---------------------------------------------------------------------------
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Se requieren permisos de administrador.
    echo   Click derecho sobre este .bat -> "Ejecutar como administrador"
    pause
    exit /b 1
)
echo [OK] Permisos de administrador verificados.

REM ---------------------------------------------------------------------------
REM 1) Clonar repositorio (si no estamos ya dentro del repo)
REM ---------------------------------------------------------------------------
if exist "instalador_pos.bat" (
    echo [OK] Ya estamos dentro del repositorio. Se omite el clon.
    set "REPO_DIR=."
    goto :deps
)

if exist "%REPO_DIR%\instalador_pos.bat" (
    echo [OK] El repositorio ya existe en %REPO_DIR%\. Se omite el clon.
    goto :deps
)

echo.
echo --- Clonando repositorio ---
echo     URL: %REPO_URL%
echo     Dir: %REPO_DIR%\

REM 1a) Buscar git disponible
set "GIT_CMD=git"
where git >nul 2>&1
if errorlevel 1 (
    REM Intentar PortableGit en tools/ (si el script esta dentro del repo)
    if exist "tools\PortableGit\cmd\git.exe" (
        set "GIT_CMD=tools\PortableGit\cmd\git.exe"
        echo [INFO] Usando PortableGit de tools\
    ) else (
        REM Descargar PortableGit
        echo [INFO] Git no encontrado. Descargando PortableGit...
        if not exist "%DOWNLOAD_DIR%" mkdir "%DOWNLOAD_DIR%"
        curl -L -o "%DOWNLOAD_DIR%\%PORTABLEGIT_EXE%" "%PORTABLEGIT_URL%"
        if errorlevel 1 (
            echo [ERROR] No se pudo descargar PortableGit.
            echo         URL: %PORTABLEGIT_URL%
            pause
            exit /b 1
        )
        echo [OK] PortableGit descargado. Extrayendo...
        "%DOWNLOAD_DIR%\%PORTABLEGIT_EXE%" -y -o"%DOWNLOAD_DIR%\PortableGit"
        if errorlevel 1 (
            echo [ERROR] No se pudo extraer PortableGit.
            pause
            exit /b 1
        )
        set "GIT_CMD=%DOWNLOAD_DIR%\PortableGit\cmd\git.exe"
        echo [OK] PortableGit extraido.
    )
)

REM 1b) Clonar
echo Clonando...
"%GIT_CMD%" clone "%REPO_URL%" "%REPO_DIR%"
if errorlevel 1 (
    echo [ERROR] No se pudo clonar el repositorio.
    echo         Verifique conexion a internet.
    pause
    exit /b 1
)
echo [OK] Repositorio clonado en %REPO_DIR%\

REM ---------------------------------------------------------------------------
REM 2) Instalar dependencias (Python, PostgreSQL, GTK3)
REM ---------------------------------------------------------------------------
:deps
if not exist "%DOWNLOAD_DIR%" mkdir "%DOWNLOAD_DIR%"

REM --- 2a) Python 3.12 ---
echo.
echo --- Verificando Python 3.12 ---

REM Buscar python 3.12 en ubicaciones comunes
set "PYTHON_FOUND="
for %%p in (
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files (x86)\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) do (
    if exist "%%~p" (
        set "PYTHON_FOUND=%%~p"
    )
)

REM Tambien buscar en PATH
if not defined PYTHON_FOUND (
    python --version 2>nul | findstr "3.12" >nul
    if not errorlevel 1 (
        for /f "delims=" %%i in ('where python 2^>nul') do (
            if not defined PYTHON_FOUND set "PYTHON_FOUND=%%i"
        )
    )
)

if defined PYTHON_FOUND (
    echo [OK] Python 3.12 encontrado: !PYTHON_FOUND!
) else (
    echo [INFO] Python 3.12 no encontrado. Descargando...
    curl -L -o "%DOWNLOAD_DIR%\%PYTHON_EXE%" "%PYTHON_URL%"
    if errorlevel 1 (
        echo [ERROR] No se pudo descargar Python.
        echo         URL: %PYTHON_URL%
        pause
        exit /b 1
    )
    echo [OK] Python descargado. Instalando silenciosamente...
    "%DOWNLOAD_DIR%\%PYTHON_EXE%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar Python 3.12.
        pause
        exit /b 1
    )
    echo [OK] Python 3.12 instalado.
    set "PYTHON_FOUND=C:\Program Files\Python312\python.exe"
)

REM Refrescar PATH para que python sea visible en esta sesion
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%b"
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USR_PATH=%%b"
set "PATH=!SYS_PATH!;!USR_PATH!"

REM --- 2b) PostgreSQL 16 ---
echo.
echo --- Verificando PostgreSQL ---

set "PG_FOUND="
where psql >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('where psql 2^>nul') do set "PG_FOUND=%%i"
)
if not defined PG_FOUND (
    for %%v in (18 17 16 15 14 13) do (
        for %%b in (
            "C:\Program Files\PostgreSQL\%%v\bin\psql.exe"
            "C:\Program Files (x86)\PostgreSQL\%%v\bin\psql.exe"
        ) do (
            if exist "%%~b" if not defined PG_FOUND set "PG_FOUND=%%~b"
        )
    )
)

if defined PG_FOUND (
    echo [OK] PostgreSQL encontrado: !PG_FOUND!
) else (
    echo [INFO] PostgreSQL no encontrado. Descargando...
    echo        Tamano aprox: 350 MB (puede tardar varios minutos)...
    curl -L -o "%DOWNLOAD_DIR%\%PG_EXE%" "%PG_URL%"
    if errorlevel 1 (
        echo [ERROR] No se pudo descargar PostgreSQL.
        echo         URL: %PG_URL%
        pause
        exit /b 1
    )
    echo [OK] PostgreSQL descargado. Instalando silenciosamente...
    "%DOWNLOAD_DIR%\%PG_EXE%" --mode unattended --unattendedmodeui none --superpassword %PG_SUPERPASS% --serverport 5432
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar PostgreSQL.
        pause
        exit /b 1
    )
    echo [OK] PostgreSQL instalado (superpassword: %PG_SUPERPASS%).
    REM Buscar psql recien instalado
    for %%v in (18 17 16 15 14 13) do (
        if exist "C:\Program Files\PostgreSQL\%%v\bin\psql.exe" (
            set "PG_FOUND=C:\Program Files\PostgreSQL\%%v\bin\psql.exe"
        )
    )
)

REM Agregar PostgreSQL al PATH de esta sesion
if defined PG_FOUND (
    for %%f in ("!PG_FOUND!") do set "PG_DIR=%%~dpf"
    set "PATH=!PG_DIR!;!PATH!"
)

REM --- 2c) GTK3 Runtime (para WeasyPrint) ---
echo.
echo --- Verificando GTK3 Runtime ---

set "GTK_FOUND="
for %%p in (
    "C:\Program Files\GTK3-Runtime Win64\bin"
    "C:\GTK3-Runtime Win64\bin"
    "C:\Program Files\GTK3-Runtime\bin"
) do (
    if exist "%%~p\libgobject-2.0-0.dll" set "GTK_FOUND=%%~p"
)

if defined GTK_FOUND (
    echo [OK] GTK3 Runtime encontrado: !GTK_FOUND!
) else (
    echo [INFO] GTK3 Runtime no encontrado. Descargando...
    curl -L -o "%DOWNLOAD_DIR%\%GTK_EXE%" "%GTK_URL%"
    if errorlevel 1 (
        echo [ADVERTENCIA] No se pudo descargar GTK3 Runtime.
        echo           WeasyPrint puede no funcionar. Continuando...
        echo.
        goto :call_installer
    )
    echo [OK] GTK3 descargado. Instalando silenciosamente...
    "%DOWNLOAD_DIR%\%GTK_EXE%" /S
    if errorlevel 1 (
        echo [ADVERTENCIA] No se pudo instalar GTK3 Runtime.
        echo           WeasyPrint puede no funcionar. Continuando...
    ) else (
        echo [OK] GTK3 Runtime instalado.
    )
)

REM ---------------------------------------------------------------------------
REM 3) Llamar al instalador base del proyecto
REM ---------------------------------------------------------------------------
:call_installer
echo.
echo ============================================
echo   Llamando al instalador base del proyecto
echo ============================================
echo.

cd /d "%~dp0!REPO_DIR!"
if not exist "instalador_pos.bat" (
    echo [ERROR] No se encontro instalador_pos.bat en el directorio actual.
    echo         Directorio: %CD%
    pause
    exit /b 1
)

call instalador_pos.bat
set "INSTALL_RESULT=!errorlevel!"

REM ---------------------------------------------------------------------------
REM 4) Limpiar descargas temporales
REM ---------------------------------------------------------------------------
if exist "%DOWNLOAD_DIR%" (
    echo Limpiando archivos temporales...
    rmdir /s /q "%DOWNLOAD_DIR%" 2>nul
)

if !INSTALL_RESULT! neq 0 (
    echo.
    echo [ERROR] El instalador base finalizo con errores (codigo: !INSTALL_RESULT!).
    pause
    exit /b !INSTALL_RESULT!
)

echo.
echo ============================================
echo   INSTALACION COMPLETA
echo ============================================
echo.
pause
exit /b 0
