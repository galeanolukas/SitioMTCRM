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

REM 1) Crear entorno virtual venv si no existe
IF NOT EXIST venv (
    echo Creando entorno virtual venv...
    python -m venv venv
    if errorlevel 1 (
        echo Error al crear el entorno virtual venv. Verifica que Python este instalado y en el PATH.
        pause
        exit /b 1
    )
) ELSE (
    echo Entorno virtual venv ya existe.
)

REM 2) Activar entorno virtual venv
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
    echo Error actualizando pip. Continuando de todas formas...
)

REM 3) Instalar dependencias
echo Instalando dependencias desde requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error instalando dependencias.
    pause
    exit /b 1
)

REM Verificacion rapida de pandas y openpyxl en este entorno virtual
python -c "import pandas, openpyxl; print('pandas:', pandas.__version__)" >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudo importar pandas u openpyxl en el entorno virtual venv.
    echo Verifique la instalacion manualmente con:
    echo   call venv\Scripts\activate
    echo   pip install pandas openpyxl
)

REM 4) Configurar Git Portable para actualizaciones automaticas
echo.
echo ============================================
echo  Configurando Git Portable
echo ============================================
echo.

REM Crear directorio tools si no existe
IF NOT EXIST tools (
    echo Creando directorio tools...
    mkdir tools
)

REM Verificar si Git Portable ya esta configurado
IF EXIST tools\PortableGit\bin\git.exe (
    echo [OK] Git Portable ya esta configurado.
    echo.
    echo Git Portable listo para usar en actualizaciones automaticas.
    echo Puede usar el boton "Actualizar (Portable)" cuando haya actualizaciones.
    goto skip_git_portable
)

REM Intentar descargar Git Portable automaticamente
echo Git Portable no encontrado. Intentando descarga automatica...
echo.

REM Verificar si curl esta disponible
curl --version >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] curl no esta disponible.
    echo.
    echo Opciones para Git Portable:
    echo 1. Descargar manualmente desde: https://git-scm.com/download/win
    echo 2. Usar Git instalado en el sistema
    echo 3. El instalador intentara usar Git del sistema
    echo.
    echo Para configurar Git Portable manualmente:
    echo   1. Descargue "Portable Git" desde la web oficial
    echo   2. Extraiga en: tools\git-portable\
    echo   3. El sistema lo detectara automaticamente
    echo.
    set /p git_option="Desea continuar sin Git Portable? (S/N): "
    if /i not "%git_option%"=="S" (
        echo Instalacion cancelada.
        pause
        exit /b 1
    )
    goto skip_git_portable
)

REM Descargar Git Portable
echo Descargando Git Portable (esto puede tardar varios minutos)...
set "GIT_URL=https://github.com/git-for-windows/git/releases/download/v2.45.0.windows.1/PortableGit-2.45.0-64-bit.7z.exe"
set "GIT_INSTALLER=tools\PortableGit-2.45.0-64-bit.7z.exe"

curl -L -o "%GIT_INSTALLER%" "%GIT_URL%"
if errorlevel 1 (
    echo [ERROR] Error al descargar Git Portable.
    echo Verifique su conexion a internet.
    echo.
    echo Continuando sin Git Portable. Podra configurarlo mas tarde.
    goto skip_git_portable
)

echo [OK] Git Portable descargado exitosamente.

REM Extraer Git Portable
echo Extrayendo Git Portable...
echo Esto puede tardar varios minutos, por favor espere...

REM Usar 7z si esta disponible, sino intentar con el auto-extractor
7z x "%GIT_INSTALLER%" -o"tools\PortableGit" >nul 2>&1
if errorlevel 1 (
    echo Intentando extraccion automatica...
    "%GIT_INSTALLER%" -y -o"tools\PortableGit" >nul 2>&1
    if errorlevel 1 (
        echo [ADVERTENCIA] Error al extraer Git Portable automaticamente.
        echo.
        echo Extraiga manualmente:
        echo   1. Abra: %GIT_INSTALLER%
        echo   2. Seleccione destino: tools\PortableGit\
        echo   3. Extraiga todos los archivos
        echo.
        echo El instalador continuara, pero Git Portable no estara disponible.
        goto cleanup_installer
    )
)

REM Limpiar instalador
:cleanup_installer
del "%GIT_INSTALLER%" 2>nul

REM Verificar instalacion
IF EXIST tools\PortableGit\bin\git.exe (
    echo [OK] Git Portable instalado exitosamente!
    echo.
    echo Configurando Git Portable...
    
    REM Configurar Git Portable
    tools\PortableGit\bin\git.exe config --global user.name "POS User"
    tools\PortableGit\bin\git.exe config --global user.email "pos@multilideres.com"
    tools\PortableGit\bin\git.exe config --global init.defaultBranch main
    tools\PortableGit\bin\git.exe config --global pull.rebase false
    tools\PortableGit\bin\git.exe config --global safe.directory "*"
    
    echo [OK] Git Portable configurado.
    echo.
    echo Git Portable esta listo para usar en actualizaciones automaticas.
) ELSE (
    echo [ADVERTENCIA] Git Portable no se pudo instalar correctamente.
    echo.
    echo Puede configurarlo mas tarde ejecutando:
    echo   setup_git_portable.bat
)

:skip_git_portable
echo.
echo ============================================
echo  Git Portable - Configuracion Completa
echo ============================================
echo.

REM 5) Migraciones
echo Creando migraciones si hacen falta (apps user y erp)...
python manage.py makemigrations user erp
if errorlevel 1 (
    echo Error ejecutando makemigrations.
    pause
    exit /b 1
)

echo Ejecutando migraciones de la base de datos...
python manage.py migrate
if errorlevel 1 (
    echo Error ejecutando migraciones.
    pause
    exit /b 1
)

REM 6) Crear superusuario si no existe
echo Creando superusuario por defecto (admin/admin)...
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superusuario admin creado con contrasena: admin')
else:
    print('Superusuario admin ya existe')
"

REM 7) Crear acceso directo en el escritorio
echo Creando acceso directo en el escritorio...
set "SHORTCUT=%USERPROFILE%\Desktop\MultilideresCRM POS.lnk"
set "TARGET=%~dp0lanzar_pos.bat"

powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT%'); $Shortcut.TargetPath = '%TARGET%'; $Shortcut.Save()"

echo.
echo ============================================
echo  INSTALACION COMPLETADA EXITOSAMENTE!
echo ============================================
echo.
echo El sistema ha sido instalado y configurado.
echo.
echo Componentes instalados:
echo   - Entorno virtual venv
echo   - Dependencias Python
echo   - Base de datos SQLite
echo   - Superusuario: admin / admin
echo   - Acceso directo en escritorio
echo   - Git Portable: %IF EXIST tools\PortableGit\bin\git.exe (echo Listo) ELSE (echo No disponible)%
echo.
echo Para iniciar el sistema:
echo   1. Use el acceso directo en el escritorio
echo   2. O ejecute: lanzar_pos.bat
echo.
echo Para actualizaciones futuras:
echo   - Use la interfaz web: http://localhost:8000/erp/updates/
echo   - O ejecute: actualizar_pos.bat
echo.
echo Si Git Portable esta disponible, podra usar:
echo   - Boton "Actualizar (Portable)" en la web
echo   - Script: actualizar_pos_portable.bat
echo.
echo Presione cualquier tecla para salir...
pause >nulse
if errorlevel 1 (
    echo No se pudo crear el acceso directo con PowerShell.
    echo Puedes crear manualmente un acceso directo a lanzar_pos.bat en el escritorio.
) else (
    echo Acceso directo creado en el escritorio: POS_Local.lnk
)

pause
