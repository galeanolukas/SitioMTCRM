@echo off
setlocal EnableDelayedExpansion
REM Ir siempre a la carpeta donde está este script
cd /d "%~dp0"

echo ============================================
echo Actualizador POS Local - SitioMTCRM (Windows)
echo ============================================
echo.

REM Verificar si Git esta instalado
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git no esta instalado o no se encuentra en el PATH.
    echo Para usar este actualizador debe tener Git para Windows instalado.
    echo Puede descargar Git para Windows desde la pagina oficial:
    echo   https://git-scm.com/download/win
    echo.
    echo Instale Git y vuelva a ejecutar este script.
    pause
    exit /b 1
)

REM Verificar si estamos en un repositorio git
if not exist .git (
    echo [ERROR] No se encuentra el directorio .git en esta carpeta.
    echo Este script debe ejecutarse desde la raiz del proyecto clonado desde GitHub.
    echo.
    echo Si descargo el proyecto como ZIP, por favor:
    echo 1. Elimine la carpeta actual
    echo 2. Clone el repositorio con: git clone https://github.com/galeanolukas/SitioMTCRM.git
    echo 3. Vuelva a ejecutar este script desde la nueva carpeta
    pause
    exit /b 1
)

REM Verificar si hay cambios sin commitear
git status --porcelain >nul 2>&1
git diff-index --quiet HEAD --
if errorlevel 1 (
    echo [ADVERTENCIA] Se detectaron cambios locales sin guardar en Git.
    echo Estos cambios podrian perderse al actualizar desde GitHub.
    echo.
    echo Opciones:
    echo 1. Continuar con la actualizacion (los cambios locales se perderan)
    echo 2. Cancelar para hacer backup manual de los cambios
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
git pull origin main
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

REM Actualizar archivo de version
echo Actualizando archivo de version...
set "NEW_VERSION="
for /f "tokens=*" %%i in ('git describe --tags --abbrev=0 2^>nul') do set "NEW_VERSION=%%i"
if not defined NEW_VERSION for /f "tokens=*" %%i in ('git log -1 "--format=%%h"') do set "NEW_VERSION=%%i"
if not defined NEW_VERSION set "NEW_VERSION=unknown"
if "!NEW_VERSION:~0,1!"=="v" set "NEW_VERSION=!NEW_VERSION:~1!"
> version.txt echo !NEW_VERSION!
echo [OK] version.txt actualizado a !NEW_VERSION!

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
    echo No se pudo actualizar pip. Continuando con la instalacion de dependencias...
)

REM 3) Instalar/actualizar dependencias
echo Instalando/actualizando dependencias desde requirements.txt...

REM Asegurar que no quede instalada la libreria vieja pandas-openpyxl
pip uninstall -y pandas-openpyxl >nul 2>&1

pip install -r requirements.txt
if errorlevel 1 (
    echo Error instalando dependencias.
    pause
    exit /b 1
)

REM Verificacion rapida de pandas y openpyxl
python -c "import pandas, openpyxl; print('pandas:', pandas.__version__)" >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudo importar pandas u openpyxl en el entorno virtual.
    echo Verifique la instalacion manualmente.
)

REM 4) Migraciones
echo Creando migraciones si hacen falta...
python manage.py makemigrations user erp
if errorlevel 1 (
    echo Error ejecutando makemigrations.
    pause
    exit /b 1
)

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
echo El POS ha sido actualizado a la ultima version desde GitHub.
echo.
echo Para iniciar el POS actualizado:
echo   1) Cierre esta ventana
echo   2) Ejecute: lanzar_pos.bat
echo   3) Abra su navegador y acceda al sistema
echo.
echo Si experimenta problemas, puede verificar la version
echo en el menu Actualizaciones del sistema.
echo ============================================

pause
