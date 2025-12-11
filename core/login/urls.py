from django.urls import path
from core.login.views import *



urlpatterns = [
    path('', LoginFormView.as_view(), name='login'),
    path('simple/', SimpleLoginView.as_view(), name='simple_login'),
    path('logout/', LogoutRedirectView.as_view(), name='logout'),
]
