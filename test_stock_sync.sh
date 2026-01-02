#!/bin/bash

echo "=== Prueba de sincronización de stock ==="
echo ""

echo "PASO 1: Vamos a probar si los cambios de stock se marcan para sincronizar"
echo ""

echo "Instrucciones:"
echo "1. Abre la interfaz web del POS en tu navegador"
echo "2. Ve a la sección de Productos"
echo "3. Busca cualquier producto y cambia su stock (ej: de 10 a 15)"
echo "4. Guarda los cambios"
echo "5. Vuelve a esta terminal y presiona ENTER"
echo ""

read -p "Presiona ENTER cuando hayas cambiado el stock de un producto..."

echo ""
echo "PASO 2: Verificando si el cambio se marcó para sincronizar..."
echo ""

# Intentar ejecutar el comando check_sync
echo "Ejecutando: python3 manage.py check_sync"
echo ""

# Intentar different python commands
if command -v python3 &> /dev/null; then
    echo "Intentando con python3..."
    cd /media/lukas/ARCHIVOS/GitHub/SitioMTCRM
    
    # Intentar ejecutar sin entorno virtual primero
    python3 manage.py check_sync 2>&1 | head -20
    RESULT=$?
    
    if [ $RESULT -eq 0 ]; then
        echo ""
        echo "✅ Comando ejecutado exitosamente"
    else
        echo ""
        echo "❌ Error al ejecutar el comando. Intentando encontrar entorno virtual..."
        
        # Buscar entornos virtuales
        for venv_dir in /media/lukas/ARCHIVOS/GitHub/*/venv /media/lukas/ARCHIVOS/GitHub/*/env /media/lukas/ARCHIVOS/GitHub/*/.venv; do
            if [ -d "$venv_dir" ] && [ -f "$venv_dir/bin/python" ]; then
                echo "Intentando con entorno virtual: $venv_dir"
                source "$venv_dir/bin/activate" 2>/dev/null
                python manage.py check_sync 2>&1 | head -20
                deactivate 2>/dev/null
                break
            fi
        done
    fi
else
    echo "❌ Python3 no encontrado"
fi

echo ""
echo "PASO 3: Análisis de resultados"
echo ""

echo "Si el comando anterior mostró:"
echo "• 'Hay X productos pendientes de sincronizar' → ✅ Los cambios se marcaron correctamente"
echo "• 'No hay productos pendientes de sincronizar' → ❌ Los cambios NO se marcaron"
echo ""

echo "Si los cambios no se marcaron, el problema está en:"
echo "• El método save() del modelo Product"
echo "• Las actualizaciones de stock no pasan por el save() del modelo"
echo ""

echo "PASO 4: Forzar sincronización manual"
echo ""

echo "Para forzar la sincronización de productos pendientes:"
echo "python3 manage.py sync_products_to_remote"
echo ""

echo "=== Fin de prueba ==="
