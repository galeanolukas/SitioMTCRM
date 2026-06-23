/**
 * Utilidades de notificación y mensajes
 * Manejo de alertas de éxito y error
 */

/**
 * Muestra un mensaje de éxito
 * @param {string} message - Mensaje a mostrar
 */
function message_success(message) {
    var html = '';
    html = '<div id="success-block" class="alert alert-success alert-dismissible">';
    html += '<button type="button" class="close" data-bs-dismiss="alert" aria-label="Close">';
    html += '<span aria-hidden="true">&times;</span>';
    html += '</button>';
    html += '<h5><i class="fas fa-check me-2"></i> Operación exitosa</h5>';
    html += '<p>' + message + '</p>';
    html += '</div>';

    var successContainer = document.getElementById('success-block');
    if (successContainer) {
        successContainer.innerHTML = html;
    }
}

/**
 * Muestra un mensaje de error
 * @param {Object|string} obj - Objeto con errores o string con mensaje de error
 */
function message_error(obj) {
    var html = '';
    if (typeof (obj) === 'object') {
        html = '<div id="error-block" class="alert alert-danger alert-dismissible">';
        html += '<button type="button" class="close" data-bs-dismiss="alert" aria-label="Close">';
        html += '<span aria-hidden="true">&times;</span>';
        html += '</button>';
        html += '<h5><i class="fas fa-ban me-2"></i> Ha ocurrido un error al querer guardar el registro</h5>';
        html += '<ul>';
        
        $.each(obj, function (key, value) {
            html += '<li>' + value + '</li>';
        });
        
        html += '</ul>';
        html += '</div>';
    } else {
      html = '<div id="error-block" class="alert alert-danger alert-dismissible">';
      html += '<button type="button" class="close" data-bs-dismiss="alert" aria-label="Close">';
      html += '<span aria-hidden="true">&times;</span>';
      html += '</button>';
      html += '<h5><i class="fas fa-ban me-2"></i> Ha ocurrido un error al querer guardar el registro</h5>';
      html += '<p>' + obj + '</p>';
      html += '</div>';
    }

    var errorContainer = document.getElementById('error-block');
    if (errorContainer) {
        errorContainer.innerHTML = html;
    }
}

/**
 * Muestra un toast de notificación
 * @param {string} message - Mensaje a mostrar
 * @param {string} type - Tipo de notificación (success, error, warning, info)
 * @param {number} duration - Duración en milisegundos (default: 3000)
 */
function show_toast(message, type = 'info', duration = 3000) {
    var icon = 'info-circle';
    var bgClass = 'toast-info';
    
    switch(type) {
        case 'success':
            icon = 'check-circle';
            bgClass = 'toast-success';
            break;
        case 'error':
            icon = 'exclamation-circle';
            bgClass = 'toast-error';
            break;
        case 'warning':
            icon = 'exclamation-triangle';
            bgClass = 'toast-warning';
            break;
        default:
            icon = 'info-circle';
            bgClass = 'toast-info';
    }
    
    var toastHtml = `
        <div class="toast ${bgClass}" role="alert" aria-live="assertive" aria-atomic="true" data-delay="${duration}">
            <div class="toast-header">
                <i class="fas fa-${icon} me-2"></i>
                <strong class="me-auto">Notificación</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    // Crear contenedor de toasts si no existe
    var toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 right-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Agregar toast al contenedor
    var toastElement = document.createElement('div');
    toastElement.innerHTML = toastHtml;
    toastContainer.appendChild(toastElement.firstElementChild);
    
    // Mostrar toast
    var toast = new bootstrap.Toast(toastContainer.lastElementChild);
    toast.show();
    
    // Eliminar toast después de ocultarse
    toastContainer.lastElementChild.addEventListener('hidden.bs.toast', function () {
        this.remove();
    });
}

/**
 * Limpia todos los mensajes de notificación
 */
function clear_notifications() {
    var successBlock = document.getElementById('success-block');
    var errorBlock = document.getElementById('error-block');
    
    if (successBlock) {
        successBlock.innerHTML = '';
    }
    
    if (errorBlock) {
        errorBlock.innerHTML = '';
    }
}
