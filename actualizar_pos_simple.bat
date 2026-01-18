@echo off
REM Script de actualización simplificado para Windows
REM Llama al script Python unificado

cd /d "%~dp0"

echo ============================================
echo Actualizador POS - SitioMTCRM (Windows)
echo ============================================
echo.

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no está instalado o no está en el PATH.
    echo.
    echo Por favor, instale Python desde https://python.org
    pause
    exit /b 1
)

REM Ejecutar el script de actualización
python update_system.py %*

REM Si el script falló, pausar para ver el error
if errorlevel 1 (
    echo.
    echo La actualización falló. Revise los mensajes de error arriba.
    pause
)
