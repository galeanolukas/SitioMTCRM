from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.shortcuts import render


def get_active_company_id(request):
    """
    Fuente unica de verdad para la empresa activa.
    - Superuser: usa session['company_id'] (seteada por el selector)
    - Usuario comun: usa session['company_id'] (seteada al login = user.company_id)
    - Fallback: user.company_id si no hay session
    Retorna None si no hay empresa activa.
    """
    cid = request.session.get('company_id')
    if not cid:
        cid = getattr(request.user, 'company_id', None)
    return cid


class ValidatePermissionRequiredMixin(object):
    permission_required = ''
    url_redirect = None

    def get_perms(self):
        if isinstance(self.permission_required, str):
            perms = (self.permission_required,)
        else:
            perms = self.permission_required
        return perms

    def get_url_redirect(self):
        if self.url_redirect is None:
            return reverse_lazy('login')
        return self.url_redirect

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())

        if request.user.is_superuser or request.user.has_perms(self.get_perms()):
            return super().dispatch(request, *args, **kwargs)

        # Usuario autenticado pero sin permisos -> mostrar página de acceso denegado
        try:
            from django.contrib import messages
            messages.error(request, 'No tiene permisos para ingresar a este módulo')
        except Exception:
            # Si el middleware de mensajes no está disponible, continuar sin mensaje
            pass

        return render(request, '403.html', {
            'title': 'Acceso Denegado',
            'message': 'No tiene los permisos necesarios para acceder a esta página.',
            'required_perms': self.get_perms(),
            'user_perms': list(request.user.get_all_permissions()),
        })


class CompanyInitialMixin(object):
    """
    Mixin para preseleccionar la empresa activa en formularios.
    Usa get_active_company_id() como fuente unica.
    """

    def get_initial(self):
        initial = super().get_initial()
        company_id = get_active_company_id(self.request)
        if company_id:
            initial['company'] = company_id
        return initial