/**
 * Funcionalidad principal del Punto de Venta (POS)
 */

// Variables globales del POS
let posItems = [];
let selectedClient = null;

/**
 * Inicializa el POS
 */
document.addEventListener('DOMContentLoaded', function() {
  initBarcodeInput();
  initButtons();
  initKeyboardShortcuts();
  initScanPoll();
});

/**
 * Inicializa el input de código de barras
 */
function initBarcodeInput() {
  const barcodeInput = document.getElementById('barcodeInput');
  if (!barcodeInput) return;
  
  barcodeInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      addProductByBarcode(this.value);
      this.value = '';
    }
  });
  
  // Autocompletado/sugerencias
  barcodeInput.addEventListener('input', function() {
    if (this.value.length >= 2) {
      showSuggestions(this.value);
    } else {
      hideSuggestions();
    }
  });
}

/**
 * Inicializa los botones del POS
 */
function initButtons() {
  // Botón limpiar
  const btnClear = document.getElementById('btnClear');
  if (btnClear) {
    btnClear.addEventListener('click', clearPos);
  }

  // Nota: Los botones de producto genérico, cliente, checkout,
  // cuenta corriente y presupuesto se manejan en pos.js para evitar
  // handlers duplicados que causan dobles backdrops de modal.
}

/**
 * Inicializa atajos de teclado
 */
function initKeyboardShortcuts() {
  document.addEventListener('keydown', function(e) {
    // F2 - Registrar venta
    if (e.key === 'F2') {
      e.preventDefault();
      const btnCheckout = document.getElementById('btnCheckout');
      if (btnCheckout && !btnCheckout.disabled) {
        processSale();
      }
    }
    
    // F3 - Cuenta corriente empleado
    if (e.key === 'F3') {
      e.preventDefault();
      const btnEmployeeAccount = document.getElementById('btnEmployeeAccount');
      if (btnEmployeeAccount && !btnEmployeeAccount.disabled) {
        processEmployeeAccount();
      }
    }
    
    // F4 - Crear presupuesto
    if (e.key === 'F4') {
      e.preventDefault();
      const btnCreateBudget = document.getElementById('btnCreateBudget');
      if (btnCreateBudget && !btnCreateBudget.disabled) {
        processBudget();
      }
    }
    
    // Delete - Eliminar item seleccionado
    if (e.key === 'Delete') {
      const selectedRow = document.querySelector('#posItems tbody tr.selected');
      if (selectedRow) {
        const index = selectedRow.dataset.index;
        removeItem(parseInt(index));
      }
    }
  });
}

/**
 * Agrega un producto por código de barras
 */
function addProductByBarcode(barcode) {
  if (!barcode) return;
  
  fetch(`/erp/api/product/by-barcode/${barcode}/`)
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        showToast('Error', data.error, 'danger');
        return;
      }
      addItemToPos(data);
    })
    .catch(error => {
      console.error('Error al buscar producto:', error);
      showToast('Error', 'No se pudo encontrar el producto', 'danger');
    });
}

/**
 * Agrega un item a la lista del POS
 */
function addItemToPos(product) {
  const existingIndex = posItems.findIndex(item => item.id === product.id);
  
  if (existingIndex >= 0) {
    posItems[existingIndex].quantity += 1;
  } else {
    posItems.push({
      id: product.id,
      name: product.name,
      price: product.price,
      quantity: 1,
      iva: product.iva || 21
    });
  }
  
  updatePosTable();
  updateTotals();
}

/**
 * Actualiza la tabla del POS
 */
function updatePosTable() {
  const tbody = document.querySelector('#posItems tbody');
  if (!tbody) return;
  
  tbody.innerHTML = posItems.map((item, index) => `
    <tr data-index="${index}" class="${index === posItems.length - 1 ? 'selected' : ''}">
      <td>${item.name}</td>
      <td class="text-center">${item.quantity}</td>
      <td class="text-end">${formatCurrency(item.price)}</td>
      <td class="text-end">${formatCurrency(item.price * item.quantity)}</td>
      <td class="text-center">
        <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeItem(${index})">
          <i class="fas fa-trash"></i>
        </button>
      </td>
    </tr>
  `).join('');
}

/**
 * Elimina un item del POS
 */
function removeItem(index) {
  posItems.splice(index, 1);
  updatePosTable();
  updateTotals();
}

/**
 * Limpia el POS
 */
function clearPos() {
  posItems = [];
  selectedClient = null;
  updatePosTable();
  updateTotals();
  const elClientName = document.getElementById('selectedClientName');
  const elClientId = document.getElementById('selectedClientId');
  if (elClientName) elClientName.textContent = 'Anónimo';
  if (elClientId) elClientId.value = '';
}

/**
 * Actualiza los totales del POS
 */
function updateTotals() {
  const subtotal = posItems.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  const iva = subtotal * 0.21; // 21% IVA
  const total = subtotal + iva;
  
  const elItems = document.getElementById('tItems');
  const elSubtotal = document.getElementById('tSubtotal');
  const elIva = document.getElementById('tIva');
  const elTotal = document.getElementById('tTotal');
  
  if (elItems) elItems.textContent = posItems.reduce((sum, item) => sum + item.quantity, 0);
  if (elSubtotal) elSubtotal.textContent = formatCurrency(subtotal);
  if (elIva) elIva.textContent = formatCurrency(iva);
  if (elTotal) elTotal.textContent = formatCurrency(total);
}

/**
 * Muestra un toast de notificación
 */
function showToast(title, message, type = 'info') {
  const toast = document.getElementById('posToast');
  if (!toast) return;
  
  document.getElementById('posToastTitle').textContent = title;
  document.getElementById('posToastBody').textContent = message;
  
  const toastElement = new bootstrap.Toast(toast);
  toastElement.show();
}

/**
 * Muestra sugerencias de productos
 */
function showSuggestions(query) {
  // Implementar búsqueda de productos
  const suggestions = document.getElementById('suggestions');
  if (!suggestions) return;
  
  fetch(`/erp/api/product/search/?q=${query}`)
    .then(response => response.json())
    .then(data => {
      if (data.results && data.results.length > 0) {
        suggestions.innerHTML = data.results.map(product => `
          <a href="#" class="list-group-item list-group-item-action" data-barcode="${product.barcode}">
            ${product.name} - ${formatCurrency(product.price)}
          </a>
        `).join('');
        suggestions.style.display = 'block';
        
        // Agregar event listeners
        suggestions.querySelectorAll('a').forEach(link => {
          link.addEventListener('click', function(e) {
            e.preventDefault();
            addProductByBarcode(this.dataset.barcode);
            hideSuggestions();
          });
        });
      } else {
        hideSuggestions();
      }
    })
    .catch(() => hideSuggestions());
}

/**
 * Oculta las sugerencias
 */
function hideSuggestions() {
  const suggestions = document.getElementById('suggestions');
  if (suggestions) {
    suggestions.style.display = 'none';
  }
}

/**
 * Muestra el modal de producto genérico
 */
function showGenericProductModal() {
  const modal = new bootstrap.Modal(document.getElementById('genericProductModal'));
  modal.show();
}

/**
 * Muestra el modal de selección de cliente
 */
function showClientModal() {
  const modal = new bootstrap.Modal(document.getElementById('clientSelectModal'));
  modal.show();
}

/**
 * Procesa una venta normal
 */
function processSale() {
  if (posItems.length === 0) {
    showToast('Error', 'No hay items en la venta', 'warning');
    return;
  }
  
  const modal = new bootstrap.Modal(document.getElementById('saleModeModal'));
  modal.show();
}

/**
 * Procesa una venta a cuenta corriente de empleado
 */
function processEmployeeAccount() {
  if (posItems.length === 0) {
    showToast('Error', 'No hay items en la venta', 'warning');
    return;
  }
  
  const modal = new bootstrap.Modal(document.getElementById('employeeAccountModal'));
  modal.show();
}

/**
 * Procesa un presupuesto
 */
function processBudget() {
  if (posItems.length === 0) {
    showToast('Error', 'No hay items en el presupuesto', 'warning');
    return;
  }
  
  // Implementar lógica de presupuesto
  showToast('Info', 'Funcionalidad de presupuesto en desarrollo', 'info');
}

/**
 * Poll de códigos escaneados desde el celular
 * Consulta al servidor cada 2 segundos si hay nuevos scans
 */
function initScanPoll() {
  setInterval(function() {
    fetch('/erp/api/scan/poll/')
      .then(response => response.json())
      .then(data => {
        if (data.codes && data.codes.length > 0) {
          data.codes.forEach(function(code) {
            addProductByBarcode(code);
          });
        }
      })
      .catch(function(err) {
        // Silencioso: el servidor puede no estar disponible
      });
  }, 2000);
}
