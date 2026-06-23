/**
 * Utilidades de gestión de modales
 * Manejo de modales de confirmación y diálogos
 */

/**
 * Muestra un modal de confirmación con callback
 * @param {string} title - Título del modal
 * @param {string} content - Contenido del modal
 * @param {Function} callback - Función a ejecutar al confirmar
 */
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

/**
 * Muestra un modal con contenido personalizado
 * @param {string} title - Título del modal
 * @param {string} content - Contenido HTML del modal
 * @param {Object} options - Opciones adicionales (size, backdrop, keyboard)
 */
function show_modal(title, content, options = {}) {
  var sizeClass = options.size || '';
  var backdrop = options.backdrop !== undefined ? options.backdrop : true;
  var keyboard = options.keyboard !== undefined ? options.keyboard : true;
  
  var modal = `
    <div class="modal fade ${sizeClass}" id="customModal" tabindex="-1" aria-labelledby="customModalLabel" aria-hidden="true" data-bs-backdrop="${backdrop}" data-bs-keyboard="${keyboard}">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="customModalLabel">${title}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            ${content}
          </div>
        </div>
      </div>
    </div>
  `;
  
  $('#customModal').remove();
  $('body').append(modal);
  $('#customModal').modal('show');
  
  $('#customModal').on('hidden.bs.modal', function () {
    $(this).remove();
  });
  
  return $('#customModal');
}

/**
 * Cierra todos los modales abiertos
 */
function close_all_modals() {
  $('.modal').modal('hide');
}

/**
 * Muestra un modal de carga
 * @param {string} message - Mensaje a mostrar (opcional)
 */
function show_loading_modal(message = 'Cargando...') {
  var modal = `
    <div class="modal fade" id="loadingModal" tabindex="-1" aria-hidden="true" data-bs-backdrop="static" data-bs-keyboard="false">
      <div class="modal-dialog modal-dialog-centered modal-sm">
        <div class="modal-content">
          <div class="modal-body text-center">
            <div class="spinner-border text-primary" role="status">
              <span class="visually-hidden">Cargando...</span>
            </div>
            <p class="mt-3 mb-0">${message}</p>
          </div>
        </div>
      </div>
    </div>
  `;
  
  $('#loadingModal').remove();
  $('body').append(modal);
  $('#loadingModal').modal('show');
}

/**
 * Oculta el modal de carga
 */
function hide_loading_modal() {
  $('#loadingModal').modal('hide');
  $('#loadingModal').on('hidden.bs.modal', function () {
    $(this).remove();
  });
}
