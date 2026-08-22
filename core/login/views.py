from typing import Any
from django import http
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View, FormView, RedirectView
from django.contrib.auth.views import LoginView
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from core.erp.forms import AuthenticationFormWithFormControl
from core.erp.sync_utils import run_full_sync
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth import login, logout
from core.erp.forms import *
from core.erp.models import Company
from django.urls import reverse
from django.conf import settings

User = get_user_model()


class LoginFormView(LoginView):
    template_name = "login.html"
    form_class = AuthenticationFormWithFormControl

    def dispatch(self, request, *args: Any, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect('/erp/launcher/')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Llamar al método form_valid del padre para hacer el login
        response = super().form_valid(form)
        
        # Setear empresa activa en sesión para usuarios no-superuser
        if not self.request.user.is_superuser:
            company_id = getattr(self.request.user, 'company_id', None)
            if company_id:
                self.request.session['company_id'] = company_id
        
        # Asegurar que la sincronización esté activada para operadores
        if not self.request.user.is_superuser:
            try:
                from core.erp.models import GlobalSyncStatus
                GlobalSyncStatus.ensure_sync_enabled()
            except Exception:
                # No impedir el login si falla la activación de sync
                pass
        
        return response

    def get_success_url(self):
        return '/erp/launcher/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Iniciar Sesión"
        return context


class LogoutRedirectView(RedirectView):
    pattern_name = "login"

    def dispatch(self, request, *args, **kwargs):
        # Antes de cerrar sesión, intentar una sincronización general del POS.
        try:
            run_full_sync()
        except Exception:
            # No impedir el cierre de sesión si la sync falla.
            pass
        logout(request)
        return super().dispatch(request, *args, **kwargs)


class SimpleLoginView(View):
    def get(self, request):
        from django.contrib.auth.forms import AuthenticationForm
        form = AuthenticationForm()
        return render(request, 'login.html', {'form': form, 'title': 'Iniciar Sesión'})
    
    def post(self, request):
        from django.contrib.auth.forms import AuthenticationForm
        from django.contrib.auth import login, authenticate
        form = AuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                if not user.is_superuser:
                    company_id = getattr(user, 'company_id', None)
                    if company_id:
                        request.session['company_id'] = company_id
                return HttpResponseRedirect('/erp/launcher/')
            else:
                return render(request, 'login.html', {'form': form, 'title': 'Iniciar Sesión'})
        
        return render(request, 'login.html', {'form': form, 'title': 'Iniciar Sesión'})
