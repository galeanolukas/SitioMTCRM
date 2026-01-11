@echo off
REM Actualizador POS Portable con Git Portable - Windows
REM Requiere Git Portable en USB o carpeta local

echo ============================================
echo  Actualizador POS Portable - MultilideresCRM
echo  Versión con Git Portable (thumbdrive edition)
echo ============================================
echo.

REM Configuración de rutas
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%"
set "GIT_PORTABLE_DIR=%SCRIPT_DIR%tools\git-portable"
set "GIT_CMD=%GIT_PORTABLE_DIR%\bin\git.exe"
set "GIT_BASH=%GIT_PORTABLE_DIR%\git-bash.exe"

REM Verificar si Git Portable existe
if not exist "%GIT_CMD%" (
    echo [ERROR] Git Portable no encontrado.
    echo.
    echo Descargue Git Portable desde:
    echo   https://git-scm.com/download/win
    echo.
    echo Extraiga en: %GIT_PORTABLE_DIR%
    echo.
    echo Estructura esperada:
    echo   tools\git-portable\
    echo   ├── bin\git.exe
    echo   ├── git-bash.exe
    echo   └── ...
    echo.
    pause
    exit /b 1
)

echo [OK] Git Portable encontrado en: %GIT_PORTABLE_DIR%
echo.

REM Verificar conexión a internet
echo Verificando conexion a internet...
ping -n 1 google.com >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No hay conexion a internet.
    echo Verifique su conexion y vuelva a intentarlo.
    pause
    exit /b 1
)

echo [OK] Conexion a internet verificada.
echo.

REM Verificar si hay cambios pendientes
echo Verificando cambios locales...
"%GIT_CMD%" status --porcelain >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudo verificar el estado del repositorio.
    echo Continuando con la actualizacion...
)

REM Contar archivos modificados
for /f %%i in ('"%GIT_CMD%" status --porcelain ^| find /c /v ""') do set CHANGES_COUNT=%%i

if %CHANGES_COUNT% gtr 0 (
    echo.
    echo [ADVERTENCIA] Hay cambios locales no guardados:
    echo.
    "%GIT_CMD%" status --short
    echo.
    echo Estos cambios se perderan si continua con la actualizacion.
    echo.
    set /p continue="Desea continuar con la actualizacion? (S/N): "
    if /i not "%continue%"=="S" (
        echo Actualizacion cancelada.
        pause
        exit /b 0
    )
)

REM Backup de archivos importantes si existen
if exist venv (
    echo Haciendo backup del entorno virtual...
    if exist venv_backup (
        rmdir /s /q venv_backup
    )
    move venv venv_backup
)

REM Backup de la base de datos local si existe
if exist db.sqlite3 (
    echo Haciendo backup de la base de datos local...
    if exist db.sqlite3_backup (
        del db.sqlite3_backup
    )
    copy db.sqlite3 db.sqlite3_backup
)

echo Actualizando codigo desde GitHub...
"%GIT_CMD%" fetch origin
"%GIT_CMD%" reset --hard origin/main
if errorlevel 1 (
    echo [ERROR] Error al actualizar desde GitHub.
    echo Verifique su conexion a internet o si hay conflictos de fusion.
    echo.
    echo Si hay conflictos, resuelvalos manualmente y vuelva a ejecutar.
    
    REM Restaurar backup si falla
    if exist venv_backup (
        echo Restaurando entorno virtual desde backup...
        move venv_backup venv
    )
    
    if exist db.sqlite3_backup (
        echo Restaurando base de datos desde backup...
        move db.sqlite3_backup db.sqlite3
    )
    
    pause
    exit /b 1
)

echo [OK] Codigo actualizado exitosamente.
echo.

REM 1) Activar entorno virtual (o crearlo si no existe)
IF NOT EXIST venv (
    echo Entorno virtual no encontrado. Creando uno nuevo...
    python -m venv venv
    if errorlevel 1 (
        echo Error al crear el entorno virtual. Verifica que Python este instalado.
        pause
        exit /b 1
    )
) ELSE (
    echo Activando entorno virtual existente...
)

call venv\Scripts\activate
if errorlevel 1 (
    echo No se pudo activar el entorno virtual.
    pause
    exit /b 1
)

REM 2) Actualizar pip
echo Actualizando pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo Error actualizando pip. Continuando de todas formas...
)

REM 3) Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error instalando dependencias.
    pause
    exit /b 1
)

REM 4) Ejecutar migraciones
echo Ejecutando migraciones...
python manage.py migrate
if errorlevel 1 (
    echo Error ejecutando migraciones.
    pause
    exit /b 1
)

REM 5) Limpiar backup antiguo si la actualizacion fue exitosa
if exist venv_backup (
    echo Limpiando backup antiguo...
    rmdir /s /q venv_backup
)

if exist db.sqlite3_backup (
    echo Limpiando backup de base de datos...
    del db.sqlite3_backup
)

echo.
echo ============================================
echo Actualizacion completada exitosamente!
echo ============================================
echo.
echo Sistema actualizado con Git Portable.
echo.
echo Para iniciar el POS local:
echo   call venv\Scripts\activate
echo   python manage.py runserver 0.0.0.0:8000
echo.
echo Presione cualquier tecla para salir...
pause >nul
