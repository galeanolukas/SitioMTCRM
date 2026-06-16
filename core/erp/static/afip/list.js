// List AFIP JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Verificar que la tabla existe antes de inicializar DataTables
    if ($('#data').length) {
        $('#data').DataTable({
            responsive: true,
            lengthChange: false,
            autoWidth: false,
            language: {
                url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/es.json'
            },
            columnDefs: [
                { orderable: false, targets: -1 } // Deshabilitar ordenamiento en la última columna (Opciones)
            ]
        });
    }
});
