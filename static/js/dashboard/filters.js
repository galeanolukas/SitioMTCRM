/**
 * Módulo de filtros para el dashboard
 * Manejo de filtros de fecha, búsqueda y selección
 */

/**
 * Inicializa un filtro de rango de fechas
 * @param {string} startDateId - ID del input de fecha inicio
 * @param {string} endDateId - ID del input de fecha fin
 * @param {Function} callback - Función a ejecutar al cambiar las fechas
 */
function init_date_range_filter(startDateId, endDateId, callback) {
  var startDate = document.getElementById(startDateId);
  var endDate = document.getElementById(endDateId);
  
  if (!startDate || !endDate) return;
  
  // Configurar datepicker si está disponible
  if ($.fn.datepicker) {
    $(startDate).datepicker({
      format: 'dd/mm/yyyy',
      autoclose: true,
      todayHighlight: true
    });
    
    $(endDate).datepicker({
      format: 'dd/mm/yyyy',
      autoclose: true,
      todayHighlight: true
    });
  }
  
  // Evento de cambio
  $(startDate).on('changeDate', function() {
    if (typeof callback === 'function') {
      callback(startDate.value, endDate.value);
    }
  });
  
  $(endDate).on('changeDate', function() {
    if (typeof callback === 'function') {
      callback(startDate.value, endDate.value);
    }
  });
}

/**
 * Inicializa un filtro de búsqueda
 * @param {string} searchId - ID del input de búsqueda
 * @param {Function} callback - Función a ejecutar al buscar
 * @param {number} delay - Retraso en milisegundos (debounce)
 */
function init_search_filter(searchId, callback, delay = 500) {
  var searchInput = document.getElementById(searchId);
  if (!searchInput) return;
  
  var timeout;
  
  $(searchInput).on('keyup', function() {
    clearTimeout(timeout);
    timeout = setTimeout(function() {
      if (typeof callback === 'function') {
        callback(searchInput.value);
      }
    }, delay);
  });
}

/**
 * Inicializa un filtro de selección múltiple
 * @param {string} selectId - ID del select
 * @param {Function} callback - Función a ejecutar al cambiar la selección
 */
function init_multi_select_filter(selectId, callback) {
  var select = document.getElementById(selectId);
  if (!select) return;
  
  // Configurar select2 si está disponible
  if ($.fn.select2) {
    $(select).select2({
      placeholder: 'Seleccionar opciones',
      allowClear: true
    });
  }
  
  $(select).on('change', function() {
    if (typeof callback === 'function') {
      var selectedValues = Array.from(select.selectedOptions).map(option => option.value);
      callback(selectedValues);
    }
  });
}

/**
 * Inicializa un filtro de radio buttons
 * @param {string} name - Nombre del grupo de radio buttons
 * @param {Function} callback - Función a ejecutar al cambiar la selección
 */
function init_radio_filter(name, callback) {
  var radios = document.querySelectorAll('input[name="' + name + '"]');
  if (radios.length === 0) return;
  
  radios.forEach(function(radio) {
    $(radio).on('change', function() {
      if (this.checked && typeof callback === 'function') {
        callback(this.value);
      }
    });
  });
}

/**
 * Inicializa un filtro de checkboxes
 * @param {string} name - Nombre del grupo de checkboxes
 * @param {Function} callback - Función a ejecutar al cambiar la selección
 */
function init_checkbox_filter(name, callback) {
  var checkboxes = document.querySelectorAll('input[name="' + name + '"]');
  if (checkboxes.length === 0) return;
  
  checkboxes.forEach(function(checkbox) {
    $(checkbox).on('change', function() {
      if (typeof callback === 'function') {
        var checkedValues = Array.from(document.querySelectorAll('input[name="' + name + '"]:checked'))
          .map(cb => cb.value);
        callback(checkedValues);
      }
    });
  });
}

/**
 * Aplica filtros y recarga datos
 * @param {Object} filters - Objeto con los filtros activos
 * @param {string} url - URL para obtener datos filtrados
 * @param {Function} callback - Función a ejecutar con los datos
 */
function apply_filters(filters, url, callback) {
  show_loading_modal('Filtrando datos...');
  
  $.ajax({
    url: url,
    type: 'GET',
    data: filters,
    dataType: 'json',
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  }).done(function(data) {
    if (typeof callback === 'function') {
      callback(data);
    }
  }).fail(function(jqXHR, textStatus, errorThrown) {
    console.error('Error applying filters:', textStatus, errorThrown);
    message_error('Error al aplicar filtros');
  }).always(function() {
    hide_loading_modal();
  });
}

/**
 * Limpia todos los filtros
 * @param {Array} filterIds - Array de IDs de inputs a limpiar
 */
function clear_filters(filterIds) {
  filterIds.forEach(function(id) {
    var element = document.getElementById(id);
    if (element) {
      if (element.type === 'checkbox' || element.type === 'radio') {
        element.checked = false;
      } else if (element.tagName === 'SELECT') {
        element.selectedIndex = 0;
        if ($.fn.select2) {
          $(element).select2('val', '');
        }
      } else {
        element.value = '';
      }
    }
  });
}

/**
 * Obtiene los valores de los filtros activos
 * @param {Array} filterIds - Array de IDs de inputs
 * @returns {Object} Objeto con los valores de los filtros
 */
function get_filter_values(filterIds) {
  var filters = {};
  
  filterIds.forEach(function(id) {
    var element = document.getElementById(id);
    if (element) {
      if (element.type === 'checkbox' || element.type === 'radio') {
        if (element.checked) {
          filters[id] = element.value;
        }
      } else if (element.tagName === 'SELECT' && element.multiple) {
        filters[id] = Array.from(element.selectedOptions).map(option => option.value);
      } else {
        filters[id] = element.value;
      }
    }
  });
  
  return filters;
}

/**
 * Guarda filtros en localStorage
 * @param {string} key - Clave para almacenar los filtros
 * @param {Object} filters - Objeto con los filtros
 */
function save_filters(key, filters) {
  try {
    localStorage.setItem(key, JSON.stringify(filters));
  } catch (e) {
    console.error('Error saving filters:', e);
  }
}

/**
 * Carga filtros desde localStorage
 * @param {string} key - Clave de los filtros
 * @returns {Object} Objeto con los filtros guardados
 */
function load_filters(key) {
  try {
    var filters = localStorage.getItem(key);
    return filters ? JSON.parse(filters) : {};
  } catch (e) {
    console.error('Error loading filters:', e);
    return {};
  }
}
