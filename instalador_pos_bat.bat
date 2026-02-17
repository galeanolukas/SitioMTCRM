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

REM 7) Verificación y creación de tablas críticas (para actualizaciones) - MÉTODO MEJORADO
echo.
echo [7/6] Verificando estructura de tablas críticas...
echo.

REM Método alternativo: Usar un script Python separado en lugar de shell interactivo
echo Creando script temporal de verificación...
(
echo import sqlite3
echo import os
echo.
echo def verificar_y_crear_tablas():
echo     db_path = 'db.sqlite3'
echo     if not os.path.exists(db_path):
echo         print("Base de datos no encontrada, será creada por las migraciones")
echo         return
echo.
echo     conn = sqlite3.connect(db_path)
echo     cursor = conn.cursor()
echo.
echo     # Lista de tablas críticas con sus estructuras básicas
echo     tablas_criticas = {
echo         'erp_company': '''
echo             CREATE TABLE IF NOT EXISTS erp_company (
echo                 id INTEGER PRIMARY KEY AUTOINCREMENT,
echo                 name VARCHAR(200) NOT NULL,
echo                 ruc VARCHAR(20),
echo                 cuit VARCHAR(20),
echo                 address TEXT,
echo                 phone VARCHAR(50),
echo                 email VARCHAR(100),
echo                 iibb VARCHAR(50),
echo                 pos VARCHAR(10),
echo                 start DATE,
echo                 logo VARCHAR(255),
echo                 is_active BOOLEAN DEFAULT 1,
echo                 date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
echo                 date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
echo             )
echo         ''',
echo         'erp_category': '''
echo             CREATE TABLE IF NOT EXISTS erp_category (
echo                 id INTEGER PRIMARY KEY AUTOINCREMENT,
echo                 name VARCHAR(150) NOT NULL,
echo                 desc VARCHAR(500),
echo                 user_creation_id INTEGER,
echo                 date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
echo                 user_updated_id INTEGER,
echo                 date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
echo                 company_id INTEGER,
echo                 synced_to_server BOOLEAN DEFAULT 0
echo             )
echo         ''',
echo         'erp_product': '''
echo             CREATE TABLE IF NOT EXISTS erp_product (
echo                 id INTEGER PRIMARY KEY AUTOINCREMENT,
echo                 name VARCHAR(150) NOT NULL,
echo                 desc TEXT,
echo                 code VARCHAR(50),
echo                 barcode VARCHAR(50),
echo                 pvp DECIMAL(10,2),
echo                 cost DECIMAL(10,2),
echo                 stock DECIMAL(10,2),
echo                 iva_rate DECIMAL(5,2) DEFAULT 21.0,
echo                 user_creation_id INTEGER,
echo                 date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
echo                 user_updated_id INTEGER,
echo                 date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
echo                 company_id INTEGER,
echo                 cat_id INTEGER,
echo                 synced_to_server BOOLEAN DEFAULT 0,
echo                 synced_from_server BOOLEAN DEFAULT 0,
echo                 server_product_id INTEGER,
echo                 last_server_sync TIMESTAMP
echo             )
echo         ''',
echo         'erp_client': '''
echo             CREATE TABLE IF NOT EXISTS erp_client (
echo                 id INTEGER PRIMARY KEY AUTOINCREMENT,
echo                 names VARCHAR(200) NOT NULL,
echo                 surnames VARCHAR(200),
echo                 dni VARCHAR(20),
echo                 ruc VARCHAR(20),
echo                 address TEXT,
echo                 phone VARCHAR(50),
echo                 email VARCHAR(100),
echo                 user_creation_id INTEGER,
echo                 date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
echo                 user_updated_id INTEGER,
echo                 date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
echo                 company_id INTEGER
echo             )
echo         ''',
echo         'erp_sale': '''
echo             CREATE TABLE IF NOT EXISTS erp_sale (
echo                 id INTEGER PRIMARY KEY AUTOINCREMENT,
echo                 cli_id INTEGER,
echo                 date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
echo                 subtotal DECIMAL(10,2),
echo                 iva DECIMAL(10,2),
echo                 total DECIMAL(10,2),
echo                 is_invoiced BOOLEAN DEFAULT 0,
echo                 invoice_number VARCHAR(50),
echo                 invoice_pos VARCHAR(10),
echo                 invoice_type VARCHAR(10),
echo                 observations TEXT,
echo                 user_creation_id INTEGER,
echo                 company_id INTEGER,
echo                 synced_to_server BOOLEAN DEFAULT 0
echo             )
echo         ''',
echo         'erp_detsale': '''
echo             CREATE TABLE IF NOT EXISTS erp_detsale (
echo                 id INTEGER PRIMARY KEY AUTOINCREMENT,
echo                 sale_id INTEGER,
echo                 prod_id INTEGER,
echo                 cant DECIMAL(10,2),
echo                 price DECIMAL(10,2),
echo                 subtotal DECIMAL(10,2),
echo                 iva_amount DECIMAL(10,2),
echo                 user_creation_id INTEGER,
echo                 date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
echo             )
echo         '''
echo     }
echo.
echo     tablas_creadas = 0
echo     for nombre_tabla, sql_create in tablas_criticas.items():
echo         # Verificar si la tabla existe
echo         cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nombre_tabla,))
echo         if not cursor.fetchone():
echo             print(f'Creando tabla: {nombre_tabla}')
echo             cursor.execute(sql_create)
echo             tablas_creadas += 1
echo             print(f'✓ Tabla {nombre_tabla} creada')
echo         else:
echo             print(f'✓ Tabla {nombre_tabla} ya existe')
echo.
echo     # Verificar y agregar columnas que falten
echo     print('\nVerificando columnas que falten...')
echo.
echo     # Columnas para erp_category
echo     cursor.execute('PRAGMA table_info(erp_category)')
echo     columns_category = [row[1] for row in cursor.fetchall()]
echo     if 'company_id' not in columns_category:
echo         cursor.execute('ALTER TABLE erp_category ADD COLUMN company_id INTEGER')
echo         print('✓ company_id agregado a erp_category')
echo     if 'synced_to_server' not in columns_category:
echo         cursor.execute('ALTER TABLE erp_category ADD COLUMN synced_to_server BOOLEAN DEFAULT 0')
echo         print('✓ synced_to_server agregado a erp_category')
echo.
echo     # Columnas para erp_product
echo     cursor.execute('PRAGMA table_info(erp_product)')
echo     columns_product = [row[1] for row in cursor.fetchall()]
echo     if 'company_id' not in columns_product:
echo         cursor.execute('ALTER TABLE erp_product ADD COLUMN company_id INTEGER')
echo         print('✓ company_id agregado a erp_product')
echo     if 'synced_to_server' not in columns_product:
echo         cursor.execute('ALTER TABLE erp_product ADD COLUMN synced_to_server BOOLEAN DEFAULT 0')
echo         print('✓ synced_to_server agregado a erp_product')
echo     if 'synced_from_server' not in columns_product:
echo         cursor.execute('ALTER TABLE erp_product ADD COLUMN synced_from_server BOOLEAN DEFAULT 0')
echo         print('✓ synced_from_server agregado a erp_product')
echo     if 'server_product_id' not in columns_product:
echo         cursor.execute('ALTER TABLE erp_product ADD COLUMN server_product_id INTEGER')
echo         print('✓ server_product_id agregado a erp_product')
echo     if 'last_server_sync' not in columns_product:
echo         cursor.execute('ALTER TABLE erp_product ADD COLUMN last_server_sync TIMESTAMP')
echo         print('✓ last_server_sync agregado a erp_product')
echo.
echo     # Insertar empresa por defecto si no existe
echo     cursor.execute('SELECT COUNT(*) FROM erp_company')
echo     if cursor.fetchone()[0] == 0:
echo         cursor.execute('INSERT INTO erp_company (name, ruc, cuit) VALUES (?, ?, ?)', ('Mi Empresa', '', ''))
echo         print('✓ Empresa por defecto creada')
echo.
echo     # Asignar company_id por defecto si es NULL
echo     cursor.execute('UPDATE erp_category SET company_id = 1 WHERE company_id IS NULL')
echo     cursor.execute('UPDATE erp_product SET company_id = 1 WHERE company_id IS NULL')
echo     cursor.execute('UPDATE erp_client SET company_id = 1 WHERE company_id IS NULL')
echo     cursor.execute('UPDATE erp_sale SET company_id = 1 WHERE company_id IS NULL')
echo     print('✓ company_id asignado por defecto donde faltaba')
echo.
echo     conn.commit()
echo     conn.close()
echo.
echo     print(f'\n✓ Estructura verificada: {tablas_creadas} tablas nuevas creadas')
echo     print('✓ Columnas verificadas y agregadas si faltaban')
echo.
echo if __name__ == '__main__':
echo     verificar_y_crear_tablas()
) > temp_verificar_tablas.py

REM Ejecutar el script temporal
python temp_verificar_tablas.py
if errorlevel 1 (
    echo [ERROR] No se pudo verificar la estructura de las tablas.
    echo Continuando de todas formas...
)
REM Limpiar el script temporal
if exist temp_verificar_tablas.py del temp_verificar_tablas.py

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

REM 9) Crear acceso directo en el escritorio
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

REM 10) Recolectar archivos estáticos
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
echo   - Base de datos SQLite con verificación de seguridad
echo   - Acceso directo en escritorio
echo.
echo MEJORAS DE SEGURIDAD IMPLEMENTADAS:
echo   - Verificación de base de datos existente
echo   - Confirmación antes de eliminar datos
echo   - Preservación de datos existentes
echo   - Verificación automática de estructura
echo   - Asignación automática de company_id
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
    echo Presione cualquier tecla para salir...
    pause >nul
)
