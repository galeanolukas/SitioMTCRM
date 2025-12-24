var tblSale;

function format(d) {
    var html = '<table class="table table-sm">';
    html += '<thead>';
    html += '<tr><th scope="col">Producto</th>';
    html += '<th scope="col">Categoría</th>';
    html += '<th scope="col">PVP</th>';
    html += '<th scope="col">Cantidad</th>';
    html += '<th scope="col">Subtotal</th>';
    html += '</thead>';
    html += '<tbody>';
    $.each(d.det, function (key, value) {
        html += '<tr>';
        html += '<td>' + value.prod.name + '</td>';
        html += '<td>' + value.prod.cat.name + '</td>';
        html += '<td>' + value.price + '</td>';
        html += '<td>' + value.cant + '</td>';
        html += '<td>' + value.subtotal + '</td>';
        html += '</tr>';
    });
    html += '</tbody>';
    return html;
}

$(function () {
    console.log('Inicializando DataTable de ventas...');
    
    // Function to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Verificar que el elemento #data existe
    if ($('#data').length === 0) {
        console.error('El elemento #data no existe en el DOM');
        return;
    }
    
    console.log('Elemento #data encontrado, inicializando DataTable...');
    
    tblSale = $('#data').DataTable({
        //responsive: true,
        scrollX: true,
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
            dataSrc: function (json) {
                // Log the raw response data
                console.log('Raw API response:', json);
                if (json && json.length > 0) {
                    console.log('First item date_joined:', json[0].date_joined, 'Type:', typeof json[0].date_joined);
                }
                return json;
            },
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest'
            },
            error: function(xhr, textStatus, errorThrown) {
                // Check if it's an authentication issue
                if (xhr.status === 302 || xhr.status === 403) {
                    // Redirect to login page
                    window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
                    return;
                }
                // For other errors, show the DataTables error
                console.error('DataTables Ajax Error:', textStatus, errorThrown);
                $('#data').DataTable().clear().draw();
                $('#data').before('<div class="alert alert-danger">Error loading data. Please refresh the page or contact support.</div>');
            }
        },
        columns: [
            {
                class: 'dt-control',
                orderable: false,
                data: null,
                defaultContent: ''
            },
            { "data": "id" },
            { "data": "cli" },
            { 
                "data": "date_joined_display",
                "render": function(data, type, row) {
                    if (type === 'display' || type === 'filter') {
                        console.log('Rendering date_joined_display:', data, 'for row:', row.id);
                        return data || '-';
                    }
                    return data;
                }
            },
            { "data": "subtotal" },
            { "data": "iva" },
            { "data": "total" },
            { "data": "id" },
        ],
        columnDefs: [
            {
                targets: [1],
                class: 'text-center',
                render: function (data, type, row) {
                    return row.invoice_number ? row.invoice_number : data;
                }
            },
            {
                targets: [-2, -3, -4],
                class: 'text-center',
                render: function (data, type, row) {
                    return '$' + parseFloat(data).toFixed(2);
                }
            },
            {
                targets: [-1],
                class: 'text-center',
                orderable: false,
                render: function (data, type, row) {
                    var buttons = '<a href="/erp/sale/delete/' + row.id + '/" type="button" class="btn btn-danger btn-xs btn-flat"><i class="fas fa-trash-alt"></i></a> ';
                    buttons += '<a href="/erp/sale/update/' + row.id + '/" class="btn btn-warning btn-xs btn-flat"><i class="fas fa-edit" style="color: #fafafa;"></i></a> ';
                    if (row.is_invoiced) {
                        var title = row.invoice_number ? ('PDF ' + row.invoice_number) : 'PDF';
                        buttons += '<a href="/erp/invoice/pdf/' + row.id + '/" target="_blank" class="btn btn-primary btn-xs btn-flat" title="' + title + '"><i class="fas fa-file-pdf"></i></a> ';
                    } else {
                        buttons += '<a rel="invoice" class="btn btn-primary btn-xs btn-flat" title="Facturar"><i class="fas fa-file-invoice-dollar"></i></a> ';
                    }
                    buttons += '<a rel="details" class="btn btn-success btn-xs btn-flat"><i class="fas fa-search"></i></a>';
                    return buttons;
                }
            },
            {
                targets: [-8],
                orderable: false,
            },
        ],
        initComplete: function (settings, json) {

        }
    })
        .on('click', 'tbody td.dt-control', function () {
            let tr = event.target.closest('tr');
            let row = tblSale.row(tr);
            let idx = detailRows.indexOf(tr.id);

            if (row.child.isShown()) {
                tr.classList.remove('details');
                row.child.hide();
                detailRows.splice(idx, 1);
            }
            else {
                tr.classList.add('details');
                row.child(format(row.data())).show();
                if (idx === -1) {
                    detailRows.push(tr.id);
                }
            }
        })


    const detailRows = [];

    $('#data tbody')
        .on('click', 'a[rel="invoice"]', function () {
            var tr = tblSale.cell($(this).closest('td, li')).index();
            var data = tblSale.row(tr.row).data();
            $.ajax({
                url: window.location.pathname,
                type: 'POST',
                data: {
                    'action': 'invoice',
                    'id': data.id
                },
                dataType: 'json'
            }).done(function (resp) {
                tblSale.ajax.reload(null, false);
                window.open('/erp/invoice/pdf/' + data.id + '/', '_blank');
            }).fail(function (jqXHR, textStatus, errorThrown) {
                alert('Error al facturar: ' + (jqXHR.responseJSON ? jqXHR.responseJSON.error : textStatus));
            });
        })
        .on('click', 'a[rel="details"]', function () {
            var tr = tblSale.cell($(this).closest('td, li')).index();
            var data = tblSale.row(tr.row).data();

            // Completar cabecera de información de la venta
            try {
                $('#detCli').text(data.cli || 'Anónimo');
                // Format the date for display in the modal
                if (data.date_joined_display) {
                    $('#detDate').text(data.date_joined_display);
                } else {
                    $('#detDate').text(data.date_joined || '-');
                }
                $('#detTime').text('');
                var invoiceLabel = data.invoice_number ? (data.invoice_number) : ('POS ' + (data.invoice_pos || '-') + ' · Tipo ' + (data.invoice_type || '-'));
                $('#detInvoice').text(invoiceLabel);
                $('#detPay').text(data.payment_method_display || data.payment_method || '-');
                // Resumen
                var items = Array.isArray(data.det) ? data.det.length : 0;
                $('#detItems').text(items);
                $('#detSubtotal').text('$' + parseFloat(data.subtotal || 0).toFixed(2));
                $('#detIva').text('$' + parseFloat(data.iva || 0).toFixed(2));
                $('#detTotal').text('$' + parseFloat(data.total || 0).toFixed(2));
            } catch (e) {
                console.warn('No se pudo completar cabecera del detalle:', e);
            }

            // Tabla de productos de la venta
            $('#tblDet').DataTable({
                //responsive: true,
                scrollX: true,
                destroy: true,
                deferRender: true,
                language: {
                    url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/es-AR.json'
                },
                ajax: {
                    url: window.location.pathname,
                    type: 'POST',
                    data: {
                        'action': 'search_details_prod',
                        'id': data.id
                    },
                    dataSrc: ""
                },
                columns: [
                    { "data": "prod.name" },
                    { "data": "prod.cat.name" },
                    { "data": "price" },
                    { "data": "cant" },
                    { "data": "subtotal" },
                ],
                columnDefs: [
                    {
                        targets: [-1, -3],
                        class: 'text-center',
                        render: function (data, type, row) {
                            return '$' + parseFloat(data).toFixed(2);
                        }
                    },
                    {
                        targets: [-2],
                        class: 'text-center',
                        render: function (data, type, row) {
                            return data;
                        }
                    },
                ],
                initComplete: function (settings, json) {
                }
            })

            $('#myModalDet').modal('show');

        })


});