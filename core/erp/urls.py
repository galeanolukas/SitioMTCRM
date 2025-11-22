from django.urls import path
from core.erp.views.category.views import *
from core.erp.views.product.views import *
from core.erp.views.client.views import *
from core.erp.views.sale.views import *
from core.erp.views.tests.views import *
from core.erp.views.dashboard.views import (
    DashboardView,
    CompanyUpdateView,
    SwitchCompanyView,
    CompanyView,
    LauncherView,
    SupplierView,
    ReportsHomeView,
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
    # reports (superuser)
    path('reports/', ReportsHomeView.as_view(), name='reports_home'),
    path('reports/inventory/export/', report_inventory_export, name='reports_inventory_export'),
    path('reports/sales/export/', report_sales_export, name='reports_sales_export'),
    path('reports/expenses/export/', report_expenses_export, name='reports_expenses_export'),
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
]
