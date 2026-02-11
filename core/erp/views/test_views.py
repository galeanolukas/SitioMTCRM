from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from core.erp.mixins import ValidatePermissionRequiredMixin
from django.views.generic import View

class TestPermissionView(ValidatePermissionRequiredMixin, LoginRequiredMixin, View):
    """Vista de prueba para verificar el funcionamiento del mixin de permisos"""
    permission_required = 'erp.view_product'
    template_name = '403.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.has_perm(self.permission_required):
            return render(request, 'base.html', {
                'title': 'Acceso Permitido',
                'message': 'Tiene los permisos necesarios'
            })
        else:
            return render(request, '403.html', {
                'title': 'Acceso Denegado',
                'message': 'No tiene los permisos necesarios',
                'required_perms': self.get_perms(),
                'user_perms': list(request.user.get_all_permissions()),
            })
