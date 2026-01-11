@echo off
REM Script para preparar un paquete de instalacion con Git Portable incluido

echo ============================================
echo  Preparador de Paquete Portable
echo  MultilideresCRM - Git Portable Edition
echo ============================================
echo.

REM Configuracion
set "PROJECT_DIR=%~dp0"
set "TOOLS_DIR=%PROJECT_DIR%tools"
set "GIT_PORTABLE_DIR=%TOOLS_DIR%\PortableGit"
set "PACK_DIR=%PROJECT_DIR%paquete_instalacion"
set "GIT_DOWNLOAD_URL=https://github.com/git-for-windows/git/releases/download/v2.45.0.windows.1/PortableGit-2.45.0-64-bit.7z.exe"
set "GIT_INSTALLER=%TOOLS_DIR%\PortableGit-2.45.0-64-bit.7z.exe"

echo Este script prepara un paquete de instalacion que incluye:
echo - El sistema completo
echo - Git Portable pre-configurado
echo - Scripts de instalacion mejorados
echo.

set /p confirm="Desea preparar el paquete portable? (S/N): "
if /i not "%confirm%"=="S" (
    echo Operacion cancelada.
    pause
    exit /b 0
)

REM Crear directorio tools si no existe
if not exist "%TOOLS_DIR%" (
    echo Creando directorio tools...
    mkdir "%TOOLS_DIR%"
)

REM Verificar si Git Portable ya existe
if exist "%GIT_PORTABLE_DIR%\bin\git.exe" (
    echo [OK] Git Portable ya existe en: %GIT_PORTABLE_DIR%
    set /p redownload="Desea descargar nuevamente? (S/N): "
    if /i not "%redownload%"=="S" (
        goto skip_download
    )
)

REM Descargar Git Portable
echo.
echo Descargando Git Portable...
echo URL: %GIT_DOWNLOAD_URL%
echo Destino: %GIT_INSTALLER%
echo.

REM Verificar curl
curl --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] curl no esta disponible.
    echo Descargue Git Portable manualmente y extraiga en:
    echo   %GIT_PORTABLE_DIR%
    pause
    exit /b 1
)

curl -L -o "%GIT_INSTALLER%" "%GIT_DOWNLOAD_URL%"
if errorlevel 1 (
    echo [ERROR] Error al descargar Git Portable.
    echo Verifique su conexion a internet.
    pause
    exit /b 1
)

echo [OK] Git Portable descargado.

REM Extraer Git Portable
echo Extrayendo Git Portable...
echo Esto puede tardar varios minutos...

REM Usar 7z si esta disponible
7z x "%GIT_INSTALLER%" -o"%GIT_PORTABLE_DIR%" >nul 2>&1
if errorlevel 1 (
    echo Intentando extraccion automatica...
    "%GIT_INSTALLER%" -y -o"%GIT_PORTABLE_DIR%" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Error al extraer Git Portable.
        echo.
        echo Extraiga manualmente:
        echo   1. Abra: %GIT_INSTALLER%
        echo   2. Seleccione destino: %GIT_PORTABLE_DIR%
        echo   3. Extraiga todos los archivos
        pause
        exit /b 1
    )
)

REM Limpiar instalador
del "%GIT_INSTALLER%"

:skip_download
REM Verificar instalacion
if exist "%GIT_PORTABLE_DIR%\bin\git.exe" (
    echo [OK] Git Portable instalado en: %GIT_PORTABLE_DIR%
    
    REM Configurar Git Portable
    echo Configurando Git Portable...
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global user.name "POS User"
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global user.email "pos@multilideres.com"
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global init.defaultBranch main
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global pull.rebase false
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global safe.directory "*"
    
    echo [OK] Git Portable configurado.
) else (
    echo [ERROR] Git Portable no encontrado en: %GIT_PORTABLE_DIR%
    pause
    exit /b 1
)

REM Crear paquete de instalacion
echo.
echo Creando paquete de instalacion...

REM Limpiar paquete anterior
if exist "%PACK_DIR%" (
    echo Limpiando paquete anterior...
    rmdir /s /q "%PACK_DIR%"
)

mkdir "%PACK_DIR%"

REM Copiar archivos del proyecto
echo Copiando archivos del proyecto...
xcopy "%PROJECT_DIR%" "%PACK_DIR%" /E /I /H /Y
if errorlevel 1 (
    echo [ERROR] Error al copiar archivos del proyecto.
    pause
    exit /b 1
)

REM Excluir archivos temporales y de desarrollo
echo Excluyendo archivos temporales...
if exist "%PACK_DIR%\.git" rmdir /s /q "%PACK_DIR%\.git"
if exist "%PACK_DIR%\__pycache__" rmdir /s /q "%PACK_DIR%\__pycache__"
if exist "%PACK_DIR%\.pytest_cache" rmdir /s /q "%PACK_DIR%\.pytest_cache"
if exist "%PACK_DIR%\.vscode" rmdir /s /q "%PACK_DIR%\.vscode"
if exist "%PACK_DIR%\.idea" rmdir /s /q "%PACK_DIR%\.idea"
if exist "%PACK_DIR%\node_modules" rmdir /s /q "%PACK_DIR%\node_modules"
if exist "%PACK_DIR%*.pyc" del /q "%PACK_DIR%\*.pyc"
if exist "%PACK_DIR%*.pyo" del /q "%PACK_DIR%\*.pyo"
if exist "%PACK_DIR%*.log" del /q "%PACK_DIR%\*.log"

REM Crear archivo de informacion del paquete
echo Creando informacion del paquete...
(
echo Paquete de Instalacion - MultilideresCRM
echo ============================================
echo.
echo Este paquete incluye:
echo - Sistema completo MultilideresCRM
echo - Git Portable v2.45.0 pre-configurado
echo - Scripts de instalacion automatica
echo - Soporte para actualizaciones sin instalar Git
echo.
echo Estructura:
echo - SitioMTCRM\          : Sistema principal
echo - tools\PortableGit\    : Git Portable incluido
echo.
echo Instalacion:
echo 1. Ejecute: instalador_pos_bat.bat
echo 2. Siga las instrucciones
echo 3. El sistema detectara Git Portable automaticamente
echo.
echo Actualizaciones:
echo - Use la interfaz web: http://localhost:8000/erp/updates/
echo - Boton "Actualizar (Portable)" disponible
echo.
echo Creado: %date% %time%
echo Sistema: %COMPUTERNAME%
echo.
) > "%PACK_DIR%\PAQUETE_INFO.txt"

REM Crear script de instalacion mejorado
echo Creando instalador mejorado...
(
echo @echo off
echo REM Instalador MultilideresCRM - Git Portable Edition
echo REM Este paquete incluye Git Portable pre-configurado
echo.
echo echo ============================================
echo echo  Instalador MultilideresCRM
echo echo  Git Portable Edition
echo echo ============================================
echo echo.
echo echo Este paquete incluye Git Portable pre-configurado.
echo echo No necesita instalar Git en su sistema.
echo echo.
echo pause
echo.
echo REM Ejecutar instalador original
echo call instalador_pos_bat.bat
) > "%PACK_DIR%\INSTALAR.bat"

REM Obtener tamaño del paquete
for /f "tokens=3" %%a in ('dir "%PACK_DIR%" /s /-c ^| find "bytes"') do set SIZE=%%a

echo.
echo ============================================
echo  PAQUETE CREADO EXITOSAMENTE!
echo ============================================
echo.
echo Ubicacion del paquete: %PACK_DIR%
echo Tamano: %SIZE% bytes
echo.
echo Contenido del paquete:
echo - Sistema completo MultilideresCRM
echo - Git Portable v2.45.0 pre-configurado
echo - Scripts de instalacion automatica
echo - Documentacion de instalacion
echo.
echo Para distribuir:
echo 1. Comprima la carpeta: %PACK_DIR%
echo 2. Enviar a los usuarios
echo 3. Los usuarios ejecutan INSTALAR.bat
echo.
echo Los usuarios no necesitaran instalar Git!
echo Git Portable esta incluido y configurado.
echo.
pause
