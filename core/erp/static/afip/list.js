// List AFIP JavaScript

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
