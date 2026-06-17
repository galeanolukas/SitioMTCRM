/**
 * Utilidades para formateo de moneda y números
 */

/**
 * Formatea un monto como moneda con separadores de miles
 * @param {number} amount - El monto a formatear
 * @param {string} locale - Locale para formateo (default: 'es-AR')
 * @returns {string} - Monto formateado como moneda
 */
function formatCurrency(amount, locale = 'es-AR') {
  if (isNaN(amount)) amount = 0;
  return '$' + Number(amount).toLocaleString(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

/**
 * Parsea un string de moneda formateado a número
 * @param {string} formatted - String formateado (ej: "$1.234,56")
 * @returns {number} - Valor numérico
 */
function parseCurrency(formatted) {
  if (!formatted) return 0;
  const clean = formatted.toString().replace('$', '').replace(/\./g, '').replace(',', '.');
  return parseFloat(clean) || 0;
}

/**
 * Actualiza el formato de los totales en el DOM
 */
function updateTotalsFormat() {
  const subtotal = parseCurrency($('#tSubtotal').text());
  const iva = parseCurrency($('#tIva').text());
  const total = parseCurrency($('#tTotal').text());
  
  $('#tSubtotal').text(formatCurrency(subtotal));
  $('#tIva').text(formatCurrency(iva));
  $('#tTotal').text(formatCurrency(total));
}
