(function () {
  const $input = $('#barcodeInput');
  const $tbody = $('#posItems tbody');
  const $suggest = $('#suggestions');
  const $tItems = $('#tItems'), $tSubtotal = $('#tSubtotal'), $tIva = $('#tIva'), $tTotal = $('#tTotal');

  const getIvaRate = () => {
    // IVA global desactivado: si el producto no tiene iva_rate, se considera 0
    return 0;
  };
  let items = [];
  let selectedIndex = -1;
  let lastSaleId = null; // ID de la última venta registrada (para ticket)

  function csrftoken() {
    const name = 'csrftoken';
    const cookies = document.cookie ? document.cookie.split('; ') : [];
    for (const c of cookies) { const [k, v] = c.split('='); if (k === name) return decodeURIComponent(v); }
    return '';
  }

  function fmt(n) { return '$' + (parseFloat(n || 0).toFixed(2)); }

  function recalc() {
    let subtotal = 0;
    let iva = 0;
    items.forEach(it => {
      const price = parseFloat(it.price) || 0;
      const cant = parseInt(it.cant) || 0;
      it.subtotal = price * cant;
      subtotal += it.subtotal;
      const rate = (typeof it.iva_rate !== 'undefined' && !isNaN(parseFloat(it.iva_rate))) ? parseFloat(it.iva_rate) : getIvaRate();
      iva += it.subtotal * rate;
    });
    const total = subtotal + iva;
    $tItems.text(items.length);
    $tSubtotal.text(fmt(subtotal));
    $tIva.text(fmt(iva));
    $tTotal.text(fmt(total));
    render();
  }

  function render() {
    $tbody.empty();
    items.forEach((it, idx) => {
      const tr = $(`
        <tr data-idx="${idx}" class="${idx===selectedIndex ? 'table-primary' : ''}">
          <td>${it.name}</td>
          <td class="text-center">
            <div class="input-group input-group-sm">
              <button class="btn btn-outline-secondary btnMinus">-</button>
              <input type="number" class="form-control text-center inpCant" value="${it.cant}" min="1" style="max-width: 72px">
              <button class="btn btn-outline-secondary btnPlus">+</button>
            </div>
          </td>
          <td class="text-end">${fmt(it.price)}</td>
          <td class="text-end">${fmt(it.subtotal)}</td>
          <td class="text-center">
            <button class="btn btn-danger btn-sm btnDel"><i class="fas fa-trash"></i></button>
          </td>
        </tr>
      `);
      $tbody.append(tr);
    });
  }

  function findById(id) { return items.find(x => x.id === id); }

  function addOrInc(prod) {
    let it = findById(prod.id);
    if (it) {
      it.cant += 1;
    } else {
      // price = pvp neto; pvp_final se usará solo al facturar
      it = {
        id: prod.id,
        name: prod.name,
        price: parseFloat(prod.pvp || prod.price || 0),
        pvp_final: parseFloat(prod.pvp_final || 0),
        iva_rate: (typeof prod.iva_rate !== 'undefined' && !isNaN(parseFloat(prod.iva_rate))) ? parseFloat(prod.iva_rate) : getIvaRate(),
        cant: 1,
        subtotal: 0
      };
      items.push(it);
    }
    selectedIndex = items.indexOf(it);
    recalc();
  }

  function ajaxAction(action, data) {
    return $.ajax({
      url: window.location.pathname,
      method: 'POST',
      data,
      headers: { 'X-CSRFToken': csrftoken() },
      dataType: 'json'
    });
  }

  // Debounce helper
  function debounce(fn, wait) {
    let t; return function(...args){ clearTimeout(t); t=setTimeout(()=>fn.apply(this,args), wait); };
  }

  // Sugerencias por palabras clave
  const doSuggest = debounce(function () {
    const term = ($input.val() || '').trim();
    if (term.length < 2) { $suggest.hide().empty(); return; }
    ajaxAction('search_products', { action: 'search_products', term })
      .done(list => {
        $suggest.empty();
        if (!Array.isArray(list) || !list.length) { $suggest.hide(); return; }
        list.forEach(p => {
          const item = $(`<button type="button" class="list-group-item list-group-item-action">${p.name} <span class='text-muted small'>${p.code || ''}</span> <span class='float-end'>$${parseFloat(p.pvp).toFixed(2)}</span></button>`);
          item.on('click', () => {
            // Pasamos todo el objeto p para conservar pvp_final e iva_rate
            addOrInc(p);
            $suggest.hide().empty();
            $input.val('').focus();
          });
          $suggest.append(item);
        });
        $suggest.show();
      })
      .fail(() => { $suggest.hide().empty(); });
  }, 180);

  $input.on('input', function (e) {
    if (e.originalEvent && e.originalEvent.inputType === 'insertLineBreak') return; // handled by keydown
    doSuggest();
  });

  // Leer producto por código / nombre al presionar Enter
  $input.on('keydown', function (e) {
    if (e.key === 'Enter') {
      const code = ($input.val() || '').trim();
      if (!code) return;
      $suggest.hide().empty();
      ajaxAction('product_by_code', { action: 'product_by_code', code })
        .done(resp => {
          addOrInc(resp);
          $input.val('').focus();
        })
        .fail(jq => {
          // Si no encontró exacto por código/nombre, intenta sugerencias inmediatamente
          doSuggest();
          $input.select();
        });
    }
  });

  // Ocultar sugerencias al hacer click fuera
  $(document).on('click', function (e) {
    if (!$(e.target).closest('#suggestions, #barcodeInput').length) {
      $suggest.hide();
    }
  });

  // Botones +/- y delete
  $tbody.on('click', '.btnPlus', function () {
    const idx = $(this).closest('tr').data('idx'); items[idx].cant += 1; selectedIndex = idx; recalc();
  });
  $tbody.on('click', '.btnMinus', function () {
    const idx = $(this).closest('tr').data('idx'); items[idx].cant = Math.max(1, items[idx].cant - 1); selectedIndex = idx; recalc();
  });
  $tbody.on('change', '.inpCant', function () {
    const idx = $(this).closest('tr').data('idx'); items[idx].cant = Math.max(1, parseInt($(this).val() || 1)); selectedIndex = idx; recalc();
  });
  $tbody.on('click', '.btnDel', function () {
    const idx = $(this).closest('tr').data('idx'); items.splice(idx, 1); selectedIndex = -1; recalc();
  });
  $tbody.on('click', 'tr', function () {
    selectedIndex = $(this).data('idx'); render();
  });

  // Atajos de teclado
  $(document).on('keydown', function (e) {
    if (e.key === 'Delete' && selectedIndex >= 0) {
      items.splice(selectedIndex, 1); selectedIndex = -1; recalc();
    }
    if (e.key === 'F2') {
      $('#btnCheckout').trigger('click');
      e.preventDefault();
    }
  });

  // Limpiar
  $('#btnClear').on('click', function () {
    items = []; selectedIndex = -1; recalc(); $input.val('').focus();
  });

  function buildPayload() {
    let subtotal_neto = 0;
    let iva_total = 0;
    items.forEach(it => {
      const net = parseFloat(it.price) || 0;           // pvp neto
      const cant = parseInt(it.cant) || 0;
      const sub_neto = net * cant;
      subtotal_neto += sub_neto;
      const rate = (typeof it.iva_rate !== 'undefined' && !isNaN(parseFloat(it.iva_rate))) ? parseFloat(it.iva_rate) : getIvaRate();
      iva_total += sub_neto * rate;
    });
    const items_net = items.map(it => {
      const net = parseFloat(it.price) || 0;
      const cant = parseInt(it.cant) || 0;
      return {
        id: it.id,
        cant,
        price: net,
        subtotal: net * cant,
      };
    });
    const items_final = items.map(it => {
      const net = parseFloat(it.price) || 0;
      const rate = parseFloat(it.iva_rate) || 0;
      const final = it.pvp_final && !isNaN(parseFloat(it.pvp_final))
        ? parseFloat(it.pvp_final)
        : net * (1 + rate);
      const cant = parseInt(it.cant) || 0;
      return {
        id: it.id,
        cant,
        price: final,
        subtotal: final * cant,
      };
    });
    return {
      subtotal_neto,
      iva_total,
      items_net,
      items_final,
    };
  }

  function doCreateSale() {
    const calc = buildPayload();
    const subtotal = calc.subtotal_neto;
    const iva = 0;
    const total = subtotal;
    const payMethod = ($('#payMethod').val() || 'cash');
    const payload = {
      items: calc.items_net,     // Detalle con precio neto
      subtotal, iva, total,
      payment_method: payMethod
    };
    ajaxAction('create_sale', { action: 'create_sale', sale: JSON.stringify(payload) })
      .done(resp => {
        if (resp && resp.id) {
          lastSaleId = resp.id;
          const modalEl = document.getElementById('printTicketModal');
          if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
          }
        }
        $('#btnClear').trigger('click');
      })
      .fail(jq => {
        alert('Error al registrar: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
      });
  }

  function doInvoiceSale() {
    const calc = buildPayload();
    const subtotal = calc.subtotal_neto;
    const iva = calc.iva_total;
    const total = subtotal + iva;
    const payMethod = ($('#payMethod').val() || 'cash');
    const payload = {
      items: calc.items_final,   // Detalle con precio con IVA
      subtotal, iva, total,
      payment_method: payMethod
    };
    ajaxAction('invoice', { action: 'invoice', sale: JSON.stringify(payload) })
      .done(resp => {
        if (resp.invoice_url) {
          window.open(resp.invoice_url, '_blank');
        } else {
          alert('Factura generada.');
        }
        $('#btnClear').trigger('click');
      })
      .fail(jq => {
        alert('Error al facturar: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
      });
  }

  // Botón principal: abrir modal para elegir modo de registro
  $('#btnCheckout').on('click', function () {
    if (!items.length) { alert('No hay ítems'); return; }
    const modalEl = document.getElementById('saleModeModal');
    if (!modalEl) {
      // Fallback si por alguna razón no se cargó el modal
      doCreateSale();
      return;
    }
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  });

  // Botones del modal de modo de registro
  $(document).on('click', '#btnModeNoInvoice', function () {
    const modal = bootstrap.Modal.getInstance(document.getElementById('saleModeModal'));
    if (modal) modal.hide();
    doCreateSale();
  });

  $(document).on('click', '#btnModeInvoice', function () {
    const modal = bootstrap.Modal.getInstance(document.getElementById('saleModeModal'));
    if (modal) modal.hide();
    doInvoiceSale();
  });

  // Botón del modal de impresión de ticket
  $(document).on('click', '#btnPrintTicket', function () {
    const modal = bootstrap.Modal.getInstance(document.getElementById('printTicketModal'));
    if (modal) modal.hide();
    if (lastSaleId) {
      const url = '/erp/sale/ticket/' + lastSaleId + '/print/';
      window.open(url, '_blank');
    }
  });

  // Inicializar
  recalc();
  $input.focus();
})();