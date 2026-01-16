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
echo  Configurando Git Portable (Opcional)
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

REM Preguntar si desea configurar Git Portable
echo Git Portable permite actualizaciones automaticas sin instalar Git en Windows.
echo Si no desea configurarlo ahora, puede hacerlo mas tarde.
echo.
set /p git_option="Desea configurar Git Portable ahora? (S/N): "
if /i not "%git_option%"=="S" (
    echo Omitiendo configuracion de Git Portable.
    echo Podra configurarlo mas tarde ejecutando: setup_git_portable.bat
    goto skip_git_portable
)

REM Intentar descargar Git Portable automaticamente
echo Intentando descarga automatica de Git Portable...
echo.

REM Verificar si curl esta disponible
curl --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] curl no esta disponible. Omitiendo descarga automatica.
    echo.
    echo Para configurar Git Portable manualmente:
    echo   1. Descargue "Portable Git" desde: https://git-scm.com/download/win
    echo   2. Extraiga en: tools\PortableGit\
    echo   3. El sistema lo detectara automaticamente
    echo.
    goto skip_git_portable
)

REM Descargar Git Portable con timeout y reintentos
echo Descargando Git Portable (esto puede tardar varios minutos)...
set "GIT_URL=https://github.com/git-for-windows/git/releases/download/v2.45.0.windows.1/PortableGit-2.45.0-64-bit.7z.exe"
set "GIT_INSTALLER=tools\PortableGit-2.45.0-64-bit.7z.exe"

REM Intentar descarga con reintentos limitados
set retry_count=0
:download_retry
set /a retry_count+=1
curl -L --max-time 300 -o "%GIT_INSTALLER%" "%GIT_URL%" 2>nul
if errorlevel 1 (
    if %retry_count% lss 3 (
        echo Reintento %retry_count%/3...
        goto download_retry
    ) else (
        echo [ADVERTENCIA] No se pudo descargar Git Portable despues de 3 intentos.
        echo Continuando con la instalacion sin Git Portable.
        goto cleanup_installer
    )
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
    tools\PortableGit\bin\git.exe config --global user.name "POS User" 2>nul
    tools\PortableGit\bin\git.exe config --global user.email "pos@multilideres.com" 2>nul
    tools\PortableGit\bin\git.exe config --global init.defaultBranch main 2>nul
    tools\PortableGit\bin\git.exe config --global pull.rebase false 2>nul
    tools\PortableGit\bin\git.exe config --global safe.directory "*" 2>nul
    
    echo [OK] Git Portable configurado.
    echo.
    echo Git Portable esta listo para usar en actualizaciones automaticas.
) ELSE (
    echo [INFO] Git Portable no se pudo instalar correctamente.
    echo.
    echo Esto no afecta el funcionamiento del sistema.
    echo Puede configurarlo mas tarde ejecutando: setup_git_portable.bat
)

:skip_git_portable
echo.
echo ============================================
echo  Git Portable - Configuracion Completa
echo ============================================
echo.

REM 5) Migraciones - Asegurar creación completa de tablas
echo.
echo ============================================
echo  Creando Base de Datos y Tablas
echo ============================================
echo.

REM Limpiar migraciones anteriores solo si existen archivos de migración
IF EXIST core\erp\migrations\ (
    echo [1/6] Limpiando migraciones anteriores...
    del /Q core\erp\migrations\*.py 2>nul
    del /Q core\user\migrations\*.py 2>nul
    echo Hecho.
)

REM Crear directorios de migraciones si no existen
IF NOT EXIST core\erp\migrations (
    mkdir core\erp\migrations
    echo. > core\erp\migrations\__init__.py
)

IF NOT EXIST core\user\migrations (
    mkdir core\user\migrations
    echo. > core\user\migrations\__init__.py
)

echo [2/6] Creando migraciones iniciales para user...
python manage.py makemigrations user --empty user --name initial
if errorlevel 1 (
    echo Advertencia: No se pudo crear migración inicial para user
)

echo [3/6] Creando migraciones iniciales para erp...
python manage.py makemigrations erp --empty erp --name initial
if errorlevel 1 (
    echo Advertencia: No se pudo crear migración inicial para erp
)

echo [4/6] Creando migraciones automáticas...
python manage.py makemigrations user erp
if errorlevel 1 (
    echo Error en makemigrations automatico, intentando metodo alternativo...
    python manage.py makemigrations
)

echo [5/6] Aplicando migraciones con --fake-initial...
python manage.py migrate --fake-initial
if errorlevel 1 (
    echo Error en --fake-initial, continuando con migrate normal...
)

echo [6/6] Aplicando todas las migraciones...
python manage.py migrate
if errorlevel 1 (
    echo ERROR CRITICO: No se pudieron aplicar las migraciones
    echo.
    echo Posibles soluciones:
    echo 1. Elimine el archivo db.sqlite3 y reintente
    echo 2. Verifique que no haya programas usando la base de datos
    echo 3. Ejecute manualmente: python manage.py migrate
    echo.
    pause
    exit /b 1
)

REM 6) Omitir creación automática de superusuario
echo.
echo ============================================
echo  Creacion de Superusuario (Manual)
echo ============================================
echo.
echo IMPORTANTE: Por seguridad, no se crea un superusuario automaticamente.
echo Debe crearlo manualmente despues de la instalacion.
echo.
echo Para crear el superusuario, ejecute:
echo   python manage.py createsuperuser
echo.
echo O acceda a la administracion y siga las instrucciones.
echo.

REM 7) Crear acceso directo en el escritorio
echo Creando acceso directo en el escritorio...
set "SHORTCUT=%USERPROFILE%\Desktop\MultilideresCRM POS.lnk"
set "TARGET=%~dp0lanzar_pos.bat"

powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT%'); $Shortcut.TargetPath = '%TARGET%'; $Shortcut.Save()" 2>nul
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudo crear el acceso directo automaticamente.
    echo Puede crearlo manualmente:
    echo   1. Boton derecho en el escritorio
    echo   2. Nuevo - Acceso directo
    echo   3. Destino: "%TARGET%"
    echo   4. Nombre: MultilideresCRM POS
    echo.
    echo Continuando con la instalacion...
)

REM 8) Recolectar archivos estáticos
echo.
echo ============================================
echo  Recolectando Archivos Estaticos
echo ============================================
echo.

python manage.py collectstatic --noinput
if errorlevel 1 (
    echo [ADVERTENCIA] Error al recolectar archivos estáticos.
    echo Esto puede afectar la visualizacion de algunos elementos.
    echo.
    echo Puede ejecutar manualmente: python manage.py collectstatic --noinput
    echo.
    echo Continuando con la instalacion...
) else (
    echo [OK] Archivos estáticos recolectados exitosamente.
)

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
echo   - Acceso directo en escritorio
echo   - Git Portable: %IF EXIST tools\PortableGit\bin\git.exe (echo Listo) ELSE (echo No disponible)%
echo.
echo PASOS IMPORTANTES ANTES DE USAR:
echo   1. Cree un superusuario: python manage.py createsuperuser
echo   2. Inicie el servidor: python manage.py runserver
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

REM Preguntar si desea iniciar el programa automáticamente
set /p start_program="¿Desea iniciar el programa automáticamente? (s/n): "
if /i "%start_program%"=="s" (
    echo.
    echo Iniciando el programa...
    echo El servidor se iniciará en: http://127.0.0.1:8000/
    echo Presione Ctrl+C para detener el servidor.
    echo.
    python manage.py runserver 0.0.0.0:8000
) else (
    echo.
    echo Presione cualquier tecla para salir...
    pause >nul
)
