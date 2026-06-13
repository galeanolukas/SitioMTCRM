from django.urls import path
from .views import (
    ProfileUpdateView,
    UserAdminUpdateView,
    UserPasswordChangeView,
    UserPasswordChangeDoneView,
    UsersListView,
    OperatorsPermissionsView,
    user_create,
    user_toggle_active,
    user_delete,
)

app_name = 'user'

urlpatterns = [
    path('profile/', ProfileUpdateView.as_view(), name='profile'),
    path('password/change/', UserPasswordChangeView.as_view(), name='password_change'),
    path('password/change/done/', UserPasswordChangeDoneView.as_view(), name='password_change_done'),
    path('users/', UsersListView.as_view(), name='list'),
    path('users/create/', user_create, name='create'),
    path('users/<int:pk>/edit/', UserAdminUpdateView.as_view(), name='edit'),
    path('users/<int:pk>/toggle-active/', user_toggle_active, name='toggle_active'),
    path('users/<int:pk>/delete/', user_delete, name='delete'),
    path('operators/permissions/', OperatorsPermissionsView.as_view(), name='operators_permissions'),
]