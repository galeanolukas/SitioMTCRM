#!/bin/bash

# Script para ejecutar release automático en Linux

echo
echo "========================================"
echo "  RELEASE AUTOMATICO - LINUX"
echo "========================================"
echo

# Verificar si existe el script de Python
if [ ! -f "release_manager.py" ]; then
    echo "❌ Error: No se encuentra release_manager.py"
    exit 1
fi

# Verificar si Python está disponible
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 no está disponible"
    exit 1
fi

# Función para mostrar menú
show_menu() {
    echo
    echo "📦 Tipo de release:"
    echo "  1. Patch (1.0.0 -> 1.0.1) - Corrección de errores"
    echo "  2. Minor (1.0.1 -> 1.1.0) - Nuevas características"
    echo "  3. Major (1.1.0 -> 2.0.0) - Cambios importantes"
    echo
}

# Mostrar menú
show_menu

# Leer selección del usuario
read -p "Seleccione el tipo de release (1-3): " choice

case $choice in
    1)
        release_type="patch"
        echo "✅ Seleccionado: Patch Release"
        ;;
    2)
        release_type="minor"
        echo "✅ Seleccionado: Minor Release"
        ;;
    3)
        release_type="major"
        echo "✅ Seleccionado: Major Release"
        ;;
    *)
        echo "❌ Opción inválida"
        exit 1
        ;;
esac

echo
read -p "Mensaje del commit (opcional, presione Enter para usar automático): " commit_msg

# Ejecutar el release manager
echo
echo "🚀 Iniciando proceso de release..."
echo

if [ -z "$commit_msg" ]; then
    python3 release_manager.py "$release_type"
else
    python3 release_manager.py "$release_type" "$commit_msg"
fi

# Verificar resultado
if [ $? -eq 0 ]; then
    echo
    echo "✅ Release completado exitosamente"
else
    echo
    echo "❌ El proceso de release falló"
    exit 1
fi
