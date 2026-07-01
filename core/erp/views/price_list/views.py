from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from decimal import Decimal
import json

from core.erp.mixins import ValidatePermissionRequiredMixin
from core.erp.models import PriceList, PriceListProduct, Product


class PriceListListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = PriceList
    template_name = 'price_list/list.html'
    permission_required = 'erp.view_pricelist'

    def get_queryset(self):
        active_cid = self.request.session.get('company_id')
        if not active_cid:
            active_cid = getattr(self.request.user, 'company_id', None)
        qs = PriceList.objects.select_related('company').all()
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Listas de Precios'
        ctx['entity'] = 'Listas de Precios'
        ctx['create_url'] = reverse_lazy('erp:pricelist_create')
        ctx['list_url'] = reverse_lazy('erp:pricelist_list')
        return ctx


class PriceListCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    model = PriceList
    template_name = 'price_list/form.html'
    fields = ['name', 'discount_percentage', 'is_active']
    success_url = reverse_lazy('erp:pricelist_list')
    permission_required = 'erp.add_pricelist'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Nueva Lista de Precios'
        ctx['entity'] = 'Listas de Precios'
        ctx['list_url'] = reverse_lazy('erp:pricelist_list')
        ctx['action'] = 'add'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Lista de precios '{form.instance.name}' creada correctamente.")
        return super().form_valid(form)


class PriceListUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = PriceList
    template_name = 'price_list/form.html'
    fields = ['name', 'discount_percentage', 'is_active']
    success_url = reverse_lazy('erp:pricelist_list')
    permission_required = 'erp.change_pricelist'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Editar Lista de Precios'
        ctx['entity'] = 'Listas de Precios'
        ctx['list_url'] = reverse_lazy('erp:pricelist_list')
        ctx['action'] = 'edit'
        # Productos con override en esta lista
        ctx['overrides'] = self.object.products.select_related('product').all()
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Lista de precios '{form.instance.name}' actualizada correctamente.")
        return super().form_valid(form)


class PriceListDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = PriceList
    template_name = 'price_list/delete.html'
    success_url = reverse_lazy('erp:pricelist_list')
    permission_required = 'erp.delete_pricelist'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Eliminar Lista de Precios'
        ctx['entity'] = 'Listas de Precios'
        ctx['list_url'] = reverse_lazy('erp:pricelist_list')
        return ctx


class PriceListProductManageView(LoginRequiredMixin, View):
    """Vista AJAX para agregar/quitar productos de una lista (overrides y excepciones)"""

    def post(self, request, pk):
        if not request.user.has_perm('erp.change_pricelist'):
            return HttpResponseForbidden()

        price_list = get_object_or_404(PriceList, pk=pk)
        action = request.POST.get('action')

        if action == 'add_product':
            product_id = request.POST.get('product_id')
            fixed_price = request.POST.get('fixed_price') or None
            discount_override = request.POST.get('discount_override') or None
            is_exception = request.POST.get('is_exception') == 'on'

            product = get_object_or_404(Product, pk=product_id)

            plp, created = PriceListProduct.objects.get_or_create(
                price_list=price_list,
                product=product,
                defaults={
                    'fixed_price': Decimal(fixed_price) if fixed_price else None,
                    'discount_override': Decimal(discount_override) if discount_override else None,
                    'is_exception': is_exception,
                }
            )
            if not created:
                plp.fixed_price = Decimal(fixed_price) if fixed_price else None
                plp.discount_override = Decimal(discount_override) if discount_override else None
                plp.is_exception = is_exception
                plp.save()

            return JsonResponse({'success': True, 'message': f'Producto {product.name} agregado a la lista.'})

        elif action == 'remove_product':
            plp_id = request.POST.get('plp_id')
            PriceListProduct.objects.filter(pk=plp_id, price_list=price_list).delete()
            return JsonResponse({'success': True, 'message': 'Producto quitado de la lista.'})

        elif action == 'search_products':
            query = request.POST.get('q', '')
            existing_ids = set(price_list.products.values_list('product_id', flat=True))
            products = Product.objects.filter(name__icontains=query).exclude(id__in=existing_ids)[:20]
            results = [{'id': p.id, 'name': p.name, 'pvp': str(p.pvp)} for p in products]
            return JsonResponse({'results': results})

        return JsonResponse({'error': 'Acción no válida'}, status=400)
