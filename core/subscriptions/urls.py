from django.urls import path

from .views import (
    PlanListView, SubscriptionDetailView, SubscriptionListView, SuspendedView,
)

app_name = 'subscriptions'

urlpatterns = [
    path('', SubscriptionListView.as_view(), name='list'),
    path('plans/', PlanListView.as_view(), name='plans'),
    path('company/<int:pk>/', SubscriptionDetailView.as_view(), name='detail'),
    path('suspended/', SuspendedView.as_view(), name='suspended'),
]
