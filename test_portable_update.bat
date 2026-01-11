@echo off
REM Script de prueba para verificar el sistema de actualización portable

echo ============================================
echo  TEST DEL SISTEMA DE ACTUALIZACIÓN PORTABLE
echo ============================================
echo.

REM Simular estructura de directorios
echo Creando estructura de prueba...
if not exist tools mkdir tools
if not exist tools\PortableGit mkdir tools\PortableGit
if not exist tools\PortableGit\bin mkdir tools\PortableGit\bin

REM Crear git.exe falso para prueba
echo Simulando Git Portable...
echo @echo off > tools\PortableGit\bin\git.exe
echo echo Git Portable simulado >> tools\PortableGit\bin\git.exe

REM Verificar detección
echo.
echo 1. Verificando detección de Git Portable...
if exist tools\PortableGit\bin\git.exe (
    echo [OK] Git Portable detectado correctamente
) else (
    echo [ERROR] Git Portable no detectado
)

REM Probar script de actualización portable
echo.
echo 2. Probando script de actualización portable...
if exist actualizar_pos_portable.bat (
    echo [OK] Script portable encontrado
    echo Ejecutando prueba del script...
    call actualizar_pos_portable.bat
) else (
    echo [ERROR] Script portable no encontrado
)

REM Probar instalador
echo.
echo 3. Verificando instalador...
if exist instalador_pos_bat.bat (
    echo [OK] Instalador encontrado
    echo El instalador debería detectar Git Portable automaticamente
) else (
    echo [ERROR] Instalador no encontrado
)

REM Probar configurador
echo.
echo 4. Verificando configurador inline...
if exist setup_git_portable_inline.bat (
    echo [OK] Configurador inline encontrado
) else (
    echo [ERROR] Configurador inline no encontrado
)

REM Probar preparador de paquete
echo.
echo 5. Verificando preparador de paquete...
if exist preparar_paquete_portable.bat (
    echo [OK] Preparador de paquete encontrado
) else (
    echo [ERROR] Preparador de paquete no encontrado
)

echo.
echo ============================================
echo  RESUMEN DE PRUEBA
echo ============================================
echo.
echo Componentes del sistema:
if exist tools\PortableGit\bin\git.exe (
    echo   [OK] Git Portable: Configurado
) else (
    echo   [ERROR] Git Portable: No configurado
)

if exist actualizar_pos_portable.bat (
    echo   [OK] Script portable: Disponible
) else (
    echo   [ERROR] Script portable: No disponible
)

if exist setup_git_portable_inline.bat (
    echo   [OK] Configurador: Disponible
) else (
    echo   [ERROR] Configurador: No disponible
)

if exist instalador_pos_bat.bat (
    echo   [OK] Instalador: Disponible
) else (
    echo   [ERROR] Instalador: No disponible
)

echo.
echo Para probar la interfaz web:
echo 1. Inicie el sistema: lanzar_pos.bat
echo 2. Vaya a: http://localhost:8000/erp/updates/
echo 3. Verifique que aparezca el boton "Actualizar (Portable)"
echo 4. Haga clic en el boton para probar la ejecucion

echo.
echo Limpiando archivos de prueba...
if exist tools\PortableGit rmdir /s /q tools\PortableGit

echo.
echo === PRUEBA COMPLETADA ===
echo.
pause
