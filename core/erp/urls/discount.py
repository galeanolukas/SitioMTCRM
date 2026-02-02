from django.urls import path
from core.erp.views.discount import views as discount_views

app_name = 'discount'

urlpatterns = [
    path('list/', discount_views.DiscountRuleListView.as_view(), name='discountrule_list'),
    path('create/', discount_views.DiscountRuleCreateView.as_view(), name='discountrule_create'),
    path('edit/<int:pk>/', discount_views.DiscountRuleUpdateView.as_view(), name='discountrule_update'),
    path('delete/<int:pk>/', discount_views.DiscountRuleDeleteView.as_view(), name='discountrule_delete'),
]
