$(function () {
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

    // ---------- Búsqueda custom ----------
    // Filtra por código/barcode EXACTO (code, external_code, codigo_proveedor)
    // o por NOMBRE similar: todas las palabras del término deben aparecer.
    // Además ordena los resultados por relevancia (más parecidos primero).
    var productTable = null;
    var lastSearchTerm = '';
    var codeExactNames = {};

    function getSearchTerm() {
        var t = productTable ? productTable.search() : '';
        return (t || '').trim().toLowerCase();
    }

    // Score del nombre: menor = más parecido
    function nameScore(term, name) {
        name = String(name || '').toLowerCase();
        if (!term) return 0;
        if (name === term) return 0;                 // exacto
        if (name.indexOf(term) === 0) return 1;      // empieza con el término
        if (name.indexOf(term) > 0) return 2;        // contiene el término completo
        var words = term.split(/\s+/).filter(Boolean);
        if (words.length && words.every(function (w) { return name.indexOf(w) !== -1; })) return 3;
        return 9;                                    // no coincide
    }

    function rowMatches(term, rowData) {
        if (!term) return true;
        // Match exacto por código / código de barras / códigos alternativos
        var code = String(rowData.code || '').toLowerCase();
        var ext = String(rowData.external_code || '').toLowerCase();
        var prov = String(rowData.codigo_proveedor || '').toLowerCase();
        if (code === term || ext === term || prov === term) return true;
        // Nombre similar
        return nameScore(term, rowData.name) <= 3;
    }

    $.fn.dataTable.ext.search.push(function (settings, searchData, index, rowData, counter) {
        if (settings.nTable && settings.nTable.id !== 'data') return true;
        return rowMatches(getSearchTerm(), rowData || {});
    });

    // Ordenamiento por relevancia del nombre según el término buscado
    $.fn.dataTable.ext.type.order['relevance-asc'] = function (a, b) {
        var sa = codeExactNames[a] ? -1 : nameScore(lastSearchTerm, a);
        var sb = codeExactNames[b] ? -1 : nameScore(lastSearchTerm, b);
        if (sa !== sb) return sa - sb;
        return String(a || '').localeCompare(String(b || ''));
    };
    $.fn.dataTable.ext.type.order['relevance-desc'] = function (a, b) {
        return -1 * $.fn.dataTable.ext.type.order['relevance-asc'](a, b);
    };

    productTable = $('#data').DataTable({
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
            dataSrc: "",
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest'
            },
            error: function(xhr, textStatus, errorThrown) {
                if (textStatus === 'abort' || xhr.status === 0) {
                    // Solicitud cancelada normalmente (reload, cambio de página, etc)
                    return;
                }
                console.log('DataTables Error Details:');
                console.log('Status:', xhr.status);
                console.log('Status Text:', xhr.statusText);
                console.log('Response Text:', xhr.responseText);
                console.log('Text Status:', textStatus);
                console.log('Error Thrown:', errorThrown);

                // Check if it's an authentication issue
                if (xhr.status === 302 || xhr.status === 403) {
                    if (xhr.responseText && xhr.responseText.includes('login')) {
                        window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
                        return;
                    }
                }

                var table = $('#data').DataTable();
                if (table) {
                    table.clear().draw();
                }
                if ($('#dt-error-alert').length === 0) {
                    $('#data').before('<div id="dt-error-alert" class="alert alert-danger">Error loading data. Please refresh the page or contact support. Check console for details.</div>');
                }
            }
        },
        columns: [
            {"data": "id"},
            {"data": "name"},
            {"data": "code"},
            {"data": "cat.name"},
            {"data": "image"},
            {"data": "stock"},       // Stock disponible
            {"data": "pvp"},         // Precio neto (sin IVA)
            {"data": "pvp_final"},   // Precio final (con IVA)
            {"data": "id"},
        ],
        columnDefs: [
            {
                targets: 1, // columna 'name' - orden por relevancia al buscar
                type: 'relevance'
            },
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
                targets: 5, // stock
                class: 'text-center',
                orderable: true,
                render: function (data, type, row) {
                    var stock = parseFloat(data);
                    if (isNaN(stock)) {
                        stock = 0;
                    }
                    // Mostrar solo número entero
                    return Math.floor(stock).toString();
                }
            },
            {
                targets: [6, 7], // precios s/IVA y c/IVA
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
                targets: 8, // opciones
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
            var count = $('#data').DataTable().data().count();
            var badge = document.getElementById('totalCountBadge');
            if (badge) badge.textContent = count;
        }
    });

    // Al buscar, ordenar por relevancia del nombre; al limpiar, volver al orden por Nro
    productTable.on('search.dt', function () {
        var term = getSearchTerm();
        if (term === lastSearchTerm) return;
        lastSearchTerm = term;
        // Productos con match exacto de código van primero en el orden
        codeExactNames = {};
        if (term) {
            productTable.rows().every(function () {
                var d = this.data() || {};
                var codes = [d.code, d.external_code, d.codigo_proveedor];
                var exact = codes.some(function (c) {
                    return String(c || '').toLowerCase() === term;
                });
                if (exact) codeExactNames[String(d.name || '')] = true;
            });
        }
        productTable.order(term ? [[1, 'asc']] : [[0, 'asc']]).draw(false);
    });
});