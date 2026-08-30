(function () {
  const $input = $('#barcodeInput');
  const $tbody = $('#posItems tbody');
  const $suggest = $('#suggestions');
  const $tItems = $('#tItems'), $tSubtotal = $('#tSubtotal'), $tIva = $('#tIva'), $tTotal = $('#tTotal'), $tSavings = $('#tSavings');
  const $summaryCard = $('#posSummaryCard');

  const getIvaRate = (forInvoice = false) => {
    // Usar siempre 21% por defecto (se sobrescribe con iva_rate del producto si está disponible)
    return 0.21;
  };
  let items = [];
  let selectedIndex = -1;
  let lastSaleId = null; // ID de la última venta registrada (para ticket)
  let pendingWeightProduct = null; // Producto pendiente de ingresar peso
  let originalPrices = {}; // Precios originales para restaurar al cambiar cliente
  let currentPriceList = null; // Lista de precios activa del cliente seleccionado

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
    let subtotal = 0;  // PVP con IVA (precio original sin descuento)
    let total = 0;     // Total a pagar (con descuento aplicado)
    
    // Calcular totales
    items.forEach(it => {
      const price = parseFloat(it.price) || 0;  // PVP sin IVA (con descuento si aplica)
      const cant = parseFloat(it.cant) || 0;
      
      // Calcular IVA: PVP sin IVA * tasa IVA
      let rate = (typeof it.iva_rate !== 'undefined' && !isNaN(parseFloat(it.iva_rate))) ? parseFloat(it.iva_rate) : getIvaRate();
      if (rate > 1) {
        rate = rate / 100;
      }
      
      // Calcular subtotal usando precio original (sin descuento de lista)
      const origPrice = originalPrices[it.id] || price;
      const origPriceWithIva = origPrice * (1 + rate);
      subtotal += origPriceWithIva * cant;
      
      // Calcular PVP con IVA para el total (con descuento)
      const price_with_iva = price * (1 + rate);
      it.subtotal = price_with_iva * cant;
      total += it.subtotal;
    });
    
    const savings = subtotal - total;
    
    // Actualizar totales
    $tItems.text(items.length);
    $tSubtotal.text(fmt(subtotal));
    $tTotal.text(fmt(total));
    
    // Mostrar/ocultar ahorro por lista
    if (currentPriceList && savings > 0.01) {
      $('#priceListSavingsRow').show();
      $('#priceListName').text('(' + currentPriceList.list_name + ')');
      $tSavings.text('-' + fmt(savings));
    } else {
      $('#priceListSavingsRow').hide();
    }
    
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
      
      // Calcular PVP con IVA para mostrar en la columna
      let rate = (typeof it.iva_rate !== 'undefined' && !isNaN(parseFloat(it.iva_rate))) ? parseFloat(it.iva_rate) : getIvaRate();
      if (rate > 1) {
        rate = rate / 100;
      }
      const pvp_with_iva = it.pvp_final && !isNaN(parseFloat(it.pvp_final)) ? parseFloat(it.pvp_final) : it.price * (1 + rate);
      
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
            <input type="number" class="form-control form-control-sm text-end inpPrice" value="${pvp_with_iva}" min="0" step="0.01" style="max-width: 90px; margin: 0 auto;">
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
      // Si hay lista de precios activa, obtener precio ajustado
      if (currentPriceList && currentPriceList.has_price_list) {
        // Hacer request para obtener el precio de este producto específico
        $.ajax({
          url: window.location.pathname,
          type: 'POST',
          data: {
            action: 'get_client_prices',
            client_id: $('#selectedClientId').val(),
            product_ids: String(prod.id),
            csrfmiddlewaretoken: csrftoken()
          },
          dataType: 'json',
          async: false, // Sincrónico para aplicar el precio antes de agregar al carrito
          success: function(resp) {
            if (resp.has_price_list && resp.prices && resp.prices[String(prod.id)] !== undefined) {
              const adjusted = resp.prices[String(prod.id)];
              originalPrices[prod.id] = finalPrice;
              const ratio = adjusted / finalPrice;
              finalPrice = adjusted;
              it.price = adjusted;
              it.pvp_final = it.pvp_final * ratio;
            }
          }
        });
      }
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

        // Si hay un único producto cuyo código coincide exactamente con el término, agregarlo directo
        if (list.length === 1) {
          const p = list[0];
          if ((p.code || '').toLowerCase() === term.toLowerCase()) {
            if (p.unit === 'kg') {
              showWeightModal(p);
            } else {
              addOrInc(p);
            }
            $input.val('').focus();
            $suggest.hide().empty();
            return;
          }
        }

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
    // El input muestra PVP con IVA, calcular PVP sin IVA
    let rate = (typeof items[idx].iva_rate !== 'undefined' && !isNaN(parseFloat(items[idx].iva_rate))) ? parseFloat(items[idx].iva_rate) : getIvaRate();
    if (rate > 1) {
      rate = rate / 100;
    }
    // PVP sin IVA = PVP con IVA / (1 + tasa)
    items[idx].price = Math.max(0, v / (1 + rate));
    // Actualizar pvp_final también
    items[idx].pvp_final = v;
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
    let subtotal_neto = 0;  // PVP sin IVA (Base imponible)
    let iva_total = 0;       // IVA total
    let subtotal_con_iva = 0;  // PVP con IVA (Total a cobrar)
    let subtotal_original = 0;  // Subtotal original sin descuento (con IVA)
    
    // Agrupar IVA por alícuota para Libro IVA Digital
    let vat_breakdown = {};  // { '21': { base: 0, amount: 0 }, '10.5': { base: 0, amount: 0 }, ... }
    
    items.forEach(it => {
      const net = parseFloat(it.price) || 0;           // PVP sin IVA (con descuento si aplica)
      const cant = parseFloat(it.cant) || 0;
      const sub_neto = net * cant;
      subtotal_neto += sub_neto;
      
      // Calcular IVA: PVP sin IVA * tasa IVA
      const rate = (typeof it.iva_rate !== 'undefined' && !isNaN(parseFloat(it.iva_rate))) ? parseFloat(it.iva_rate) : getIvaRate(forInvoice);
      // Convert to decimal if it's in percentage format (> 1)
      const rate_decimal = rate > 1 ? rate / 100 : rate;
      const iva_item = net * rate_decimal * cant;
      iva_total += iva_item;
      
      // Agrupar por alícuota para Libro IVA
      const rate_percent = (rate_decimal * 100).toFixed(1); // 21.0, 10.5, 27.0, etc.
      if (!vat_breakdown[rate_percent]) {
        vat_breakdown[rate_percent] = { base: 0, amount: 0 };
      }
      vat_breakdown[rate_percent].base += sub_neto;
      vat_breakdown[rate_percent].amount += iva_item;
      
      // Calcular subtotal con IVA (con descuento)
      const pvp_with_iva = it.pvp_final && !isNaN(parseFloat(it.pvp_final)) ? parseFloat(it.pvp_final) : net * (1 + rate_decimal);
      subtotal_con_iva += pvp_with_iva * cant;
      
      // Calcular subtotal original (sin descuento, con IVA)
      const origPrice = originalPrices[it.id] || net;
      const origPriceWithIva = origPrice * (1 + rate_decimal);
      subtotal_original += origPriceWithIva * cant;
    });
    
    const discount_amount = subtotal_original - subtotal_con_iva;
    
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
    const clientName = $('#selectedClientName').text() || 'Anónimo';
    const priceListId = $('#selectedPriceListId').val() || null;
    const priceListName = $('#selectedPriceListName').text() || null;
    
    const items_with_names = items.map(it => {
      const net = parseFloat(it.price) || 0;
      const cant = parseFloat(it.cant) || 0;
      return {
        id: it.id,
        name: it.name || 'Producto',
        cant,
        price: net,
        pvp: net,
        subtotal: net * cant,
      };
    });
    return {
      subtotal_neto,
      iva_total,
      subtotal_con_iva,
      subtotal_original,
      discount_amount,
      vat_breakdown,  // Desglose de IVA por alícuota para Libro IVA Digital
      items_net: items_with_names,
      items_final,
      client_id: clientId,
      client_name: clientName,
      price_list_id: priceListId,
      price_list_name: priceListName,
    };
  }

  // Función para cargar clientes
  let clientSearchTimer = null;
  function loadClients(searchTerm = '') {
    clearTimeout(clientSearchTimer);
    clientSearchTimer = setTimeout(function() {
      $.ajax({
        url: window.location.pathname,
        type: 'POST',
        data: {
          action: 'search_clients',
          term: searchTerm,
          csrfmiddlewaretoken: csrftoken()
        },
        dataType: 'json',
        success: function(data) {
          const tbody = $('#clientListBody');
          tbody.empty();
          
          if (data.length === 0) {
            tbody.append('<tr><td colspan="4" class="text-center text-muted">No se encontraron clientes</td></tr>');
            return;
          }
          
          data.forEach(function(client) {
            const fullName = (client.names || '') + ' ' + (client.surnames || '');
            const dni = client.dni || '-';
            const address = client.address || '-';
            
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
        error: function(xhr) {
          console.error('Error loading clients:', xhr.responseText);
          showToast('error', 'Error al cargar clientes');
        }
      });
    }, 300);
  }

  // Función global para abrir modal de cliente (accesible desde onclick)
  window.openClientModal = function() {
    const modalEl = document.getElementById('clientSelectModal');
    if (!modalEl) {
      console.error('[POS] Modal clientSelectModal no encontrado');
      return;
    }
    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.show();
    loadClients();
  };

  // Evento para abrir modal de selección de cliente (respaldo jQuery)
  $('#btnSelectClient').on('click', function(e) {
    e.preventDefault();
    e.stopPropagation();
    window.openClientModal();
  });

  // Evento para buscar clientes
  $('#clientSearchInput').on('input', function() {
    const searchTerm = $(this).val();
    loadClients(searchTerm);
  });

  // Evento para consultar padrón AFIP
  $('#btnConsultAfip').on('click', function() {
    const cuit = $('#afipCuitInput').val().trim();
    if (!cuit) {
      showToast('error', 'Ingrese un CUIT');
      return;
    }

    // Validar formato de CUIT (11 dígitos)
    const cuitClean = cuit.replace(/[^0-9]/g, '');
    if (cuitClean.length !== 11) {
      showToast('error', 'El CUIT debe tener 11 dígitos');
      return;
    }

    showToast('info', 'Consultando padrón AFIP...');

    $.ajax({
      url: window.location.pathname,
      type: 'POST',
      data: {
        action: 'consult_afip_padron',
        cuit: cuitClean,
        csrfmiddlewaretoken: csrftoken()
      },
      success: function(response) {
        if (response.success) {
          // Crear cliente automáticamente desde datos AFIP
          createClientFromAfip(response);
        } else if (response.error) {
          showToast('error', 'Error AFIP: ' + response.error);
        }
      },
      error: function() {
        showToast('error', 'Error al consultar padrón AFIP');
      }
    });
  });

  // Función para crear cliente desde datos AFIP
  function createClientFromAfip(afipData) {
    showToast('info', 'Creando cliente desde datos AFIP...');

    $.ajax({
      url: window.location.pathname,
      type: 'POST',
      data: {
        action: 'create_client_from_afip',
        afip_data: JSON.stringify(afipData),
        csrfmiddlewaretoken: csrftoken()
      },
      success: function(response) {
        if (response.success) {
          showToast('success', 'Cliente creado: ' + afipData.name);
          // Seleccionar el cliente creado
          $('#selectedClientId').val(response.client_id);
          $('#selectedClientName').text(afipData.name);
          // Actualizar tipo de comprobante según condición IVA
          updateInvoiceTypeByClientCondition(afipData.condicion_iva);
          // Cerrar modal
          const modalEl = document.getElementById('clientSelectModal');
          const modal = bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
          // Limpiar input
          $('#afipCuitInput').val('');
        } else if (response.error) {
          showToast('error', 'Error al crear cliente: ' + response.error);
        }
      },
      error: function() {
        showToast('error', 'Error al crear cliente');
      }
    });
  }

  // Evento para seleccionar cliente
  $(document).on('click', '.btn-select-client', function() {
    const clientId = $(this).data('client-id');
    const clientName = $(this).data('client-name');

    $('#selectedClientId').val(clientId);
    $('#selectedClientName').text(clientName);

    const modalEl = document.getElementById('clientSelectModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
    showToast('success', 'Cliente seleccionado: ' + clientName);

    // Obtener datos del cliente para determinar tipo de comprobante
    $.ajax({
      url: window.location.pathname,
      type: 'POST',
      data: {
        action: 'get_client_data',
        client_id: clientId,
        csrfmiddlewaretoken: csrftoken()
      },
      success: function(response) {
        if (response && response.condicion_iva) {
          updateInvoiceTypeByClientCondition(response.condicion_iva);
        }
      },
      error: function() {
        console.error('Error al obtener datos del cliente');
      }
    });

    // Aplicar lista de precios si el cliente tiene una
    applyClientPriceList(clientId);
  });

  // Función para actualizar tipo de comprobante según condición IVA del cliente
  function updateInvoiceTypeByClientCondition(condicionIva) {
    const $invoiceType = $('#invoiceType');
    if (!$invoiceType.length) return;

    // Lógica según normativa AFIP:
    // - Responsable Inscripto (RI) → Factura A
    // - Monotributista (M) → Factura B
    // - Consumidor Final (CF) → Factura B
    // - Exento (EX) → Factura B
    // - No Categorizado (NC) → Factura B

    let newInvoiceType = 'B'; // Default: Factura B

    if (condicionIva === 'RI') {
      newInvoiceType = 'A';
      showToast('info', 'Cliente Responsable Inscripto - Cambiando a Factura A');
    } else {
      showToast('info', 'Cliente ' + (condicionIva === 'CF' ? 'Consumidor Final' : condicionIva) + ' - Factura B');
    }

    $invoiceType.val(newInvoiceType);
  }

  // Función para restaurar tipo de comprobante por defecto
  function restoreDefaultInvoiceType() {
    const $invoiceType = $('#invoiceType');
    if (!$invoiceType.length) return;

    // Obtener tipo por defecto del atributo data-default-invoice-type si existe
    const defaultType = $invoiceType.data('default-invoice-type') || 'B';
    $invoiceType.val(defaultType);
    showToast('info', 'Restaurando tipo de comprobante por defecto: Factura ' + defaultType);
  }

  // Guardar precios originales para poder restaurar al limpiar cliente
  // (declarados arriba junto a items)

  function applyClientPriceList(clientId) {
    if (!clientId) return;
    $.ajax({
      url: window.location.pathname,
      type: 'POST',
      data: {
        action: 'get_client_prices',
        client_id: clientId,
        product_ids: '', // Enviar vacío para obtener info de lista sin precios específicos
        csrfmiddlewaretoken: csrftoken()
      },
      dataType: 'json',
      success: function(resp) {
        if (resp.has_price_list) {
          currentPriceList = resp;
          // Si hay items en el carrito, recalcular sus precios
          if (items.length > 0) {
            const productIds = items.map(it => it.id).join(',');
            // Obtener precios para los productos actuales
            $.ajax({
              url: window.location.pathname,
              type: 'POST',
              data: {
                action: 'get_client_prices',
                client_id: clientId,
                product_ids: productIds,
                csrfmiddlewaretoken: csrftoken()
              },
              dataType: 'json',
              success: function(resp2) {
                if (resp2.has_price_list) {
                  items.forEach(it => {
                    if (!originalPrices[it.id]) {
                      originalPrices[it.id] = it.price;
                    }
                    const adjusted = resp2.prices[String(it.id)];
                    if (adjusted !== undefined) {
                      const ratio = adjusted / (originalPrices[it.id] || adjusted);
                      it.price = adjusted;
                      it.pvp_final = (it.pvp_final || 0) * ratio;
                    }
                  });
                  recalc();
                  const interestText = resp.interest_percentage > 0 ? ' + ' + resp.interest_percentage + '% int' : '';
                  showToast('info', 'Lista de precios aplicada: ' + resp.list_name + ' (' + resp.discount_percentage + '% desc' + interestText + ')');
                }
              }
            });
          } else {
            const interestText = resp.interest_percentage > 0 ? ' + ' + resp.interest_percentage + '% int' : '';
            showToast('info', 'Lista de precios activa: ' + resp.list_name + ' (' + resp.discount_percentage + '% desc' + interestText + ')');
          }
        } else {
          restoreOriginalPrices();
        }
      },
      error: function() {
        // Silencioso: si falla, no bloquea la venta
      }
    });
  }

  function restoreOriginalPrices() {
    if (Object.keys(originalPrices).length === 0) return;
    items.forEach(it => {
      if (originalPrices[it.id] !== undefined) {
        const orig = originalPrices[it.id];
        const ratio = orig / (it.price || orig);
        it.price = orig;
        it.pvp_final = (it.pvp_final || 0) * ratio;
      }
    });
    originalPrices = {};
    currentPriceList = null;
    recalc();
  }

  // Evento para limpiar cliente
  $('#btnClearClient').on('click', function() {
    $('#selectedClientId').val('');
    $('#selectedClientName').text('Anónimo');
    restoreOriginalPrices();
    restoreDefaultInvoiceType();
    // También limpiar lista de precios seleccionada manualmente
    $('#selectedPriceListId').val('');
    $('#selectedPriceListName').text('-');
    const modalEl = document.getElementById('clientSelectModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
    showToast('info', 'Cliente limpiado');
  });

  // Función global para abrir modal de lista de precios (accesible desde onclick)
  window.openPriceListModal = function() {
    const modalEl = document.getElementById('priceListSelectModal');
    if (!modalEl) {
      console.error('[POS] Modal priceListSelectModal no encontrado');
      return;
    }
    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.show();
    loadPriceLists();
  };

  // Evento para abrir modal de selección de lista de precios (respaldo jQuery)
  $('#btnSelectPriceList').on('click', function(e) {
    e.preventDefault();
    e.stopPropagation();
    window.openPriceListModal();
  });

  // Cargar listas de precios disponibles
  function loadPriceLists() {
    $.ajax({
      url: window.location.pathname,
      type: 'POST',
      data: {
        action: 'get_price_lists',
        csrfmiddlewaretoken: csrftoken()
      },
      dataType: 'json',
      success: function(resp) {
        const tbody = $('#priceListTableBody');
        tbody.empty();
        
        if (resp.length === 0) {
          tbody.append('<tr><td colspan="2" class="text-center text-muted">No hay listas de precios disponibles</td></tr>');
          return;
        }
        
        resp.forEach(pl => {
          const infoText = `${pl.discount_percentage}% desc` + (pl.interest_percentage > 0 ? ` + ${pl.interest_percentage}% int` : '');
        tbody.append(`
            <tr>
              <td>${pl.name} <span class="text-muted small">(${infoText})</span></td>
              <td>
                <button class="btn btn-sm btn-outline-primary" onclick="selectPriceList(${pl.id}, '${pl.name}', ${pl.discount_percentage}, ${pl.interest_percentage})">
                  <i class="fas fa-check"></i> Seleccionar
                </button>
              </td>
            </tr>
          `);
        });
      },
      error: function() {
        showToast('error', 'Error al cargar listas de precios');
      }
    });
  }

  // Seleccionar lista de precios
  window.selectPriceList = function(priceListId, priceListName, discountPercentage, interestPercentage) {
    $('#selectedPriceListId').val(priceListId);
    $('#selectedPriceListName').text(priceListName);
    
    // Guardar precios originales si no están guardados
    if (Object.keys(originalPrices).length === 0) {
      items.forEach(it => {
        originalPrices[it.id] = it.price;
      });
    }
    
    // Aplicar lista de precios
    currentPriceList = {
      list_name: priceListName,
      discount_percentage: discountPercentage,
      interest_percentage: interestPercentage || 0,
      has_price_list: true
    };
    
    // Obtener precios ajustados para los productos actuales
    if (items.length > 0) {
      const productIds = items.map(it => it.id).join(',');
      $.ajax({
        url: window.location.pathname,
        type: 'POST',
        data: {
          action: 'get_price_list_prices',
          price_list_id: priceListId,
          product_ids: productIds,
          csrfmiddlewaretoken: csrftoken()
        },
        dataType: 'json',
        success: function(resp) {
          if (resp.has_price_list) {
            items.forEach(it => {
              const newPrice = resp.prices[String(it.id)];
              if (newPrice && newPrice !== it.price) {
                it.price = newPrice; // Precio neto con descuento (sin IVA)
                // Calcular pvp_final con IVA
                const rate = (typeof it.iva_rate !== 'undefined' && !isNaN(parseFloat(it.iva_rate))) ? parseFloat(it.iva_rate) : getIvaRate();
                const rate_decimal = rate > 1 ? rate / 100 : rate;
                it.pvp_final = newPrice * (1 + rate_decimal); // Precio con IVA
              }
            });
            recalc();
            showToast('success', `Lista "${priceListName}" aplicada`);
          }
        },
        error: function() {
          showToast('error', 'Error al aplicar lista de precios');
        }
      });
    } else {
      recalc();
      showToast('success', `Lista "${priceListName}" seleccionada`);
    }
    
    // Cerrar modal
    const modalEl = document.getElementById('priceListSelectModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
  };

  // Evento para limpiar lista de precios
  $('#btnClearPriceList').on('click', function() {
    $('#selectedPriceListId').val('');
    $('#selectedPriceListName').text('-');
    restoreOriginalPrices();
    const modalEl = document.getElementById('priceListSelectModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
    showToast('info', 'Lista de precios limpiada');
  });

  function showAfipInfo(resp) {
    const infoBox = document.getElementById('afipInfoBox');
    const errorBox = document.getElementById('afipErrorBox');
    if (!infoBox || !errorBox) return;
    infoBox.style.display = 'none';
    errorBox.style.display = 'none';
    if (resp.afip_error) {
      errorBox.style.display = '';
      document.getElementById('afipErrorText').textContent = 'AFIP: ' + resp.afip_error;
      // Mostrar toast de error más visible
      showToast('error', 'Error AFIP: ' + resp.afip_error);
    } else if (resp.afip_cae) {
      infoBox.style.display = '';
      document.getElementById('afipCaeText').textContent = resp.afip_cae;
      document.getElementById('afipVtoText').textContent = resp.afip_cae_vto || '-';
      if (resp.afip_qr) {
        document.getElementById('afipQrImg').src = resp.afip_qr;
      }
    }
  }

  function doCreateSale() {
    const calc = buildPayload(false); // Ticket
    const subtotal = calc.subtotal_neto; // Subtotal = PVP sin IVA (neto)
    const iva = calc.iva_total; // IVA total
    const total = calc.subtotal_con_iva; // Total a Pagar = Subtotal + IVA
    const payMethod = ($('#payMethod').val() || 'cash');
    const invoiceType = ($('#invoiceType').val() || 'B'); // Tipo de factura seleccionado

    // Manejar notas de crédito (NC-A, NC-B, NC-C)
    let isCreditNote = false;
    let invoiceLetter = invoiceType;
    if (invoiceType.startsWith('NC-')) {
      isCreditNote = true;
      invoiceLetter = invoiceType.split('-')[1]; // Extraer A, B, o C
    }

    // Generar token único para esta venta
    const saleToken = 'sale_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    const payload = {
      cli: calc.client_id,
      items: calc.items_net,     // Detalle con precio neto
      subtotal, iva, total,
      vat_breakdown: calc.vat_breakdown,  // Desglose de IVA por alícuota
      payment_method: payMethod,
      invoice_type: invoiceLetter, // Letra de factura (A, B, C)
      is_credit_note: isCreditNote, // Indicador de nota de crédito
      sale_token: saleToken  // Agregar token
    };
    
    // Agregar datos de tarjeta si corresponde
    if (payMethod === 'card' && window.cardPaymentData) {
      payload.card_type = window.cardPaymentData.card_type;
      payload.card_brand = window.cardPaymentData.card_brand;
      payload.card_plan_id = window.cardPaymentData.card_plan_id;
      payload.card_auth_code = window.cardPaymentData.card_auth_code;
      
      // Si es crédito con cuotas, recalcular total con multiplicador
      if (window.cardPaymentData.card_type === 'credit' && window.cardPaymentData.card_plan_id) {
        const cardPlanOption = $('#cardPlan').find(':selected');
        const multiplier = parseFloat(cardPlanOption.data('multiplier'));
        console.log('[DEBUG] Multiplicador para cálculo (doCreateSale):', multiplier);
        
        let effMultiplier = (!isNaN(multiplier) && multiplier > 0) ? multiplier : 1;
        if (effMultiplier !== 1) {
          payload.subtotal = (subtotal * effMultiplier).toFixed(2);
          payload.iva = (iva * effMultiplier).toFixed(2);
          payload.total = (total * effMultiplier).toFixed(2);
          console.log('[DEBUG] Totales con recargo - Subtotal:', payload.subtotal, 'IVA:', payload.iva, 'Total:', payload.total);
        } else {
          console.log('[DEBUG] Multiplicador 1 o 0, sin recargo');
        }
      }
      
      // Limpiar datos de tarjeta después de usar
      window.cardPaymentData = null;
    }
    ajaxAction('create_sale', { action: 'create_sale', sale: JSON.stringify(payload), sale_token: saleToken })
      .done(resp => {
        if (resp && resp.id) {
          lastSaleId = resp.id;
          flashSummary();
          showToast('success', 'Venta registrada correctamente.');
          showAfipInfo(resp);
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
    const subtotal = calc.subtotal_neto; // Subtotal = PVP sin IVA (neto)
    const iva = calc.iva_total;
    const total = calc.subtotal_con_iva; // Total a Pagar = Subtotal + IVA
    const payMethod = ($('#payMethod').val() || 'cash');
    const invoiceType = ($('#invoiceType').val() || 'B'); // Tipo de factura seleccionado

    // Manejar notas de crédito (NC-A, NC-B, NC-C)
    let isCreditNote = false;
    let invoiceLetter = invoiceType;
    if (invoiceType.startsWith('NC-')) {
      isCreditNote = true;
      invoiceLetter = invoiceType.split('-')[1]; // Extraer A, B, o C
    }

    // Generar token único para esta factura
    const saleToken = 'invoice_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    const payload = {
      cli: calc.client_id,
      items: calc.items_final,   // Detalle con IVA incluido
      subtotal, iva, total,
      vat_breakdown: calc.vat_breakdown,  // Desglose de IVA por alícuota
      payment_method: payMethod,
      invoice_type: invoiceLetter, // Letra de factura (A, B, C)
      is_credit_note: isCreditNote, // Indicador de nota de crédito
      sale_token: saleToken  // Agregar token
    };
    
    // Agregar datos de tarjeta si corresponde
    if (payMethod === 'card' && window.cardPaymentData) {
      payload.card_type = window.cardPaymentData.card_type;
      payload.card_brand = window.cardPaymentData.card_brand;
      payload.card_plan_id = window.cardPaymentData.card_plan_id;
      payload.card_auth_code = window.cardPaymentData.card_auth_code;
      
      // Si es crédito con cuotas, recalcular total con multiplicador
      if (window.cardPaymentData.card_type === 'credit' && window.cardPaymentData.card_plan_id) {
        const cardPlanOption = $('#cardPlan').find(':selected');
        const multiplier = parseFloat(cardPlanOption.data('multiplier'));
        console.log('[DEBUG] Multiplicador para cálculo (doInvoiceSale):', multiplier);
        
        let effMultiplier = (!isNaN(multiplier) && multiplier > 0) ? multiplier : 1;
        if (effMultiplier !== 1) {
          payload.subtotal = (subtotal * effMultiplier).toFixed(2);
          payload.iva = (iva * effMultiplier).toFixed(2);
          payload.total = (total * effMultiplier).toFixed(2);
          console.log('[DEBUG] Totales con recargo - Subtotal:', payload.subtotal, 'IVA:', payload.iva, 'Total:', payload.total);
        } else {
          console.log('[DEBUG] Multiplicador 1 o 0, sin recargo');
        }
      }
      
      // Limpiar datos de tarjeta después de usar
      window.cardPaymentData = null;
    }
    ajaxAction('invoice', { action: 'invoice', sale: JSON.stringify(payload), sale_token: saleToken })
      .done(resp => {
        if (resp && resp.id) {
          lastSaleId = resp.id;
          flashSummary();
          showToast('success', 'Factura generada correctamente.');
          showAfipInfo(resp);
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

  function doCreateBudget() {
    const calc = buildPayload(false); // Usar precios netos (sin IVA)
    const subtotal = calc.subtotal_con_iva; // Usar subtotal con IVA
    const iva = 0; // Presupuestos no tienen IVA
    const total = subtotal;
    const payMethod = ($('#payMethod').val() || 'cash');
    const budgetNotes = $('#budgetNotes').val() || '';
    
    // Llenar modal de confirmación
    $('#budgetConfirmClient').text(calc.client_name || 'Cliente no seleccionado');
    $('#budgetConfirmNotes').text(budgetNotes || 'Sin notas');
    
    // Llenar tabla de items
    const tbody = $('#budgetConfirmItems');
    tbody.empty();
    
    calc.items_net.forEach(item => {
      const row = `
        <tr>
          <td>${item.name}</td>
          <td class="text-center">${item.cant}</td>
          <td class="text-end">${fmt(item.pvp)}</td>
          <td class="text-end">${fmt(item.cant * item.pvp)}</td>
        </tr>
      `;
      tbody.append(row);
    });
    
    // Llenar totales
    $('#budgetConfirmItemsCount').text(calc.items_net.length);
    $('#budgetConfirmSubtotal').text(fmt(subtotal));
    $('#budgetConfirmIva').text('$0.00');
    $('#budgetConfirmTotal').text(fmt(total));
    
    // Guardar datos para enviar después de confirmar
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    const dateStr = now.getFullYear() + '-' + pad(now.getMonth()+1) + '-' + pad(now.getDate()) + ' ' + pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
    window.budgetPayload = {
      cli: calc.client_id,
      products: calc.items_net.map(it => ({ id: it.id, cant: it.cant, price: it.price, subtotal: it.subtotal })),
      subtotal, iva, total,
      payment_method: payMethod,
      is_budget: true,
      budget_notes: budgetNotes,
      date_joined: dateStr,
      sale_token: 'budget_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
    };
    
    // Mostrar modal
    const modal = new bootstrap.Modal(document.getElementById('budgetConfirmModal'));
    modal.show();
  }

  // Mostrar/ocultar campo de importe recibido según método de pago
  function updateCashPaymentSection() {
    const payMethod = $('#payMethod').val();
    const $cashSection = $('#cashPaymentSection');
    
    if (payMethod === 'cash') {
      $cashSection.show();
      // Calcular vuelto inicial
      calculateChange();
    } else {
      $cashSection.hide();
    }
  }

  // Calcular vuelto
  function calculateChange() {
    const total = parseFloat($('#tTotal').text().replace('$', '').replace(/,/g, '')) || 0;
    const amountReceived = parseFloat($('#amountReceived').val()) || 0;
    const change = amountReceived - total;
    
    $('#changeAmount').text(fmt(change >= 0 ? change : 0));
    
    // Si el importe recibido es menor al total, mostrar en rojo
    if (change < 0) {
      $('#changeAmount').removeClass('text-success').addClass('text-danger');
    } else {
      $('#changeAmount').removeClass('text-danger').addClass('text-success');
    }
  }

  // Event listener para cambio de método de pago
  $('#payMethod').on('change', function() {
    updateCashPaymentSection();
  });

  // Event listener para cambio de importe recibido
  $('#amountReceived').on('input', function() {
    calculateChange();
  });

  // Actualizar vuelto y resumen de cuenta corriente cuando cambian los totales
  const originalRecalc = recalc;
  recalc = function() {
    originalRecalc();
    calculateChange();
    updateEmployeeAccountSummary();
  };

  // Inicializar estado del campo de efectivo
  updateCashPaymentSection();

  // Botón principal: abrir modal para elegir modo de registro
  $('#btnCheckout').on('click', function () {
    // Prevenir doble clic
    if ($(this).prop('disabled')) return;
    
    if (!items.length) { showToast('warning', 'No hay ítems en el carrito.'); return; }
    
    // Verificar si se seleccionó pagos combinados
    const payMethod = $('#payMethod').val();
    console.log('[DEBUG] Método de pago seleccionado:', payMethod);
    
    if (payMethod === 'combined') {
      openCombinedPaymentModal();
      return;
    }
    
    // Si el método de pago es tarjeta, abrir modal de selección de tarjeta
    if (payMethod === 'card') {
      console.log('[DEBUG] Abriendo modal de tarjeta...');
      openCardPaymentModal();
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

  // Funciones para pagos con tarjeta
  function openCardPaymentModal() {
    // Resetear modal
    $('#cardDebit').prop('checked', false);
    $('#cardCredit').prop('checked', true);
    $('#cardBrand').val('visa');
    $('#cardPlan').val('');
    $('#cardAuthCode').val('');
    $('#installmentInfo').hide();
    $('#creditOptions').show();
    $('#cardInfoText').text('Seleccione las opciones de tarjeta para continuar');
    
    // Filtrar planes por marca inicial
    $('#cardBrand').trigger('change');
    
    const modal = new bootstrap.Modal(document.getElementById('cardPaymentModal'));
    modal.show();
  }
  
  // Manejar cambio de tipo de tarjeta
  $(document).on('change', 'input[name="cardType"]', function() {
    const cardType = $(this).val();
    if (cardType === 'debit') {
      $('#creditOptions').hide();
      $('#cardInfoText').text('Pago con tarjeta de débito - sin recargo');
    } else {
      $('#creditOptions').show();
      $('#cardInfoText').text('Seleccione el plan de cuotas para ver el recargo');
    }
  });
  
  // Manejar cambio de marca de tarjeta - filtrar planes por marca
  $(document).on('change', '#cardBrand', function() {
    const brand = $(this).val();
    const $planSelect = $('#cardPlan');
    const $options = $planSelect.find('option');
    
    // Mostrar solo las opciones que coinciden con la marca (o la opción vacía)
    $options.each(function() {
      const optBrand = $(this).data('card-brand');
      if (!optBrand || optBrand === brand) {
        $(this).show().prop('disabled', false);
      } else {
        $(this).hide().prop('disabled', true);
      }
    });
    
    // Resetear selección
    $planSelect.val('');
    $('#installmentInfo').hide();
    
    // Actualizar info
    if ($planSelect.find('option:not(:disabled)').length > 1) {
      $('#cardInfoText').text('Seleccione el plan de cuotas para ver el recargo');
    } else {
      $('#cardInfoText').text('No hay planes disponibles para esta marca');
    }
  });
  
  // Manejar cambio de plan de cuotas
  $(document).on('change', '#cardPlan', function() {
    const selectedOption = $(this).find(':selected');
    const installments = parseFloat(selectedOption.data('installments'));
    let multiplier = parseFloat(selectedOption.data('multiplier'));
    
    if (isNaN(multiplier) || multiplier <= 0) {
      multiplier = 1; // Sin recargo
    }
    
    if (installments && !isNaN(installments) && installments > 0) {
      // Obtener el total real del carrito desde el DOM
      const originalTotal = parseFormattedAmount($('#tTotal').text());
      
      const newTotal = originalTotal * multiplier;
      const installmentAmount = newTotal / installments;
      const surchargeAmount = newTotal - originalTotal;
      const surchargePercent = ((multiplier - 1) * 100).toFixed(1);
      
      $('#cardOriginalTotal').text(fmt(originalTotal));
      if (surchargeAmount > 0.01) {
        $('#cardSurcharge').text(fmt(surchargeAmount) + ' (' + surchargePercent + '%)');
      } else {
        $('#cardSurcharge').text('Sin recargo');
      }
      $('#cardNewTotal').text(fmt(newTotal));
      $('#installmentCount').text(installments);
      $('#installmentAmount').text(fmt(installmentAmount));
      $('#installmentInfo').show();
      if (surchargeAmount > 0.01) {
        $('#cardInfoText').text('Plan seleccionado: ' + installments + ' cuotas con recargo del ' + surchargePercent + '%');
      } else {
        $('#cardInfoText').text('Plan seleccionado: ' + installments + ' cuotas sin recargo');
      }
    } else {
      $('#installmentInfo').hide();
      $('#cardInfoText').text('Seleccione un plan de cuotas');
    }
  });
  
  // Confirmar pago con tarjeta
  $(document).on('click', '#btnConfirmCardPayment', function() {
    const cardType = $('input[name="cardType"]:checked').val();
    const cardBrand = $('#cardBrand').val();
    const cardPlan = $('#cardPlan').val();
    const cardAuthCode = $('#cardAuthCode').val();
    
    if (!cardType) {
      showToast('warning', 'Debe seleccionar el tipo de tarjeta');
      return;
    }
    
    if (cardType === 'credit' && !cardPlan) {
      showToast('warning', 'Debe seleccionar un plan de cuotas');
      return;
    }
    
    // Guardar datos de tarjeta en variable global para usar en la venta
    window.cardPaymentData = {
      card_type: cardType,
      card_brand: cardBrand,
      card_plan_id: cardPlan || null,
      card_auth_code: cardAuthCode
    };
    
    // Cerrar modal y continuar con el flujo normal
    bootstrap.Modal.getInstance(document.getElementById('cardPaymentModal')).hide();
    
    // Abrir modal de modo de venta (ticket vs factura)
    const modalEl = document.getElementById('saleModeModal');
    if (modalEl) {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    } else {
      doCreateSale();
    }
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
    
    // Deshabilitar y ocultar el método ya elegido en el segundo select
    $('#secondPaymentMethod option').prop('disabled', false).show();
    $('#secondPaymentMethod option[value="' + firstMethod + '"]').prop('disabled', true).hide();
    // Si el valor actual es el deshabilitado, cambiar al primero disponible
    if ($('#secondPaymentMethod').val() === firstMethod) {
      const firstAvailable = $('#secondPaymentMethod option:not(:disabled)').first().val();
      $('#secondPaymentMethod').val(firstAvailable);
    }
    
    // Establecer el segundo pago con el restante
    const secondPaymentValue = remaining.toFixed(2);
    $('#secondPaymentAmount').val(secondPaymentValue);
    
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
      payment_method: 'combined',
      payment_method_desc: paymentDescription,
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

  // Funcionalidad para cuenta corriente
  let clients = [];

  // Cargar clientes al abrir el modal
  $(document).on('show.bs.modal', '#employeeAccountModal', function () {
    loadClients();
    updateEmployeeAccountSummary();
  });

  function loadClients() {
    $.ajax({
      url: window.location.pathname,
      type: 'POST',
      data: {
        action: 'get_clients',
        csrfmiddlewaretoken: csrftoken()
      },
      success: function(response) {
        clients = response;
        const $select = $('#employeeSelect');
        $select.empty().append('<option value="">Seleccione un cliente...</option>');
        clients.forEach(cli => {
          $select.append(`<option value="${cli.id}">${cli.name}</option>`);
        });
      },
      error: function() {
        showToast('error', 'Error al cargar clientes');
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

  // La función recalc ya fue modificada para incluir updateEmployeeAccountSummary()

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

  // Botón para crear presupuesto (solo para usuarios Servidor Local)
  $('#btnCreateBudget').on('click', function() {
    console.log('[DEBUG] btnCreateBudget click, items.length=', items.length);
    if (items.length === 0) {
      showToast('warning', 'Debe agregar productos antes de crear un presupuesto');
      return;
    }
    
    doCreateBudget();
  });

  // Botón para confirmar creación de presupuesto
  $('#btnConfirmBudget').on('click', function() {
    console.log('[DEBUG] btnConfirmBudget click, budgetPayload=', window.budgetPayload);
    if (!window.budgetPayload) {
      showToast('error', 'Error: no hay datos del presupuesto');
      return;
    }
    
    // Cerrar modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('budgetConfirmModal'));
    modal.hide();
    
    // Enviar datos al backend
    console.log('[DEBUG] Enviando presupuesto al backend...');
    ajaxAction('create_sale', { action: 'create_sale', sale: JSON.stringify(window.budgetPayload), sale_token: window.budgetPayload.sale_token })
      .done(resp => {
        console.log('[DEBUG] Respuesta del backend:', resp);
        if (resp && resp.id) {
          lastSaleId = resp.id;
          flashSummary();
          showToast('success', 'Presupuesto creado correctamente. ID: ' + resp.id);
          
          // Limpiar campos
          $('#budgetNotes').val('');
          $('#btnClear').trigger('click');
          window.budgetPayload = null;
          
          // Recargar página para mostrar el presupuesto en la lista
          setTimeout(() => {
            window.location.reload();
          }, 1000);
        }
      })
      .fail(jq => {
        console.error('[DEBUG] Error AJAX presupuesto:', jq.responseText, jq.status, jq.statusText);
        showToast('error', 'Error al crear presupuesto: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
      });
  });

  // Botón para agregar nuevo empleado (desactivado, ahora se usan clientes)
  // $('#btnAddEmployee').on('click', function() { ... });

  // Guardar nuevo empleado (desactivado)
  /*
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

*/

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

  // Confirmar cuenta corriente
  $(document).on('click', '#btnConfirmEmployeeAccount', function() {
    const clientId = $('#employeeSelect').val();
    const notes = $('#employeeNotes').val();
    const isCombinedPayment = $('#employeeCombinedPayment').is(':checked');

    if (!clientId) {
      showToast('warning', 'Debe seleccionar un cliente');
      return;
    }

    if (items.length === 0) {
      showToast('warning', 'Debe agregar productos antes de registrar una cuenta corriente');
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
    // Para clientes en cuenta corriente, el IVA es 0
    const iva = 0;
    const total = subtotal + iva;

    const saleData = {
      client_id: clientId,
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

  // Anular venta desde el POS sin salir de la pagina
  $(document).on('click', '.btn-anular-venta', function(e) {
    e.preventDefault();
    const saleId = $(this).data('sale-id');
    const saleInfo = $(this).data('sale-info');
    const $btn = $(this);

    if (!confirm('¿Anular la venta?\n\n' + saleInfo + '\n\nEsta acción restaurará el stock y eliminará la venta.')) {
      return;
    }

    $btn.prop('disabled', true).find('i').removeClass('fa-ban').addClass('fa-spinner fa-spin');

    $.ajax({
      url: '/erp/sale/delete/' + saleId + '/',
      type: 'POST',
      data: { csrfmiddlewaretoken: csrftoken() },
      success: function(resp) {
        if (resp.error) {
          showToast('error', 'Error al anular: ' + resp.error);
          $btn.prop('disabled', false).find('i').removeClass('fa-spinner fa-spin').addClass('fa-ban');
        } else {
          showToast('success', 'Venta anulada correctamente');
          $btn.closest('tr').fadeOut(400, function() { $(this).remove(); });
        }
      },
      error: function(jq) {
        showToast('error', 'Error al anular venta: ' + (jq.responseJSON ? jq.responseJSON.error : jq.statusText));
        $btn.prop('disabled', false).find('i').removeClass('fa-spinner fa-spin').addClass('fa-ban');
      }
    });
  });

  // Inicializar
  recalc();
  $input.focus();

  // === Atajos de teclado: Doble Enter = Confirmar, Esc = Cerrar ===

  // Mapa de modales a su botón primario de confirmación
  const modalConfirmButtons = {
    'genericProductModal': 'btnGenericProductSave',
    'saleModeModal': 'btnModeInvoice',
    'printTicketModal': 'btnPrintTicket',
    'combinedPaymentModal': 'btnCombinedPaymentStep2',
    'combinedPaymentStep2Modal': 'btnCombinedPaymentConfirm',
    'employeeAccountModal': 'btnConfirmEmployeeAccount',
    'addEmployeeModal': 'btnSaveEmployee',
    'cardPaymentModal': 'btnConfirmCardPayment',
  };

  let lastEnterTime = 0;
  const DOUBLE_ENTER_DELAY = 400; // ms entre enters

  $(document).on('keydown', function(e) {
    // === Esc: cerrar modal visible ===
    if (e.key === 'Escape') {
      for (const [modalId, _] of Object.entries(modalConfirmButtons)) {
        const modalEl = document.getElementById(modalId);
        if (modalEl && modalEl.classList.contains('show')) {
          e.preventDefault();
          const modal = bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
          return;
        }
      }
      return;
    }

    // === Doble Enter: confirmar ===
    if (e.key === 'Enter') {
      const now = Date.now();
      const isDouble = (now - lastEnterTime) < DOUBLE_ENTER_DELAY;
      lastEnterTime = now;

      if (!isDouble) return;

      // Reset para que no se dispare nuevamente
      lastEnterTime = 0;

      // Si hay un modal visible, clickear su botón de confirmación
      for (const [modalId, btnId] of Object.entries(modalConfirmButtons)) {
        const modalEl = document.getElementById(modalId);
        if (modalEl && modalEl.classList.contains('show')) {
          e.preventDefault();
          const btn = document.getElementById(btnId);
          if (btn && !btn.disabled) {
            btn.click();
          }
          return;
        }
      }

      // Si no hay modal visible, clickear el botón principal de venta
      const btnCheckout = document.getElementById('btnCheckout');
      const btnBudget = document.getElementById('btnCreateBudget');
      if (btnCheckout && !btnCheckout.disabled) {
        e.preventDefault();
        btnCheckout.click();
      } else if (btnBudget && !btnBudget.disabled) {
        e.preventDefault();
        btnBudget.click();
      }
    }
  });
})();