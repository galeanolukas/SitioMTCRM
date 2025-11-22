@echo off
REM Actualizar POS local de SitioMTCRM en Windows

REM Ir siempre a la carpeta donde esta este script
cd /d "%~dp0"

echo ============================================
echo  Actualizador POS Local - SitioMTCRM
echo ============================================
echo.

REM Verificar que exista el entorno virtual
if not exist venv\Scripts\activate.bat (
    echo [ERROR] Entorno virtual no encontrado.
    echo Cree el venv primero (ejecute instalador_pos_bat.bat).
    pause
    exit /b 1
)

REM Verificar que Git este instalado
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git no esta instalado o no se encuentra en el PATH.
    echo Instale Git para Windows desde:
    echo   https://git-scm.com/download/win
    echo y luego vuelva a ejecutar este actualizador.
    pause
    exit /b 1
)

REM Activar entorno virtual
call venv\Scripts\activate
if errorlevel 1 (
    echo [ERROR] No se pudo activar el entorno virtual.
    pause
    exit /b 1
)

echo 1) Actualizando codigo desde Git (git pull)...
git pull
if errorlevel 1 (
    echo [ERROR] Error ejecutando git pull. Verifique la conexion a Internet o la configuracion del repositorio.
    pause
    exit /b 1
)

echo.
echo 2) Actualizando dependencias (pip install -r requirements.txt)...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ADVERTENCIA] Hubo errores actualizando dependencias. Revise el log anterior.
    echo Puede continuar, pero si el POS falla revise manualmente.
)

echo.
echo 3) Aplicando migraciones (python manage.py migrate)...
python manage.py migrate
if errorlevel 1 (
    echo [ERROR] Error ejecutando migraciones.
    pause
    exit /b 1
)

echo.
echo ============================================
echo Actualizacion completada.
echo Ya puede volver a iniciar el POS con lanzar_pos.bat
echo ============================================

pause
