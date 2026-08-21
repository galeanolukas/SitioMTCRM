var tblRemito;

function getData() {
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

    tblRemito = $('#data').DataTable({
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
                if (xhr.status === 302 || xhr.status === 403) {
                    window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
                    return;
                }
                console.error('DataTables Ajax Error:', textStatus, errorThrown);
                $('#data').DataTable().clear().draw();
                $('#data').before('<div class="alert alert-danger">Error loading data. Please refresh the page or contact support.</div>');
            }
        },
        columns: [
            {"data": "numero"},
            {
                "data": "tipo",
                "render": function (data, type, row) {
                    if (data === 'entrada') {
                        return '<span class="badge bg-success">Entrada</span>';
                    } else if (data === 'salida') {
                        return '<span class="badge bg-warning">Salida</span>';
                    }
                    return data;
                }
            },
            {"data": "supplier.name"},
            {
                "data": "fecha",
                "render": function (data, type, row) {
                    if (data) {
                        const date = new Date(data);
                        return date.toLocaleDateString('es-AR');
                    }
                    return '-';
                }
            },
            {
                "data": "estado",
                "render": function (data, type, row) {
                    if (data === 'pending') {
                        return '<span class="badge bg-warning">Pendiente</span>';
                    } else if (data === 'processed') {
                        return '<span class="badge bg-success">Procesado</span>';
                    } else if (data === 'cancelled') {
                        return '<span class="badge bg-danger">Anulado</span>';
                    }
                    return data;
                }
            },
            {"data": "created_by.username"},
            {"data": "id"},
        ],
        columnDefs: [
            {
                targets: [-1],
                class: 'text-center',
                orderable: false,
                render: function (data, type, row) {
                    var buttons = '<a href="/erp/remito/detail/' + data + '/" class="btn btn-info btn-xs btn-flat" title="Ver detalle"><i class="fas fa-eye"></i></a> ';
                    if (row.estado === 'pending') {
                        buttons += '<a href="/erp/remito/update/' + data + '/" class="btn btn-warning btn-xs btn-flat" title="Editar"><i class="fas fa-edit"></i></a> ';
                        buttons += '<a href="/erp/remito/delete/' + data + '/" class="btn btn-danger btn-xs btn-flat" title="Eliminar"><i class="fas fa-trash"></i></a>';
                    } else if (row.estado === 'processed') {
                        buttons += '<button onclick="anularRemito(' + data + ')" class="btn btn-danger btn-xs btn-flat" title="Anular"><i class="fas fa-undo"></i></button>';
                    }
                    return buttons;
                }
            },
        ],
        initComplete: function (settings, json) {
            var count = tblRemito.data().count();
            var badge = document.getElementById('totalCountBadge');
            if (badge) badge.textContent = count;
        }
    });
}

$(function () {
    getData();
});

function anularRemito(id) {
    if (confirm('¿Está seguro de anular este remito? Esto revertirá el stock.')) {
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

        fetch(`/erp/remito/anular/${id}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                tblRemito.ajax.reload();
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => alert('Error: ' + error));
    }
}
