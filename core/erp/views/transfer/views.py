from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View, ListView, DetailView
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from decimal import Decimal

from core.erp.models import InternalTransfer, InternalTransferDetail, Product, Company
from core.erp.forms import InternalTransferForm, InternalTransferDetailForm


class TransferListView(LoginRequiredMixin, ListView):
    model = InternalTransfer
    template_name = 'transfer/list.html'
    context_object_name = 'transfers'
    
    def get_queryset(self):
        qs = super().get_queryset()
        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        return qs.select_related('created_by', 'company').prefetch_related('details')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Transferencias Internas'
        context['entity'] = 'Transferencias'
        context['create_url'] = reverse_lazy('erp:transfer_create')
        return context


class TransferDetailView(LoginRequiredMixin, DetailView):
    model = InternalTransfer
    template_name = 'transfer/detail.html'
    context_object_name = 'transfer'
    
    def get_queryset(self):
        qs = super().get_queryset()
        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        return qs.select_related('created_by', 'company').prefetch_related('details__product')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Detalle Transferencia {self.transfer.transfer_number}'
        return context


class TransferCreateView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        context = {
            'title': 'Nueva Transferencia Interna',
            'entity': 'Transferencia',
            'action': 'add',
            'list_url': reverse_lazy('erp:transfer_list'),
        }
        return render(request, 'transfer/create.html', context)
    
    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            
            if action == 'add':
                with transaction.atomic():
                    # Obtener empresa activa
                    active_cid = request.session.get('company_id')
                    if not request.user.is_superuser:
                        active_cid = active_cid or getattr(request.user, 'company_id', None)
                    
                    if not active_cid:
                        data['error'] = 'No se puede determinar la empresa activa'
                        return JsonResponse(data)
                    
                    company = Company.objects.filter(pk=active_cid).first()
                    if not company:
                        data['error'] = 'Empresa no encontrada'
                        return JsonResponse(data)
                    
                    # Crear transferencia
                    transfer = InternalTransfer()
                    transfer.company_id = active_cid
                    transfer.created_by = request.user
                    transfer.origin_pos = request.POST.get('origin_pos', company.pos or '0001')
                    transfer.destination_pos = request.POST.get('destination_pos')
                    transfer.observations = request.POST.get('observations', '')
                    transfer.save()
                    
                    # Procesar productos
                    products_data = request.POST.getlist('products[]')
                    quantities_data = request.POST.getlist('quantities[]')
                    prices_data = request.POST.getlist('prices[]')
                    
                    for i, product_id in enumerate(products_data):
                        if i < len(quantities_data) and i < len(prices_data):
                            product = Product.objects.filter(pk=product_id, company_id=active_cid).first()
                            if product:
                                quantity = Decimal(str(quantities_data[i] or '0'))
                                unit_price = Decimal(str(prices_data[i] or '0'))
                                
                                if quantity > 0:
                                    # Verificar stock suficiente
                                    if product.stock >= quantity:
                                        # Crear detalle
                                        detail = InternalTransferDetail()
                                        detail.transfer = transfer
                                        detail.product = product
                                        detail.quantity = quantity
                                        detail.unit_price = unit_price
                                        detail.save()
                                        
                                        # Descontar stock del POS origen
                                        product.stock -= quantity
                                        product.save()
                                    else:
                                        data['error'] = f'Stock insuficiente para {product.name}. Disponible: {product.stock}, Requerido: {quantity}'
                                        return JsonResponse(data)
                    
                    # Cambiar estado a "En Tránsito"
                    transfer.status = 'in_transit'
                    transfer.save()
                    
                    data['id'] = transfer.id
                    data['transfer_number'] = transfer.transfer_number
                    data['success'] = 'Transferencia creada exitosamente'
            
            else:
                data['error'] = 'Acción no válida'
                
        except Exception as e:
            data['error'] = str(e)
        
        return JsonResponse(data)


class TransferReceiveView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        data = {}
        try:
            transfer_id = request.POST.get('transfer_id')
            action = request.POST.get('action', 'receive')
            
            # Obtener transferencia
            transfer = InternalTransfer.objects.get(pk=transfer_id)
            
            # Verificar permisos
            active_cid = request.session.get('company_id')
            if not request.user.is_superuser:
                active_cid = active_cid or getattr(request.user, 'company_id', None)
            
            if active_cid and transfer.company_id != active_cid:
                data['error'] = 'No tiene permisos para esta transferencia'
                return JsonResponse(data)
            
            if action == 'receive':
                with transaction.atomic():
                    if transfer.status != 'in_transit':
                        data['error'] = 'Esta transferencia no puede ser recibida'
                        return JsonResponse(data)
                    
                    # Aumentar stock en el POS destino
                    for detail in transfer.details.all():
                        product = detail.product
                        product.stock += detail.quantity
                        product.save()
                    
                    # Cambiar estado a "Recibido"
                    transfer.status = 'received'
                    transfer.updated_at = timezone.now()
                    transfer.save()
                    
                    data['success'] = 'Transferencia recibida exitosamente'
                    data['status'] = 'received'
            
            elif action == 'cancel':
                with transaction.atomic():
                    if transfer.status in ['received', 'cancelled']:
                        data['error'] = 'Esta transferencia no puede ser cancelada'
                        return JsonResponse(data)
                    
                    # Devolver stock al POS origen si está en tránsito
                    if transfer.status == 'in_transit':
                        for detail in transfer.details.all():
                            product = detail.product
                            product.stock += detail.quantity
                            product.save()
                    
                    # Cambiar estado a "Cancelado"
                    transfer.status = 'cancelled'
                    transfer.updated_at = timezone.now()
                    transfer.save()
                    
                    data['success'] = 'Transferencia cancelada exitosamente'
                    data['status'] = 'cancelled'
            
            else:
                data['error'] = 'Acción no válida'
                
        except InternalTransfer.DoesNotExist:
            data['error'] = 'Transferencia no encontrada'
        except Exception as e:
            data['error'] = str(e)
        
        return JsonResponse(data)


class TransferSearchView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            
            if action == 'search_products':
                term = (request.POST.get('term') or '').strip()
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
                
                qs = Product.objects.filter(is_active=True)
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                
                products = qs.filter(
                    models.Q(code__iexact=term) | 
                    models.Q(name__icontains=term)
                )[:10]
                
                data = []
                for prod in products:
                    item = {
                        'id': prod.id,
                        'name': prod.name,
                        'code': prod.code,
                        'stock': float(prod.stock),
                        'pvp': float(prod.pvp),
                        'unit': prod.get_unit_display(),
                    }
                    data.append(item)
            
            elif action == 'searchdata':
                # Para DataTables
                data = []
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
                
                qs = InternalTransfer.objects.all()
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                
                for transfer in qs:
                    data.append(transfer.toJSON())
            
            else:
                data['error'] = 'Ha ocurrido un error'
                
        except Exception as e:
            data['error'] = str(e)
        
        return JsonResponse(data, safe=False)
