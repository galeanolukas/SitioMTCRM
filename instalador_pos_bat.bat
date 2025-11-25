@echo off
REM Ir siempre a la carpeta donde está este script
cd /d "%~dp0"

echo ============================================
echo Instalador POS Local - SitioMTCRM (Windows)
echo ============================================
echo.

REM Verificar si Git esta instalado (recomendado para futuras actualizaciones)
git --version >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] Git no esta instalado o no se encuentra en el PATH.
    echo Para usar el actualizador automatico llamado actualizar_pos.bat debe tener Git para Windows instalado.
    echo Puede descargar Git para Windows desde la pagina oficial:
    echo   https://git-scm.com/download/win
    echo.
    echo Este instalador continuara, pero las actualizaciones futuras deberan hacerse manualmente si no instala Git.
    echo.
)

REM 1) Crear entorno virtual si no existe
IF NOT EXIST venv (
    echo Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo Error al crear el entorno virtual. Verifica que Python este instalado y en el PATH.
        pause
        exit /b 1
    )
) ELSE (
    echo Entorno virtual ya existe.
)

REM 2) Activar entorno virtual
call venv\Scripts\activate
if errorlevel 1 (
    echo No se pudo activar el entorno virtual.
    pause
    exit /b 1
)

REM 2.1) Actualizar pip en el entorno virtual
echo Actualizando pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo No se pudo actualizar pip. Continuando con la instalacion de dependencias...
) else (
    echo pip actualizado correctamente.
)

REM 3) Instalar dependencias (incluye pandas y openpyxl desde requirements.txt)
echo Instalando dependencias desde requirements.txt...

REM Asegurar que no quede instalada la libreria vieja pandas-openpyxl
pip uninstall -y pandas-openpyxl >nul 2>&1

pip install -r requirements.txt
if errorlevel 1 (
    echo Error instalando dependencias.
    pause
    exit /b 1
)

REM Verificacion rapida de pandas y openpyxl en este entorno virtual
python -c "import pandas, openpyxl; print('pandas:', pandas.__version__)" >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudo importar pandas u openpyxl en el entorno virtual.
    echo Verifique la instalacion manualmente con:
    echo   call venv\Scripts\activate
    echo   pip install pandas openpyxl
)

REM 4) Migraciones
echo Creando migraciones si hacen falta (apps user y erp)...
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

echo.
echo ============================================
echo Instalacion terminada.
echo ============================================
echo Si es la primera vez, crea un superusuario con:
echo   python manage.py createsuperuser
echo.
echo Para iniciar el POS local:
echo   call venv\Scripts\activate
echo   python manage.py runserver 0.0.0.0:8000
echo y luego abre: http://localhost:8000/erp/sale/pos/
echo.
echo Para futuras actualizaciones del POS (nueva version desde GitHub):
echo   1) Cierre el POS.
echo   2) Ejecute: actualizar_pos.bat
echo   3) Vuelva a iniciar con lanzar_pos.bat
echo ============================================

REM Crear acceso directo (launcher) en el escritorio para el POS local
set "LAUNCHER_TARGET=%CD%\lanzar_pos.bat"
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\POS_Local.lnk"
REM Icono esperado en la raiz del proyecto, junto a este instalador
set "ICON_FILE=%CD%\icon.ico"

echo Creando acceso directo en el escritorio...

if not exist "%LAUNCHER_TARGET%" (
    echo No se encontro el archivo lanzar_pos.bat en la carpeta del proyecto.
    echo Crea el archivo lanzar_pos.bat y vuelve a ejecutar este instalador.
    pause
    exit /b 1
)

REM Crear acceso directo usando PowerShell y WScript.Shell
powershell -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT_PATH%');$s.TargetPath='%LAUNCHER_TARGET%';$s.WorkingDirectory='%CD%';$s.IconLocation='%ICON_FILE%';$s.Save()" >nul 2>&1

if errorlevel 1 (
    echo No se pudo crear el acceso directo con PowerShell.
    echo Puedes crear manualmente un acceso directo a lanzar_pos.bat en el escritorio.
) else (
    echo Acceso directo creado en el escritorio: POS_Local.lnk
)

pause
