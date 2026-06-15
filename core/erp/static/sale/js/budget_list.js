$(document).ready(function() {
  // Función para ver detalle del presupuesto
  $('.btn-view').on('click', function() {
    const id = $(this).attr('data-id');
    
    $.ajax({
      url: `/erp/sale/api/detail/${id}/`,
      type: 'GET',
      dataType: 'json',
      success: function(data) {
        $('#detCli').text(data.cli || 'Anónimo');
        $('#detPosId').text(data.pos_id || '-');
        $('#detDate').text(data.date_joined);
        $('#detTime').text(data.time);
        $('#detPay').text(data.payment_method_display);
        $('#detNotes').text(data.budget_notes || 'Sin notas');
        
        // Llenar tabla de detalles
        const tbody = $('#tblDet tbody');
        tbody.empty();
        
        data.details.forEach(function(det) {
          const row = `
            <tr>
              <td>${det.prod_name}</td>
              <td>${det.cat_name || '-'}</td>
              <td>$${det.price.toFixed(2)}</td>
              <td>${det.cant}</td>
              <td>$${det.subtotal.toFixed(2)}</td>
            </tr>
          `;
          tbody.append(row);
        });
        
        // Llenar totales
        $('#detItems').text(data.items_count);
        $('#detSubtotal').text('$' + data.subtotal.toFixed(2));
        $('#detIva').text('$' + data.iva.toFixed(2));
        $('#detTotal').text('$' + data.total.toFixed(2));
        
        // Guardar ID del presupuesto para conversión
        $('#btnConvertBudget').attr('data-id', id);
        
        // Mostrar modal
        $('#myModalDet').modal('show');
      },
      error: function() {
        alert('Error al cargar el detalle del presupuesto');
      }
    });
  });
  
  // Función para convertir presupuesto a venta
  $('#btnConvertBudget').on('click', function() {
    const id = $(this).attr('data-id');
    
    if (!confirm('¿Está seguro de convertir este presupuesto en una venta real? Se descontará el stock de los productos.')) {
      return;
    }
    
    $.ajax({
      url: `/erp/budget/convert/${id}/`,
      type: 'POST',
      dataType: 'json',
      success: function(data) {
        if (data.success) {
          alert(data.message);
          $('#myModalDet').modal('hide');
          location.reload();
        } else {
          alert('Error: ' + data.error);
        }
      },
      error: function() {
        alert('Error al convertir el presupuesto');
      }
    });
  });
});
