$(function () {
    $('#data').DataTable({
        responsive: true,
        autoWidth: false,
        destroy: true,
        deferRender: true,
        language: {
            url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/es-AR.json'
        },
        ajax: {
            url: window.location.pathname,
            type: 'POST',
            data: {
                'action': 'searchdata'
            },
            dataSrc: ""
        },
        columns: [
            {"data": "id"},
            {"data": "name"},
            {"data": "code"},
            {"data": "cat.name"},
            {"data": "image"},
            {"data": "pvp"},         // Precio neto (sin IVA)
            {"data": "pvp_final"},   // Precio final (con IVA)
            {"data": "id"},
        ],
        columnDefs: [
            {
                targets: 2, // columna 'code'
                class: 'text-center',
                orderable: true,
                render: function (data, type, row) {
                    var hasCode = data && data.length;
                    var fallback = '';
                    try {
                        var catName = (row.cat && row.cat.name) ? row.cat.name : '';
                        var initial = catName ? catName.charAt(0).toUpperCase() : 'X';
                        fallback = initial + '-' + row.id;
                    } catch (e) {
                        fallback = 'X-' + row.id;
                    }
                    if (type === 'display') {
                        return hasCode ? data : fallback;
                    }
                    // Para ordenar/buscar usar el valor real si existe, sino el fallback generado
                    return hasCode ? data : fallback;
                }
            },
            {
                targets: 4, // imagen
                class: 'text-center',
                orderable: false,
                render: function (data, type, row) {
                    return '<img src="'+data+'" class="img-fluid d-block mx-auto" style="width: 20px; height: 20px;">';
                }
            },
            {
                targets: [5, 6], // precios s/IVA y c/IVA
                class: 'text-center',
                orderable: false,
                render: function (data, type, row) {
                    var num = parseFloat(data);
                    if (isNaN(num)) {
                        num = 0;
                    }
                    return '$' + num.toFixed(2);
                }
            },
            {
                targets: 7, // opciones
                class: 'text-center',
                orderable: false,
                render: function (data, type, row) {
                    var buttons = '<a href="/erp/product/update/' + row.id + '/" class="btn btn-warning btn-xs btn-flat"><i class="fas fa-edit"></i></a> ';
                    buttons += '<a href="/erp/product/delete/' + row.id + '/" type="button" class="btn btn-danger btn-xs btn-flat"><i class="fas fa-trash-alt"></i></a>';
                    return buttons;
                }
            },
        ],
        initComplete: function (settings, json) {

        }
    });
});