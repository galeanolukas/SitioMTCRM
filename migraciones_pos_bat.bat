@echo off
REM Script de Migraciones - SitioMTCRM (Windows)
REM Extraído del instalador_pos_bat.bat - Solo la parte de migraciones

REM Ir siempre a la carpeta donde está este script
cd /d "%~dp0"

echo ============================================
echo  MIGRACIONES - SITIOMTCRM (Windows)
echo ============================================
echo.

REM Verificar si estamos en el directorio correcto
if not exist "manage.py" (
    echo ERROR: No se encuentra el archivo manage.py
    echo Por favor, ejecute este script desde el directorio raiz del proyecto
    pause
    exit /b 1
)

echo Iniciando proceso de migraciones...
echo.

REM Opción de limpiar base de datos si existe
IF EXIST db.sqlite3 (
    echo ADVERTENCIA: Se encontró una base de datos existente (db.sqlite3)
    set /p clean_db="¿Desea eliminarla y crear una nueva? (s/n): "
    if /i "%clean_db%"=="s" (
        echo Eliminando base de datos existente...
        del db.sqlite3
        echo Base de datos eliminada.
    ) else (
        echo Manteniendo base de datos existente.
    )
    echo.
)

REM Migraciones - Asegurar creación completa de tablas
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

echo.
echo ============================================
echo  MIGRACIONES COMPLETADAS EXITOSAMENTE!
echo ============================================
echo.

REM Omitir creación automática de superusuario
echo ============================================
echo  Creacion de Superusuario (Manual)
echo ============================================
echo.
echo IMPORTANTE: Por seguridad, no se crea un superusuario automaticamente.
echo Debe crearlo manualmente despues de las migraciones.
echo.
echo Para crear el superusuario, ejecute:
echo   python manage.py createsuperuser
echo.
echo O acceda a la administracion y siga las instrucciones.
echo.

REM Recolectar archivos estáticos
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
    echo Continuando...
) else (
    echo [OK] Archivos estáticos recolectados exitosamente.
)

echo.
echo ============================================
echo  PROCESO DE MIGRACIONES FINALIZADO
echo ============================================
echo.
echo La base de datos ha sido creada y actualizada correctamente.
echo.
echo PASOS SIGUIENTES:
echo   1. Cree un superusuario: python manage.py createsuperuser
echo   2. Inicie el servidor: python manage.py runserver
echo.
echo Para iniciar manualmente:
echo   python manage.py runserver 0.0.0.0:8000
echo.
echo Presione cualquier tecla para salir...
pause >nul
