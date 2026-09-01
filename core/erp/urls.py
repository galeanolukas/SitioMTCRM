from django.urls import path, include
from core.erp.views.category.views import *
from core.erp.views.product.views import *
from core.erp.views.client.views import ClientListView, ClientCreateView, ClientUpdateView, ClientDeleteView
from core.erp.views.sale.views import SaleListView, SaleCreateView, SaleUpdateView, SaleDeleteView, ticket_print, ticket_x_print, ticket_budget_print, POSView, InvoiceListView, InvoiceCreateView, invoice_pdf, sync_sales_api, EmployeeAccountListView, employee_account_pdf_export, BudgetListView, BudgetConvertView, BudgetDetailView, BudgetSendLocalView, CardPlanListView, CardPlanCreateView, CardPlanUpdateView, CardPlanDeleteView, CardPlanExportView, CardPlanImportView
from core.erp.views.transfer.views import TransferListView, TransferCreateView, TransferDetailView, TransferReceiveView, TransferSearchView, TransferProductSearchView
from core.erp.views.operator_reports.views import OperatorSalesReportView, operator_sales_export
from core.erp.views.sync.views import SyncToggleView, SyncStatusView, ProductSyncView
from core.erp.views.tests.views import *
from core.erp.views.activity_log import ActivityLogView, ActivityLogDashboardView
from core.erp.views.scanner.views import ScannerMobileView, ScanSubmitView, ScanPollView
from core.erp.views.clear_db.views import ClearLocalDBView
from core.erp.api.updates import check_updates_api, refresh_version_info, execute_update_script, version_diagnostics, check_update_status
from core.erp.api.release import execute_release
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
    expense_export,
    MercadoPagoConfigUpdateView,
    AutoSyncConfigUpdateView,
    sync_data_view,
    DatabaseCleanupView,
)
from core.erp.views.remito.views import (
    RemitoListView,
    RemitoCreateView,
    RemitoDetailView,
    RemitoUpdateView,
    RemitoDeleteView,
    procesar_remito,
    anular_remito,
    agregar_detalle_remito,
    eliminar_detalle_remito,
    facturar_remito,
)

# Importar vistas de reportes
from core.erp.views.reports.views import (
    UnifiedReportsView,
    ExportReportView,
)
from core.erp.views.reports.undo_views import (
    UndoChangeView,
    ChangeHistoryView,
    SaveConfigurationView,
    LoadConfigurationView,
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
from core.erp.views.catalogo.views import (
    enviar_productos_catalogo,
    CatalogoConfigListView,
    CatalogoConfigCreateView,
    CatalogoConfigUpdateView,
    CatalogoConfigDeleteView,
    get_catalogo_config,
)
from core.erp.views.api.budget_views import receive_budget, confirm_budget
from core.erp.views.price_list.views import (
    PriceListListView, PriceListCreateView,
    PriceListUpdateView, PriceListDeleteView,
    PriceListProductManageView,
)

# Importar vistas de descuentos (comentado temporalmente para evitar errores de importación)
# from core.erp.views.discount.views import (
#     DiscountRuleListView, DiscountRuleCreateView, DiscountRuleUpdateView, DiscountRuleDeleteView
# )

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
    path('product/category-suggest/', CategorySuggestView.as_view(), name='product_category_suggest'),
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
    path('sale/ticket/<int:pk>/print/x/', ticket_x_print, name='sale_ticket_x_print'),
    # card plans (solo superusuarios)
    path('card-plan/list/', CardPlanListView.as_view(), name='card_plan_list'),
    path('card-plan/add/', CardPlanCreateView.as_view(), name='card_plan_create'),
    path('card-plan/update/<int:pk>/', CardPlanUpdateView.as_view(), name='card_plan_update'),
    path('card-plan/delete/<int:pk>/', CardPlanDeleteView.as_view(), name='card_plan_delete'),
    path('card-plan/export/', CardPlanExportView.as_view(), name='card_plan_export'),
    path('card-plan/import/', CardPlanImportView.as_view(), name='card_plan_import'),
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
    path('sync/data/', sync_data_view, name='sync_data'),
    path('database/cleanup/', DatabaseCleanupView.as_view(), name='database_cleanup'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('updates/', UpdatesView.as_view(), name='updates'),
    path('backup-to-server/', UpdatesView.as_view(), name='backup_to_server'),
    # reports (superuser)
    path('reports/', UnifiedReportsView.as_view(), name='unified_reports'),
    path('reports/export/', ExportReportView.as_view(), name='export_report'),
    # Nuevos reportes avanzados con sistema de deshacer
    path('reports/enhanced/', UnifiedReportsView.as_view(), name='enhanced_reports'),
    path('reports/undo/', UndoChangeView.as_view(), name='undo_change'),
    path('reports/history/', ChangeHistoryView.as_view(), name='change_history'),
    path('reports/save-config/', SaveConfigurationView.as_view(), name='save_configuration'),
    path('reports/load-config/', LoadConfigurationView.as_view(), name='load_configuration'),
    # operator reports
    path('operator/sales/', OperatorSalesReportView.as_view(), name='operator_sales_report'),
    path('operator/sales/export/', operator_sales_export, name='operator_sales_export'),
    # profit reports (superuser only)
    path('profit-report/', ProfitReportView.as_view(), name='profit_report'),
    path('generate-profit-report/', GenerateProfitReportView.as_view(), name='generate_profit_report'),
    path('profit-report-list/', ProfitReportListView.as_view(), name='profit_report_list'),
    # pos
    path('pos/', POSView.as_view(), name='pos'),
    # employee account
    path('employee-account/', EmployeeAccountListView.as_view(), name='employee_account_list'),
    path('employee-account/pdf/', employee_account_pdf_export, name='employee_account_pdf'),
    # remitos
    path('remito/list/', RemitoListView.as_view(), name='remito_list'),
    path('remito/add/', RemitoCreateView.as_view(), name='remito_create'),
    path('remito/detail/<int:pk>/', RemitoDetailView.as_view(), name='remito_detail'),
    path('remito/update/<int:pk>/', RemitoUpdateView.as_view(), name='remito_update'),
    path('remito/delete/<int:pk>/', RemitoDeleteView.as_view(), name='remito_delete'),
    path('remito/procesar/<int:pk>/', procesar_remito, name='remito_procesar'),
    path('remito/anular/<int:pk>/', anular_remito, name='remito_anular'),
    path('remito/agregar-detalle/', agregar_detalle_remito, name='remito_agregar_detalle'),
    path('remito/eliminar-detalle/<int:detalle_id>/', eliminar_detalle_remito, name='remito_eliminar_detalle'),
    path('remito/facturar/<int:pk>/', facturar_remito, name='remito_facturar'),
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
    path('expense/export/', expense_export, name='expense_export'),
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
    # Listas de Precios
    path('price-list/', PriceListListView.as_view(), name='pricelist_list'),
    path('price-list/add/', PriceListCreateView.as_view(), name='pricelist_create'),
    path('price-list/edit/<int:pk>/', PriceListUpdateView.as_view(), name='pricelist_edit'),
    path('price-list/delete/<int:pk>/', PriceListDeleteView.as_view(), name='pricelist_delete'),
    path('price-list/<int:pk>/manage/', PriceListProductManageView.as_view(), name='pricelist_manage'),
    # sync toggle
    path('sync/toggle/', SyncToggleView.as_view(), name='sync_toggle'),
    # sync status (public for all authenticated users)
    path('sync/status/', SyncStatusView.as_view(), name='sync_status'),
    # product sync (solo superusuarios)
    path('sync/products/', ProductSyncView.as_view(), name='sync_products'),
    # activity log (solo superusuarios)
    path('activity/log/', ActivityLogView.as_view(), name='activity_log'),
    path('activity/dashboard/', ActivityLogDashboardView.as_view(), name='activity_dashboard'),
    # API de actualizaciones
    path('api/updates/check/', check_updates_api, name='api_check_updates'),
    path('api/updates/refresh/', refresh_version_info, name='api_refresh_version'),
    path('api/updates/execute/', execute_update_script, name='api_execute_update'),
    path('api/updates/status/', check_update_status, name='api_check_update_status'),
    path('api/updates/diagnostics/', version_diagnostics, name='api_version_diagnostics'),
    path('api/execute-release/', execute_release, name='api_execute_release'),
    # AFIP
    path('afip/', include('core.erp.afip.urls', namespace='afip')),
    # Catálogo Marcos
    path('catalogo/list/', CatalogoConfigListView.as_view(), name='catalogo_list'),
    path('catalogo/add/', CatalogoConfigCreateView.as_view(), name='catalogo_add'),
    path('catalogo/update/<int:pk>/', CatalogoConfigUpdateView.as_view(), name='catalogo_update'),
    path('catalogo/delete/<int:pk>/', CatalogoConfigDeleteView.as_view(), name='catalogo_delete'),
    path('catalogo/sync/', enviar_productos_catalogo, name='enviar_productos_catalogo'),
    path('catalogo/config/<int:catalogo_id>/', get_catalogo_config, name='catalogo_config'),
    # Descuentos y Ofertas (comentado temporalmente para evitar errores de importación)
    # path('discounts/', DiscountRuleListView.as_view(), name='discount_list'),
    # path('discounts/add/', DiscountRuleCreateView.as_view(), name='discount_create'),
    # path('discounts/update/<int:pk>/', DiscountRuleUpdateView.as_view(), name='discount_update'),
    # path('discounts/delete/<int:pk>/', DiscountRuleDeleteView.as_view(), name='discount_delete'),
    # API de presupuestos para sincronización local
    path('api/budgets/receive/', receive_budget, name='api_budgets_receive'),
    path('api/budgets/confirm/<int:sale_id>/', confirm_budget, name='api_budgets_confirm'),
    # Presupuestos pendientes
    path('budget/list/', BudgetListView.as_view(), name='budget_list'),
    path('budget/convert/<int:pk>/', BudgetConvertView.as_view(), name='budget_convert'),
    path('sale/api/detail/<int:pk>/', BudgetDetailView.as_view(), name='budget_detail'),
    path('budget/ticket/<int:pk>/', ticket_budget_print, name='ticket_budget_print'),
    path('budget/send-local/<int:pk>/', BudgetSendLocalView.as_view(), name='budget_send_local'),
    # Scanner móvil
    path('scanner/', ScannerMobileView.as_view(), name='scanner_mobile'),
    path('api/scan/submit/', ScanSubmitView.as_view(), name='scan_submit'),
    path('api/scan/poll/', ScanPollView.as_view(), name='scan_poll'),
    # Limpiar DB local
    path('clear-db/', ClearLocalDBView.as_view(), name='clear_local_db'),
]
