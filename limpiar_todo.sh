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
echo "[1/5] Eliminando base de datos..."
rm -f db.sqlite3
echo "Base de datos eliminada."

# 2. Eliminar migraciones
echo "[2/5] Eliminando migraciones..."
find . -path "*/migrations/*.py" ! -name "__init__.py" -delete
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
echo "Migraciones eliminadas."

# 3. Eliminar archivos estáticos
echo "[3/5] Eliminando archivos estáticos recolectados..."
rm -rf staticfiles
rm -rf core/static
echo "Archivos estáticos eliminados."

# 4. Eliminar archivos de caché
echo "[4/5] Eliminando archivos de caché..."
find . -name "*.pyc" -delete
find . -name "*.pyo" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
echo "Caché eliminado."

# 5. Eliminar archivos temporales
echo "[5/5] Eliminando archivos temporales..."
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
echo "Esto creará una base de datos completamente nueva."
echo
