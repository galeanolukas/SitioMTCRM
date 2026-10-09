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

    def _render_blocked(self, reason):
        """Re-renderiza el login con el aviso de bloqueo (sin errores de form)."""
        form = self.get_form()
        return self.render_to_response(
            self.get_context_data(form=form, blocked_message=reason)
        )

    def form_valid(self, form):
        user = form.get_user()
        # Verificar estado del usuario contra el servidor central (POS locales)
        if user is not None and not user.is_superuser:
            from core.erp.sync_utils import verify_remote_user_access
            allowed, reason = verify_remote_user_access(user)
            if not allowed:
                return self._render_blocked(reason)

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

    def form_invalid(self, form):
        # Si el usuario existe pero está inactivo, mostrar aviso de bloqueo
        username = self.request.POST.get('username', '')
        if username:
            local_user = User.objects.filter(username__iexact=username).first()
            if local_user and not local_user.is_active:
                return self._render_blocked(
                    'Este usuario está bloqueado. Contacte al administrador para regularizar su cuenta.'
                )
        return super().form_invalid(form)

    def get_success_url(self):
        return '/erp/launcher/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Iniciar Sesión"
        if self.request.GET.get('blocked') and 'blocked_message' not in context:
            context['blocked_message'] = (
                'Su usuario fue bloqueado por el administrador. '
                'Contacte a soporte para regularizar su cuenta.'
            )
        return context


class LogoutRedirectView(RedirectView):
    pattern_name = "login"

    def dispatch(self, request, *args, **kwargs):
        # Antes de cerrar sesión, intentar una sincronización general del POS.
        # Los superusers (admin) pueden trabajar en local sin disparar sync.
        if not request.user.is_superuser:
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
                if not user.is_superuser:
                    from core.erp.sync_utils import verify_remote_user_access
                    allowed, reason = verify_remote_user_access(user)
                    if not allowed:
                        return render(request, 'login.html', {
                            'form': AuthenticationForm(),
                            'title': 'Iniciar Sesión',
                            'blocked_message': reason,
                        })
                login(request, user)
                if not user.is_superuser:
                    company_id = getattr(user, 'company_id', None)
                    if company_id:
                        request.session['company_id'] = company_id
                return HttpResponseRedirect('/erp/launcher/')
            else:
                local_user = User.objects.filter(username__iexact=username).first()
                if local_user and not local_user.is_active:
                    return render(request, 'login.html', {
                        'form': AuthenticationForm(),
                        'title': 'Iniciar Sesión',
                        'blocked_message': 'Este usuario está bloqueado. Contacte al administrador para regularizar su cuenta.',
                    })
                return render(request, 'login.html', {'form': form, 'title': 'Iniciar Sesión'})
        
        return render(request, 'login.html', {'form': form, 'title': 'Iniciar Sesión'})
