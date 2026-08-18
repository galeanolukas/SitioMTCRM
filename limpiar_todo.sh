#!/bin/bash
# Script para limpiar completamente todas las migraciones y base de datos
# Útil para instalaciones frescas o para resetear completamente

echo "============================================"
echo "Limpiador Completo de Base de Datos"
echo "============================================"
echo

cd "$(dirname "$0")"

echo "⚠️  ADVERTENCIA: Esto eliminará TODOS los datos!"
echo "   - Base de datos SQLite"
echo "   - Entorno virtual DJENV"
echo "   - Todas las migraciones"
echo "   - Archivos estáticos recolectados"
echo

read -p "¿Está seguro de continuar? (escriba 'BORRAR TODO'): " confirm

if [ "$confirm" != "BORRAR TODO" ]; then
    echo "Operación cancelada."
    exit 0
fi

echo "Iniciando limpieza completa..."

# 1. Eliminar base de datos
echo "[1/6] Eliminando base de datos..."
rm -f db.sqlite3
echo "Base de datos eliminada."

# 2. Eliminar entorno virtual DJENV
echo "[2/6] Eliminando entorno virtual DJENV..."
rm -rf DJENV
echo "Entorno virtual eliminado."

# 3. Eliminar migraciones
echo "[3/6] Eliminando migraciones..."
find ./core -path "*/migrations/*.py" ! -name "__init__.py" -delete 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
echo "Migraciones eliminadas."

# 4. Eliminar archivos estáticos
echo "[4/6] Eliminando archivos estáticos recolectados..."
rm -rf staticfiles
rm -rf core/static
echo "Archivos estáticos eliminados."

# 5. Eliminar archivos de caché
echo "[5/6] Eliminando archivos de caché..."
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
echo "Caché eliminado."

# 6. Eliminar archivos temporales
echo "[6/6] Eliminando archivos temporales..."
find . -name "*.tmp" -delete
find . -name "*.log" -delete
find . -name ".DS_Store" -delete
echo "Archivos temporales eliminados."

echo
echo "============================================"
echo "¡LIMPIEZA COMPLETADA!"
echo "============================================"
echo
echo "Ahora puede ejecutar el instalador:"
echo "  Windows: ejecutar instalador_pos_bat.bat"
echo "  Linux:   ./install.sh"
echo
echo "Esto creará una base de datos y entorno virtual completamente nuevos."
echo
