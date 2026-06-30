from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.urls import reverse_lazy
from django.views.generic import UpdateView, ListView, TemplateView
from django.shortcuts import redirect, get_object_or_404, render
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
    fields = ["first_name", "last_name", "email", "phone", "image", "company", "is_active", "is_superuser"]
    template_name = "user/user_edit.html"
    success_url = reverse_lazy("user:list")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return redirect('erp:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Editar Usuario'
        ctx['entity'] = 'Usuarios'
        ctx['list_url'] = reverse_lazy('user:list')
        from core.erp.models import Company
        ctx['companies'] = Company.objects.filter(is_active=True)
        ctx['groups'] = Group.objects.all()
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Usuario '{form.instance.username}' actualizado correctamente.")
        return super().form_valid(form)

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
        from core.erp.models import Company
        ctx['companies'] = Company.objects.filter(is_active=True)
        return ctx


@require_POST
def user_create(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    
    UserModel = get_user_model()
    username = request.POST.get('username')
    password = request.POST.get('password')
    password_confirm = request.POST.get('password_confirm')
    first_name = request.POST.get('first_name', '')
    last_name = request.POST.get('last_name', '')
    email = request.POST.get('email', '')
    phone = request.POST.get('phone', '')
    company_id = request.POST.get('company')
    is_superuser = request.POST.get('is_superuser') == 'on'
    is_active = request.POST.get('is_active') == 'on'
    
    # Validaciones
    if not username or not password:
        messages.error(request, 'Usuario y contraseña son obligatorios.')
        return redirect('user:list')
    
    if password != password_confirm:
        messages.error(request, 'Las contraseñas no coinciden.')
        return redirect('user:list')
    
    if UserModel.objects.filter(username=username).exists():
        messages.error(request, 'El usuario ya existe.')
        return redirect('user:list')
    
    # Crear usuario
    user = UserModel.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        is_superuser=is_superuser,
        is_active=is_active
    )
    
    # Asignar empresa si se proporcionó
    if company_id:
        from core.erp.models import Company
        try:
            company = Company.objects.get(pk=company_id)
            user.company = company
            user.save()
        except Company.DoesNotExist:
            pass
    
    messages.success(request, f"Usuario '{username}' creado exitosamente.")
    return redirect('user:list')


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
        group_id = self.kwargs.get('group_id')
        if group_id:
            try:
                return Group.objects.get(pk=group_id)
            except Group.DoesNotExist:
                return None
        # Si no se especifica grupo, usar 'operadores' por defecto
        group, _ = Group.objects.get_or_create(name='operadores')
        return group

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        group = self.get_group()
        if not group:
            ctx['error'] = 'Grupo no encontrado'
            ctx['groups'] = Group.objects.all()
            return ctx
        
        ctx['title'] = f'Permisos: {group.name}'
        ctx['entity'] = 'Permisos de Grupo'
        ctx['group'] = group
        ctx['groups'] = Group.objects.all()
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
        if not group:
            messages.error(request, 'Grupo no encontrado')
            return redirect('user:operators_permissions')
        
        # Si se está cambiando de grupo
        if 'change_group' in request.POST:
            new_group_id = request.POST.get('group_id')
            if new_group_id:
                try:
                    new_group = Group.objects.get(pk=new_group_id)
                    return redirect('user:operators_permissions', group_id=new_group.id)
                except Group.DoesNotExist:
                    messages.error(request, 'Grupo no encontrado')
            return redirect('user:operators_permissions')
        
        ids = request.POST.getlist('permissions')
        perms = Permission.objects.filter(id__in=ids)
        group.permissions.set(perms)
        messages.success(request, f'Permisos actualizados para el grupo {group.name}.')
        return redirect('user:operators_permissions', group_id=group.id)
