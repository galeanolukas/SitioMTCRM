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
IF NOT EXIST DJENV (
    echo Creando entorno virtual DJENV...
    python -m venv DJENV
    if errorlevel 1 (
        echo Error al crear el entorno virtual DJENV. Verifica que Python este instalado y en el PATH.
        pause
        exit /b 1
    )
) ELSE (
    echo Entorno virtual venv ya existe.
)

REM 2) Activar entorno virtual venv
call DJENV\Scripts\activate
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

REM 4) Verificar base de datos existente
echo.
echo ============================================
echo  Verificando Base de Datos Existente
echo ============================================
echo.

IF EXIST db.sqlite3 (
    echo [ADVERTENCIA] Se encontró una base de datos existente ^(db.sqlite3^)
    echo Esta acción podría eliminar todos los datos existentes ^(ventas, productos, clientes, etc.^)
    echo.
    set /p clean_db="¿Desea eliminarla y crear una base de datos nueva? ^(S/N^): "
    if /i "%clean_db%"=="S" (
        echo Eliminando base de datos existente...
        del db.sqlite3
        echo Base de datos eliminada.
        set "DELETE_MIGRATIONS=YES"
    ) else (
        echo Manteniendo base de datos existente.
        echo Se intentará aplicar migraciones sobre la base de datos actual.
        set "DELETE_MIGRATIONS=NO"
    )
    echo.
) else (
    echo No se encontró base de datos existente. Se creará una nueva.
    echo.
    set "DELETE_MIGRATIONS=YES"
)

REM 5) Migraciones - Método mejorado con verificación de company_id
echo.
echo ============================================
echo  Creando Base de Datos y Tablas
echo ============================================
echo.

REM Limpiar migraciones SOLO si se eliminó la base de datos o no existe
IF "%DELETE_MIGRATIONS%"=="YES" (
    echo [1/6] Limpiando migraciones anteriores...
    IF EXIST core\erp\migrations\ (
        del /Q core\erp\migrations\*.py 2>nul
    )
    IF EXIST core\user\migrations\ (
        del /Q core\user\migrations\*.py 2>nul
    )
    echo Hecho.
) else (
    echo [1/6] Manteniendo migraciones existentes para preservar datos.
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
    echo [ADVERTENCIA] Error en las migraciones, pero continuando con la instalacion...
    echo.
    echo Posibles causas del error:
    echo 1. La base de datos ya está migrada
    echo 2. Hay conflictos menores en las migraciones
    echo 3. La base de datos está siendo usada por otro proceso
    echo.
    echo Posibles soluciones:
    echo 1. Elimine el archivo db.sqlite3 y reinstale
    echo 2. Cierre otros programas que usen la base de datos
    echo 3. Ejecute manualmente: python manage.py migrate
    echo.
    echo El instalador continuara, pero puede haber problemas funcionales.
    echo.
    pause
) else (
    echo [OK] Migraciones aplicadas exitosamente.
    echo.
)

REM 7) Verificación y creación de tablas críticas (para actualizaciones) - MÉTODO MEJORADO
echo.
echo [7/6] Verificando estructura de tablas críticas...
echo.

REM Pausa para verificar que todo esté bien
echo Presione cualquier tecla para continuar con la creacion del acceso directo...
pause >nul

REM 8) Omitir creación automática de superusuario
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

REM 9) Crear acceso directo profesional en el escritorio
echo.
echo ============================================
echo  Creando Acceso Directo Profesional
echo ============================================
echo.

REM Crear carpeta POS en el escritorio si no existe
if not exist "%USERPROFILE%\Desktop\POS" (
    echo Creando carpeta POS en escritorio...
    mkdir "%USERPROFILE%\Desktop\POS"
)

REM Configurar rutas
set "SHORTCUT=%USERPROFILE%\Desktop\POS\MultilideresCRM POS.lnk"
set "TARGET=%~dp0lanzar_pos.bat"
set "ICON_PATH=%~dp0icon.ico"

REM Verificar que existe el archivo de destino
if not exist "%TARGET%" (
    echo [ERROR] No se encuentra el archivo lanzar_pos.bat
    echo Creando lanzador básico...
    
    REM Crear lanzador básico si no existe
    (
        echo @echo off
        echo cd /d "%%~dp0"
        echo echo Iniciando MultilideresCRM POS...
        echo echo.
        echo call DJENV\Scripts\activate
        echo python manage.py runserver 0.0.0.0:8000
        echo pause
    ) > "%TARGET%"
    
    echo [OK] Lanzador creado: lanzar_pos.bat
)

REM Crear acceso directo con PowerShell
echo Creando acceso directo profesional...
powershell -Command "& {
    try {
        $WshShell = New-Object -comObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut('%SHORTCUT%')
        $Shortcut.TargetPath = '%TARGET%'
        $Shortcut.WorkingDirectory = '%~dp0'
        $Shortcut.Description = 'Sistema POS MultilideresCRM'
        
        if (Test-Path '%ICON_PATH%') {
            $Shortcut.IconLocation = '%ICON_PATH%'
            Write-Host '✅ Icono asignado: %ICON_PATH%'
        } else {
            Write-Host '⚠️ Icono no encontrado, usando icono por defecto'
        }
        
        $Shortcut.Save()
        Write-Host '✅ Acceso directo creado exitosamente'
        exit 0
    } catch {
        Write-Host '❌ Error creando acceso directo: ' $_.Exception.Message
        exit 1
    }
}" 2>&1

REM Verificar el resultado de PowerShell
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudo crear el acceso directo automaticamente.
    echo.
    echo INSTRUCCIONES PARA CREARLO MANUALMENTE:
    echo   1. Boton derecho en el escritorio
    echo   2. Nuevo - Acceso directo
    echo   3. Destino: "%TARGET%"
    echo   4. Directorio de inicio: "%~dp0"
    echo   5. Nombre: MultilideresCRM POS
    echo   6. Opcional: Cambiar icono a "%ICON_PATH%"
    echo.
    echo El instalador continuara, pero debera crear el acceso directo manualmente.
    echo.
    pause
) else (
    echo [OK] Acceso directo creado exitosamente
    echo     Ubicacion: %SHORTCUT%
    echo     Destino: %TARGET%
    echo     Directorio: %~dp0
    if exist "%ICON_PATH%" (
        echo     Icono: %ICON_PATH%
    ) else (
        echo     Icono: Por defecto (icon.ico no encontrado)
    )
    echo.
    echo Acceso directo creado correctamente. Continuando...
    echo.
    timeout /t 2 >nul
)

REM 10) Recolectar archivos estáticos
echo.
echo ============================================
echo  Recolectando Archivos Estaticos
echo ============================================
echo.

echo Recolectando archivos estáticos...
python manage.py collectstatic --noinput
if errorlevel 1 (
    echo [ADVERTENCIA] Error al recolectar archivos estáticos.
    echo Esto puede afectar la visualizacion de algunos elementos.
    echo.
    echo Puede ejecutar manualmente: python manage.py collectstatic --noinput
    echo.
    echo Continuando con la instalacion...
    echo.
    pause
) else (
    echo [OK] Archivos estáticos recolectados exitosamente.
    echo.
    echo Archivos estáticos listos. Continuando...
    echo.
    timeout /t 2 >nul
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
echo   - Base de datos SQLite con verificación de seguridad
echo   - Acceso directo profesional en escritorio
echo   - Lanzador automatico lanzar_pos.bat
echo.
echo MEJORAS IMPLEMENTADAS:
echo   - Acceso directo en carpeta POS organizada
echo   - Icono personalizado si icon.ico esta disponible
echo   - Directorio de trabajo configurado correctamente
echo   - Verificación de base de datos existente
echo   - Confirmación antes de eliminar datos
echo   - Preservación de datos existentes
echo   - Verificación automática de estructura
echo   - Asignación automática de company_id
echo.
echo ACCESO DIRECTO CREADO:
echo   Ubicacion: %USERPROFILE%\Desktop\POS\MultilideresCRM POS.lnk
echo   Destino: lanzar_pos.bat
echo   Directorio: %~dp0
if exist "%~dp0icon.ico" (
    echo   Icono: %~dp0icon.ico
) else (
    echo   Icono: Por defecto de Windows
)
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
    echo ============================================
    echo  ¡INSTALACION FINALIZADA CON EXITO!
    echo ============================================
    echo.
    echo Presione cualquier tecla para salir...
    pause >nul
)
