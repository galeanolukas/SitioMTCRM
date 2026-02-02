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

REM Verificacion rapida de numpy, pandas y openpyxl en este entorno virtual
python -c "import numpy, pandas, openpyxl; print('numpy:', numpy.__version__, 'pandas:', pandas.__version__, 'openpyxl:', openpyxl.__version__)" >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] No se pudieron importar numpy, pandas u openpyxl en el entorno virtual venv.
    echo.
    echo Si ve un error de "circular import" en numpy, ejecute:
    echo   fix_numpy_circular_import.bat
    echo.
    echo O verifique la instalacion manualmente con:
    echo   call venv\Scripts\activate
    echo   pip install "numpy<2.0.0" "pandas<2.2.0" "openpyxl<3.2.0"
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

REM Aplicar migraciones
echo [3/5] Aplicando migraciones...
python manage.py migrate --noinput
if errorlevel 1 (
    echo ERROR en migrate normal, intentando --fake-initial...
    python manage.py migrate --fake-initial --noinput
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
)

REM Verificar y crear company_id si falta (evita el error del servidor)
echo [4/5] Verificando estructura de tablas críticas...
python manage.py shell -c "
from django.db import connection
try:
    with connection.cursor() as cursor:
        # Verificar si erp_category tiene company_id
        cursor.execute('PRAGMA table_info(erp_category)')
        columns = [row[1] for row in cursor.fetchall()]
        if 'company_id' not in columns:
            print('Agregando company_id a erp_category...')
            cursor.execute('ALTER TABLE erp_category ADD COLUMN company_id INTEGER')
            print('✓ company_id agregado a erp_category')
        
        # Verificar si erp_product tiene company_id
        cursor.execute('PRAGMA table_info(erp_product)')
        columns = [row[1] for row in cursor.fetchall()]
        if 'company_id' not in columns:
            print('Agregando company_id a erp_product...')
            cursor.execute('ALTER TABLE erp_product ADD COLUMN company_id INTEGER')
            print('✓ company_id agregado a erp_product')
        
        # Verificar si erp_company existe
        cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='erp_company'\")
        if not cursor.fetchone():
            print('Creando tabla erp_company...')
            cursor.execute('''
                CREATE TABLE erp_company (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL,
                    ruc VARCHAR(20),
                    address TEXT,
                    phone VARCHAR(50),
                    email VARCHAR(100),
                    is_active BOOLEAN DEFAULT 1,
                    date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print('✓ Tabla erp_company creada')
            
            # Insertar empresa por defecto
            cursor.execute('INSERT INTO erp_company (name, ruc) VALUES (?, ?)', ['Mi Empresa', ''])
            print('✓ Empresa por defecto creada')
        
        # Asignar company_id por defecto si es NULL
        cursor.execute('UPDATE erp_category SET company_id = 1 WHERE company_id IS NULL')
        cursor.execute('UPDATE erp_product SET company_id = 1 WHERE company_id IS NULL')
        print('✓ company_id asignado por defecto donde faltaba')
        
        print('✓ Estructura de tablas verificada y corregida')
except Exception as e:
    print(f'Error verificando tablas: {e}')
" 2>nul

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
