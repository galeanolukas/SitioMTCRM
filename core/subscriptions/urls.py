from django.urls import path

from .views import (
    PlanListView, PlanRequestListView, PublicPlansView, SubscriptionDetailView,
    SubscriptionListView, SuspendedView, plan_request_approve,
    plan_request_pay_link, plan_request_pay_status, plan_request_reject,
)

app_name = 'subscriptions'

urlpatterns = [
    path('', SubscriptionListView.as_view(), name='list'),
    path('plans/', PlanListView.as_view(), name='plans'),
    path('company/<int:pk>/', SubscriptionDetailView.as_view(), name='detail'),
    path('requests/', PlanRequestListView.as_view(), name='requests'),
    path('requests/<int:pk>/approve/', plan_request_approve, name='request_approve'),
    path('requests/<int:pk>/pay-link/', plan_request_pay_link, name='request_pay_link'),
    path('requests/<int:pk>/pay-status/', plan_request_pay_status, name='request_pay_status'),
    path('requests/<int:pk>/reject/', plan_request_reject, name='request_reject'),
    path('suspended/', SuspendedView.as_view(), name='suspended'),
    path('oferta/', PublicPlansView.as_view(), name='public'),
]
