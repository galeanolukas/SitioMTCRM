/**
 * Módulo de widgets para el dashboard
 * Manejo de widgets, tarjetas de estadísticas y componentes de UI
 */

/**
 * Inicializa un widget de estadística
 * @param {string} widgetId - ID del widget
 * @param {number} value - Valor a mostrar
 * @param {string} label - Etiqueta del widget
 * @param {string} icon - Clase del icono FontAwesome
 * @param {string} color - Color del widget (primary, success, warning, danger, info)
 */
function init_stat_widget(widgetId, value, label, icon, color = 'primary') {
  var widget = document.getElementById(widgetId);
  if (!widget) return;
  
  var colorClasses = {
    primary: 'stat-card',
    success: 'stat-card success',
    warning: 'stat-card warning',
    danger: 'stat-card danger',
    info: 'stat-card info'
  };
  
  var iconColors = {
    primary: 'text-primary',
    success: 'text-success',
    warning: 'text-warning',
    danger: 'text-danger',
    info: 'text-info'
  };
  
  widget.className = 'card ' + (colorClasses[color] || colorClasses.primary);
  
  widget.innerHTML = `
    <div class="card-body">
      <div class="d-flex align-items-center">
        <div class="mr-3">
          <i class="fas fa-${icon} ${iconColors[color] || iconColors.primary} fa-2x"></i>
        </div>
        <div>
          <div class="stat-value">${value}</div>
          <div class="stat-label">${label}</div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Actualiza el valor de un widget de estadística
 * @param {string} widgetId - ID del widget
 * @param {number} newValue - Nuevo valor
 */
function update_stat_widget(widgetId, newValue) {
  var widget = document.getElementById(widgetId);
  if (!widget) return;
  
  var valueElement = widget.querySelector('.stat-value');
  if (valueElement) {
    // Animación del valor
    var currentValue = parseFloat(valueElement.textContent.replace(/[^0-9.-]+/g, '')) || 0;
    animate_value(valueElement, currentValue, newValue, 500);
  }
}

/**
 * Anima un valor numérico
 * @param {HTMLElement} element - Elemento a animar
 * @param {number} start - Valor inicial
 * @param {number} end - Valor final
 * @param {number} duration - Duración en milisegundos
 */
function animate_value(element, start, end, duration) {
  var range = end - start;
  var startTime = null;
  
  function step(timestamp) {
    if (!startTime) startTime = timestamp;
    var progress = Math.min((timestamp - startTime) / duration, 1);
    var value = start + (range * progress);
    
    element.textContent = format_number(value);
    
    if (progress < 1) {
      window.requestAnimationFrame(step);
    }
  }
  
  window.requestAnimationFrame(step);
}

/**
 * Formatea un número con separadores de miles
 * @param {number} num - Número a formatear
 * @returns {string} Número formateado
 */
function format_number(num) {
  return num.toLocaleString('es-AR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  });
}

/**
 * Inicializa un widget de lista de actividad
 * @param {string} widgetId - ID del widget
 * @param {Array} activities - Array de actividades
 */
function init_activity_widget(widgetId, activities) {
  var widget = document.getElementById(widgetId);
  if (!widget) return;
  
  var listContainer = widget.querySelector('.activity-list');
  if (!listContainer) return;
  
  listContainer.innerHTML = '';
  
  activities.forEach(function(activity) {
    var item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `
      <div class="d-flex align-items-start">
        <div class="activity-icon">
          <i class="fas fa-${activity.icon || 'bell'}"></i>
        </div>
        <div class="ml-3">
          <div class="activity-text">${activity.text}</div>
          <div class="activity-time">${activity.time}</div>
        </div>
      </div>
    `;
    listContainer.appendChild(item);
  });
}

/**
 * Agrega una actividad al widget
 * @param {string} widgetId - ID del widget
 * @param {Object} activity - Objeto con la actividad
 */
function add_activity(widgetId, activity) {
  var widget = document.getElementById(widgetId);
  if (!widget) return;
  
  var listContainer = widget.querySelector('.activity-list');
  if (!listContainer) return;
  
  var item = document.createElement('div');
  item.className = 'activity-item';
  item.innerHTML = `
    <div class="d-flex align-items-start">
      <div class="activity-icon">
        <i class="fas fa-${activity.icon || 'bell'}"></i>
      </div>
      <div class="ml-3">
        <div class="activity-text">${activity.text}</div>
        <div class="activity-time">${activity.time}</div>
      </div>
    </div>
  `;
  
  listContainer.insertBefore(item, listContainer.firstChild);
  
  // Limitar a 10 actividades
  while (listContainer.children.length > 10) {
    listContainer.removeChild(listContainer.lastChild);
  }
}

/**
 * Inicializa un widget de progreso
 * @param {string} widgetId - ID del widget
 * @param {number} value - Valor del progreso (0-100)
 * @param {string} label - Etiqueta del widget
 * @param {string} color - Color de la barra (primary, success, warning, danger)
 */
function init_progress_widget(widgetId, value, label, color = 'primary') {
  var widget = document.getElementById(widgetId);
  if (!widget) return;
  
  var colorClasses = {
    primary: 'bg-primary',
    success: 'bg-success',
    warning: 'bg-warning',
    danger: 'bg-danger'
  };
  
  widget.innerHTML = `
    <div class="card-body">
      <div class="d-flex justify-content-between mb-2">
        <span>${label}</span>
        <span>${value}%</span>
      </div>
      <div class="progress">
        <div class="progress-bar ${colorClasses[color] || colorClasses.primary}" 
             role="progressbar" 
             style="width: ${value}%" 
             aria-valuenow="${value}" 
             aria-valuemin="0" 
             aria-valuemax="100">
        </div>
      </div>
    </div>
  `;
}

/**
 * Actualiza el progreso de un widget
 * @param {string} widgetId - ID del widget
 * @param {number} newValue - Nuevo valor de progreso (0-100)
 */
function update_progress_widget(widgetId, newValue) {
  var widget = document.getElementById(widgetId);
  if (!widget) return;
  
  var progressBar = widget.querySelector('.progress-bar');
  var percentageText = widget.querySelector('.d-flex span:last-child');
  
  if (progressBar) {
    progressBar.style.width = newValue + '%';
    progressBar.setAttribute('aria-valuenow', newValue);
  }
  
  if (percentageText) {
    percentageText.textContent = newValue + '%';
  }
}

/**
 * Inicializa un widget de gráfico pequeño (sparkline)
 * @param {string} widgetId - ID del widget
 * @param {Array} data - Datos del gráfico
 * @param {string} color - Color del gráfico
 */
function init_sparkline_widget(widgetId, data, color = 'primary') {
  var widget = document.getElementById(widgetId);
  if (!widget) return;
  
  var canvas = widget.querySelector('canvas');
  if (!canvas) return;
  
  var colors = {
    primary: 'rgba(0, 123, 255, 1)',
    success: 'rgba(40, 167, 69, 1)',
    warning: 'rgba(255, 193, 7, 1)',
    danger: 'rgba(220, 53, 69, 1)',
    info: 'rgba(23, 162, 184, 1)'
  };
  
  var backgroundColors = {
    primary: 'rgba(0, 123, 255, 0.1)',
    success: 'rgba(40, 167, 69, 0.1)',
    warning: 'rgba(255, 193, 7, 0.1)',
    danger: 'rgba(220, 53, 69, 0.1)',
    info: 'rgba(23, 162, 184, 0.1)'
  };
  
  new Chart(canvas, {
    type: 'line',
    data: {
      labels: data.map((_, i) => i),
      datasets: [{
        data: data,
        borderColor: colors[color] || colors.primary,
        backgroundColor: backgroundColors[color] || backgroundColors.primary,
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        x: {
          display: false
        },
        y: {
          display: false
        }
      }
    }
  });
}

/**
 * Refresca los datos de un widget
 * @param {string} widgetId - ID del widget
 * @param {string} url - URL para obtener los datos
 * @param {Function} callback - Función a ejecutar con los datos
 */
function refresh_widget(widgetId, url, callback) {
  var widget = document.getElementById(widgetId);
  if (!widget) return;
  
  var refreshIcon = widget.querySelector('.refresh-icon');
  if (refreshIcon) {
    refreshIcon.classList.add('fa-spin');
  }
  
  $.ajax({
    url: url,
    type: 'GET',
    dataType: 'json',
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  }).done(function(data) {
    if (typeof callback === 'function') {
      callback(data);
    }
  }).fail(function(jqXHR, textStatus, errorThrown) {
    console.error('Error refreshing widget:', textStatus, errorThrown);
  }).always(function() {
    if (refreshIcon) {
      refreshIcon.classList.remove('fa-spin');
    }
  });
}

/**
 * Configura el auto-refresh de un widget
 * @param {string} widgetId - ID del widget
 * @param {string} url - URL para obtener los datos
 * @param {Function} callback - Función a ejecutar con los datos
 * @param {number} interval - Intervalo en milisegundos
 */
function setup_widget_auto_refresh(widgetId, url, callback, interval = 60000) {
  refresh_widget(widgetId, url, callback);
  setInterval(function() {
    refresh_widget(widgetId, url, callback);
  }, interval);
}
