// List Catalogo JavaScript

document.addEventListener('DOMContentLoaded', function() {
    $('#data').DataTable({
        responsive: true,
        lengthChange: false,
        autoWidth: false,
        language: {
            url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/es.json'
        }
    });
});

function syncCatalogo(button) {
    const catalogoId = button.getAttribute('data-catalogo-id');
    
    if (!confirm('¿Deseas sincronizar los productos con el catálogo?')) {
        return;
    }
    
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    fetch('/erp/catalogo/sync/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Productos sincronizados correctamente: ' + data.message);
        } else {
            alert('Error al sincronizar: ' + data.error);
        }
    })
    .catch(error => {
        alert('Error de conexión: ' + error);
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-sync"></i>';
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
