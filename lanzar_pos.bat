@echo off
REM Lanzar POS local de MultilideresCRM en Windows

REM Ir siempre a la carpeta donde esta este script
cd /d "%~dp0"

if not exist DJENV\Scripts\activate.bat (
    echo [ERROR] Entorno virtual venv no encontrado. Cree el venv primero:
    echo python -m venv DJENV
    pause
    exit /b 1
)

call DJENV\Scripts\activate

REM Asegurar entorno de POS (no production)
set ENVIRONMENT=development

REM Leer dominio local desde .env (si existe)
set "ACCESS_HOST=localhost"
if exist .env (
    for /f "tokens=1,* delims==" %%a in (.env) do (
        if /I "%%a"=="LOCAL_DOMAIN" (
            set "DOMAIN_VALUE=%%b"
            if not "!DOMAIN_VALUE!"=="" set "ACCESS_HOST=!DOMAIN_VALUE!"
        )
    )
)

echo Iniciando servidor Django en http://%ACCESS_HOST%:8000 ...
REM Abrir el servidor en una nueva ventana para no bloquear este script
start "POS_Local_Django" python manage.py runserver 0.0.0.0:8000

REM Esperar unos segundos a que levante el servidor (ajustado a 10s para equipos mas lentos)
timeout /t 10 /nobreak >nul

REM Abrir el navegador en la URL del POS (launcher)
start "" "http://%ACCESS_HOST%:8000/erp/launcher/"

pause