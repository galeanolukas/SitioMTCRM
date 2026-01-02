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
from django.db import models

from core.erp.models import InternalTransfer, InternalTransferDetail, Product, Company
from core.erp.forms import InternalTransferForm, InternalTransferDetailForm


@method_decorator(csrf_exempt, name='dispatch')
class TransferProductSearchView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        """Obtener productos de una empresa específica para transferencia"""
        company_id = request.GET.get('company_id')
        term = request.GET.get('term', '').strip()
        
        if not company_id:
            return JsonResponse({'error': 'Empresa no especificada'}, status=400)
        
        # Verificar que el usuario tiene permisos para esta empresa
        active_cid = request.session.get('company_id')
        if not request.user.is_superuser:
            active_cid = active_cid or getattr(request.user, 'company_id', None)
        
        if active_cid and active_cid != int(company_id):
            return JsonResponse({'error': 'Sin permisos para esta empresa'}, status=403)
        
        # Filtrar productos por empresa y término de búsqueda
        products = Product.objects.filter(company_id=company_id)
        
        if term:
            # Buscar por palabras clave en nombre o por código (similar al POS)
            for w in filter(None, term.split()):
                products = products.filter(
                    models.Q(name__icontains=w) | 
                    models.Q(code__icontains=w)
                )
        
        # Limitar a 10 resultados (como el POS)
        products = products[:10]
        
        data = []
        for product in products:
            data.append({
                'id': product.id,
                'name': product.name,
                'code': product.code or '',
                'stock': float(product.stock),
                'unit': product.get_unit_display(),
                'cost_price': float(product.cost_price or 0),
                'pvp': float(product.pvp),
                'iva_rate': float(product.iva_rate),
                'pvp_final': float(product.pvp_final),
            })
        
        return JsonResponse(data, safe=False)


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
        # Obtener empresas disponibles para transferencia
        active_cid = request.session.get('company_id')
        if not request.user.is_superuser:
            active_cid = active_cid or getattr(request.user, 'company_id', None)
        
        # Todas las empresas activas (incluida la actual como opción de origen)
        companies = Company.objects.filter(is_active=True)
        current_company = Company.objects.filter(pk=active_cid).first() if active_cid else None
        
        # Si la empresa actual no tiene productos, buscar una que sí tenga
        if current_company and Product.objects.filter(company_id=current_company.id).count() == 0:
            # Buscar la primera empresa con productos
            for company in companies:
                if Product.objects.filter(company_id=company.id).exists():
                    current_company = company
                    active_cid = company.id
                    break
        
        # Obtener productos de TODAS las empresas para el filtrado dinámico
        all_products_data = []
        for company in companies:
            products = Product.objects.filter(company_id=company.id)
            for product in products:
                all_products_data.append({
                    'id': product.id,
                    'name': product.name,
                    'code': product.code or '',
                    'stock': float(product.stock),
                    'unit': product.get_unit_display(),
                    'pvp': float(product.pvp),
                    'company_id': company.id,
                    'company_name': company.name
                })
        
        # Serializar a JSON
        import json
        all_products_json = json.dumps(all_products_data)
        
        # Obtener productos de la empresa actual para mostrar inicialmente
        products_json = '[]'
        if current_company:
            products = Product.objects.filter(company_id=current_company.id)
            products_data = []
            for product in products:
                products_data.append({
                    'id': product.id,
                    'name': product.name,
                    'code': product.code or '',
                    'stock': float(product.stock),
                    'unit': product.get_unit_display(),
                    'pvp': float(product.pvp)
                })
            products_json = json.dumps(products_data)
        
        context = {
            'title': 'Nueva Transferencia entre Empresas',
            'entity': 'Transferencia',
            'action': 'add',
            'list_url': reverse_lazy('erp:transfer_list'),
            'companies': companies,
            'current_company': current_company,
            'products': Product.objects.filter(company_id=current_company.id) if current_company else Product.objects.none(),
            'products_json': products_json,
            'all_products_json': all_products_json,
        }
        return render(request, 'transfer/create.html', context)
    
    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            
            if action == 'add':
                with transaction.atomic():
                    # Obtener empresas origen y destino
                    origin_company_id = request.POST.get('origin_company')
                    destination_company_id = request.POST.get('destination_company')
                    
                    if not origin_company_id or not destination_company_id:
                        data['error'] = 'Debe seleccionar empresas de origen y destino'
                        return JsonResponse(data)
                    
                    if origin_company_id == destination_company_id:
                        data['error'] = 'Las empresas de origen y destino deben ser diferentes'
                        return JsonResponse(data)
                    
                    origin_company = Company.objects.filter(pk=origin_company_id).first()
                    destination_company = Company.objects.filter(pk=destination_company_id).first()
                    
                    if not origin_company or not destination_company:
                        data['error'] = 'Empresa no encontrada'
                        return JsonResponse(data)
                    
                    # Verificar que el usuario tiene permisos en la empresa origen
                    active_cid = request.session.get('company_id')
                    if not request.user.is_superuser:
                        active_cid = active_cid or getattr(request.user, 'company_id', None)
                    
                    if active_cid and active_cid != origin_company_id:
                        data['error'] = 'Solo puede transferir productos desde su empresa activa'
                        return JsonResponse(data)
                    
                    # Crear transferencia
                    transfer = InternalTransfer()
                    transfer.company_id = origin_company_id  # La transferencia pertenece a la empresa origen
                    transfer.created_by = request.user
                    transfer.origin_pos = f"{origin_company.name[:3]}-{origin_company.pos}"
                    transfer.destination_pos = f"{destination_company.name[:3]}-{destination_company.pos}"
                    transfer.observations = f"Transferencia a {destination_company.name}. " + request.POST.get('observations', '')
                    transfer.save()
                    
                    # Procesar productos
                    products_data = request.POST.getlist('products[]')
                    quantities_data = request.POST.getlist('quantities[]')
                    prices_data = request.POST.getlist('prices[]')
                    total_amount = 0
                    
                    for i, product_id in enumerate(products_data):
                        if i < len(quantities_data) and i < len(prices_data):
                            # Buscar producto en empresa origen
                            product = Product.objects.filter(pk=product_id, company_id=origin_company_id).first()
                            if product:
                                quantity = Decimal(str(quantities_data[i] or '0'))
                                unit_price = Decimal(str(prices_data[i] or '0'))
                                
                                if quantity > 0:
                                    # Verificar stock suficiente en origen
                                    if product.stock >= quantity:
                                        # Crear detalle
                                        detail = InternalTransferDetail()
                                        detail.transfer = transfer
                                        detail.product = product
                                        detail.quantity = quantity
                                        detail.unit_price = unit_price
                                        detail.save()
                                        
                                        total_amount += quantity * unit_price
                                        
                                        # Descontar stock del origen
                                        product.stock -= quantity
                                        product.synced_to_server = False  # Marcar para sincronizar
                                        product.save()
                                        
                                        # Buscar o crear producto en destino
                                        dest_product = Product.objects.filter(
                                            name=product.name, 
                                            company_id=destination_company_id
                                        ).first()
                                        
                                        if dest_product:
                                            # Si existe, aumentar stock
                                            dest_product.stock += quantity
                                            dest_product.synced_to_server = False  # Marcar para sincronizar
                                            dest_product.save()
                                        else:
                                            # Si no existe, crear copia en destino
                                            dest_product = Product.objects.create(
                                                name=product.name,
                                                code=product.code,
                                                cat=product.cat,
                                                company_id=destination_company_id,
                                                cost_price=product.cost_price,
                                                pvp=product.pvp,
                                                iva_rate=product.iva_rate,
                                                pvp_final=product.pvp_final,
                                                unit=product.unit,
                                                stock=quantity,
                                                is_active=True
                                            )
                                    else:
                                        data['error'] = f'Stock insuficiente para {product.name}. Disponible: {product.stock}, Requerido: {quantity}'
                                        return JsonResponse(data)
                    
                    # Cambiar estado a "En Tránsito"
                    transfer.status = 'in_transit'
                    transfer.save()
                    
                    # Agregar información de montos
                    data['id'] = transfer.id
                    data['transfer_number'] = transfer.transfer_number
                    data['total_amount'] = float(total_amount)
                    data['origin_company'] = origin_company.name
                    data['destination_company'] = destination_company.name
                    data['success'] = f'Transferencia creada exitosamente. Monto total: ${total_amount:.2f}'
            
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
                        product.synced_to_server = False  # Marcar para sincronizar
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
                            product.synced_to_server = False  # Marcar para sincronizar
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
