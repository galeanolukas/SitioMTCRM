from typing import Any
from django import http
from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView
from django.views.generic import FormView, RedirectView
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.http import HttpResponseRedirect
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


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)


class LoginFormView(LoginView):
    template_name = "login.html"
    form_class = AuthenticationFormWithFormControl

    def dispatch(self, request, *args: Any, **kwargs):
        if request.user.is_authenticated:
            return redirect("erp:launcher")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Llamar al padre que maneja el login
        response = super().form_valid(form)
        
        # Forzar guardado de sesión
        self.request.session.save()
        
        return response

    def get_success_url(self):
        user = self.request.user
        # Guardar empresa del usuario en sesión si no es superusuario
        if user and user.is_authenticated and not user.is_superuser:
            self.request.session['company_id'] = getattr(user, 'company_id', None)
        # Superusuario: si no existe o faltan datos clave, ir a configuración
        if user and user.is_authenticated and user.is_superuser:
            company = Company.objects.first()
            if not company or not company.name:
                return reverse('erp:company')
        return reverse('erp:launcher')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Iniciar Sesión"
        return context


class LoginFormView2(FormView):
    template_name = "login.html"
    form_class = AuthenticationFormWithFormControl
    success_url = reverse_lazy("erp:dashboard")

    def dispatch(self, request, *args: Any, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        login(self.request, form.get_user())
        return HttpResponseRedirect(self.success_url)

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


class RegisterView(FormView):
    template_name = "register.html"
    form_class = CustomUserCreationForm
    # Tras registrarse, se mostrará el login; el usuario quedará inactivo hasta que un admin lo habilite
    success_url = reverse_lazy("login")

    def dispatch(self, request, *args: Any, **kwargs):
        # En POS locales (no produccion) deshabilitar el registro y mostrar mensaje
        if getattr(settings, 'ENVIRONMENT', 'development') != 'production':
            return render(request, 'register_disabled.html', {})

        if request.user.is_authenticated:
            return redirect("erp:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for f in form.visible_fields():
            f.field.widget.attrs["class"] = "form-control"
            f.field.widget.attrs["autocomplete"] = "off"
        return form

    def form_valid(self, form):
        # Crear usuario inactivo por defecto
        user = form.save(commit=False)
        user.is_active = False
        user.save()

        if not user.is_superuser:
            group, _ = Group.objects.get_or_create(name='operadores')
            user.groups.set([group])

        # No iniciar sesión automáticamente; redirigir al login
        # Un administrador deberá activar manualmente al usuario.
        return HttpResponseRedirect(self.success_url)
