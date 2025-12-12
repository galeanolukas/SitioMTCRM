(function () {
  const $input = $('#barcodeInput');
  const $tbody = $('#posItems tbody');
  const $suggest = $('#suggestions');
  const $tItems = $('#tItems'), $tSubtotal = $('#tSubtotal'), $tIva = $('#tIva'), $tTotal = $('#tTotal');
  const $summaryCard = $('#posSummaryCard');

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

  function showToast(type, message) {
    const toastEl = document.getElementById('posToast');
    if (!toastEl) {
      alert(message);
      return;
    }
    const toastBody = document.getElementById('posToastBody');
    const toastTitle = document.getElementById('posToastTitle');
    const header = toastEl.querySelector('.toast-header');

    let title = 'Información';
    let headerClass = 'toast-header bg-primary text-white';
    if (type === 'error') {
      title = 'Error';
      headerClass = 'toast-header bg-danger text-white';
    } else if (type === 'success') {
      title = 'Éxito';
      headerClass = 'toast-header bg-success text-white';
    } else if (type === 'warning') {
      title = 'Atención';
      headerClass = 'toast-header bg-warning text-dark';
    }

    toastBody.textContent = message;
    toastTitle.textContent = title;
    header.className = headerClass;

    const toast = new bootstrap.Toast(toastEl);
    toast.show();
  }

  function flashSummary() {
    if (!$summaryCard.length) return;
    $summaryCard.addClass('pos-summary-highlight border border-success');
    setTimeout(() => {
      $summaryCard.removeClass('pos-summary-highlight border border-success');
    }, 700);
  }

  function recalc() {
    let subtotal = 0;
    let iva = 0;
    items.forEach(it => {
      const price = parseFloat(it.price) || 0;
      const cant = parseFloat(it.cant) || 0;
      it.subtotal = price * cant;
      subtotal += it.subtotal;
      let rate = (typeof it.iva_rate !== 'undefined' && !isNaN(parseFloat(it.iva_rate))) ? parseFloat(it.iva_rate) : getIvaRate();
      // Convert to decimal if it's in percentage format (> 1)
      if (rate > 1) {
        rate = rate / 100;
      }
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
              <input type="number" class="form-control text-center inpCant" value="${it.cant}" min="0.01" step="0.01" style="max-width: 72px">
              <button class="btn btn-outline-secondary btnPlus">+</button>
            </div>
          </td>
          <td class="text-end">
            <input type="number" class="form-control form-control-sm text-end inpPrice" value="${it.price}" min="0" step="0.01" style="max-width: 90px; margin: 0 auto;">
          </td>
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
      it.cant = (parseFloat(it.cant) || 0) + 1;
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
    const idx = $(this).closest('tr').data('idx');
    const current = parseFloat(items[idx].cant || 0);
    items[idx].cant = (current || 0) + 1;
    selectedIndex = idx; recalc();
  });
  $tbody.on('click', '.btnMinus', function () {
    const idx = $(this).closest('tr').data('idx');
    const current = parseFloat(items[idx].cant || 0);
    items[idx].cant = Math.max(0.01, (current || 0) - 1);
    selectedIndex = idx; recalc();
  });
  $tbody.on('change', '.inpCant', function () {
    const idx = $(this).closest('tr').data('idx');
    const v = parseFloat($(this).val() || 0);
    items[idx].cant = Math.max(0.01, v || 0);
    selectedIndex = idx; recalc();
  });
  $tbody.on('change', '.inpPrice', function () {
    const idx = $(this).closest('tr').data('idx');
    const v = parseFloat($(this).val() || 0);
    items[idx].price = Math.max(0, v || 0);
    selectedIndex = idx; recalc();
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

  // Producto genérico: abrir modal
  // Cargar categorías para el modal de producto genérico
  function loadCategories(selectId, callback) {
    ajaxAction('list_categories', { action: 'list_categories' })
      .done(function(categories) {
        const $select = $(`#${selectId}`);
        $select.empty();
        
        // Agregar categoría predeterminada "Varios"
        $select.append('<option value="">Seleccione una categoría</option>');
        $select.append('<option value="Varios" selected>Varios</option>');
        
        // Agregar categorías existentes
        if (categories && categories.length > 0) {
          categories.forEach(function(cat) {
            if (cat.name !== 'Varios') {
              $select.append(`<option value="${cat.name}">${cat.name}</option>`);
            }
          });
        }
        
        if (typeof callback === 'function') {
          callback();
        }
      })
      .fail(function() {
        showToast('error', 'No se pudieron cargar las categorías');
        $(`#${selectId}`).html('<option value="">Error al cargar categorías</option>');
      });
  }

  // Mostrar/ocultar el formulario de nueva categoría
  $(document).on('click', '#btnNewCategory', function() {
    $('#newCategoryGroup').show();
    $('#newCategoryName').focus();
  });

  // Guardar nueva categoría
  $(document).on('click', '#btnSaveCategory', function() {
    const categoryName = $('#newCategoryName').val().trim();
    if (!categoryName) {
      showToast('warning', 'Ingrese un nombre para la categoría');
      return;
    }
    
    ajaxAction('create_category', {
      action: 'create_category',
      name: categoryName
    })
    .done(function() {
      showToast('success', 'Categoría creada correctamente');
      loadCategories('genericProdCategory', function() {
        $('#genericProdCategory').val(categoryName);
        $('#newCategoryGroup').hide();
        $('#newCategoryName').val('');
      });
    })
    .fail(function(jqXHR) {
      const errorMsg = jqXHR.responseJSON && jqXHR.responseJSON.error 
        ? jqXHR.responseJSON.error 
        : 'Error al crear la categoría';
      showToast('error', errorMsg);
    });
  });

  // Inicializar el modal de producto genérico
  $('#btnGenericProduct').on('click', function () {
    const modalEl = document.getElementById('genericProductModal');
    if (!modalEl) return;
    
    // Resetear formulario
    $('#genericProdName').val('PRODUCTO GENERICO');
    $('#genericProdPrice').val('');
    $('#genericProdIva').val('0');
    $('#genericProdCode').val('');
    $('#newCategoryGroup').hide();
    $('#newCategoryName').val('');
    
    // Cargar categorías
    loadCategories('genericProdCategory');
    
    // Mostrar modal
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  });

  // Guardar producto genérico desde modal
  $(document).on('click', '#btnGenericProductSave', function () {
    const name = ($('#genericProdName').val() || 'PRODUCTO GENERICO').trim();
    const price = $('#genericProdPrice').val();
    const iva_rate = $('#genericProdIva').val();
    const code = $('#genericProdCode').val();

    const category = $('#genericProdCategory').val() || 'Varios';
    
    ajaxAction('quick_create_product', {
      action: 'quick_create_product',
      name,
      price,
      iva_rate,
      code,
      category
    })
      .done(function (prod) {
        if (prod && prod.id) {
          addOrInc(prod);
          const modalEl = document.getElementById('genericProductModal');
          if (modalEl) {
            const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
            modal.hide();
          }
          showToast('success', 'Producto genérico agregado.');
          $input.focus();
        } else {
          showToast('error', 'No se pudo crear el producto genérico.');
        }
      })
      .fail(function (jq) {
        const msg = jq.responseJSON && jq.responseJSON.error ? jq.responseJSON.error : jq.statusText;
        showToast('error', 'Error al crear producto genérico: ' + msg);
      });
  });

  // Importar compra rápida (QuickOrder) por preference_id o ID
  $('#btnImportQuickOrder').on('click', function () {
    const raw = ($('#quickOrderInput').val() || '').trim();
    if (!raw) {
      showToast('warning', 'Ingrese un preference_id o ID de orden rápida.');
      return;
    }

    const data = { action: 'import_quickorder' };
    if (/^\d+$/.test(raw)) {
      data.quickorder_id = raw;
    } else {
      data.preference_id = raw;
    }

    ajaxAction('import_quickorder', data)
      .done(resp => {
        if (resp && resp.id) {
          showToast('success', 'Compra rápida importada como venta #' + resp.id + '.');
          $('#quickOrderInput').val('');
        } else if (resp && resp.error) {
          showToast('error', resp.error);
        } else {
          showToast('error', 'No se pudo importar la compra rápida.');
        }
      })
      .fail(jq => {
        const msg = jq.responseJSON && jq.responseJSON.error ? jq.responseJSON.error : jq.statusText;
        showToast('error', 'Error al importar compra rápida: ' + msg);
      });
  });

  function buildPayload() {
    let subtotal_neto = 0;
    let iva_total = 0;
    items.forEach(it => {
      const net = parseFloat(it.price) || 0;           // pvp neto
      const cant = parseFloat(it.cant) || 0;
      const sub_neto = net * cant;
      subtotal_neto += sub_neto;
      const rate = (typeof it.iva_rate !== 'undefined' && !isNaN(parseFloat(it.iva_rate))) ? parseFloat(it.iva_rate) : getIvaRate();
      iva_total += sub_neto * rate;
    });
    const items_net = items.map(it => {
      const net = parseFloat(it.price) || 0;
      const cant = parseFloat(it.cant) || 0;
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
          flashSummary();
          showToast('success', 'Venta registrada correctamente.');
          const modalEl = document.getElementById('printTicketModal');
          if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
          }
          // Recargar página después de venta exitosa
          setTimeout(() => {
            window.location.reload();
          }, 2000);
        }
        $('#btnClear').trigger('click');
      })
      .fail(jq => {
        showToast('error', 'Error al registrar: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
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
        flashSummary();
        if (resp.invoice_url) {
          window.open(resp.invoice_url, '_blank');
        } else {
          showToast('success', 'Factura generada.');
        }
        // Recargar página después de generar factura
        setTimeout(() => {
          window.location.reload();
        }, 2000);
        $('#btnClear').trigger('click');
      })
      .fail(jq => {
        showToast('error', 'Error al facturar: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
      });
  }

  // Botón principal: abrir modal para elegir modo de registro
  $('#btnCheckout').on('click', function () {
    if (!items.length) { showToast('warning', 'No hay ítems en el carrito.'); return; }
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