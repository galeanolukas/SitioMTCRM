// List Catalogo JavaScript

function syncCatalogo(button) {
    const catalogoId = button.getAttribute('data-catalogo-id');
    
    if (!confirm('¿Deseas sincronizar los productos con el catálogo?')) {
        return;
    }
    
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    console.log('Iniciando sincronización de catálogo ID:', catalogoId);
    
    fetch('/erp/catalogo/sync/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
    })
    .then(response => {
        console.log('Respuesta recibida, status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Datos recibidos:', data);
        if (data.success) {
            alert('Productos sincronizados correctamente: ' + data.message);
            location.reload();
        } else {
            let errorMsg = 'Error al sincronizar: ' + data.error;
            if (data.status_code) {
                errorMsg += '\n\nCódigo de estado HTTP: ' + data.status_code;
            }
            if (data.response) {
                console.error('Respuesta del servidor:', data.response);
                errorMsg += '\n\nDetalles adicionales (ver consola para más información)';
            }
            alert(errorMsg);
        }
    })
    .catch(error => {
        console.error('Error de conexión:', error);
        alert('Error de conexión: ' + error);
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-sync"></i>';
    });
}

function syncAllCatalogo() {
    if (!confirm('¿Deseas sincronizar todo el inventario con el catálogo online?')) {
        return;
    }
    
    const button = event.target.closest('button');
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sincronizando...';
    
    console.log('Iniciando sincronización completa de inventario');
    
    fetch('/erp/catalogo/sync/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
    })
    .then(response => {
        console.log('Respuesta recibida, status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Datos recibidos:', data);
        if (data.success) {
            alert('Inventario sincronizado correctamente: ' + data.message);
            location.reload();
        } else {
            let errorMsg = 'Error al sincronizar inventario: ' + data.error;
            if (data.status_code) {
                errorMsg += '\n\nCódigo de estado HTTP: ' + data.status_code;
            }
            if (data.response) {
                console.error('Respuesta del servidor:', data.response);
                errorMsg += '\n\nDetalles adicionales (ver consola para más información)';
            }
            alert(errorMsg);
        }
    })
    .catch(error => {
        console.error('Error de conexión:', error);
        alert('Error de conexión: ' + error);
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-cloud-upload-alt"></i> Sincronizar Inventario';
    });
}

function downloadConfig(button) {
    const catalogoId = button.getAttribute('data-catalogo-id');
    
    console.log('Descargando configuración del catálogo ID:', catalogoId);
    
    // Fetch configuration data
    fetch(`/erp/catalogo/config/${catalogoId}/`, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Error al obtener configuración');
        }
        return response.json();
    })
    .then(data => {
        // Create JSON file with configuration
        const configData = {
            catalogo_id: data.id,
            empresa: data.company ? data.company.name : 'Global',
            url_catalogo: data.catalogo_url,
            api_key: data.api_key,
            activo: data.is_active,
            auto_sync: data.auto_sync,
            intervalo_sync_horas: data.sync_interval_hours,
            ultima_sync: data.last_sync,
            fecha_creacion: data.created_at,
            fecha_actualizacion: data.updated_at,
            endpoint_ventas: `${data.catalogo_url}/erp/api/ventas/receive/`,
            instruccion: 'Usar esta API Key en el header Authorization: Bearer {api_key}'
        };
        
        // Create and download file
        const blob = new Blob([JSON.stringify(configData, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `catalogo_config_${catalogoId}_${data.company ? data.company.name.replace(/\s+/g, '_') : 'global'}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        alert('Configuración descargada exitosamente');
    })
    .catch(error => {
        console.error('Error al descargar configuración:', error);
        alert('Error al descargar configuración: ' + error);
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
