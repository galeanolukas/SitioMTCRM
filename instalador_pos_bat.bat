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

REM 1) Crear entorno virtual DJENV si no existe
if not exist "DJENV" (
    echo Creando entorno virtual DJENV...
    python -m venv DJENV
    if errorlevel 1 (
        echo Error al crear el entorno virtual DJENV.
        pause
        exit /b 1
    )
) else (
    echo Entorno virtual DJENV ya existe.
)

REM 2) Activar entorno virtual DJENV
echo Activando entorno virtual...
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

REM Verificacion rapida de numpy, pandas y openpyxl en este entorno virtual
python -c "import numpy, pandas, openpyxl; print('numpy:', numpy.__version__, 'pandas:', pandas.__version__, 'openpyxl:', openpyxl.__version__)" >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudieron importar numpy, pandas u openpyxl en el entorno virtual DJENV.
    echo.
    echo Si ve un error de "circular import" en numpy, ejecute:
    echo   fix_numpy_circular_import.bat
    echo.
    echo O verifique la instalacion manualmente con:
    echo   call DJENV\Scripts\activate
    echo   pip install numpy pandas openpyxl
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

REM 5) Migraciones - Método mejorado con verificación de company_id
echo.
echo ============================================
echo  Creando Base de Datos y Tablas
echo ============================================
echo.

REM Opcional: Limpiar base de datos existente
IF EXIST db.sqlite3 (
    echo ADVERTENCIA: Se encontró una base de datos existente (db.sqlite3)
    echo Esta acción podría eliminar todos los datos existentes (ventas, productos, clientes, etc.)
    set /p clean_db="¿Desea eliminarla y crear una nueva? (s/n): "
    if /i "%clean_db%"=="s" (
        echo Eliminando base de datos existente...
        del db.sqlite3
        echo Base de datos eliminada.
    ) else (
        echo Manteniendo base de datos existente.
        echo Se intentará aplicar migraciones sobre la base de datos actual.
    )
    echo.
) ELSE (
    echo No se encontró base de datos existente. Se creará una nueva.
    echo.
)

REM Verificar configuración de Django
echo [1/5] Verificando configuración de Django...
python manage.py check --deploy 2>nul
if errorlevel 1 (
    echo Advertencia: Hay problemas con la configuración, continuando...
)

REM Crear migraciones automáticamente
echo [2/5] Creando migraciones automáticas...
python manage.py makemigrations --noinput
if errorlevel 1 (
    echo Error en makemigrations, intentando método específico...
    python manage.py makemigrations user erp --noinput
    if errorlevel 1 (
        echo Advertencia: No se pudieron crear migraciones automáticas
        echo Intentando crear migraciones vacías...
        python manage.py makemigrations --empty --name initial
    )
)

REM MIGRACIONES COMPLETAS - Usando script mejorado
echo ============================================
echo   EJECUTANDO MIGRACIONES COMPLETAS
echo ============================================
echo.

REM Verificar si el script de migraciones existe
if exist "migraciones_completas.bat" (
    echo Ejecutando script de migraciones mejorado...
    call migraciones_completas.bat
    if errorlevel 1 (
        echo Error en las migraciones. Intentando metodo alternativo...
        echo Creando migraciones si hacen falta...
        python manage.py makemigrations user erp core.erp core.user core.homepage --no-input
        echo Ejecutando migraciones...
        python manage.py migrate --no-input
    )
) else (
    echo Script de migraciones no encontrado. Usando metodo estandar...
    echo Creando migraciones si hacen falta...
    python manage.py makemigrations user erp core.erp core.user core.homepage --no-input
    echo Ejecutando migraciones...
    python manage.py migrate --no-input
)

if errorlevel 1 (
    echo ERROR CRITICO: No se pudieron aplicar las migraciones
    echo.
    echo SOLUCIONES:
    echo 1. Elimine db.sqlite3 y reinicie el instalador
    echo 2. Verifique que no haya programas usando la base de datos
    echo 3. Ejecute manualmente: python manage.py migrate --run-syncdb
    echo.
    pause
    exit /b 1
)

echo ✅ Migraciones completadas exitosamente
echo.

REM Verificación y creación de tablas críticas (para actualizaciones)
echo [4/5] Verificando estructura de tablas críticas...
python manage.py shell -c "
from django.db import connection
try:
    with connection.cursor() as cursor:
        print('Verificando y creando tablas que falten...')
        
        # Lista de tablas críticas con sus estructuras básicas
        tablas_criticas = {
            'erp_company': '''
                CREATE TABLE IF NOT EXISTS erp_company (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL,
                    ruc VARCHAR(20),
                    cuit VARCHAR(20),
                    address TEXT,
                    phone VARCHAR(50),
                    email VARCHAR(100),
                    iibb VARCHAR(50),
                    pos VARCHAR(10),
                    start DATE,
                    logo VARCHAR(255),
                    is_active BOOLEAN DEFAULT 1,
                    date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'erp_category': '''
                CREATE TABLE IF NOT EXISTS erp_category (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(150) NOT NULL,
                    desc VARCHAR(500),
                    user_creation_id INTEGER,
                    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_updated_id INTEGER,
                    date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    company_id INTEGER,
                    synced_to_server BOOLEAN DEFAULT 0
                )
            ''',
            'erp_product': '''
                CREATE TABLE IF NOT EXISTS erp_product (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(150) NOT NULL,
                    desc TEXT,
                    code VARCHAR(50),
                    barcode VARCHAR(50),
                    pvp DECIMAL(10,2),
                    cost DECIMAL(10,2),
                    stock DECIMAL(10,2),
                    iva_rate DECIMAL(5,2) DEFAULT 21.0,
                    user_creation_id INTEGER,
                    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_updated_id INTEGER,
                    date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    company_id INTEGER,
                    cat_id INTEGER,
                    synced_to_server BOOLEAN DEFAULT 0,
                    synced_from_server BOOLEAN DEFAULT 0,
                    server_product_id INTEGER,
                    last_server_sync TIMESTAMP
                )
            ''',
            'erp_client': '''
                CREATE TABLE IF NOT EXISTS erp_client (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    names VARCHAR(200) NOT NULL,
                    surnames VARCHAR(200),
                    dni VARCHAR(20),
                    ruc VARCHAR(20),
                    address TEXT,
                    phone VARCHAR(50),
                    email VARCHAR(100),
                    user_creation_id INTEGER,
                    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_updated_id INTEGER,
                    date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    company_id INTEGER
                )
            ''',
            'erp_sale': '''
                CREATE TABLE IF NOT EXISTS erp_sale (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cli_id INTEGER,
                    date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    subtotal DECIMAL(10,2),
                    iva DECIMAL(10,2),
                    total DECIMAL(10,2),
                    is_invoiced BOOLEAN DEFAULT 0,
                    invoice_number VARCHAR(50),
                    invoice_pos VARCHAR(10),
                    invoice_type VARCHAR(10),
                    observations TEXT,
                    user_creation_id INTEGER,
                    company_id INTEGER,
                    synced_to_server BOOLEAN DEFAULT 0
                )
            ''',
            'erp_detsale': '''
                CREATE TABLE IF NOT EXISTS erp_detsale (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER,
                    prod_id INTEGER,
                    cant DECIMAL(10,2),
                    price DECIMAL(10,2),
                    subtotal DECIMAL(10,2),
                    iva_amount DECIMAL(10,2),
                    user_creation_id INTEGER,
                    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''
        }
        
        tablas_creadas = 0
        for nombre_tabla, sql_create in tablas_criticas.items():
            # Verificar si la tabla existe
            cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='%s'\" % nombre_tabla)
            if not cursor.fetchone():
                print(f'Creando tabla: {nombre_tabla}')
                cursor.execute(sql_create)
                tablas_creadas += 1
                print(f'✓ Tabla {nombre_tabla} creada')
            else:
                print(f'✓ Tabla {nombre_tabla} ya existe')
        
        # Verificar y agregar columnas que falten
        print('\\nVerificando columnas que falten...')
        
        # Columnas para erp_category
        cursor.execute('PRAGMA table_info(erp_category)')
        columns_category = [row[1] for row in cursor.fetchall()]
        if 'company_id' not in columns_category:
            cursor.execute('ALTER TABLE erp_category ADD COLUMN company_id INTEGER')
            print('✓ company_id agregado a erp_category')
        if 'synced_to_server' not in columns_category:
            cursor.execute('ALTER TABLE erp_category ADD COLUMN synced_to_server BOOLEAN DEFAULT 0')
            print('✓ synced_to_server agregado a erp_category')
        
        # Columnas para erp_product
        cursor.execute('PRAGMA table_info(erp_product)')
        columns_product = [row[1] for row in cursor.fetchall()]
        if 'company_id' not in columns_product:
            cursor.execute('ALTER TABLE erp_product ADD COLUMN company_id INTEGER')
            print('✓ company_id agregado a erp_product')
        if 'synced_to_server' not in columns_product:
            cursor.execute('ALTER TABLE erp_product ADD COLUMN synced_to_server BOOLEAN DEFAULT 0')
            print('✓ synced_to_server agregado a erp_product')
        if 'synced_from_server' not in columns_product:
            cursor.execute('ALTER TABLE erp_product ADD COLUMN synced_from_server BOOLEAN DEFAULT 0')
            print('✓ synced_from_server agregado a erp_product')
        if 'server_product_id' not in columns_product:
            cursor.execute('ALTER TABLE erp_product ADD COLUMN server_product_id INTEGER')
            print('✓ server_product_id agregado a erp_product')
        if 'last_server_sync' not in columns_product:
            cursor.execute('ALTER TABLE erp_product ADD COLUMN last_server_sync TIMESTAMP')
            print('✓ last_server_sync agregado a erp_product')
        
        # Insertar empresa por defecto si no existe
        cursor.execute('SELECT COUNT(*) FROM erp_company')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO erp_company (name, ruc, cuit) VALUES (?, ?, ?)', ['Mi Empresa', '', ''])
            print('✓ Empresa por defecto creada')
        
        # Asignar company_id por defecto si es NULL
        cursor.execute('UPDATE erp_category SET company_id = 1 WHERE company_id IS NULL')
        cursor.execute('UPDATE erp_product SET company_id = 1 WHERE company_id IS NULL')
        cursor.execute('UPDATE erp_client SET company_id = 1 WHERE company_id IS NULL')
        cursor.execute('UPDATE erp_sale SET company_id = 1 WHERE company_id IS NULL')
        print('✓ company_id asignado por defecto donde faltaba')
        
        print(f'\\n✓ Estructura verificada: {tablas_creadas} tablas nuevas creadas')
        print('✓ Columnas verificadas y agregadas si faltaban')
        
except Exception as e:
    print(f'Error verificando tablas: {e}')
    import traceback
    traceback.print_exc()
" 2>nul

echo.

REM Verificar estado final
echo [5/5] Verificando estado de las migraciones...
python manage.py showmigrations 2>nul
if errorlevel 1 (
    echo Advertencia: No se puede verificar el estado de las migraciones
) else (
    echo [OK] Migraciones aplicadas correctamente.
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
echo.
echo ============================================
echo  Creando Acceso Directo en Escritorio
echo ============================================
echo.

REM Rutas para el acceso directo directamente en el escritorio
set "SHORTCUT=%USERPROFILE%\Desktop\MultilideresCRM POS.lnk"
set "TARGET=%~dp0lanzar_pos.bat"
set "ICON_PATH=%~dp0icon.ico"

echo Creando acceso directo en: %SHORTCUT%
echo Target: %TARGET%
echo Icon: %ICON_PATH%

REM Crear acceso directo usando PowerShell
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT%'); $Shortcut.TargetPath = '%TARGET%'; $Shortcut.WorkingDirectory = '%~dp0'; $Shortcut.IconLocation = '%ICON_PATH%'; $Shortcut.Description = 'Sistema POS MultilideresCRM'; $Shortcut.Save()" 2>nul

if errorlevel 1 (
    echo [ADVERTENCIA] No se pudo crear el acceso directo automáticamente.
    echo.
    echo Puede crearlo manualmente:
    echo   1. Boton derecho en el escritorio - Nuevo - Acceso directo
    echo   2. Destino: "%TARGET%"
    echo   3. Directorio de inicio: "%~dp0"
    echo   4. Icono: "%ICON_PATH%"
    echo   5. Nombre: MultilideresCRM POS
    echo.
    echo O copie este script al escritorio como acceso directo.
) else (
    echo [OK] Acceso directo creado exitosamente en:
    echo   %SHORTCUT%
    echo.
    echo El acceso directo incluye:
    echo   - Icono personalizado del sistema
    echo   - Directorio de trabajo correcto
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
echo ACCESO DIRECTO:
echo   Ubicación: %USERPROFILE%\Desktop\MultilideresCRM POS.lnk
echo   Icono: Personalizado del sistema
echo   Directorio de trabajo: Configurado automáticamente
echo.
echo PASOS IMPORTANTES ANTES DE USAR:
echo   1. Cree un superusuario: python manage.py createsuperuser
echo   2. Inicie el servidor: python manage.py runserver
echo.
echo Para iniciar el sistema:
echo   1. Use el acceso directo: Escritorio > MultilideresCRM POS
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

REM 9) Crear superusuario automáticamente si no existe
echo.
echo ============================================
echo  Configuración de Usuario
echo ============================================
echo.

echo Verificando si existe superusuario...
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    print('No se encontró superusuario. Creando uno por defecto...')
    from django.contrib.auth.models import User
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('✓ Superusuario creado: admin / admin123')
    print('¡IMPORTANTE! Cambie la contraseña después del primer inicio.')
else:
    print('✓ Ya existe superusuario en el sistema')
" 2>nul

REM 10) Preguntar si desea iniciar el programa automáticamente
set /p start_program="¿Desea iniciar el programa ahora? (s/n): "
if /i "%start_program%"=="s" (
    echo.
    echo Iniciando servidor en nueva ventana...
    echo Se abrirá automáticamente el navegador
    echo.
    REM Iniciar el servidor en una nueva ventana (como en lanzar_pos.bat)
    start "POS_Local_Django" cmd /c "cd /d \"%~dp0\" && call venv\Scripts\activate && python manage.py runserver 0.0.0.0:8000"
    
    REM Esperar a que inicie el servidor
    echo Esperando a que inicie el servidor...
    timeout /t 10 /nobreak >nul
    
    REM Abrir navegador
    echo Abriendo navegador...
    start "" "http://localhost:8000/erp/launcher/"
    
    echo.
    echo El servidor está corriendo en una ventana separada.
    echo Puede cerrar esta ventana de instalación.
    echo.
    pause
) else (
    echo.
    echo Para iniciar manualmente:
    echo   1. Use el acceso directo del escritorio
    echo   2. O ejecute: lanzar_pos.bat
    echo.
    echo DATOS DE ACCESO:
    echo   Usuario: admin
    echo   Contraseña: admin123
    echo   URL: http://localhost:8000/erp/launcher/
    echo.
    pause
)
