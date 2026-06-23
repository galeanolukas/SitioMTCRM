/**
 * Módulo de gráficos para el dashboard
 * Configuración y manejo de gráficos Chart.js
 */

/**
 * Inicializa un gráfico de líneas
 * @param {string} canvasId - ID del elemento canvas
 * @param {Array} labels - Etiquetas del eje X
 * @param {Array} data - Datos del gráfico
 * @param {string} label - Etiqueta del dataset
 * @param {Object} options - Opciones adicionales del gráfico
 * @returns {Chart} Instancia del gráfico
 */
function init_line_chart(canvasId, labels, data, label, options = {}) {
  var ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  
  var defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top'
      }
    },
    scales: {
      y: {
        beginAtZero: true
      }
    }
  };
  
  var chartOptions = Object.assign({}, defaultOptions, options);
  
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: label,
        data: data,
        borderColor: 'rgba(0, 123, 255, 1)',
        backgroundColor: 'rgba(0, 123, 255, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4
      }]
    },
    options: chartOptions
  });
}

/**
 * Inicializa un gráfico de barras
 * @param {string} canvasId - ID del elemento canvas
 * @param {Array} labels - Etiquetas del eje X
 * @param {Array} data - Datos del gráfico
 * @param {string} label - Etiqueta del dataset
 * @param {Object} options - Opciones adicionales del gráfico
 * @returns {Chart} Instancia del gráfico
 */
function init_bar_chart(canvasId, labels, data, label, options = {}) {
  var ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  
  var defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top'
      }
    },
    scales: {
      y: {
        beginAtZero: true
      }
    }
  };
  
  var chartOptions = Object.assign({}, defaultOptions, options);
  
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: label,
        data: data,
        backgroundColor: 'rgba(0, 123, 255, 0.7)',
        borderColor: 'rgba(0, 123, 255, 1)',
        borderWidth: 1
      }]
    },
    options: chartOptions
  });
}

/**
 * Inicializa un gráfico de dona
 * @param {string} canvasId - ID del elemento canvas
 * @param {Array} labels - Etiquetas de las secciones
 * @param {Array} data - Datos del gráfico
 * @param {Object} options - Opciones adicionales del gráfico
 * @returns {Chart} Instancia del gráfico
 */
function init_doughnut_chart(canvasId, labels, data, options = {}) {
  var ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  
  var colors = [
    'rgba(0, 123, 255, 0.7)',
    'rgba(40, 167, 69, 0.7)',
    'rgba(255, 193, 7, 0.7)',
    'rgba(220, 53, 69, 0.7)',
    'rgba(23, 162, 184, 0.7)',
    'rgba(108, 117, 125, 0.7)'
  ];
  
  var borderColors = [
    'rgba(0, 123, 255, 1)',
    'rgba(40, 167, 69, 1)',
    'rgba(255, 193, 7, 1)',
    'rgba(220, 53, 69, 1)',
    'rgba(23, 162, 184, 1)',
    'rgba(108, 117, 125, 1)'
  ];
  
  var defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'right'
      }
    }
  };
  
  var chartOptions = Object.assign({}, defaultOptions, options);
  
  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors.slice(0, data.length),
        borderColor: borderColors.slice(0, data.length),
        borderWidth: 1
      }]
    },
    options: chartOptions
  });
}

/**
 * Inicializa un gráfico de torta
 * @param {string} canvasId - ID del elemento canvas
 * @param {Array} labels - Etiquetas de las secciones
 * @param {Array} data - Datos del gráfico
 * @param {Object} options - Opciones adicionales del gráfico
 * @returns {Chart} Instancia del gráfico
 */
function init_pie_chart(canvasId, labels, data, options = {}) {
  var ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  
  var colors = [
    'rgba(0, 123, 255, 0.7)',
    'rgba(40, 167, 69, 0.7)',
    'rgba(255, 193, 7, 0.7)',
    'rgba(220, 53, 69, 0.7)',
    'rgba(23, 162, 184, 0.7)',
    'rgba(108, 117, 125, 0.7)'
  ];
  
  var borderColors = [
    'rgba(0, 123, 255, 1)',
    'rgba(40, 167, 69, 1)',
    'rgba(255, 193, 7, 1)',
    'rgba(220, 53, 69, 1)',
    'rgba(23, 162, 184, 1)',
    'rgba(108, 117, 125, 1)'
  ];
  
  var defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'right'
      }
    }
  };
  
  var chartOptions = Object.assign({}, defaultOptions, options);
  
  return new Chart(ctx, {
    type: 'pie',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors.slice(0, data.length),
        borderColor: borderColors.slice(0, data.length),
        borderWidth: 1
      }]
    },
    options: chartOptions
  });
}

/**
 * Actualiza los datos de un gráfico existente
 * @param {Chart} chart - Instancia del gráfico
 * @param {Array} newData - Nuevos datos
 */
function update_chart_data(chart, newData) {
  if (!chart) return;
  chart.data.datasets[0].data = newData;
  chart.update();
}

/**
 * Destruye un gráfico existente
 * @param {Chart} chart - Instancia del gráfico
 */
function destroy_chart(chart) {
  if (chart) {
    chart.destroy();
  }
}

/**
 * Obtiene datos de gráfico desde una URL
 * @param {string} url - URL de la API
 * @param {Function} callback - Función a ejecutar con los datos
 */
function fetch_chart_data(url, callback) {
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
    console.error('Error fetching chart data:', textStatus, errorThrown);
  });
}
