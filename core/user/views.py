from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.urls import reverse_lazy
from django.views.generic import UpdateView, ListView, TemplateView
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import Group, Permission
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import HttpResponseForbidden


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = get_user_model()
    fields = ["first_name", "last_name", "email", "phone", "image"]
    template_name = "user/profile_form.html"
    success_url = reverse_lazy("erp:dashboard")

    def get_object(self, queryset=None):
        return self.request.user


class UserAdminUpdateView(LoginRequiredMixin, UpdateView):
    model = get_user_model()
    fields = ["first_name", "last_name", "email", "phone", "image", "company"]
    template_name = "user/profile_form.html"
    success_url = reverse_lazy("user:list")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return redirect('erp:dashboard')
        return super().dispatch(request, *args, **kwargs)

class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "user/password_change_form.html"
    success_url = reverse_lazy("user:password_change_done")


class UserPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "user/password_change_done.html"


class UsersListView(LoginRequiredMixin, ListView):
    template_name = "user/list.html"
    context_object_name = "users"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return redirect('erp:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        UserModel = get_user_model()
        qs = UserModel.objects.select_related('company').all()
        active_cid = self.request.session.get('company_id')
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Usuarios'
        ctx['entity'] = 'Usuarios'
        ctx['list_url'] = reverse_lazy('user:list')
        return ctx


@require_POST
def user_toggle_active(request, pk):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    UserModel = get_user_model()
    user = get_object_or_404(UserModel, pk=pk)
    if user.pk == request.user.pk:
        messages.error(request, 'No puedes desactivar tu propio usuario.')
        return redirect('user:list')
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    messages.success(request, f"Usuario '{user.username}' ahora está {'activo' if user.is_active else 'inactivo'}.")
    return redirect('user:list')


@require_POST
def user_delete(request, pk):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    UserModel = get_user_model()
    user = get_object_or_404(UserModel, pk=pk)
    if user.pk == request.user.pk:
        messages.error(request, 'No puedes eliminar tu propio usuario.')
        return redirect('user:list')
    username = user.username
    user.delete()
    messages.success(request, f"Usuario '{username}' eliminado.")
    return redirect('user:list')


class OperatorsPermissionsView(LoginRequiredMixin, TemplateView):
    template_name = "vtc/operators_permissions.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return redirect('erp:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_group(self):
        group, _ = Group.objects.get_or_create(name='operadores')
        return group

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        group = self.get_group()
        ctx['title'] = 'Permisos Operadores'
        ctx['entity'] = 'Permisos Operadores'
        ctx['group'] = group
        perms = list(Permission.objects.select_related('content_type').order_by('content_type__app_label', 'codename'))
        replacements = {
            'Can add ': 'Puede crear ',
            'Can change ': 'Puede editar ',
            'Can delete ': 'Puede eliminar ',
            'Can view ': 'Puede ver ',
        }
        overrides = {
            # 'app_label.codename': 'Texto en español',
        }
        for p in perms:
            name = p.name
            for en, es in replacements.items():
                if name.startswith(en):
                    name = es + name[len(en):]
                    break
            key = f"{p.content_type.app_label}.{p.codename}"
            p.display_name = overrides.get(key, name)
        ctx['permissions'] = perms
        ctx['group_permission_ids'] = set(group.permissions.values_list('id', flat=True))
        ctx['list_url'] = reverse_lazy('user:operators_permissions')
        return ctx

    def post(self, request, *args, **kwargs):
        group = self.get_group()
        ids = request.POST.getlist('permissions')
        perms = Permission.objects.filter(id__in=ids)
        group.permissions.set(perms)
        messages.success(request, 'Permisos actualizados para el grupo operadores.')
        return redirect('user:operators_permissions')
