(function () {
  const $input = $('#barcodeInput');
  const $tbody = $('#posItems tbody');
  const $suggest = $('#suggestions');
  const $tItems = $('#tItems'), $tSubtotal = $('#tSubtotal'), $tIva = $('#tIva'), $tTotal = $('#tTotal');
  const $summaryCard = $('#posSummaryCard');

  const getIvaRate = (forInvoice = false) => {
    // Para facturas usar 21%, para tickets usar 0% (IVA global desactivado)
    return forInvoice ? 0.21 : 0;
  };
  let items = [];
  let selectedIndex = -1;
  let lastSaleId = null; // ID de la última venta registrada (para ticket)
  let pendingWeightProduct = null; // Producto pendiente de ingresar peso

  function csrftoken() {
    const name = 'csrftoken';
    const cookies = document.cookie ? document.cookie.split('; ') : [];
    for (const c of cookies) { const [k, v] = c.split('='); if (k === name) return decodeURIComponent(v); }
    return '';
  }

  function fmt(n) { 
  const num = parseFloat(n || 0);
  return '$' + num.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
  
  // Función para formatear números para inputs (punto decimal)
  function fmtNumber(n) { return (parseFloat(n || 0)).toFixed(2); }

  // Función para parsear formato US (punto decimal, coma miles)
  function parseFormattedAmount(text) {
    const cleanText = text.replace('$', '').replace(/,/g, '');
    return parseFloat(cleanText) || 0;
  }

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
    
    // Calcular totales
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
    
    // Actualizar totales
    $tItems.text(items.length);
    $tSubtotal.text(fmt(subtotal));
    $tIva.text(fmt(iva));
    $tTotal.text(fmt(total));
    
    // Renderizar items
    render();
  }

  function clearItems() {
    items = [];
    selectedIndex = -1;
    recalc();
    $input.val('').focus();
  }

  function render() {
    $tbody.empty();
    items.forEach((it, idx) => {
      // Formatear la cantidad según la unidad
      let displayCant = it.cant;
      let cantStep = "1";
      let cantMin = "1";
      
      if (it.unit === 'kg') {
        displayCant = parseFloat(it.cant).toFixed(3);
        cantStep = "0.001";
        cantMin = "0.001";
      } else {
        displayCant = Math.round(it.cant);
      }
      
      const tr = $(`
        <tr data-idx="${idx}" class="${idx===selectedIndex ? 'table-primary' : ''}">
          <td>${it.name}${it.unit === 'kg' ? ' <small class="text-muted">(kg)</small>' : ''}</td>
          <td class="text-center">
            <div class="input-group input-group-sm">
              <button class="btn btn-outline-secondary btnMinus">-</button>
              <input type="number" class="form-control text-center inpCant" value="${displayCant}" min="${cantMin}" step="${cantStep}" style="max-width: 72px">
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

  function showWeightModal(product) {
    pendingWeightProduct = product;
    $('#weightProductName').text(product.name);
    $('#weightInput').val('').focus();
    const modal = new bootstrap.Modal(document.getElementById('weightModal'));
    modal.show();
  }

  function addOrInc(prod, quantity = null) {
    // Validar que el producto tenga un ID válido
    if (!prod || !prod.id) {
      console.error("Invalid product data:", prod);
      showToast('error', 'Producto inválido');
      return;
    }
    
    // Validación simple de stock
    const currentStock = parseFloat(prod.stock) || 0;
    if (currentStock <= 0) {
      showToast('error', `SIN STOCK - No hay unidades disponibles de ${prod.name}`);
      return;
    }
    
    if (currentStock <= 5) {
      showToast('warning', `STOCK BAJO - Solo ${currentStock} unidades disponibles de ${prod.name}`);
    }
    
    let it = findById(prod.id);
    
    // Determinar la cantidad a agregar
    let addQuantity = 1;
    if (quantity !== null) {
      addQuantity = parseFloat(quantity) || 1;
    }
    
    if (it) {
      // Si el producto es por kg, sumar el peso
      if (prod.unit === 'kg') {
        it.cant = (parseFloat(it.cant) || 0) + addQuantity;
      } else {
        it.cant = (parseFloat(it.cant) || 0) + 1;
      }
    } else {
      // Calcular precio según unidad
      let finalPrice = parseFloat(prod.pvp || prod.price || 0);
      let displayQuantity = 1;
      
      if (prod.unit === 'kg') {
        // Si es por kg y se especifica cantidad, usar esa cantidad
        displayQuantity = addQuantity;
        // El precio ya es por kg, solo se multiplicará por la cantidad en recalc()
      }
      
      // price = pvp neto; pvp_final se usará solo al facturar
      it = {
        id: prod.id,
        name: prod.name || 'Producto sin nombre',
        price: finalPrice,
        pvp_final: parseFloat(prod.pvp_final || 0),
        iva_rate: (typeof prod.iva_rate !== 'undefined' && !isNaN(parseFloat(prod.iva_rate))) ? parseFloat(prod.iva_rate) : getIvaRate(),
        cant: displayQuantity,
        subtotal: 0,
        unit: prod.unit || 'unit',
        prod_data: prod // Guardar datos completos del producto para validación de stock
      };
      items.push(it);
    }
    
    selectedIndex = items.indexOf(it);
    recalc();
    flashSummary();
  }

  function ajaxAction(action, data) {
    return $.ajax({
      url: window.location.pathname,
      method: 'POST',
      data: { action, ...data },
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
    
    ajaxAction('search_products', { term })
      .done(list => {
        $suggest.empty();
        if (!Array.isArray(list) || !list.length) { $suggest.hide(); return; }
        
        list.forEach(p => {
          const item = $(`<button type="button" class="list-group-item list-group-item-action">${p.name} <span class='text-muted small'>${p.code || ''}</span> <span class='float-end'>$${parseFloat(p.pvp).toFixed(2)}</span></button>`);
          item.on('click', function(e) {
            e.preventDefault();
            if (p.unit === 'kg') {
              showWeightModal(p);
            } else {
              addOrInc(p);
            }
            $suggest.hide().empty();
            $input.val('').focus();
          });
          $suggest.append(item);
        });
        $suggest.show();
      })
      .fail(() => { $suggest.hide().empty(); });
  }, 200);

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
      ajaxAction('product_by_code', { code })
        .done(resp => {
          if (resp.unit === 'kg') {
            showWeightModal(resp);
          } else {
            addOrInc(resp);
          }
          $input.val('').focus();
        })
        .fail((jqXHR, textStatus, errorThrown) => {
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
    
    // Determinar el incremento según la unidad
    let increment = 1;
    if (items[idx].unit === 'kg') {
      increment = 0.1; // Incrementar por 100g para productos por kg
    }
    
    const newCant = current + increment;
    
    // Validación simple de stock
    const productStock = parseFloat(items[idx].prod_data?.stock || 0);
    if (newCant > productStock && productStock > 0) {
      const unit = items[idx].unit === 'kg' ? 'kg' : 'unidades';
      showToast('error', `Stock insuficiente. Disponible: ${productStock} ${unit}`);
      return;
    }
    
    items[idx].cant = newCant;
    selectedIndex = idx; recalc();
  });
  $tbody.on('click', '.btnMinus', function () {
    const idx = $(this).closest('tr').data('idx');
    const current = parseFloat(items[idx].cant || 0);
    
    // Determinar el decremento según la unidad
    let decrement = 1;
    let minVal = 1;
    if (items[idx].unit === 'kg') {
      decrement = 0.1; // Decrementar por 100g para productos por kg
      minVal = 0.001; // Mínimo 1 gramo
    }
    
    items[idx].cant = Math.max(minVal, (current || 0) - decrement);
    selectedIndex = idx; recalc();
  });
  $tbody.on('change', '.inpCant', function () {
    const idx = $(this).closest('tr').data('idx');
    const v = parseFloat($(this).val() || 0);
    
    // Determinar el mínimo según la unidad
    let minVal = 1;
    if (items[idx].unit === 'kg') {
      minVal = 0.001; // Mínimo 1 gramo para productos por kg
    }
    
    const newCant = Math.max(minVal, v || 0);
    
    // Validación simple de stock
    const productStock = parseFloat(items[idx].prod_data?.stock || 0);
    if (newCant > productStock && productStock > 0) {
      const unit = items[idx].unit === 'kg' ? 'kg' : 'unidades';
      showToast('error', `Stock insuficiente. Disponible: ${productStock} ${unit}`);
      $(this).val(items[idx].cant); // Restaurar valor anterior
      return;
    }
    
    items[idx].cant = newCant;
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
    clearItems();
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

  function buildPayload(forInvoice = false) {
    let subtotal_neto = 0;
    let iva_total = 0;
    items.forEach(it => {
      const net = parseFloat(it.price) || 0;           // pvp neto
      const cant = parseFloat(it.cant) || 0;
      const sub_neto = net * cant;
      subtotal_neto += sub_neto;
      const rate = (typeof it.iva_rate !== 'undefined' && !isNaN(parseFloat(it.iva_rate))) ? parseFloat(it.iva_rate) : getIvaRate(forInvoice);
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
    const clientId = $('#selectedClientId').val() || null;
    return {
      subtotal_neto,
      iva_total,
      items_net,
      items_final,
      client_id: clientId,
    };
  }

  // Función para cargar clientes
  function loadClients(searchTerm = '') {
    $.ajax({
      url: '/erp/client/list/',
      type: 'POST',
      data: {
        action: 'searchdata',
        csrfmiddlewaretoken: csrftoken()
      },
      dataType: 'json',
      success: function(data) {
        const tbody = $('#clientListBody');
        tbody.empty();
        
        if (data.length === 0) {
          tbody.append('<tr><td colspan="4" class="text-center">No se encontraron clientes</td></tr>');
          return;
        }
        
        data.forEach(function(client) {
          const fullName = client.names + ' ' + client.surnames;
          const dni = client.dni || '-';
          const address = client.address || '-';
          
          // Filtrar por término de búsqueda
          if (searchTerm && !fullName.toLowerCase().includes(searchTerm.toLowerCase()) && 
              !dni.includes(searchTerm)) {
            return;
          }
          
          const row = `
            <tr>
              <td>${fullName}</td>
              <td>${dni}</td>
              <td>${address}</td>
              <td>
                <button class="btn btn-sm btn-primary btn-select-client" data-client-id="${client.id}" data-client-name="${fullName}">
                  <i class="fas fa-check"></i>
                </button>
              </td>
            </tr>
          `;
          tbody.append(row);
        });
      },
      error: function() {
        showToast('error', 'Error al cargar clientes');
      }
    });
  }

  // Evento para abrir modal de selección de cliente
  $('#btnSelectClient').on('click', function() {
    $('#clientSelectModal').modal('show');
    loadClients();
  });

  // Evento para buscar clientes
  $('#clientSearchInput').on('input', function() {
    const searchTerm = $(this).val();
    loadClients(searchTerm);
  });

  // Evento para seleccionar cliente
  $(document).on('click', '.btn-select-client', function() {
    const clientId = $(this).data('client-id');
    const clientName = $(this).data('client-name');
    
    $('#selectedClientId').val(clientId);
    $('#selectedClientName').text(clientName);
    
    $('#clientSelectModal').modal('hide');
    showToast('success', 'Cliente seleccionado: ' + clientName);
  });

  // Evento para limpiar cliente
  $('#btnClearClient').on('click', function() {
    $('#selectedClientId').val('');
    $('#selectedClientName').text('Anónimo');
    $('#clientSelectModal').modal('hide');
    showToast('info', 'Cliente limpiado');
  });

  function doCreateSale() {
    const calc = buildPayload(false); // Ticket sin IVA
    const subtotal = calc.subtotal_neto;
    const iva = 0; // Tickets no tienen IVA
    const total = subtotal; // Total es solo el subtotal sin IVA
    const payMethod = ($('#payMethod').val() || 'cash');
    
    // Generar token único para esta venta
    const saleToken = 'sale_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    
    const payload = {
      cli: calc.client_id,
      items: calc.items_net,     // Detalle con precio neto
      subtotal, iva, total,
      payment_method: payMethod,
      sale_token: saleToken  // Agregar token
    };
    ajaxAction('create_sale', { action: 'create_sale', sale: JSON.stringify(payload), sale_token: saleToken })
      .done(resp => {
        if (resp && resp.id) {
          lastSaleId = resp.id;
          flashSummary();
          showToast('success', 'Venta registrada correctamente.');
          const modalEl = document.getElementById('printTicketModal');
          if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
            // Recargar página después de que el modal se cierre
            modalEl.addEventListener('hidden.bs.modal', function () {
              window.location.reload();
            }, { once: true });
          }
        }
        $('#btnClear').trigger('click');
      })
      .fail(jq => {
        showToast('error', 'Error al registrar: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
      });
  }

  function doInvoiceSale() {
    const calc = buildPayload(true); // Factura con IVA
    const subtotal = calc.subtotal_neto;
    const iva = calc.iva_total;
    const total = subtotal + iva;
    const payMethod = ($('#payMethod').val() || 'cash');
    
    // Generar token único para esta factura
    const saleToken = 'invoice_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    
    const payload = {
      cli: calc.client_id,
      items: calc.items_final,   // Detalle con IVA incluido
      subtotal, iva, total,
      payment_method: payMethod,
      sale_token: saleToken  // Agregar token
    };
    ajaxAction('invoice', { action: 'invoice', sale: JSON.stringify(payload), sale_token: saleToken })
      .done(resp => {
        if (resp && resp.id) {
          lastSaleId = resp.id;
          flashSummary();
          showToast('success', 'Factura generada correctamente.');
          const modalEl = document.getElementById('printTicketModal');
          if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
            // Recargar página después de que el modal se cierre
            modalEl.addEventListener('hidden.bs.modal', function () {
              window.location.reload();
            }, { once: true });
          }
          $('#btnClear').trigger('click');
        }
      })
      .fail(jq => {
        showToast('error', 'Error al facturar: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
      });
  }

  // Botón principal: abrir modal para elegir modo de registro
  $('#btnCheckout').on('click', function () {
    // Prevenir doble clic
    if ($(this).prop('disabled')) return;
    
    if (!items.length) { showToast('warning', 'No hay ítems en el carrito.'); return; }
    
    // Verificar si se seleccionó pagos combinados
    const payMethod = $('#payMethod').val();
    if (payMethod === 'combined') {
      openCombinedPaymentModal();
      return;
    }
    
    const modalEl = document.getElementById('saleModeModal');
    if (!modalEl) {
      // Fallback si por alguna razón no se cargó el modal
      doCreateSale();
      return;
    }
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  });

  // Funciones para pagos combinados
  function openCombinedPaymentModal() {
    // Establecer valores iniciales
    $('#firstPaymentAmount').val('');
    $('#firstPaymentMethod').val('cash');
    $('#combinedRemaining').text(fmt(0));
    $('#btnCombinedPaymentStep2').prop('disabled', true);
    
    // Calcular totales según el tipo de comprobante seleccionado
    updateCombinedTotals();
    
    const modal = new bootstrap.Modal(document.getElementById('combinedPaymentModal'));
    modal.show();
  }

  // Actualizar totales cuando cambia tipo de comprobante
  $(document).on('change', 'input[name="combinedInvoiceType"]', function() {
    updateCombinedTotals();
  });

  function updateCombinedTotals() {
    const wantsInvoice = $('#combinedInvoice').is(':checked');
    
    console.log('updateCombinedTotals - items:', items);
    console.log('updateCombinedTotals - items.length:', items.length);
    
    if (wantsInvoice) {
      // Para facturas, recalcular con IVA al 21%
      let subtotal = 0;
      let iva = 0;
      
      items.forEach(it => {
        const price = parseFloat(it.price) || 0;
        const cant = parseFloat(it.cant) || 0;
        const itemSubtotal = price * cant;
        subtotal += itemSubtotal;
        // Usar 21% para facturas
        const ivaRate = 0.21;
        iva += itemSubtotal * ivaRate;
      });
      
      const total = subtotal + iva;
      
      console.log('Factura - subtotal:', subtotal, 'iva:', iva, 'total:', total);
      
      $('#combinedSubtotalAmount').text(fmt(subtotal));
      $('#combinedIvaAmount').text(fmt(iva));
      $('#combinedTotalAmount').text(fmt(total));
    } else {
      // Para tickets, calcular desde los items (sin IVA)
      let subtotal = 0;
      items.forEach(it => {
        const price = parseFloat(it.price) || 0;
        const cant = parseFloat(it.cant) || 0;
        subtotal += price * cant;
      });
      
      console.log('Ticket - subtotal:', subtotal);
      
      $('#combinedSubtotalAmount').text(fmt(subtotal));
      $('#combinedIvaAmount').text(fmt(0));
      $('#combinedTotalAmount').text(fmt(subtotal));
    }
    
    // Actualizar restante
    const firstAmountText = $('#firstPaymentAmount').val();
    const firstAmount = parseFloat(firstAmountText) || 0;
    const totalText = $('#combinedTotalAmount').text();
    const total = parseFormattedAmount(totalText);
    
    // Si el primer monto es mayor que el nuevo total, limpiar el campo
    if (firstAmount > total) {
      $('#firstPaymentAmount').val('');
      $('#combinedRemaining').text(fmt(total));
      $('#btnCombinedPaymentStep2').prop('disabled', true);
    } else {
      const remaining = total - firstAmount;
      
      // Si el restante es negativo, mostrar 0 y deshabilitar el botón
      if (remaining < 0) {
        $('#combinedRemaining').text(fmt(0));
        $('#btnCombinedPaymentStep2').prop('disabled', true);
      } else {
        $('#combinedRemaining').text(fmt(remaining));
        // Habilitar solo si el primer monto es válido
        $('#btnCombinedPaymentStep2').prop('disabled', firstAmount <= 0 || firstAmount >= total);
      }
    }
  }

  // Calcular monto restante en tiempo real
  $(document).on('input', '#firstPaymentAmount', function() {
    const totalText = $('#combinedTotalAmount').text();
    const total = parseFormattedAmount(totalText);
    const firstAmountText = $(this).val();
    const firstAmount = parseFloat(firstAmountText) || 0;
    const remaining = total - firstAmount;
    
    if (firstAmount > 0 && firstAmount < total) {
      $('#combinedRemaining').text(fmt(remaining));
      $('#btnCombinedPaymentStep2').prop('disabled', false);
    } else if (firstAmount >= total) {
      $('#combinedRemaining').text(fmt(0));
      $('#btnCombinedPaymentStep2').prop('disabled', true);
      showToast('warning', 'El primer monto debe ser menor que el total');
    } else {
      $('#combinedRemaining').text(fmt(0));
      $('#btnCombinedPaymentStep2').prop('disabled', true);
    }
  });

  // Continuar al paso 2
  $(document).on('click', '#btnCombinedPaymentStep2', function() {
    const total = parseFormattedAmount($('#combinedTotalAmount').text());
    const firstAmount = parseFloat($('#firstPaymentAmount').val()) || 0;
    const firstMethod = $('#firstPaymentMethod').val();
    
    if (firstAmount <= 0 || firstAmount >= total) {
      showToast('warning', 'Ingrese un monto válido menor que el total');
      return;
    }
    
    const remaining = total - firstAmount;
    
    // Validar que remaining sea un número válido
    if (isNaN(remaining) || remaining < 0) {
      showToast('error', 'Error en el cálculo del monto restante');
      return;
    }
    
    // Llenar datos del paso 2
    const wantsInvoice = $('#combinedInvoice').is(':checked');
    const invoiceType = wantsInvoice ? 'Factura' : 'Ticket';
    $('#firstPaymentSummary').text(`${getPaymentMethodName(firstMethod)}: ${fmt(firstAmount)} (${invoiceType})`);
    
    // Establecer el segundo pago con el restante
    const secondPaymentValue = remaining.toFixed(2);
    $('#secondPaymentAmount').val(secondPaymentValue);
    $('#secondPaymentMethod').val('cash');
    
    // Cerrar modal paso 1 y abrir paso 2
    bootstrap.Modal.getInstance(document.getElementById('combinedPaymentModal')).hide();
    const modal2 = new bootstrap.Modal(document.getElementById('combinedPaymentStep2Modal'));
    modal2.show();
    
    // Establecer el segundo pago después de que el modal se muestre
    setTimeout(() => {
      $('#secondPaymentAmount').val(secondPaymentValue);
    }, 100);
  });

  // Volver al paso 1
  $(document).on('click', '#btnCombinedPaymentBack', function() {
    bootstrap.Modal.getInstance(document.getElementById('combinedPaymentStep2Modal')).hide();
    const modal1 = new bootstrap.Modal(document.getElementById('combinedPaymentModal'));
    modal1.show();
  });

  // Permitir edición manual del segundo monto y validar en tiempo real
  $(document).on('input', '#secondPaymentAmount', function() {
    const total = parseFormattedAmount($('#combinedTotalAmount').text());
    const firstAmount = parseFloat($('#firstPaymentAmount').val()) || 0;
    const secondAmount = parseFloat($(this).val()) || 0;
    const remaining = total - firstAmount - secondAmount;
    
    // Mostrar advertencia si el monto no es correcto
    if (secondAmount <= 0) {
      showToast('warning', 'El segundo monto debe ser mayor que 0');
    } else if (Math.abs((firstAmount + secondAmount) - total) > 0.01) {
      showToast('warning', `El restante debería ser ${fmt(remaining)}`);
    }
  });

  // Confirmar pagos combinados
  $(document).on('click', '#btnCombinedPaymentConfirm', function() {
    const total = parseFormattedAmount($('#combinedTotalAmount').text());
    const firstAmount = parseFloat($('#firstPaymentAmount').val()) || 0;
    const firstMethod = $('#firstPaymentMethod').val();
    const secondMethod = $('#secondPaymentMethod').val();
    const secondAmount = parseFloat($('#secondPaymentAmount').val()) || 0;
    const wantsInvoice = $('#combinedInvoice').is(':checked');
    
    if (Math.abs((firstAmount + secondAmount) - total) > 0.01) {
      showToast('error', 'Los montos no suman el total correcto');
      $(this).prop('disabled', false);
      return;
    }
    
    // Construir payload de pagos combinados
    const calc = buildPayload(wantsInvoice); // Usar IVA si es factura
    const paymentDescription = `${getPaymentMethodName(firstMethod)} + ${getPaymentMethodName(secondMethod)}`;
    
    // Generar token único para esta venta combinada
    const saleToken = 'combined_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    
    // Usar items con IVA si es factura, sin IVA si es ticket
    const items = wantsInvoice ? calc.items_final : calc.items_net;
    const subtotal = wantsInvoice ? calc.subtotal_neto : calc.subtotal_neto;
    const iva = wantsInvoice ? calc.iva_total : 0;
    
    const payload = {
      items: items,
      subtotal: subtotal,
      iva: iva,
      total: total,
      payment_method: paymentDescription,
      combined_payments: [
        { method: firstMethod, amount: firstAmount },
        { method: secondMethod, amount: secondAmount }
      ]
    };
    
    // Cerrar modal y registrar venta
    bootstrap.Modal.getInstance(document.getElementById('combinedPaymentStep2Modal')).hide();
    
    if (wantsInvoice) {
      // Generar factura
      ajaxAction('invoice', { action: 'invoice', sale: JSON.stringify(payload), sale_token: saleToken })
        .done(resp => {
          flashSummary();
          if (resp.invoice_url) {
            window.open(resp.invoice_url, '_blank');
          } else {
            showToast('success', 'Factura generada.');
          }
          setTimeout(() => {
            window.location.reload();
          }, 2000);
          $('#btnClear').trigger('click');
        })
        .fail(jq => {
          showToast('error', 'Error al facturar: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
          $(this).prop('disabled', false);
        });
    } else {
      // Registrar venta normal
      ajaxAction('create_sale', { action: 'create_sale', sale: JSON.stringify(payload), sale_token: saleToken })
        .done(resp => {
          if (resp && resp.id) {
            lastSaleId = resp.id;
            flashSummary();
            showToast('success', 'Venta con pagos combinados registrada correctamente.');
            const modalEl = document.getElementById('printTicketModal');
            if (modalEl) {
              const modal = new bootstrap.Modal(modalEl);
              modal.show();
              // Recargar página después de que el modal se cierre
              modalEl.addEventListener('hidden.bs.modal', function () {
                window.location.reload();
              }, { once: true });
            }
          }
          $('#btnClear').trigger('click');
        })
        .fail(jq => {
          showToast('error', 'Error al registrar: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
          $(this).prop('disabled', false);
        });
    }
  });

  function getPaymentMethodName(method) {
    const names = {
      'cash': 'Efectivo',
      'card': 'Tarjeta',
      'transfer': 'Transferencia',
      'mp': 'Mercado Pago',
      'check': 'Cheque'
    };
    return names[method] || method;
  }

  // Botones del modal de modo de registro
  $(document).on('click', '#btnModeNoInvoice', function () {
    // Prevenir doble clic
    if ($(this).prop('disabled')) return;
    $(this).prop('disabled', true);
    
    const modal = bootstrap.Modal.getInstance(document.getElementById('saleModeModal'));
    if (modal) modal.hide();
    doCreateSale();
    
    // Rehabilitar después de 5 segundos
    setTimeout(() => {
      $(this).prop('disabled', false);
    }, 5000);
  });

  $(document).on('click', '#btnModeInvoice', function () {
    // Prevenir doble clic
    if ($(this).prop('disabled')) return;
    $(this).prop('disabled', true);
    
    const modal = bootstrap.Modal.getInstance(document.getElementById('saleModeModal'));
    if (modal) modal.hide();
    doInvoiceSale();
    
    // Rehabilitar después de 5 segundos
    setTimeout(() => {
      $(this).prop('disabled', false);
    }, 5000);
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

  // Funcionalidad para cuenta corriente de empleados
  let employees = [];

  // Cargar empleados al abrir el modal
  $(document).on('show.bs.modal', '#employeeAccountModal', function () {
    loadEmployees();
    updateEmployeeAccountSummary();
  });

  function loadEmployees() {
    $.ajax({
      url: window.location.pathname,
      type: 'POST',
      data: {
        action: 'get_employees',
        csrfmiddlewaretoken: csrftoken()
      },
      success: function(response) {
        employees = response;
        const $select = $('#employeeSelect');
        $select.empty().append('<option value="">Seleccione un empleado...</option>');
        employees.forEach(emp => {
          $select.append(`<option value="${emp.id}">${emp.name}</option>`);
        });
      },
      error: function() {
        showToast('error', 'Error al cargar empleados');
      }
    });
  }

  function updateEmployeeAccountSummary() {
    const subtotal = items.reduce((sum, it) => sum + (it.subtotal || 0), 0);
    // Para empleados, el IVA es 0
    const iva = 0;
    const total = subtotal + iva;

    $('#empItems').text(items.length);
    $('#empSubtotal').text(fmt(subtotal));
    $('#empIva').text(fmt(iva));
    $('#empTotal').text(fmt(total));
  }

  // Actualizar resumen cuando cambian los items
  const originalRecalc = recalc;
  recalc = function() {
    originalRecalc();
    updateEmployeeAccountSummary();
  };

  // Mostrar/ocultar sección de pago combinado en cuenta corriente
  $(document).on('change', '#employeeCombinedPayment', function() {
    const isChecked = $(this).is(':checked');
    $('#employeePaymentSection').toggle(isChecked);
    
    if (isChecked) {
      // Limpiar campos al mostrar
      $('#employeePaymentAmount').val('');
      $('#employeePaymentMethod').val('cash');
    }
  });

  // Botón de cuenta corriente de empleados
  $('#btnEmployeeAccount').on('click', function() {
    if (items.length === 0) {
      showToast('warning', 'Debe agregar productos antes de registrar una cuenta corriente');
      return;
    }
    
    const modal = new bootstrap.Modal(document.getElementById('employeeAccountModal'));
    modal.show();
  });

  // Botón para agregar nuevo empleado
  $('#btnAddEmployee').on('click', function() {
    const modal = new bootstrap.Modal(document.getElementById('addEmployeeModal'));
    modal.show();
  });

  // Guardar nuevo empleado
  $('#btnSaveEmployee').on('click', function() {
    const name = $('#newEmployeeName').val().trim();
    const email = $('#newEmployeeEmail').val().trim();

    if (!name) {
      showToast('warning', 'Debe ingresar el nombre del empleado');
      return;
    }

    // Prevenir doble clic
    if ($(this).prop('disabled')) return;
    $(this).prop('disabled', true);

    $.ajax({
      url: window.location.pathname,
      type: 'POST',
      data: {
        action: 'add_employee',
        name: name,
        email: email,
        csrfmiddlewaretoken: csrftoken()
      },
      success: function(response) {
        if (response.error) {
          showToast('error', response.error);
        } else {
          showToast('success', 'Empleado agregado correctamente');
          
          // Cerrar modal de agregar empleado
          const addModal = bootstrap.Modal.getInstance(document.getElementById('addEmployeeModal'));
          if (addModal) addModal.hide();
          
          // Limpiar formulario
          $('#newEmployeeName').val('');
          $('#newEmployeeEmail').val('');
          
          // Recargar lista de empleados
          loadEmployees();
          
          // Seleccionar automáticamente el nuevo empleado
          setTimeout(() => {
            $('#employeeSelect').val(response.id);
          }, 500);
        }
      },
      error: function(jq) {
        showToast('error', 'Error al agregar empleado: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
      },
      complete: function() {
        $('#btnSaveEmployee').prop('disabled', false);
      }
    });
  });

  // Confirmar peso de producto
  $(document).on('click', '#btnConfirmWeight', function() {
    const weight = parseFloat($('#weightInput').val() || 0);
    
    if (weight <= 0) {
      showToast('error', 'Debe ingresar un peso válido');
      return;
    }
    
    if (pendingWeightProduct) {
      addOrInc(pendingWeightProduct, weight);
      pendingWeightProduct = null;
      
      // Cerrar modal
      const modal = bootstrap.Modal.getInstance(document.getElementById('weightModal'));
      modal.hide();
      
      // Limpiar input
      $('#weightInput').val('');
      
      // Enfocar input principal
      $input.focus();
    }
  });

  // Permitir Enter en el input de peso
  $(document).on('keydown', '#weightInput', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      $('#btnConfirmWeight').click();
    }
  });

  // Confirmar cuenta corriente de empleado
  $(document).on('click', '#btnConfirmEmployeeAccount', function() {
    const employeeId = $('#employeeSelect').val();
    const notes = $('#employeeNotes').val();
    const isCombinedPayment = $('#employeeCombinedPayment').is(':checked');

    if (!employeeId) {
      showToast('warning', 'Debe seleccionar un empleado');
      return;
    }

    if (items.length === 0) {
      showToast('warning', 'Debe agregar productos');
      return;
    }

    // Validar pago combinado si está activado
    if (isCombinedPayment) {
      const paymentAmount = parseFloat($('#employeePaymentAmount').val()) || 0;
      const paymentMethod = $('#employeePaymentMethod').val();
      
      if (paymentAmount <= 0) {
        showToast('warning', 'Debe ingresar un monto de pago válido');
        return;
      }
      
      const subtotal = items.reduce((sum, it) => sum + (it.subtotal || 0), 0);
      if (paymentAmount > subtotal) {
        showToast('warning', 'El monto de pago no puede ser mayor al total');
        return;
      }
    }

    // Prevenir doble clic
    if ($(this).prop('disabled')) return;
    $(this).prop('disabled', true);

    const subtotal = items.reduce((sum, it) => sum + (it.subtotal || 0), 0);
    // Para empleados, el IVA es 0
    const iva = 0;
    const total = subtotal + iva;

    const saleData = {
      employee_id: employeeId,
      notes: notes,
      items: items.map(it => ({
        id: it.id,
        cant: it.cant,
        price: it.price,
        subtotal: it.subtotal
      })),
      subtotal: subtotal,
      iva: iva,
      total: total
    };

    // Agregar detalles de pago combinado si está activado
    if (isCombinedPayment) {
      const paymentAmount = parseFloat($('#employeePaymentAmount').val()) || 0;
      const paymentMethod = $('#employeePaymentMethod').val();
      
      saleData.payment_details = {
        method: paymentMethod,
        amount: paymentAmount,
        description: getPaymentMethodName(paymentMethod)
      };
    }

    // Generar token único para esta venta
    const saleToken = 'emp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    $.ajax({
      url: window.location.pathname,
      type: 'POST',
      data: {
        action: 'create_employee_account_sale',
        sale: JSON.stringify(saleData),
        sale_token: saleToken,
        csrfmiddlewaretoken: csrftoken()
      },
      success: function(response) {
        if (response.error) {
          showToast('error', response.error);
        } else {
          showToast('success', response.message || 'Cuenta corriente registrada correctamente');
          clearItems();
          const modal = bootstrap.Modal.getInstance(document.getElementById('employeeAccountModal'));
          if (modal) modal.hide();
          $('#employeeSelect').val('');
          $('#employeeNotes').val('');
          $('#employeeCombinedPayment').prop('checked', false);
          $('#employeePaymentSection').hide();
          $('#employeePaymentAmount').val('');
          flashSummary();
        }
      },
      error: function(jq) {
        showToast('error', 'Error al registrar cuenta corriente: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
      },
      complete: function() {
        $('#btnConfirmEmployeeAccount').prop('disabled', false);
      }
    });
  });

  // Atajo de teclado F3 para cuenta corriente
  $(document).on('keydown', function(e) {
    if (e.key === 'F3') {
      e.preventDefault();
      $('#btnEmployeeAccount').click();
    }
  });

  // Inicializar
  recalc();
  $input.focus();
})();