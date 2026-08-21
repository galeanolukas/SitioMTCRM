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
            dataSrc: "",
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
            { "data": "id" },
            { "data": "name" },
            { "data": "desc" },
            { "data": "desc" },
        ],
        columnDefs: [
            {
                targets: [-1],
                class: 'text-center',
                orderable: false,
                render: function (data, type, row) {
                    var buttons = '<a href="/erp/category/update/' + row.id + '/" class="btn btn-warning btn-xs btn-flat"><i class="fas fa-edit"></i></a> ';
                    buttons += '<a href="/erp/category/delete/' + row.id + '/" type="button" class="btn btn-danger btn-xs btn-flat"><i class="fas fa-trash-alt"></i></a>';
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
});