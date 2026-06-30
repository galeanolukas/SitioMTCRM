// formatCurrency ahora se importa desde utils/currency.js

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
        var modalEl = document.getElementById('ajaxModal');
        var modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
        return;
      }
      message_error(data.error);
      var modalEl = document.getElementById('ajaxModal');
      var modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }).fail(function (jqXHR, textStatus, errorThrown) {
      alert(textStatus + ': ' + errorThrown);
      var modalEl = document.getElementById('ajaxModal');
      var modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }).always(function (data) {
      
    });
  });
  
  // Mostrar el modal de Bootstrap 5
  var modalEl = document.getElementById('ajaxModal');
  var modal = new bootstrap.Modal(modalEl);
  modal.show();

  modalEl.addEventListener('hidden.bs.modal', function () {
    $('#ajaxModalConfirm').off('click');
    modalEl.remove(); // Limpiar el DOM cuando se oculta
  });
  
}
function alert_action(title, content, callback) {
  // Modal de Bootstrap
  var modal = `
    <div class="modal fade" id="ajaxModal" tabindex="-1" aria-labelledby="ajaxModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="ajaxModalLabel">${title}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <p>${content}</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
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
  
  // Mostrar el modal de Bootstrap 5 cuando se haga clic en el botón
  $('#ajaxModalConfirm').on('click', function () {
    if (typeof callback === 'function') {
      callback();
    }
    var modalEl = document.getElementById('ajaxModal');
    var modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
  });
  
  // Mostrar el modal de Bootstrap 5
  var modalEl = document.getElementById('ajaxModal');
  var modal = new bootstrap.Modal(modalEl);
  modal.show();
  
  // Eliminar el contenido del modal cuando se oculte
  modalEl.addEventListener('hidden.bs.modal', function () {
    modalEl.remove(); // Elimina el modal del DOM
  });

  
}