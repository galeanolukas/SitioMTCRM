from typing import Any
from django.shortcuts import render
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from core.erp.forms import *
from django.urls import reverse_lazy
from core.erp.models import *
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse, HttpResponseRedirect
from core.erp.mixins import ValidatePermissionRequiredMixin



@method_decorator(csrf_exempt, name='dispatch')
class CategoryListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    permission_required = (('erp.view_category'))
    model = Category
    template_name = "category/list.html"

    def get_queryset(self):
        # Filtrar categorías por empresa del usuario
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            active_cid = self.request.session.get('company_id') or getattr(self.request.user, 'company_id', None)
            if active_cid:
                qs = qs.filter(company_id=active_cid)
        return qs

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST["action"]
            if action == "searchdata":
                data = []
                qs = self.get_queryset()
                for i in qs:
                    data.append(i.toJSON())
            elif action == "delete_all":
                qs = self.get_queryset()
                count = qs.count()
                qs.delete()
                data = {'success': True, 'count': count}
            else:
                data["error"] = "Ha ocurrido un error"
        except Exception as e:
            data["error"] = str(e)
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Listado de Categorías"
        context["create_url"] = reverse_lazy("erp:category_create")
        context["list_url"] = reverse_lazy("erp:category_list")
        context["entity"] = "Categorias"
        return context


class CategoryCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "category/create.html"
    success_url = reverse_lazy('erp:category_list')
    permission_required = (('erp.add_category'),)
    url_redirect = success_url

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST["action"]
            if action == "add":
                form = self.get_form()
                data = form.save()
            else:
                data["error"] = "No ha ingresado a ninguna opción"
        except Exception as e:
            data["error"] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Creación de Categoria"
        context["list_url"] = reverse_lazy("erp:category_list")
        context["entity"] = "Categorías"
        context["action"] = "add"
        return context


class CategoryUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "category/create.html"
    success_url = reverse_lazy("erp:category_list")
    permission_required = 'erp.change_category'
    url_redirect = success_url

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST["action"]
            if action == "edit":
                form = self.get_form()
                data = form.save()
            else:
                data["error"] = "No ha ingresado a ninguna opción"
        except Exception as e:
            data["error"] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edición de Categoria"
        context["list_url"] = reverse_lazy("erp:category_list")
        context["entity"] = "Categorías"
        context["action"] = "edit"
        return context


class CategoryDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = Category
    template_name = "category/delete.html"
    success_url = reverse_lazy("erp:category_list")
    permission_required = 'erp.delete_category'
    url_redirect = success_url


    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            self.object.delete()
        except Exception as e:
            data["error"] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Eliminación de una Categoria"
        context["entity"] = "Categorias"
        context["list_url"] = reverse_lazy("erp:category_list")
        return context
