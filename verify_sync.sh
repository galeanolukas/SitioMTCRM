#!/bin/bash

echo "=== Verificación de sincronización de productos ==="
echo ""

# 1. Verificar si el servidor Django está corriendo
echo "1. Verificando si el servidor Django está activo..."
if pgrep -f "manage.py runserver" > /dev/null; then
    echo "✅ Servidor Django detectado"
else
    echo "❌ Servidor Django no detectado"
    echo "   Asegúrate de que el servidor esté corriendo con: python3 manage.py runserver"
fi

echo ""

# 2. Verificar variables de entorno
echo "2. Verificando variables de entorno de BD remota..."
if [ -f ".env" ]; then
    echo "✅ Archivo .env encontrado"
    
    # Verificar variables críticas
    if grep -q "REMOTE_DB_HOST" .env && grep -q "REMOTE_DB_NAME" .env; then
        echo "✅ Variables REMOTE_DB configuradas"
        
        # Mostrar valores (ocultando contraseña)
        echo "   Host: $(grep REMOTE_DB_HOST .env | cut -d= -f2)"
        echo "   DB: $(grep REMOTE_DB_NAME .env | cut -d= -f2)"
        echo "   User: $(grep REMOTE_DB_USER .env | cut -d= -f2)"
        echo "   Port: $(grep REMOTE_DB_PORT .env | cut -d= -f2)"
    else
        echo "❌ Faltan variables REMOTE_DB en .env"
    fi
else
    echo "❌ Archivo .env no encontrado"
fi

echo ""

# 3. Verificar configuración de entorno
echo "3. Verificando configuración de entorno..."
if grep -q "ENVIRONMENT=development" .env 2>/dev/null || [ -z "$(grep ENVIRONMENT .env 2>/dev/null)" ]; then
    echo "✅ ENVIRONMENT=development (correcto para POS)"
else
    ENV_VAL=$(grep ENVIRONMENT .env | cut -d= -f2)
    echo "⚠️  ENVIRONMENT=$ENV_VAL (debería ser 'development' para POS)"
fi

echo ""

# 4. Verificar archivos de sincronización
echo "4. Verificando archivos de sincronización..."
SYNC_FILES=(
    "core/erp/management/commands/sync_products_to_remote.py"
    "core/erp/sync_utils.py"
    "core/erp/apps.py"
)

for file in "${SYNC_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file no encontrado"
    fi
done

echo ""

# 5. Sugerencias
echo "5. Recomendaciones:"
echo "   • Si el servidor Django no está corriendo, inícialo:"
echo "     python3 manage.py runserver"
echo ""
echo "   • Para verificar sincronización manualmente:"
echo "     python3 manage.py check_sync"
echo ""
echo "   • Para forzar sincronización de productos:"
echo "     python3 manage.py sync_products_to_remote"
echo ""
echo "   • Para probar si los cambios se marcan:"
echo "     1. Cambia el stock de un producto en la interfaz"
echo "     2. Ejecuta: python3 manage.py check_sync"
echo "     3. Debería mostrar el producto como pendiente"

echo ""
echo "=== Fin de verificación ==="
