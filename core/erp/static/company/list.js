var tblCompany;
var modal_title;

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

  tblCompany = $('#data').DataTable({
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
      data: { 'action': 'searchdata' },
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
      { data: "id" },
      { data: "name" },
      { data: "cuit" },
      { data: "address" },
      { data: "phone" },
      { data: "email" },
      { data: "id" }
    ],
    columnDefs: [
      {
        targets: [-1],
        class: 'text-center',
        orderable: false,
        render: function (data, type, row) {
          let btns = '<a href="#" rel="edit" class="btn btn-warning btn-xs btn-flat me-1"><i class="fas fa-edit"></i></a>';
          btns += '<a href="/erp/afip/dashboard/?company_id=' + data + '" class="btn btn-info btn-xs btn-flat me-1" title="Configurar AFIP"><i class="fas fa-file-invoice-dollar"></i></a>';
          btns += '<a href="#" rel="delete" class="btn btn-danger btn-xs btn-flat"><i class="fas fa-trash-alt"></i></a>';
          return btns;
        }
      }
    ]
  });
}

$(function () {
  modal_title = $('.modal-title');
  getData();

  $('.btnAdd').on('click', function () {
    $('input[name="action"]').val('add');
    modal_title.find('span').html('Nueva empresa');
    modal_title.find('i').removeClass().addClass('fas fa-plus');
    $('form')[0].reset();
    $('#id').val('0');
    $('#myModalCompany').modal('show');
  });

  $('#data tbody')
    .on('click', 'a[rel="edit"]', function () {
      modal_title.find('span').html('Editar empresa');
      modal_title.find('i').removeClass().addClass('fas fa-edit');
      var tr = tblCompany.cell($(this).closest('td, li')).index();
      var data = tblCompany.row(tr.row).data();

      $('input[name="action"]').val('edit');
      $('input[name="id"]').val(data.id);

      $('input[name="name"]').val(data.name || '');
      $('input[name="cuit"]').val(data.cuit || '');
      $('input[name="address"]').val(data.address || '');
      $('input[name="pos"]').val(data.pos || '');
      $('input[name="phone"]').val(data.phone || '');
      $('input[name="email"]').val(data.email || '');
      $('input[name="start"]').val(data.start || '');

      $('#myModalCompany').modal('show');
    })
    .on('click', 'a[rel="delete"]', function () {
      var tr = tblCompany.cell($(this).closest('td, li')).index();
      var data = tblCompany.row(tr.row).data();
      var parameters = new FormData();
      parameters.append('action', 'delete');
      parameters.append('id', data.id);
      submit_with_ajax(window.location.pathname, 'Notificación', '¿Eliminar esta empresa?', parameters, function () {
        tblCompany.ajax.reload();
      });
    });

  $('form').on('submit', function (e) {
    e.preventDefault();
    var parameters = new FormData(this);
    submit_with_ajax(window.location.pathname, 'Notificación', '¿Confirmar acción?', parameters, function () {
      $('#myModalCompany').modal('hide');
      tblCompany.ajax.reload();
    });
  });
});