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

REM Verificar si Git Portable esta disponible
set "GIT_PATH=%~dp0tools\PortableGit\bin\git.exe"
IF NOT EXIST "%GIT_PATH%" (
    echo [ERROR] Git Portable no encontrado en: %GIT_PATH%
    echo.
    echo Por favor, ejecute primero el instalador o configure Git Portable:
    echo   1. Ejecute: instalador_pos_bat.bat
    echo   2. O ejecute: setup_git_portable_inline.bat
    echo.
    echo Si ya tiene Git instalado en el sistema, use actualizar_pos.bat en su lugar.
    echo.
    pause
    exit /b 1
)

echo [OK] Git Portable encontrado: %GIT_PATH%
echo.

REM Usar Git Portable para operaciones de Git
echo Usando Git Portable para actualizar el sistema...
echo.

REM Verificar estado actual del repositorio
echo Verificando estado del repositorio...
"%GIT_PATH%" status
if errorlevel 1 (
    echo [ERROR] Error al verificar estado del repositorio.
    pause
    exit /b 1
)

REM Obtener cambios remotos
echo Obteniendo cambios remotos...
"%GIT_PATH%" fetch origin
if errorlevel 1 (
    echo [ERROR] Error al obtener cambios remotos.
    pause
    exit /b 1
)

REM Verificar si hay cambios
echo Verificando si hay actualizaciones...
for /f "tokens=*" %%i in ('"%GIT_PATH%" rev-parse HEAD') do set LOCAL_COMMIT=%%i
for /f "tokens=*" %%i in ('"%GIT_PATH%" rev-parse origin/main') do set REMOTE_COMMIT=%%i

if "%LOCAL_COMMIT%"=="%REMOTE_COMMIT%" (
    echo [INFO] No hay actualizaciones disponibles.
    echo El sistema esta actualizado.
    echo.
    echo Presione cualquier tecla para salir...
    pause >nul
    exit /b 0
)

echo [OK] Hay actualizaciones disponibles.
echo.

REM Verificar si hay cambios locales sin commitear
echo Verificando cambios locales...
"%GIT_PATH%" diff --quiet
if not errorlevel 1 (
    "%GIT_PATH%" diff --cached --quiet
    if not errorlevel 1 (
        echo [OK] No hay cambios locales pendientes.
    ) else (
        echo [ADVERTENCIA] Hay cambios en el area de staging.
        echo Se hara backup de los cambios locales.
        goto create_backup
    )
) else (
    echo [ADVERTENCIA] Hay cambios locales sin commitear.
    echo Se hara backup de los cambios locales.
    goto create_backup
)

goto pull_changes

:create_backup
echo Creando backup de cambios locales...
set "BACKUP_DIR=%PROJECT_DIR%backup_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
mkdir "%BACKUP_DIR%"

REM Backup de archivos modificados
"%GIT_PATH%" diff --name-only > "%TEMP%\changed_files.txt"
for /f "tokens=*" %%f in (%TEMP%\changed_files.txt) do (
    if exist "%PROJECT_DIR%%%f" (
        copy "%PROJECT_DIR%%%f" "%BACKUP_DIR%\" >nul 2>&1
    )
)

REM Commit temporal de cambios locales
echo Haciendo commit temporal de cambios locales...
"%GIT_PATH%" add .
"%GIT_PATH%" commit -m "Backup automatico de cambios locales - %date% %time%"
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudo hacer commit de cambios locales.
    echo Continuando con actualizacion...
)

:pull_changes
echo Actualizando desde el repositorio remoto...
"%GIT_PATH%" pull origin main
if errorlevel 1 (
    echo [ERROR] Error al actualizar desde el repositorio.
    echo.
    echo Posibles causas:
    echo - Conflictos de merge
    echo - Problemas de red
    echo - Permisos insuficientes
    echo.
    echo Intente resolver manualmente:
    echo 1. Revise los conflictos con: "%GIT_PATH%" status
    echo 2. Resuelva los conflictos
    echo 3. Haga commit de los cambios
    echo 4. Vuelva a ejecutar este script
    echo.
    pause
    exit /b 1
)

echo [OK] Sistema actualizado exitosamente.
echo.

REM 1) Activar entorno virtual DJENV (o crearlo si no existe)
IF NOT EXIST DJENV (
    echo Entorno virtual DJENV no encontrado. Creando uno nuevo...
    python -m venv DJENV
    if errorlevel 1 (
        echo Error al crear el entorno virtual. Verifica que Python este instalado.
        pause
        exit /b 1
    )
) ELSE (
    echo Activando entorno virtual DJENV existente...
)

call DJENV\Scripts\activate
if errorlevel 1 (
    echo No se pudo activar el entorno virtual DJENV.
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

REM 4) Ejecutar migraciones (local y remota)
echo Ejecutando migraciones locales...
python manage.py migrate
if errorlevel 1 (
    echo Error ejecutando migraciones locales.
    pause
    exit /b 1
)
echo Ejecutando migraciones en servidor remoto...
python manage.py migrate --database=remote
if errorlevel 1 (
    echo [ADVERTENCIA] Error ejecutando migraciones remotas. Continuando...
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
  call DJENV\Scripts\activate
  python manage.py runserver 0.0.0.0:8000
echo.
echo Presione cualquier tecla para salir...
pause >nul
