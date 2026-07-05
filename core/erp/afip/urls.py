"""
URLs para el módulo AFIP
"""
from django.urls import path
from . import views
from . import views_libro_iva
from . import views_reportes

app_name = 'afip'

urlpatterns = [
    path('list/', views.AfipConfigListView.as_view(), name='list'),
    path('create/', views.AfipConfigCreateView.as_view(), name='create'),
    path('update/<int:pk>/', views.AfipConfigUpdateView.as_view(), name='update'),
    path('delete/<int:pk>/', views.AfipConfigDeleteView.as_view(), name='delete'),
    path('test/', views.AfipTestView.as_view(), name='test'),
    path('dashboard/', views.AfipDashboardView.as_view(), name='dashboard'),
    path('vouchers/', views.AfipVouchersListView.as_view(), name='vouchers'),
    path('generate-pdf/', views.generate_afip_pdf, name='generate_pdf'),
    path('libro-iva/', views_libro_iva.LibroIvaListView.as_view(), name='libro_iva'),
    path('libro-iva/export/', views_libro_iva.LibroIvaExportView.as_view(), name='libro_iva_export'),
    # Reportes fiscales
    path('asientos-contables/', views_reportes.asientos_contables_list, name='asientos_contables'),
    path('asientos-contables/export/', views_reportes.asientos_contables_export, name='asientos_contables_export'),
    path('facturas-proveedores/', views_reportes.facturas_proveedores_list, name='facturas_proveedores'),
    path('facturas-proveedores/export/', views_reportes.facturas_proveedores_export, name='facturas_proveedores_export'),
    path('cuenta-corriente-clientes/', views_reportes.cuenta_corriente_clientes_list, name='cuenta_corriente_clientes'),
    path('cuenta-corriente-clientes/export/', views_reportes.cuenta_corriente_clientes_export, name='cuenta_corriente_clientes_export'),
]
