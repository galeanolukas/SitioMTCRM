@echo off
REM Configurador de Git Portable para Actualizador POS
REM Descarga y configura Git Portable automáticamente

echo ============================================
echo  Configurador Git Portable - MultilideresCRM
echo  Thumbdrive Edition Setup
echo ============================================
echo.

REM Configuración
set "TOOLS_DIR=%~dp0tools"
set "GIT_PORTABLE_DIR=%TOOLS_DIR%\git-portable"
set "GIT_DOWNLOAD_URL=https://github.com/git-for-windows/git/releases/download/v2.45.0.windows.1/PortableGit-2.45.0-64-bit.7z.exe"
set "GIT_INSTALLER=PortableGit-2.45.0-64-bit.7z.exe"

REM Crear directorio tools si no existe
if not exist "%TOOLS_DIR%" (
    echo Creando directorio tools...
    mkdir "%TOOLS_DIR%"
)

REM Verificar si Git Portable ya está instalado
if exist "%GIT_PORTABLE_DIR%\bin\git.exe" (
    echo [OK] Git Portable ya esta instalado en: %GIT_PORTABLE_DIR%
    echo.
    echo Para usar el actualizador portable, ejecute:
    echo   actualizar_pos_portable.bat
    echo.
    pause
    exit /b 0
)

echo Git Portable no encontrado. Iniciando descarga...
echo.

REM Verificar si curl está disponible
curl --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] curl no esta disponible.
    echo.
    echo Descargue Git Portable manualmente:
    echo   URL: %GIT_DOWNLOAD_URL%
    echo.
    echo Extraiga el contenido en: %GIT_PORTABLE_DIR%
    echo.
    echo Luego ejecute este script nuevamente.
    pause
    exit /b 1
)

REM Descargar Git Portable
echo Descargando Git Portable...
echo URL: %GIT_DOWNLOAD_URL%
echo Destino: %TOOLS_DIR%\%GIT_INSTALLER%
echo.

curl -L -o "%TOOLS_DIR%\%GIT_INSTALLER%" "%GIT_DOWNLOAD_URL%"
if errorlevel 1 (
    echo [ERROR] Error al descargar Git Portable.
    echo Verifique su conexion a internet.
    pause
    exit /b 1
)

echo [OK] Git Portable descargado exitosamente.
echo.

REM Extraer Git Portable
echo Extrayendo Git Portable...
echo Esto puede tardar varios minutos...
echo.

REM Usar 7z si está disponible, sino intentar con el auto-extractor
7z x "%TOOLS_DIR%\%GIT_INSTALLER%" -o"%GIT_PORTABLE_DIR%" >nul 2>&1
if errorlevel 1 (
    echo Intentando extraccion automatica...
    "%TOOLS_DIR%\%GIT_INSTALLER%" -y -o"%GIT_PORTABLE_DIR%" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Error al extraer Git Portable.
        echo.
        echo Extraiga manualmente:
        echo   1. Abra: %TOOLS_DIR%\%GIT_INSTALLER%
        echo   2. Seleccione destino: %GIT_PORTABLE_DIR%
        echo   3. Extraiga todos los archivos
        echo.
        pause
        exit /b 1
    )
)

REM Limpiar instalador
del "%TOOLS_DIR%\%GIT_INSTALLER%"

REM Verificar instalación
if exist "%GIT_PORTABLE_DIR%\bin\git.exe" (
    echo [OK] Git Portable instalado exitosamente!
    echo.
    echo Ubicacion: %GIT_PORTABLE_DIR%
    echo Version:
    "%GIT_PORTABLE_DIR%\bin\git.exe" --version
    echo.
    echo Configurando Git Portable...
    
    REM Configurar Git Portable
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global user.name "POS User"
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global user.email "pos@multilideres.com"
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global init.defaultBranch main
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global pull.rebase false
    "%GIT_PORTABLE_DIR%\bin\git.exe" config --global safe.directory "*"
    
    echo [OK] Git Portable configurado.
    echo.
    echo Ahora puede usar el actualizador portable:
    echo   actualizar_pos_portable.bat
    echo.
) else (
    echo [ERROR] Git Portable no se pudo instalar correctamente.
    echo Verifique la extraccion manual.
    pause
    exit /b 1
)

echo ============================================
echo Configuracion completada exitosamente!
echo ============================================
echo.
echo Git Portable esta listo para usar.
echo Puede ejecutar el sistema sin instalar Git en Windows.
echo.
pause
