var tblExpense;

$(function () {
    if ($('#data').length === 0) {
        return;
    }

    // Las filas ya vienen renderizadas desde el servidor (respeta los filtros GET),
    // DataTables solo agrega paginacion, busqueda y ordenamiento en el cliente.
    tblExpense = $('#data').DataTable({
        scrollX: true,
        autoWidth: false,
        destroy: true,
        deferRender: true,
        pageLength: 25,
        lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, 'Todos']],
        language: {
            url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/es-AR.json'
        },
        order: [[0, 'desc']],
        columnDefs: [
            {
                targets: 0,
                type: 'date'
            },
            {
                targets: [-2, -1],
                orderable: false,
                searchable: false
            }
        ],
        initComplete: function () {
            var badge = document.getElementById('totalCountBadge');
            if (badge) {
                badge.textContent = tblExpense.rows({ filter: 'applied' }).count();
            }
        }
    });

    tblExpense.on('search.dt', function () {
        var badge = document.getElementById('totalCountBadge');
        if (badge) {
            badge.textContent = tblExpense.rows({ filter: 'applied' }).count();
        }
    });
});
