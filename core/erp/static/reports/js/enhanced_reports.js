/**
 * JavaScript para Reportes Avanzados con Sistema de Deshacer
 */

class EnhancedReports {
    constructor() {
        this.currentReportType = null;
        this.currentData = null;
        this.dataTables = {};
        this.charts = {};
        this.configurations = {};
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadInitialData();
    }
    
    bindEvents() {
        // Cambio de tipo de reporte
        $('#reportType').on('change', (e) => {
            this.handleReportTypeChange(e.target.value);
        });
        
        // Envío del formulario
        $('#reportForm').on('submit', (e) => {
            e.preventDefault();
            this.generateReport();
        });
        
        // Botones de control
        $('#saveConfigBtn').on('click', () => this.saveConfiguration());
        $('#loadConfigBtn').on('click', () => this.showConfigurations());
        $('#undoBtn').on('click', () => this.undoLastChange());
        $('#historyBtn').on('click', () => this.showHistory());
        
        // Exportación
        $('#exportCsvBtn').on('click', () => this.exportReport('csv'));
        $('#exportExcelBtn').on('click', () => this.exportReport('excel'));
        $('#exportPdfBtn').on('click', () => this.exportReport('pdf'));
        
        // Filtros dinámicos
        $('#stockFilter, #category, #supplier, #search').on('change', () => {
            if (this.currentReportType === 'inventory_enhanced') {
                this.generateReport();
            }
        });
        
        $('#periodType').on('change', () => {
            if (this.currentReportType === 'sales_by_period') {
                this.generateReport();
            }
        });
        
        $('#productId').on('change', () => {
            if (this.currentReportType === 'product_sales') {
                this.generateReport();
            }
        });
    }
    
    handleReportTypeChange(reportType) {
        this.currentReportType = reportType;
        
        // Ocultar todos los filtros adicionales
        $('#additionalFilters, #configControls').hide();
        $('#inventoryFilters, #periodFilters, #productFilters').hide();
        
        if (!reportType) {
            $('#reportResults').hide();
            return;
        }
        
        // Mostrar filtros específicos según el tipo
        $('#additionalFilters, #configControls').show();
        
        switch(reportType) {
            case 'inventory_enhanced':
                $('#inventoryFilters').show();
                this.loadInventoryFilters();
                break;
            case 'sales_by_period':
                $('#periodFilters').show();
                break;
            case 'product_sales':
                $('#productFilters').show();
                this.loadProducts();
                break;
        }
    }
    
    async loadInventoryFilters() {
        try {
            // Cargar categorías
            const categories = await this.fetchData('/api/categories/');
            const categorySelect = $('#category');
            categorySelect.find('option:not(:first)').remove();
            categories.forEach(cat => {
                categorySelect.append(`<option value="${cat.id}">${cat.name}</option>`);
            });
            
            // Cargar proveedores
            const suppliers = await this.fetchData('/api/suppliers/');
            const supplierSelect = $('#supplier');
            supplierSelect.find('option:not(:first)').remove();
            suppliers.forEach(sup => {
                supplierSelect.append(`<option value="${sup.id}">${sup.name}</option>`);
            });
        } catch (error) {
            console.error('Error cargando filtros de inventario:', error);
        }
    }
    
    async loadProducts() {
        try {
            const products = await this.fetchData('/api/products/');
            const productSelect = $('#productId');
            productSelect.find('option:not(:first)').remove();
            products.forEach(prod => {
                productSelect.append(`<option value="${prod.id}">${prod.name} (${prod.code})</option>`);
            });
        } catch (error) {
            console.error('Error cargando productos:', error);
        }
    }
    
    async generateReport() {
        if (!this.currentReportType) {
            this.showAlert('Por favor seleccione un tipo de reporte', 'warning');
            return;
        }
        
        this.showLoading(true);
        
        try {
            const formData = new FormData($('#reportForm')[0]);
            const params = new URLSearchParams(formData);
            
            const response = await fetch(`/erp/reports/enhanced/?${params}`);
            const data = await response.json();
            
            if (response.ok) {
                this.currentData = data;
                this.renderReport(data);
                this.loadChangeHistory();
            } else {
                this.showAlert(data.error || 'Error generando el reporte', 'error');
            }
        } catch (error) {
            console.error('Error generando reporte:', error);
            this.showAlert('Error de conexión', 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    renderReport(data) {
        $('#reportResults').show();
        
        switch(this.currentReportType) {
            case 'inventory_enhanced':
                this.renderInventoryReport(data);
                break;
            case 'sales_by_period':
                this.renderSalesPeriodReport(data);
                break;
            case 'product_sales':
                this.renderProductSalesReport(data);
                break;
        }
    }
    
    renderInventoryReport(data) {
        const inventoryData = data.inventory_enhanced_data;
        
        // Renderizar tabla
        this.renderInventoryTable(inventoryData.products_data);
        
        // Renderizar gráficos
        this.renderInventoryCharts(inventoryData);
        
        // Renderizar resumen
        this.renderInventorySummary(inventoryData.summary, inventoryData.category_breakdown, inventoryData.supplier_breakdown);
    }
    
    renderInventoryTable(products) {
        const table = $('#reportTable');
        table.empty();
        
        // Headers
        const headers = `
            <thead>
                <tr>
                    <th>Código</th>
                    <th>Producto</th>
                    <th>Categoría</th>
                    <th>Proveedor</th>
                    <th>Stock</th>
                    <th>Stock Mín</th>
                    <th>Estado</th>
                    <th>Valor</th>
                    <th>Potencial Ganancia</th>
                </tr>
            </thead>
        `;
        table.append(headers);
        
        // Data
        const tbody = $('<tbody></tbody>');
        products.forEach(product => {
            const statusClass = this.getStockStatusClass(product.stock_status);
            const row = `
                <tr>
                    <td>${product.code}</td>
                    <td>${product.name}</td>
                    <td>${product.category}</td>
                    <td>${product.supplier}</td>
                    <td>${product.stock.toFixed(2)}</td>
                    <td>${product.min_stock.toFixed(2)}</td>
                    <td><span class="badge ${statusClass}">${product.stock_status_display}</span></td>
                    <td>$${product.stock_value.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
                    <td>$${product.potential_profit.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
                </tr>
            `;
            tbody.append(row);
        });
        table.append(tbody);
        
        // Inicializar DataTable
        if (this.dataTables.inventory) {
            this.dataTables.inventory.destroy();
        }
        this.dataTables.inventory = table.DataTable({
            responsive: true,
            pageLength: 25,
            language: {
                url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/es-AR.json'
            }
        });
    }
    
    renderInventoryCharts(data) {
        // Gráfico de categorías
        const categoryCtx = document.getElementById('mainChart').getContext('2d');
        if (this.charts.category) {
            this.charts.category.destroy();
        }
        this.charts.category = new Chart(categoryCtx, {
            type: 'pie',
            data: {
                labels: data.category_breakdown.map(c => c.cat__name || 'Sin categoría'),
                datasets: [{
                    data: data.category_breakdown.map(c => c.total_value || 0),
                    backgroundColor: [
                        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Valor de Inventario por Categoría'
                    }
                }
            }
        });
        
        // Gráfico de estado de stock
        const stockCtx = document.getElementById('secondaryChart').getContext('2d');
        if (this.charts.stock) {
            this.charts.stock.destroy();
        }
        this.charts.stock = new Chart(stockCtx, {
            type: 'doughnut',
            data: {
                labels: ['Stock Normal', 'Stock Bajo', 'Sin Stock'],
                datasets: [{
                    data: [
                        data.summary.total_products - data.summary.low_stock_count - data.summary.out_of_stock_count,
                        data.summary.low_stock_count,
                        data.summary.out_of_stock_count
                    ],
                    backgroundColor: ['#28a745', '#ffc107', '#dc3545']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Estado General de Stock'
                    }
                }
            }
        });
    }
    
    renderInventorySummary(summary, categoryBreakdown, supplierBreakdown) {
        const summaryCards = $('#summaryCards');
        summaryCards.empty();
        
        const cards = [
            {
                title: 'Total Productos',
                value: summary.total_products || 0,
                icon: 'fa-boxes',
                color: 'primary'
            },
            {
                title: 'Valor Total del Inventario',
                value: `$${(summary.total_value || 0).toLocaleString('es-AR', {minimumFractionDigits: 2})}`,
                icon: 'fa-dollar-sign',
                color: 'success'
            },
            {
                title: 'Potencial de Ganancia',
                value: `$${(summary.total_profit || 0).toLocaleString('es-AR', {minimumFractionDigits: 2})}`,
                icon: 'fa-chart-line',
                color: 'info'
            },
            {
                title: 'Productos con Stock Bajo',
                value: summary.low_stock_count || 0,
                icon: 'fa-exclamation-triangle',
                color: 'warning'
            },
            {
                title: 'Productos sin Stock',
                value: summary.out_of_stock_count || 0,
                icon: 'fa-times-circle',
                color: 'danger'
            },
            {
                title: 'Margen Promedio',
                value: `${(summary.avg_margin || 0).toFixed(1)}%`,
                icon: 'fa-percentage',
                color: 'secondary'
            }
        ];
        
        cards.forEach(card => {
            const cardHtml = `
                <div class="col-md-4 mb-3">
                    <div class="card border-${card.color}">
                        <div class="card-body">
                            <div class="d-flex align-items-center">
                                <div class="flex-grow-1">
                                    <h6 class="card-title text-${card.color}">${card.title}</h6>
                                    <h4 class="card-text">${card.value}</h4>
                                </div>
                                <div class="ms-3">
                                    <i class="fas ${card.icon} fa-2x text-${card.color}"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            summaryCards.append(cardHtml);
        });
    }
    
    renderSalesPeriodReport(data) {
        const salesData = data.sales_by_period_data;
        
        this.renderSalesPeriodTable(salesData.period_data);
        this.renderSalesPeriodCharts(salesData);
        this.renderSalesPeriodSummary(salesData.summary, salesData.payment_breakdown);
    }
    
    renderSalesPeriodTable(periodData) {
        const table = $('#reportTable');
        table.empty();
        
        const headers = `
            <thead>
                <tr>
                    <th>Período</th>
                    <th>Ventas</th>
                    <th>Monto Total</th>
                    <th>Items Vendidos</th>
                    <th>Ticket Promedio</th>
                    <th>Subtotal</th>
                    <th>IVA</th>
                </tr>
            </thead>
        `;
        table.append(headers);
        
        const tbody = $('<tbody></tbody>');
        periodData.forEach(period => {
            const row = `
                <tr>
                    <td>${period.period}</td>
                    <td>${period.total_sales}</td>
                    <td>$${period.total_amount.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
                    <td>${period.total_items.toFixed(0)}</td>
                    <td>$${period.avg_ticket.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
                    <td>$${period.subtotal.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
                    <td>$${period.iva.toLocaleString('es-AR', {minimumFractionDigits: 2})}</td>
                </tr>
            `;
            tbody.append(row);
        });
        table.append(tbody);
        
        if (this.dataTables.salesPeriod) {
            this.dataTables.salesPeriod.destroy();
        }
        this.dataTables.salesPeriod = table.DataTable({
            responsive: true,
            language: {
                url: 'https://cdn.datatables.net/plug-ins/1.13.6/i18n/es-AR.json'
            }
        });
    }
    
    renderProductSalesReport(data) {
        const productData = data.product_sales_data;
        
        if (productData.error) {
            $('#reportResults').html(`<div class="alert alert-danger">${productData.error}</div>`);
            return;
        }
        
        if (productData.product_info) {
            // Reporte específico de un producto
            this.renderSpecificProductTable(productData.daily_sales, productData.product_info);
            this.renderSpecificProductCharts(productData);
            this.renderSpecificProductSummary(productData.summary, productData.product_info);
        } else {
            // Reporte general de productos
            this.renderGeneralProductsTable(productData.products);
            this.renderGeneralProductsCharts(productData);
            this.renderGeneralProductsSummary(productData.summary);
        }
    }
    
    async saveConfiguration() {
        if (!this.currentReportType || !this.currentData) {
            this.showAlert('No hay configuración para guardar', 'warning');
            return;
        }
        
        const name = prompt('Ingrese un nombre para esta configuración:');
        if (!name) return;
        
        try {
            const formData = new FormData($('#reportForm')[0]);
            formData.append('report_type', this.currentReportType);
            formData.append('name', name);
            formData.append('configuration', JSON.stringify(this.getFormConfiguration()));
            
            const response = await fetch('/erp/reports/save-config/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showAlert(result.message, 'success');
            } else {
                this.showAlert(result.message, 'error');
            }
        } catch (error) {
            console.error('Error guardando configuración:', error);
            this.showAlert('Error guardando configuración', 'error');
        }
    }
    
    async showConfigurations() {
        try {
            const response = await fetch(`/erp/reports/load-config/?report_type=${this.currentReportType}`);
            const data = await response.json();
            
            if (data.success) {
                this.renderConfigurations(data.configurations);
                $('#configModal').modal('show');
            }
        } catch (error) {
            console.error('Error cargando configuraciones:', error);
        }
    }
    
    renderConfigurations(configurations) {
        const configList = $('#configList');
        configList.empty();
        
        if (configurations.length === 0) {
            configList.html('<p>No hay configuraciones guardadas</p>');
            return;
        }
        
        configurations.forEach(config => {
            const configHtml = `
                <div class="card mb-2">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-title">${config.name}</h6>
                                <small class="text-muted">Versión ${config.version} - ${config.updated_at}</small>
                            </div>
                            <div>
                                <button class="btn btn-sm btn-primary" onclick="enhancedReports.loadConfiguration(${config.id})">
                                    Cargar
                                </button>
                                <button class="btn btn-sm btn-danger" onclick="enhancedReports.deleteConfiguration(${config.id})">
                                    Eliminar
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            configList.append(configHtml);
        });
    }
    
    async loadConfiguration(configId) {
        try {
            const config = this.configurations.find(c => c.id === configId);
            if (!config) {
                // Si no está en caché, cargar desde el servidor
                const response = await fetch(`/erp/reports/load-config/?report_type=${this.currentReportType}`);
                const data = await response.json();
                if (data.success) {
                    this.configurations = data.configurations;
                    const config = this.configurations.find(c => c.id === configId);
                    this.applyConfiguration(config);
                }
            } else {
                this.applyConfiguration(config);
            }
            
            $('#configModal').modal('hide');
            this.showAlert('Configuración cargada exitosamente', 'success');
        } catch (error) {
            console.error('Error cargando configuración:', error);
            this.showAlert('Error cargando configuración', 'error');
        }
    }
    
    applyConfiguration(config) {
        const configuration = config.configuration;
        
        // Aplicar filtros
        Object.keys(configuration).forEach(key => {
            const element = $(`#${key}`);
            if (element.length) {
                if (element.is('select')) {
                    element.val(configuration[key]);
                } else if (element.is('input[type="text"], input[type="date"]')) {
                    element.val(configuration[key]);
                }
            }
        });
        
        // Generar reporte automáticamente
        this.generateReport();
    }
    
    async undoLastChange() {
        if (!this.currentReportType) {
            this.showAlert('No hay reporte activo para deshacer cambios', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/erp/reports/undo/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: `report_type=${this.currentReportType}`
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showAlert(result.message, 'success');
                this.loadChangeHistory();
                this.generateReport(); // Recargar reporte
            } else {
                this.showAlert(result.message, 'error');
            }
        } catch (error) {
            console.error('Error deshaciendo cambio:', error);
            this.showAlert('Error deshaciendo cambio', 'error');
        }
    }
    
    async showHistory() {
        try {
            const response = await fetch(`/erp/reports/history/?report_type=${this.currentReportType}`);
            const data = await response.json();
            
            if (data.success) {
                this.renderFullHistory(data.changes);
                $('#historyModal').modal('show');
            }
        } catch (error) {
            console.error('Error cargando historial:', error);
        }
    }
    
    renderFullHistory(changes) {
        const historyContainer = $('#fullHistory');
        historyContainer.empty();
        
        if (changes.length === 0) {
            historyContainer.html('<p>No hay cambios registrados</p>');
            return;
        }
        
        const table = `
            <table class="table table-sm">
                <thead>
                    <tr>
                        <th>Fecha</th>
                        <th>Usuario</th>
                        <th>Tipo</th>
                        <th>Descripción</th>
                        <th>Estado</th>
                        <th>Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    ${changes.map(change => `
                        <tr>
                            <td>${change.created_at}</td>
                            <td>${change.user}</td>
                            <td>${change.change_type_display}</td>
                            <td>${change.description}</td>
                            <td>
                                ${change.is_reverted ? 
                                    '<span class="badge bg-secondary">Revertido</span>' : 
                                    '<span class="badge bg-success">Activo</span>'
                                }
                            </td>
                            <td>
                                ${change.can_revert ? 
                                    `<button class="btn btn-sm btn-warning" onclick="enhancedReports.revertChange(${change.id})">
                                        Revertir
                                    </button>` : 
                                    ''
                                }
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        historyContainer.html(table);
    }
    
    async revertChange(changeId) {
        try {
            const response = await fetch('/erp/reports/undo/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: `change_id=${changeId}`
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showAlert(result.message, 'success');
                this.showHistory(); // Recargar historial
                this.generateReport(); // Recargar reporte
            } else {
                this.showAlert(result.message, 'error');
            }
        } catch (error) {
            console.error('Error revirtiendo cambio:', error);
            this.showAlert('Error revirtiendo cambio', 'error');
        }
    }
    
    async loadChangeHistory() {
        if (!this.currentReportType) return;
        
        try {
            const response = await fetch(`/erp/reports/history/?report_type=${this.currentReportType}&limit=5`);
            const data = await response.json();
            
            if (data.success && data.changes.length > 0) {
                this.renderRecentChanges(data.changes);
                $('#changeHistory').show();
            } else {
                $('#changeHistory').hide();
            }
        } catch (error) {
            console.error('Error cargando historial de cambios:', error);
        }
    }
    
    renderRecentChanges(changes) {
        const tbody = $('#changesTableBody');
        tbody.empty();
        
        changes.forEach(change => {
            const row = `
                <tr>
                    <td>${change.created_at}</td>
                    <td>${change.user}</td>
                    <td>${change.change_type_display}</td>
                    <td>${change.description}</td>
                    <td>
                        ${change.can_revert ? 
                            `<button class="btn btn-sm btn-warning" onclick="enhancedReports.revertChange(${change.id})">
                                <i class="fas fa-undo"></i>
                            </button>` : 
                            '<span class="text-muted">No reversible</span>'
                        }
                    </td>
                </tr>
            `;
            tbody.append(row);
        });
    }
    
    exportReport(format) {
        if (!this.currentReportType || !this.currentData) {
            this.showAlert('No hay datos para exportar', 'warning');
            return;
        }
        
        const formData = new FormData($('#reportForm')[0]);
        formData.append('report_type', this.currentReportType);
        formData.append('format', format);
        
        // Crear formulario oculto para exportación
        const exportForm = document.createElement('form');
        exportForm.method = 'POST';
        exportForm.action = '/erp/reports/export/';
        
        for (let [key, value] of formData.entries()) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = key;
            input.value = value;
            exportForm.appendChild(input);
        }
        
        // Agregar CSRF token
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = this.getCSRFToken();
        exportForm.appendChild(csrfInput);
        
        document.body.appendChild(exportForm);
        exportForm.submit();
        document.body.removeChild(exportForm);
    }
    
    getFormConfiguration() {
        const config = {};
        $('#reportForm').serializeArray().forEach(item => {
            config[item.name] = item.value;
        });
        return config;
    }
    
    getCSRFToken() {
        const name = 'csrftoken';
        const cookies = document.cookie ? document.cookie.split(';') : [];
        for (let cookie of cookies) {
            const [key, value] = cookie.trim().split('=');
            if (key === name) return decodeURIComponent(value);
        }
        return '';
    }
    
    getStockStatusClass(status) {
        switch(status) {
            case 'in_stock': return 'bg-success';
            case 'low_stock': return 'bg-warning';
            case 'out_of_stock': return 'bg-danger';
            case 'no_track': return 'bg-secondary';
            default: return 'bg-secondary';
        }
    }
    
    showAlert(message, type) {
        // Crear alerta temporal
        const alert = $(`
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `);
        
        $('#reportForm').prepend(alert);
        
        // Auto-eliminar después de 5 segundos
        setTimeout(() => {
            alert.alert('close');
        }, 5000);
    }
    
    showLoading(show) {
        if (show) {
            $('#reportResults').prepend(`
                <div id="loadingOverlay" class="text-center py-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <p class="mt-2">Generando reporte...</p>
                </div>
            `);
        } else {
            $('#loadingOverlay').remove();
        }
    }
    
    async fetchData(url) {
        const response = await fetch(url);
        return await response.json();
    }
    
    loadInitialData() {
        // Cargar datos iniciales si es necesario
    }
}

// Inicializar cuando el documento esté listo
$(document).ready(() => {
    window.enhancedReports = new EnhancedReports();
});
