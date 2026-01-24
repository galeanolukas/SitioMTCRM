@echo off
REM Script para diagnosticar y reparar problemas con pandas y openpyxl en Windows
cd /d "%~dp0"

echo ============================================
echo Diagnosticando librerías para Excel/CSV
echo ============================================
echo.

REM Verificar si estamos en el entorno virtual
python -c "import sys; print('Python path:', sys.executable)" 2>nul
echo.

REM Verificar pandas
echo Verificando pandas...
python -c "import pandas; print('pandas version:', pandas.__version__)" 2>nul
if errorlevel 1 (
    echo [ERROR] pandas no está instalado o no se puede importar
    set PANDAS_MISSING=1
) else (
    echo [OK] pandas está instalado
    set PANDAS_MISSING=0
)
echo.

REM Verificar openpyxl
echo Verificando openpyxl...
python -c "import openpyxl; print('openpyxl version:', openpyxl.__version__)" 2>nul
if errorlevel 1 (
    echo [ERROR] openpyxl no está instalado o no se puede importar
    set OPENPYXL_MISSING=1
) else (
    echo [OK] openpyxl está instalado
    set OPENPYXL_MISSING=0
)
echo.

REM Si alguna librería falta, intentar instalar
if %PANDAS_MISSING%==1 (
    echo Instalando pandas...
    pip install pandas
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar pandas
        echo Intentando instalación forzada...
        pip install --force-reinstall pandas
    )
)

if %OPENPYXL_MISSING%==1 (
    echo Instalando openpyxl...
    pip install openpyxl
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar openpyxl
        echo Intentando instalación forzada...
        pip install --force-reinstall openpyxl
    )
)

REM Verificación final
echo.
echo ============================================
echo Verificación final
echo ============================================
echo.

python -c "import pandas, openpyxl; print('pandas:', pandas.__version__); print('openpyxl:', openpyxl.__version__)" 2>nul
if errorlevel 1 (
    echo [ERROR] Aún hay problemas con las librerías
    echo.
    echo Soluciones manuales:
    echo 1. Asegúrate de estar en el entorno virtual: venv\Scripts\activate
    echo 2. Actualiza pip: python -m pip install --upgrade pip
    echo 3. Instala manualmente: pip install pandas openpyxl
    echo 4. Si falla, intenta: pip install --no-cache-dir pandas openpyxl
    echo 5. Como último recurso: pip install --upgrade --force-reinstall pandas openpyxl
    echo.
    echo Si nada funciona, ejecuta: instalador_pos_bat.bat
) else (
    echo [EXITO] Todas las librerías están instaladas correctamente
    echo Ya deberías poder importar archivos Excel/CSV sin problemas
)

echo.
pause
