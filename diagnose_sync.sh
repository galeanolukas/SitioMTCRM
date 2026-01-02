#!/bin/bash

echo "=== DIAGNÓSTICO RÁPIDO DE ERRORES DE SINCRONIZACIÓN ==="
echo ""

# 1. Verificar estado del servidor
echo "1. 🔍 Verificando estado del servidor..."
if pgrep -f "manage.py runserver" > /dev/null; then
    echo "   ✅ Servidor Django activo"
else
    echo "   ❌ Servidor Django no está corriendo"
    echo "   💡 Inicia el servidor: python3 manage.py runserver"
fi

# 2. Verificar conexión de red
echo ""
echo "2. 🔍 Verificando conexión de red..."
if ping -c 1 www.multilideres.com > /dev/null 2>&1; then
    echo "   ✅ Conexión a servidor remota OK"
else
    echo "   ❌ No hay conexión al servidor remoto"
    echo "   💡 Verifica tu conexión a internet"
fi

# 3. Verificar archivos de log
echo ""
echo "3. 🔍 Buscando archivos de log..."
find /media/lukas/ARCHIVOS/GitHub/SitioMTCRM -name "*.log" 2>/dev/null | while read log_file; do
    echo "   📄 $log_file"
    if [ -s "$log_file" ]; then
        echo "      Últimas 5 líneas:"
        tail -5 "$log_file" | sed 's/^/      /'
    fi
done

# 4. Verificar errores recientes en archivos temporales
echo ""
echo "4. 🔍 Buscando errores de sincronización recientes..."
if [ -d "/tmp" ]; then
    echo "   Buscando archivos temporales de sincronización..."
    find /tmp -name "*sync*" -o -name "*erp*" 2>/dev/null | head -5 | while read tmp_file; do
        echo "   📄 $tmp_file"
        if [ -f "$tmp_file" ] && [ -s "$tmp_file" ]; then
            echo "      Contenido reciente:"
            tail -3 "$tmp_file" | sed 's/^/      /'
        fi
    done
fi

# 5. Verificar espacio en disco
echo ""
echo "5. 🔍 Verificando espacio en disco..."
df -h /media/lukas/ARCHIVOS/ | tail -1 | while read line; do
    echo "   $line"
    usage=$(echo $line | awk '{print $5}' | sed 's/%//')
    if [ "$usage" -gt 90 ]; then
        echo "   ⚠️  Espacio en disco bajo (${usage}%)"
    else
        echo "   ✅ Espacio en disco OK (${usage}%)"
    fi
done

# 6. Verificar procesos relacionados
echo ""
echo "6. 🔍 Verificando procesos relacionados..."
ps aux | grep -E "(python|django|manage)" | grep -v grep | while read line; do
    echo "   🔄 $line"
done

# 7. Sugerencias basadas en hallazgos
echo ""
echo "7. 💡 RECOMENDACIONES:"
echo ""

echo "   Para diagnóstico completo:"
echo "   python3 manage.py repair_sync"
echo ""

echo "   Para reparar automáticamente:"
echo "   python3 manage.py repair_sync --repair"
echo ""

echo "   Para forzar resincronización completa:"
echo "   python3 manage.py repair_sync --force-resync"
echo ""

echo "   Para verificar productos pendientes:"
echo "   python3 manage.py check_sync"
echo ""

echo "   Para sincronizar manualmente:"
echo "   python3 manage.py sync_products_to_remote"
echo ""

echo "   Para verificar estado de sincronización:"
echo "   python3 manage.py sync_status"
echo ""

echo ""
echo "8. 🚨 ERRORES COMUNES Y SOLUCIONES:"
echo ""

echo "   ❌ 'No hay conexión a BD remota':"
echo "      → Verifica variables REMOTE_DB_* en .env"
echo "      → Verifica conexión a internet"
echo "      → Revisa firewall/proxy"
echo ""

echo "   ❌ 'Productos huérfanos':"
echo "      → Ejecuta: python3 manage.py repair_sync --repair"
echo ""

echo "   ❌ 'Diferencias de datos':"
echo "      → Ejecuta: python3 manage.py repair_sync --force-resync"
echo ""

echo "   ❌ 'Muchos productos pendientes':"
echo "      → Reinicia el servidor Django"
echo "      → Ejecuta: python3 manage.py sync_products_to_remote"
echo ""

echo ""
echo "=== FIN DE DIAGNÓSTICO ==="
