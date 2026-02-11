from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from core.erp.mixins import ValidatePermissionRequiredMixin
from core.erp.models import DiscountRule, SaleDiscount
from core.erp.forms.discounts import DiscountRuleForm


class DiscountRuleListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = DiscountRule
    template_name = 'discount/list.html'
    permission_required = 'erp.view_discountrule'
    
    def get_queryset(self):
        return DiscountRule.objects.filter(is_active=True).select_related('product', 'category')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Reglas de Descuento'
        context['create_url'] = reverse_lazy('erp:discountrule_create')
        context['list_url'] = reverse_lazy('erp:discountrule_list')
        context['entity'] = 'Descuentos'
        return context


class DiscountRuleCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    model = DiscountRule
    form_class = DiscountRuleForm
    template_name = 'discount/create.html'
    success_url = reverse_lazy('erp:discountrule_list')
    permission_required = 'erp.add_discountrule'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nueva Regla de Descuento'
        context['entity'] = 'Descuentos'
        context['list_url'] = self.success_url
        context['action'] = 'add'
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Regla de descuento "{form.instance.name}" creada exitosamente.')
        return response


class DiscountRuleUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = DiscountRule
    form_class = DiscountRuleForm
    template_name = 'discount/create.html'
    success_url = reverse_lazy('erp:discountrule_list')
    permission_required = 'erp.change_discountrule'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Regla de Descuento'
        context['entity'] = 'Descuentos'
        context['list_url'] = self.success_url
        context['action'] = 'edit'
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Regla de descuento "{form.instance.name}" actualizada exitosamente.')
        return response


class DiscountRuleDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = DiscountRule
    template_name = 'discount/delete.html'
    success_url = reverse_lazy('erp:discountrule_list')
    permission_required = 'erp.delete_discountrule'
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.is_active = False
        self.object.save()
        messages.success(request, f'Regla de descuento "{self.object.name}" eliminada exitosamente.')
        return JsonResponse({'success': True})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminar Regla de Descuento'
        context['entity'] = 'Descuentos'
        context['list_url'] = self.success_url
        return context
