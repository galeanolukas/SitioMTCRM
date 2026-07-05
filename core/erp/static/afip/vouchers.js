document.addEventListener('DOMContentLoaded', function() {
    if ($('#data').length) {
        $('#data').DataTable({
            responsive: true,
            lengthChange: false,
            autoWidth: false,
            pageLength: 25,
            language: {
                url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/es.json'
            },
            columnDefs: [
                { orderable: false, targets: -1 }
            ]
        });
    }

    // Reintentar facturación AFIP
    document.querySelectorAll('.btn-retry-invoice').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var saleId = this.getAttribute('data-sale-id');
            if (!confirm('¿Reintentar emitir factura AFIP para la venta #' + saleId + '?')) return;

            var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
            var token = csrfToken ? csrfToken.value : '';

            var formData = new FormData();
            formData.append('action', 'retry_invoice');
            formData.append('sale_id', saleId);

            fetch('', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': token
                }
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    alert('Factura emitida correctamente. CAE: ' + data.cae);
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'No se pudo emitir la factura'));
                }
            })
            .catch(function(err) {
                alert('Error de conexión: ' + err);
            });
        });
    });

    // Generar PDF AFIP
    document.querySelectorAll('.btn-generate-pdf').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var saleId = this.getAttribute('data-sale-id');
            if (!confirm('¿Generar PDF fiscal AFIP para la venta #' + saleId + '?')) return;

            var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
            var token = csrfToken ? csrfToken.value : '';

            var formData = new FormData();
            formData.append('sale_id', saleId);

            fetch('/erp/afip/generate-pdf/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': token
                }
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    alert('PDF generado correctamente');
                    window.open(data.pdf_url, '_blank');
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'No se pudo generar el PDF'));
                }
            })
            .catch(function(err) {
                alert('Error de conexión: ' + err);
            });
        });
    });
});
