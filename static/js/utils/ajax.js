/**
 * Utilidades de AJAX
 * Manejo de peticiones AJAX con modales de confirmación
 */

/**
 * Envía una petición AJAX con modal de confirmación
 * @param {string} url - URL de la petición
 * @param {string} title - Título del modal
 * @param {string} content - Contenido del modal
 * @param {FormData|Object} parameters - Parámetros a enviar
 * @param {Function} callback - Función a ejecutar al completar exitosamente
 */
function submit_with_ajax(url, title, content, parameters, callback) {
  // Modal de Bootstrap
  var modal = `
    <div class="modal fade" id="ajaxModal" tabindex="-1" aria-labelledby="ajaxModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="ajaxModalLabel">${title}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" data-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <p>${content}</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" data-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-primary" id="ajaxModalConfirm">Confirmar</button>
          </div>
        </div>
      </div>
    </div>
  `;
  
  // Si existe un modal previo, eliminarlo para evitar duplicados
  $('#ajaxModal').remove();
  // Agregar el modal al cuerpo del documento
  $('body').append(modal);
  
  // Acción de confirmar: ejecutar AJAX y cerrar modal al finalizar correctamente
  $('#ajaxModalConfirm').on('click', function () {
    $.ajax({
      url: url,
      type: 'POST',
      data: parameters,
      dataType: 'json',
      processData: false,
      contentType: false,
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    }).done(function (data) {
      console.log(data);
      if (!data.hasOwnProperty('error')) {
        // Mostrar mensaje de éxito
        message_success('El registro se ha guardado correctamente.');
        
        if (typeof callback === 'function') {
          callback(data);
        }
        $('#ajaxModal').modal('hide');
        return;
      }
      message_error(data.error);
      $('#ajaxModal').modal('hide');
    }).fail(function (jqXHR, textStatus, errorThrown) {
      alert(textStatus + ': ' + errorThrown);
      $('#ajaxModal').modal('hide');
    }).always(function (data) {
      
    });
  });
  
  // Mostrar el modal de Bootstrap
  $('#ajaxModal').modal('show');

  $('#ajaxModal').on('hidden.bs.modal', function () {
    $('#ajaxModalConfirm').off('click');
    $(this).remove(); // Limpiar el DOM cuando se oculta
  });
}

/**
 * Realiza una petición AJAX GET
 * @param {string} url - URL de la petición
 * @param {Object} data - Datos a enviar
 * @param {Function} successCallback - Función a ejecutar al completar exitosamente
 * @param {Function} errorCallback - Función a ejecutar al fallar
 */
function ajax_get(url, data = {}, successCallback = null, errorCallback = null) {
  $.ajax({
    url: url,
    type: 'GET',
    data: data,
    dataType: 'json',
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  }).done(function (data) {
    if (typeof successCallback === 'function') {
      successCallback(data);
    }
  }).fail(function (jqXHR, textStatus, errorThrown) {
    if (typeof errorCallback === 'function') {
      errorCallback(jqXHR, textStatus, errorThrown);
    } else {
      console.error('AJAX Error:', textStatus, errorThrown);
    }
  });
}

/**
 * Realiza una petición AJAX POST
 * @param {string} url - URL de la petición
 * @param {FormData|Object} data - Datos a enviar
 * @param {Function} successCallback - Función a ejecutar al completar exitosamente
 * @param {Function} errorCallback - Función a ejecutar al fallar
 */
function ajax_post(url, data, successCallback = null, errorCallback = null) {
  $.ajax({
    url: url,
    type: 'POST',
    data: data,
    dataType: 'json',
    processData: false,
    contentType: false,
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  }).done(function (data) {
    if (typeof successCallback === 'function') {
      successCallback(data);
    }
  }).fail(function (jqXHR, textStatus, errorThrown) {
    if (typeof errorCallback === 'function') {
      errorCallback(jqXHR, textStatus, errorThrown);
    } else {
      console.error('AJAX Error:', textStatus, errorThrown);
    }
  });
}

/**
 * Realiza una petición AJAX DELETE
 * @param {string} url - URL de la petición
 * @param {Object} data - Datos a enviar
 * @param {Function} successCallback - Función a ejecutar al completar exitosamente
 * @param {Function} errorCallback - Función a ejecutar al fallar
 */
function ajax_delete(url, data = {}, successCallback = null, errorCallback = null) {
  $.ajax({
    url: url,
    type: 'DELETE',
    data: data,
    dataType: 'json',
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  }).done(function (data) {
    if (typeof successCallback === 'function') {
      successCallback(data);
    }
  }).fail(function (jqXHR, textStatus, errorThrown) {
    if (typeof errorCallback === 'function') {
      errorCallback(jqXHR, textStatus, errorThrown);
    } else {
      console.error('AJAX Error:', textStatus, errorThrown);
    }
  });
}

/**
 * Obtiene el token CSRF para peticiones AJAX
 * @returns {string} Token CSRF
 */
function get_csrf_token() {
  var cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
      var cookie = cookies[i].trim();
      if (cookie.substring(0, 'csrftoken'.length + 1) === ('csrftoken=')) {
        cookieValue = decodeURIComponent(cookie.substring('csrftoken'.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Configura AJAX para incluir token CSRF en todas las peticiones
 */
function setup_ajax_csrf() {
  $.ajaxSetup({
    beforeSend: function(xhr, settings) {
      if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
        xhr.setRequestHeader('X-CSRFToken', get_csrf_token());
      }
    }
  });
}
