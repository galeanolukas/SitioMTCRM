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
