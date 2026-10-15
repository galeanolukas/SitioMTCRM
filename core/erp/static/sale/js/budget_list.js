let currentBudget = null;
let currentBudgetId = null;
let currentPayLink = null;

function renderPayLink(pl) {
  currentPayLink = pl || null;
  $('#payLinkBox').toggleClass('d-none', !pl);
  if (!pl) return;
  $('#payLinkUrl').val(pl.url || '');
  const badge = $('#payLinkStatus');
  if (pl.status === 'paid') {
    badge.attr('class', 'badge bg-success').text('Pagado');
  } else if (pl.status === 'pending') {
    badge.attr('class', 'badge bg-warning text-dark').text('Pendiente');
  } else {
    badge.attr('class', 'badge bg-secondary').text(pl.status_display || pl.status);
  }
}

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
        // Configurar link de impresion
        $('#btnPrintBudget').attr('href', '/erp/budget/ticket/' + id + '/');

        currentBudget = data;
        currentBudgetId = id;
        renderPayLink(data.payment_link);
        $('#detPaidBadge').toggleClass('d-none', !(data.payment_link && data.payment_link.status === 'paid'));
        if (data.payment_link && data.payment_link.paid_at) {
          $('#detPaidAt').text('(' + data.payment_link.paid_at + ')');
        }

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
  
  // Función para enviar presupuesto al POS local
  $('.btn-send-local').on('click', function() {
    const id = $(this).attr('data-id');
    const btn = $(this);
    
    if (!confirm('¿Enviar este presupuesto al POS local?')) {
      return;
    }
    
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i>');
    
    $.ajax({
      url: `/erp/budget/send-local/${id}/`,
      type: 'POST',
      dataType: 'json',
      success: function(data) {
        if (data.success) {
          alert(data.message || 'Presupuesto enviado al POS local exitosamente');
          btn.removeClass('btn-outline-success').addClass('btn-success').html('<i class="fas fa-check"></i>');
        } else {
          alert('Error: ' + (data.error || 'No se pudo enviar'));
          btn.prop('disabled', false).html('<i class="fas fa-paper-plane"></i>');
        }
      },
      error: function(jq) {
        alert('Error: ' + (jq.responseJSON ? jq.responseJSON.error : 'No se pudo conectar'));
        btn.prop('disabled', false).html('<i class="fas fa-paper-plane"></i>');
      }
    });
  });

  // Generar (o reutilizar) link de pago de Mercado Pago
  $('#btnPayLink').on('click', function() {
    const id = currentBudgetId || $('#btnConvertBudget').attr('data-id');
    const btn = $(this);
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Generando...');
    $.ajax({
      url: '/erp/budget/payment-link/' + id + '/',
      type: 'POST',
      dataType: 'json',
      success: function(data) {
        if (data.success) {
          renderPayLink({id: data.link_id, url: data.url, status: data.status});
          $('#detPaidBadge').toggleClass('d-none', data.status !== 'paid');
        } else {
          alert('Error: ' + (data.error || 'No se pudo generar el link'));
        }
      },
      error: function(jq) {
        alert('Error: ' + (jq.responseJSON ? jq.responseJSON.error : 'No se pudo generar el link de pago'));
      },
      complete: function() {
        btn.prop('disabled', false).html('<i class="fas fa-link"></i> Link de pago');
      }
    });
  });

  // Copiar link al portapapeles
  $('#btnCopyPayLink').on('click', function() {
    const url = $('#payLinkUrl').val();
    if (!url) return;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url);
    } else {
      $('#payLinkUrl').select();
      document.execCommand('copy');
    }
    $(this).html('<i class="fas fa-check"></i>');
    const btn = $(this);
    setTimeout(function() { btn.html('<i class="fas fa-copy"></i>'); }, 1500);
  });

  // Verificar estado del pago manualmente
  $('#btnCheckPay').on('click', function() {
    if (!currentPayLink) return;
    const btn = $(this);
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i>');
    $.ajax({
      url: '/erp/payment-link/' + currentPayLink.id + '/refresh/',
      type: 'POST',
      dataType: 'json',
      success: function(data) {
        renderPayLink({id: currentPayLink.id, url: currentPayLink.url,
                       status: data.status, status_display: data.status});
        $('#detPaidBadge').toggleClass('d-none', data.status !== 'paid');
        if (data.status !== 'paid') alert('El pago aun no se acredito en Mercado Pago.');
      },
      error: function() { alert('No se pudo verificar el pago'); },
      complete: function() {
        btn.prop('disabled', false).html('<i class="fas fa-sync-alt"></i> Verificar');
      }
    });
  });

  // Compartir presupuesto por WhatsApp (con link de pago si existe)
  $('#btnShareBudgetWA').on('click', function() {
    if (!currentBudget) { alert('No hay datos del presupuesto'); return; }
    const d = currentBudget;
    let text = '*PRESUPUESTO*\n';
    if (window.ACTIVE_COMPANY_NAME) text += '*' + window.ACTIVE_COMPANY_NAME + '*\n';
    text += 'Cliente: ' + (d.cli || 'Consumidor Final') + '\n';
    text += 'Fecha: ' + (d.date_joined || '') + '\n\n*Detalle:*\n';
    (d.details || []).forEach(function(item) {
      text += '- ' + item.prod_name + ' x' + item.cant + ' - $' + item.subtotal.toFixed(2) + '\n';
    });
    text += '\n*Total: $' + d.total.toFixed(2) + '*\n';
    if (currentPayLink && currentPayLink.url) {
      text += '\nPagalo online con Mercado Pago:\n' + currentPayLink.url + '\n';
    }
    if (d.budget_notes) text += '\nNotas: ' + d.budget_notes + '\n';
    window.open('https://web.whatsapp.com/send?text=' + encodeURIComponent(text), 'whatsapp_web');
  });
});
