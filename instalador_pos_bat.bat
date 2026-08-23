@echo off
REM Ir siempre a la carpeta donde está este script
cd /d "%~dp0"

echo ============================================
echo Instalador POS Local - SitioMTCRM (Windows)
echo ============================================
echo.

REM 1. Crear entorno virtual DJENV
IF NOT EXIST DJENV (
    echo Creando entorno virtual DJENV...
    python -m venv DJENV || exit /b 1
) ELSE (
    echo Entorno virtual DJENV ya existe.
)

REM 2. Activar entorno virtual
echo Activando entorno virtual...
call DJENV\Scripts\activate || exit /b 1

REM 3. Actualizar pip
echo Actualizando pip...
python -m pip install --upgrade pip

REM 4. Instalar dependencias
echo Instalando dependencias desde requirements.txt...
pip install -r requirements.txt || exit /b 1

REM 5. Verificar base de datos existente
echo Verificando base de datos existente...
IF EXIST db.sqlite3 (
    echo ADVERTENCIA: Se encontró una base de datos existente ^(db.sqlite3^)
    echo Esta acción podría eliminar todos los datos existentes ^(ventas, productos, clientes, etc.^)
    set /p clean_db="¿Desea eliminarla y crear una base de datos nueva? ^(S/N^): "
    if /i "%clean_db%"=="S" (
        echo Eliminando base de datos existente...
        del db.sqlite3
        echo Base de datos eliminada.
    ) else (
        echo Manteniendo base de datos existente.
    )
)

REM 6. Ejecutar migraciones
echo Ejecutando migraciones de la base de datos...
python manage.py makemigrations || exit /b 1
python manage.py migrate || exit /b 1

REM 6.5 Configurar roles estandar (vendedor, admin_empresa, servidor_local)
echo Configurando roles estandar...
python manage.py setup_roles --migrate
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudieron configurar los roles. Ejecute manualmente: python manage.py setup_roles --migrate
) else (
    echo Roles configurados correctamente ^(vendedor, admin_empresa, servidor_local^)
)

REM 7. Crear acceso directo en el escritorio
echo Creando acceso directo en el escritorio...

set "SHORTCUT=%USERPROFILE%\Desktop\POS SitioMTCRM.lnk"
set "TARGET=%~dp0lanzar_pos.bat"

REM Crear lanzador si no existe
if not exist "%TARGET%" (
    echo Creando lanzador lanzar_pos.bat...
    (
        echo @echo off
        echo cd /d "%%~dp0"
        echo call DJENV\Scripts\activate
        echo echo Iniciando POS Local SitioMTCRM...
        echo echo El servidor se iniciará en: http://127.0.0.1:8000/
        echo echo Presione Ctrl+C para detener el servidor.
        echo python manage.py runserver 0.0.0.0:8000
    ) > "%TARGET%"
)

REM Crear script VBScript temporal
set "VBS_SCRIPT=%TEMP%\CreateShortcut.vbs"
echo Set WshShell = CreateObject^("WScript.Shell"^) > "%VBS_SCRIPT%"
echo Set Shortcut = WshShell.CreateShortcut^("%SHORTCUT%"^) >> "%VBS_SCRIPT%"
echo Shortcut.TargetPath = "%TARGET%" >> "%VBS_SCRIPT%"
echo Shortcut.WorkingDirectory = "%~dp0" >> "%VBS_SCRIPT%"
echo Shortcut.IconLocation = "%~dp0icon.ico" >> "%VBS_SCRIPT%"
echo Shortcut.Description = "Sistema POS SitioMTCRM" >> "%VBS_SCRIPT%"
echo Shortcut.Save >> "%VBS_SCRIPT%"

REM Ejecutar el script VBScript
cscript //nologo "%VBS_SCRIPT%"

REM Limpiar script VBScript temporal
if exist "%VBS_SCRIPT%" del "%VBS_SCRIPT%"

REM 8. Mensaje final
echo.
echo ============================================
echo INSTALACIÓN COMPLETADA EXITOSAMENTE
echo ============================================
echo.
echo Componentes instalados:
echo   - Entorno virtual DJENV
echo   - Dependencias Python
echo   - Base de datos SQLite
echo   - Acceso directo en escritorio
echo.
echo Para iniciar el sistema:
echo   1. Use el acceso directo en el escritorio
echo   2. O ejecute: lanzar_pos.bat
echo.
echo El servidor se iniciará en: http://localhost:8000
echo.
echo NOTA: Para crear un superusuario, ejecute:
echo   python manage.py createsuperuser
echo.
pause
