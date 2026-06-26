"""
URLs para el módulo AFIP
"""
from django.urls import path
from . import views

app_name = 'afip'

urlpatterns = [
    path('list/', views.AfipConfigListView.as_view(), name='list'),
    path('create/', views.AfipConfigCreateView.as_view(), name='create'),
    path('update/<int:pk>/', views.AfipConfigUpdateView.as_view(), name='update'),
    path('delete/<int:pk>/', views.AfipConfigDeleteView.as_view(), name='delete'),
    path('test/', views.AfipTestView.as_view(), name='test'),
    path('dashboard/', views.AfipDashboardView.as_view(), name='dashboard'),
    path('vouchers/', views.AfipVouchersListView.as_view(), name='vouchers'),
]
