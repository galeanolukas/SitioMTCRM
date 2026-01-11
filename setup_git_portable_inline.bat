@echo off
REM Configurador Git Portable Inline - Version Integrada
REM Este script incluye Git Portable directamente en el instalador

echo ============================================
echo  Configurador Git Portable - Version Integrada
echo  MultilideresCRM
echo ============================================
echo.

REM Configuracion
set "SCRIPT_DIR=%~dp0"
set "TOOLS_DIR=%SCRIPT_DIR%tools"
set "GIT_PORTABLE_DIR=%TOOLS_DIR%\PortableGit"
set "GIT_VERSION=2.45.0"
set "GIT_URL=https://github.com/git-for-windows/git/releases/download/v%GIT_VERSION%.windows.1/PortableGit-%GIT_VERSION%-64-bit.7z.exe"

echo Este script configurara Git Portable para actualizaciones automaticas.
echo Git Portable permite actualizar el sistema sin instalar Git en Windows.
echo.

REM Crear directorio tools si no existe
if not exist "%TOOLS_DIR%" (
    echo Creando directorio tools...
    mkdir "%TOOLS_DIR%"
)

REM Verificar si Git Portable ya esta configurado
if exist "%GIT_PORTABLE_DIR%\bin\git.exe" (
    echo [OK] Git Portable ya esta configurado.
    echo.
    echo Git Portable listo para usar.
    echo Version:
    "%GIT_PORTABLE_DIR%\bin\git.exe" --version
    echo.
    echo Puede usar el boton "Actualizar (Portable)" en la interfaz web.
    pause
    exit /b 0
)

REM Metodo 1: Descargar automaticamente
echo.
echo Metodo 1: Descarga automatica de Git Portable
echo -------------------------------------------
echo.

REM Verificar si curl esta disponible
curl --version >nul 2>&1
if not errorlevel 1 (
    echo [OK] curl detectado. Iniciando descarga automatica...
    echo.
    echo Descargando Git Portable v%GIT_VERSION%...
    echo URL: %GIT_URL%
    echo.
    
    set "GIT_INSTALLER=%TOOLS_DIR%\PortableGit-%GIT_VERSION%-64-bit.7z.exe"
    
    curl -L -o "%GIT_INSTALLER%" "%GIT_URL%"
    if not errorlevel 1 (
        echo [OK] Git Portable descargado exitosamente.
        echo.
        echo Extrayendo Git Portable...
        echo Esto puede tardar varios minutos...
        
        "%GIT_INSTALLER%" -y -o"%GIT_PORTABLE_DIR%" >nul 2>&1
        if not errorlevel 1 (
            echo [OK] Git Portable extraido exitosamente.
            del "%GIT_INSTALLER%"
            goto configure_git
        ) else (
            echo [ADVERTENCIA] Error en extraccion automatica.
            echo.
            echo Opciones:
            echo 1. Extraer manualmente: Abra %GIT_INSTALLER% y extraiga en %GIT_PORTABLE_DIR%
            echo 2. Usar metodo alternativo
            echo 3. Continuar sin Git Portable
            echo.
            set /p extract_choice="Elija una opcion (1/2/3): "
            if "%extract_choice%"=="1" (
                echo Abra el instalador manualmente cuando termine este script.
                echo Ruta: %GIT_INSTALLER%
                echo Destino: %GIT_PORTABLE_DIR%
                pause
                exit /b 0
            ) else if "%extract_choice%"=="3" (
                goto skip_git_portable
            )
        )
    ) else (
        echo [ERROR] Error al descargar Git Portable.
        echo.
    )
) else (
    echo [ADVERTENCIA] curl no esta disponible.
)

REM Metodo 2: Descarga con PowerShell
echo.
echo Metodo 2: Descarga con PowerShell
echo --------------------------------
echo.

set /p ps_download="Intentar descargar con PowerShell? (S/N): "
if /i "%ps_download%"=="S" (
    echo Descargando Git Portable con PowerShell...
    
    set "GIT_INSTALLER=%TOOLS_DIR%\PortableGit-%GIT_VERSION%-64-bit.7z.exe"
    
    powershell -Command "& {Invoke-WebRequest -Uri '%GIT_URL%' -OutFile '%GIT_INSTALLER%'}"
    if not errorlevel 1 (
        echo [OK] Git Portable descargado con PowerShell.
        echo.
        echo Extrayendo Git Portable...
        
        "%GIT_INSTALLER%" -y -o"%GIT_PORTABLE_DIR%" >nul 2>&1
        if not errorlevel 1 (
            echo [OK] Git Portable extraido exitosamente.
            del "%GIT_INSTALLER%"
            goto configure_git
        ) else (
            echo [ADVERTENCIA] Error en extraccion.
        )
    ) else (
        echo [ERROR] Error al descargar con PowerShell.
    )
) else (
    echo Omitiendo descarga con PowerShell.
)

REM Metodo 3: Instrucciones manuales
echo.
echo Metodo 3: Configuracion Manual
echo ------------------------------
echo.
echo Si los metodos automaticos fallaron, puede configurar Git Portable manualmente:
echo.
echo PASO 1: Descargar Git Portable
echo   URL: %GIT_URL%
echo   Nombre: PortableGit-%GIT_VERSION%-64-bit.7z.exe
echo.
echo PASO 2: Extraer archivos
echo   1. Ejecute el archivo descargado
echo   2. Seleccione destino: %GIT_PORTABLE_DIR%
echo   3. Extraiga todos los archivos
echo.
echo PASO 3: Verificar instalacion
echo   Debe existir: %GIT_PORTABLE_DIR%\bin\git.exe
echo.
echo PASO 4: Configurar (opcional)
echo   El sistema lo configurara automaticamente al detectarlo
echo.
echo Alternativas:
echo - Instalar Git para Windows desde https://git-scm.com/download/win
echo - Usar el sistema sin Git Portable (funciones limitadas)
echo.

set /p manual_choice="Desea intentar la configuracion manual ahora? (S/N): "
if /i not "%manual_choice%"=="S" (
    goto skip_git_portable
)

echo.
echo Espere a que complete la instalacion manual...
echo.
echo Cuando termine, presione cualquier tecla para verificar...
pause >nul

:configure_git
REM Verificar instalacion y configurar
if exist "%GIT_PORTABLE_DIR%\bin\git.exe" (
    echo [OK] Git Portable encontrado.
    echo.
    echo Configurando Git Portable...
    
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global user.name "POS User"
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global user.email "pos@multilideres.com"
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global init.defaultBranch main
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global pull.rebase false
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global safe.directory "*"
    
    echo [OK] Git Portable configurado exitosamente!
    echo.
    echo Informacion de Git Portable:
    echo   Version:
    "%GIT_PORTABLE_DIR%\bin\git.exe" --version
    echo   Ubicacion: %GIT_PORTABLE_DIR%
    echo.
    echo Git Portable esta listo para usar.
    echo.
    echo Caracteristicas disponibles:
    echo - Actualizaciones automaticas sin instalar Git
    echo - Boton "Actualizar (Portable)" en la interfaz web
    echo - Script: actualizar_pos_portable.bat
    echo.
    echo Para usar Git Portable:
    echo 1. Inicie el sistema: lanzar_pos.bat
    echo 2. Vea a: http://localhost:8000/erp/updates/
    echo 3. Use el boton "Actualizar (Portable)" cuando haya actualizaciones
    echo.
) else (
    echo [ERROR] Git Portable no encontrado en: %GIT_PORTABLE_DIR%
    echo.
    echo Verifique que:
    echo 1. Descargo el archivo correcto
    echo 2. Extrajo en la ubicacion correcta
    echo 3. El archivo git.exe existe en %GIT_PORTABLE_DIR%\bin\
    echo.
    echo Puede reintentar la configuracion ejecutando este script nuevamente.
)

:skip_git_portable
echo.
echo ============================================
echo  Configuracion Git Portable Completa
echo ============================================
echo.
echo Estado de Git Portable:
if exist "%GIT_PORTABLE_DIR%\bin\git.exe" (
    echo   [OK] Configurado y listo para usar
) else (
    echo   [NO CONFIGURADO] - No disponible
    echo.
    echo Para configurarlo mas tarde:
    echo 1. Ejecute: setup_git_portable_inline.bat
    echo 2. O descargue e instale Git para Windows
    echo.
    echo Sin Git Portable, podra usar:
    echo - Actualizaciones con Git instalado
    echo - Funciones basicas del sistema
)
echo.
echo Presione cualquier tecla para salir...
pause >nul
