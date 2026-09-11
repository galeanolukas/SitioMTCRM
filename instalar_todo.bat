@echo off
setlocal EnableDelayedExpansion

REM Instalar TODO - Bootstrap Windows para TechVentas POS
REM Clona el repositorio usando PortableGit y ejecuta instalador_pos.bat

cd /d "%~dp0"

set "REPO_URL=https://github.com/galeanolukas/SitioMTCRM.git"
set "REPO_DIR=SitioMTCRM"
set "PORTABLE_GIT=tools\PortableGit\cmd\git.exe"

echo ============================================
echo   Instalador completo - TechVentas POS
echo ============================================
echo.

REM ---------------------------------------------------------------------------
REM Verificar permisos de administrador
REM ---------------------------------------------------------------------------
net session >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] Este instalador puede requerir permisos de administrador
    echo                  para modificar el archivo hosts y crear accesos directos.
    echo.
    choice /c SN /M "Desea continuar sin permisos de administrador"
    if errorlevel 2 exit /b 1
)

REM ---------------------------------------------------------------------------
REM Verificar PortableGit
REM ---------------------------------------------------------------------------
if not exist "%PORTABLE_GIT%" (
    echo [ERROR] No se encontro PortableGit en: %PORTABLE_GIT%
    echo.
    echo Coloque PortableGit en la carpeta:
    echo   %~dp0tools\PortableGit\
    echo.
    echo O descargue PortableGit desde:
    echo https://github.com/git-for-windows/git/releases
    pause
    exit /b 1
)

echo [OK] PortableGit detectado: %PORTABLE_GIT%
echo.

REM ---------------------------------------------------------------------------
REM Clonar repositorio
REM ---------------------------------------------------------------------------
if exist "%REPO_DIR%" (
    echo La carpeta %REPO_DIR% ya existe.
    choice /c SN /M "Desea eliminarla y clonar de nuevo"
    if errorlevel 1 (
        echo Eliminando %REPO_DIR%...
        rmdir /s /q "%REPO_DIR%"
    ) else (
        echo Continuando con la carpeta existente.
    )
)

echo Clonando repositorio desde %REPO_URL%...
"%PORTABLE_GIT%" clone "%REPO_URL%" "%REPO_DIR%"
if errorlevel 1 (
    echo [ERROR] No se pudo clonar el repositorio.
    pause
    exit /b 1
)

echo [OK] Repositorio clonado en: %~dp0%REPO_DIR%
echo.

REM ---------------------------------------------------------------------------
REM Ejecutar instalador
REM ---------------------------------------------------------------------------
cd /d "%~dp0%REPO_DIR%"
if not exist "instalador_pos.bat" (
    echo [ERROR] No se encontro instalador_pos.bat en %REPO_DIR%
    pause
    exit /b 1
)

echo Ejecutando instalador_pos.bat...
call instalador_pos.bat

exit /b %errorlevel%
