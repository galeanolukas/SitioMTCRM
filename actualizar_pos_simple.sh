#!/bin/bash
# Script de actualización simplificado para Linux
# Llama al script Python unificado

cd "$(dirname "$0")"

echo "============================================"
echo "Actualizador POS - SitioMTCRM (Linux)"
echo "============================================"
echo

# Verificar si Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 no está instalado."
    echo "Por favor, instale Python3 con:"
    echo "  sudo apt install python3 python3-pip python3-venv  # Debian/Ubuntu"
    echo "  sudo dnf install python3 python3-pip  # Fedora/RHEL"
    exit 1
fi

# Hacer el script ejecutable
chmod +x update_system.py

# Ejecutar el script de actualización
python3 update_system.py "$@"
