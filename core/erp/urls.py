from django.urls import path, include
from core.erp.views.category.views import *
from core.erp.views.product.views import *
from core.erp.views.client.views import ClientListView, ClientCreateView, ClientUpdateView, ClientDeleteView
from core.erp.views.sale.views import SaleListView, SaleCreateView, SaleUpdateView, SaleDeleteView, ticket_print, POSView, InvoiceListView, InvoiceCreateView, invoice_pdf, sync_sales_api
from core.erp.views.transfer.views import TransferListView, TransferCreateView, TransferDetailView, TransferReceiveView, TransferSearchView, TransferProductSearchView
from core.erp.views.operator_reports.views import OperatorSalesReportView, operator_sales_export
from core.erp.views.tests.views import *
from core.erp.views.dashboard.views import (
    DashboardView,
    CompanyUpdateView,
    SwitchCompanyView,
    CompanyView,
    LauncherView,
    SupplierView,
    ReportsHomeView,
    UpdatesView,
    report_inventory_export,
    report_sales_export,
    report_expenses_export,
    ExpenseListView,
    ExpenseDeleteView,
    ExpenseCreateView,
    ExpenseUpdateView,
    MercadoPagoConfigUpdateView,
    AutoSyncConfigUpdateView,
    sync_data_view,
)

# Importar vistas de reportes
from core.erp.views.reports import (
    UnifiedReportsView,
    ExportReportView,
)

# Importar vistas de reportes de ganancias
from core.erp.views.profit_views import (
    ProfitReportView,
    GenerateProfitReportView,
    ProfitReportListView,
)

from core.erp.views.cash_register.views import (
    CashRegisterListView, CashRegisterCreateView,
    CashRegisterCloseView, CashRegisterDetailView,
    CashMovementCreateView, CashRegisterDeleteView,
    CashMovementDeleteView,
)

app_name = 'erp'

urlpatterns = [
    path('category/list/', CategoryListView.as_view(), name='category_list'),
    path('category/add/', CategoryCreateView.as_view(), name='category_create'),
    path('category/update/<int:pk>/', CategoryUpdateView.as_view(), name='category_update'),
    path('category/delete/<int:pk>/', CategoryDeleteView.as_view(), name='category_delete'),
    # product
    path('product/list/', ProductListView.as_view(), name='product_list'),
    path('product/add/', ProductCreateView.as_view(), name='product_create'),
    path('product/update/<int:pk>/', ProductUpdateView.as_view(), name='product_update'),
    path('product/delete/<int:pk>/', ProductDeleteView.as_view(), name='product_delete'),
    path('product/import/', ImportInventoryView.as_view(), name='product_import'),
    path('product/labels/', ProductLabelsView.as_view(), name='product_labels'),
    # public QR flows
    path('public/p/<str:token>/', ProductPublicDetailView.as_view(), name='product_public_detail'),
    path('quick-cart/', QuickCartView.as_view(), name='product_quick_cart'),
    path('quick-cart/mp-checkout/', quick_cart_mp_checkout, name='product_quick_cart_mp_checkout'),
    # client
    path('client/list/', ClientListView.as_view(), name='client_list'),
    path('client/add/', ClientCreateView.as_view(), name='client_create'),
    path('client/update/<int:pk>/', ClientUpdateView.as_view(), name='client_update'),
    path('client/delete/<int:pk>/', ClientDeleteView.as_view(), name='client_delete'),
    # sale
    path('sale/add/', SaleCreateView.as_view(), name='sale_create'),
    path('sale/list/', SaleListView.as_view(), name='sale_list'),
    path('sale/delete/<int:pk>/', SaleDeleteView.as_view(), name='sale_delete'),
    path('sale/update/<int:pk>/', SaleUpdateView.as_view(), name='sale_update'),
    path('sale/ticket/<int:pk>/print/', ticket_print, name='sale_ticket_print'),
    # transferencias internas
    path('transfer/list/', TransferListView.as_view(), name='transfer_list'),
    path('transfer/add/', TransferCreateView.as_view(), name='transfer_create'),
    path('transfer/<int:pk>/', TransferDetailView.as_view(), name='transfer_detail'),
    path('transfer/receive/', TransferReceiveView.as_view(), name='transfer_receive'),
    path('transfer/search/', TransferSearchView.as_view(), name='transfer_search'),
    path('transfer/products/', TransferProductSearchView.as_view(), name='transfer_products'),
    # api sync (POS local -> servidor)
    path('api/sync/sales/', sync_sales_api, name='api_sync_sales'),
    # invoice
    path('invoice/list/', InvoiceListView.as_view(), name='invoice_list'),
    path('invoice/add/', InvoiceCreateView.as_view(), name='invoice_add'),
    path('invoice/pdf/<int:pk>/', invoice_pdf, name='invoice_pdf'),
    #home
    path('launcher/', LauncherView.as_view(), name='launcher'),
    path('sync/', sync_data_view, name='sync_data'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('updates/', UpdatesView.as_view(), name='updates'),
    path('backup-to-server/', UpdatesView.as_view(), name='backup_to_server'),
    # reports (superuser)
    path('reports/', UnifiedReportsView.as_view(), name='unified_reports'),
    path('reports/export/', ExportReportView.as_view(), name='export_report'),
    # operator reports
    path('operator/sales/', OperatorSalesReportView.as_view(), name='operator_sales_report'),
    path('operator/sales/export/', operator_sales_export, name='operator_sales_export'),
    # profit reports (superuser only)
    path('profit-report/', ProfitReportView.as_view(), name='profit_report'),
    path('generate-profit-report/', GenerateProfitReportView.as_view(), name='generate_profit_report'),
    path('profit-report-list/', ProfitReportListView.as_view(), name='profit_report_list'),
    # pos
    path('pos/', POSView.as_view(), name='pos'),
    # company
    path('company/', CompanyUpdateView.as_view(), name='company'),
    path('company/list/', CompanyView.as_view(), name='company_list'),
    path('company/mp-config/', MercadoPagoConfigUpdateView.as_view(), name='mp_config'),
    path('sync/config/', AutoSyncConfigUpdateView.as_view(), name='sync_config'),
    # supplier
    path('supplier/list/', SupplierView.as_view(), name='supplier_list'),
    # expenses
    path('expense/list/', ExpenseListView.as_view(), name='expense_list'),
    path('expense/add/', ExpenseCreateView.as_view(), name='expense_create'),
    path('expense/update/<int:pk>/', ExpenseUpdateView.as_view(), name='expense_update'),
    path('expense/delete/<int:pk>/', ExpenseDeleteView.as_view(), name='expense_delete'),
    # switch company (superuser)
    path('company/switch/<int:pk>/', SwitchCompanyView.as_view(), name='company_switch'),
    path('company/switch/clear/', SwitchCompanyView.as_view(), name='company_switch_clear'),
    # test
    path('test/', TestView.as_view(), name='test'),
    # Cierre de Caja
    path('cash-register/list/', CashRegisterListView.as_view(), name='cash_register_list'),
    path('cash-register/add/', CashRegisterCreateView.as_view(), name='cash_register_create'),
    path('cash-register/close/<int:pk>/', CashRegisterCloseView.as_view(), name='cash_register_close'),
    path('cash-register/detail/<int:pk>/', CashRegisterDetailView.as_view(), name='cash_register_detail'),
    path('cash-register/movement/add/<int:cash_register_id>/', CashMovementCreateView.as_view(), name='cash_movement_create'),
    path('cash-register/movement/delete/<int:pk>/', CashMovementDeleteView.as_view(), name='cash_movement_delete'),
    path('cash-register/delete/<int:pk>/', CashRegisterDeleteView.as_view(), name='cash_register_delete'),
]
