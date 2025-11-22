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
      html += '<li>' + obj + '</li>';
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
    }).done(function (data) {
      console.log(data);
      if (!data.hasOwnProperty('error')) {
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
  
  // Mostrar el modal de Bootstrap cuando se haga clic en el botón
  $('#ajaxModalConfirm').on('click', function () {
    if (typeof callback === 'function') {
      callback();
    }
    $('#ajaxModal').modal('hide');
  });
  
  // Mostrar el modal de Bootstrap
  $('#ajaxModal').modal('show');
  
  // Eliminar el contenido del modal cuando se oculte
  $('#ajaxModal').on('hidden.bs.modal', function () {
    $(this).remove(); // Elimina el modal del DOM
  });

  
}