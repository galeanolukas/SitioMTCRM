/**
 * Archivo principal de funciones JavaScript
 * Importa módulos JS organizados por categoría
 */

// Importar módulos de utilidades
// Estos módulos deben cargarse antes de este archivo en el template

// Módulos importados:
// - utils/currency.js: formatCurrency, parseCurrency, updateTotals
// - utils/notification.js: message_success, message_error, show_toast, clear_notifications
// - utils/modal.js: alert_action, show_modal, close_all_modals, show_loading_modal, hide_loading_modal
// - utils/ajax.js: submit_with_ajax, ajax_get, ajax_post, ajax_delete, get_csrf_token, setup_ajax_csrf

// Configuración inicial de AJAX con CSRF
$(document).ready(function() {
    if (typeof setup_ajax_csrf === 'function') {
        setup_ajax_csrf();
    }
});