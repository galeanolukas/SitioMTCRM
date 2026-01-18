@echo off
REM Script para ejecutar release automático en Windows
echo.
echo ========================================
echo   RELEASE AUTOMATICO - WINDOWS
echo ========================================
echo.

REM Verificar si existe el script de Python
if not exist "release_manager.py" (
    echo ❌ Error: No se encuentra release_manager.py
    pause
    exit /b 1
)

REM Verificar si Python está disponible
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python no está disponible
    pause
    exit /b 1
)

REM Mostrar opciones
echo.
echo 📦 Tipo de release:
echo   1. Patch (1.0.0 -^> 1.0.1) - Correccion de errores
echo   2. Minor (1.0.1 -^> 1.1.0) - Nuevas caracteristicas  
echo   3. Major (1.1.0 -^> 2.0.0) - Cambios importantes
echo.

set /p choice="Seleccione el tipo de release (1-3): "

if "%choice%"=="1" (
    set release_type=patch
    echo ✅ Seleccionado: Patch Release
) else if "%choice%"=="2" (
    set release_type=minor
    echo ✅ Seleccionado: Minor Release
) else if "%choice%"=="3" (
    set release_type=major
    echo ✅ Seleccionado: Major Release
) else (
    echo ❌ Opcion invalida
    pause
    exit /b 1
)

echo.
set /p commit_msg="Mensaje del commit (opcional, presione Enter para usar automatico): "

REM Ejecutar el release manager
echo.
echo 🚀 Iniciando proceso de release...
echo.

if "%commit_msg%"=="" (
    python release_manager.py %release_type%
) else (
    python release_manager.py %release_type% "%commit_msg%"
)

if errorlevel 1 (
    echo.
    echo ❌ El proceso de release falló
    pause
    exit /b 1
) else (
    echo.
    echo ✅ Release completado exitosamente
    pause
)
