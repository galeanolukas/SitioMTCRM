from core.erp.mixins import ValidatePermissionRequiredMixin, CompanyInitialMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django import forms
from core.erp.models import Sale, Product, DetSale, Company, Client, QuickOrder, Category, CashRegister, EmployeeAccountSale, DetEmployeeAccount, SaleVatBreakdown, CardInstallmentPlan
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.conf import settings
try:
    from weasyprint import HTML, CSS
except Exception:
    HTML = CSS = None
import os
from core.erp.forms import SaleForm
from django.views.generic import CreateView, ListView, DeleteView, UpdateView, TemplateView, View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from django.db import transaction, IntegrityError
from django.db.models import F, Q
from django.db.models.functions import Greatest
from django.utils import timezone
import pytz
from decimal import Decimal
import time
import uuid
import logging

try:
    from core.erp.afip.client import AfipClient
except ImportError:
    AfipClient = None

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class POSView(LoginRequiredMixin, ValidatePermissionRequiredMixin, TemplateView):
    template_name = 'sale/pos.html'
    permission_required = 'erp.add_sale'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'POS / API de Ventas'
        context['entity'] = 'Ventas'
        # Usuarios normales: siempre usar su empresa asignada
        if self.request.user.is_superuser:
            active_cid = self.request.session.get('company_id')
        else:
            active_cid = getattr(self.request.user, 'company', None)
            if active_cid:
                active_cid = active_cid.id

        # Obtener tipo de factura por defecto desde configuración AFIP
        from core.erp.afip.config import get_afip_config
        afip_config = get_afip_config(active_cid)
        tipo_map = {1: 'A', 6: 'B', 11: 'C'}
        default_invoice_type = tipo_map.get(afip_config.get('tipo_comprobante', 6), 'B') if afip_config else 'B'
        context['default_invoice_type'] = default_invoice_type
        
        # Obtener planes de cuotas de tarjeta
        from core.erp.models import CardInstallmentPlan
        card_plans = CardInstallmentPlan.objects.filter(is_active=True).order_by('name', 'installments')
        if active_cid:
            card_plans = card_plans.filter(company_id=active_cid)
        context['card_plans'] = card_plans
        qs = Sale.objects.all().select_related('cli')
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        # Filtrar por pos_id para mostrar solo ventas y presupuestos de este POS
        import socket
        current_pos_id = socket.gethostname() or 'pos_default'
        # Incluir ventas sin pos_id (compatibilidad) y ventas con el mismo pos_id
        qs = qs.filter(Q(pos_id__isnull=True) | Q(pos_id='') | Q(pos_id=current_pos_id))
        from django.db.models import Sum
        # Determinar si el usuario está en el grupo "Servidor Local" para enviar presupuestos
        is_local_server_user = self.request.user.groups.filter(name='Servidor Local').exists()
        context['is_local_server_user'] = is_local_server_user
        if is_local_server_user:
            # Para Servidor Local: mostrar solo presupuestos como cola
            qs = qs.filter(is_budget=True, status='budget')
            context['recent_sales'] = qs.annotate(items=Sum('detsale__cant')).order_by('-id')[:20]
            print(f"[DEBUG] POS get_context: is_local_server_user=True, presupuestos en cola: {context['recent_sales'].count()}, pos_id={current_pos_id}")
            for s in context['recent_sales']:
                print(f"[DEBUG]   Presupuesto: id={s.id}, cli={s.cli}, total={s.total}, pos_id={s.pos_id}, date={s.date_joined}")
        else:
            context['recent_sales'] = qs.annotate(items=Sum('detsale__cant')).order_by('-id')[:10]
            print(f"[DEBUG] POS get_context: is_local_server_user=False, ventas recientes: {len(context['recent_sales'])}, pos_id={current_pos_id}")
        # Estado de caja para el usuario/empresa actual
        cr_qs = CashRegister.objects.filter(user=self.request.user, is_closed=False)
        if active_cid:
            cr_qs = cr_qs.filter(company_id=active_cid)
        current_cr = cr_qs.order_by('-created_at').first()
        context['cash_register'] = current_cr
        context['cash_register_is_open'] = bool(current_cr)
        # Determinar si el usuario es operador
        is_operator = self.request.user.groups.filter(name__in=['operadores', 'vendedor']).exists()
        context['is_operator'] = is_operator
        # Desactivar botones POS cuando no hay caja abierta (para todos los usuarios)
        context['pos_locked_by_cash'] = not current_cr
        return context

    def calculate_vat_breakdown(self, sale):
        """Calcular y guardar la apertura de alícuotas de IVA para una venta"""
        from django.db.models import Sum
        
        # Eliminar aperturas existentes para esta venta
        SaleVatBreakdown.objects.filter(sale=sale).delete()
        
        # Agrupar detalles por código de IVA AFIP
        vat_breakdown = {}
        for det in sale.detsale_set.all():
            if det.prod and det.prod.vat_code:
                vat_code = det.prod.vat_code
                vat_rate = det.prod.iva_rate or Decimal('0.00')
                
                if vat_code not in vat_breakdown:
                    vat_breakdown[vat_code] = {
                        'vat_rate': vat_rate,
                        'taxable_base': Decimal('0.00'),
                        'vat_amount': Decimal('0.00')
                    }
                
                vat_breakdown[vat_code]['taxable_base'] += Decimal(str(det.subtotal))
                vat_breakdown[vat_code]['vat_amount'] += Decimal(str(det.iva_amount))
        
        # Crear registros de apertura de IVA
        for vat_code, data in vat_breakdown.items():
            SaleVatBreakdown.objects.create(
                sale=sale,
                vat_code=vat_code,
                vat_rate=data['vat_rate'],
                taxable_base=data['taxable_base'],
                vat_amount=data['vat_amount']
            )

    def create_vat_breakdown_from_payload(self, sale, vat_breakdown):
        """Crear apertura de alícuotas de IVA desde el payload del POS"""
        from decimal import Decimal
        
        # Mapeo de tasas de IVA a códigos AFIP
        vat_code_mapping = {
            '21.0': '5',   # 21%
            '10.5': '4',  # 10.5%
            '27.0': '6',  # 27%
            '0.0': '3',   # 0% (Exento)
            '2.5': '2',   # 2.5%
            '5.0': '8',   # 5%
        }
        
        # Crear o actualizar registros de apertura de IVA desde el payload
        for rate_percent, data in vat_breakdown.items():
            vat_code = vat_code_mapping.get(rate_percent, '5')  # Default a 21%
            vat_rate = Decimal(str(rate_percent))
            
            SaleVatBreakdown.objects.update_or_create(
                sale=sale,
                vat_code=vat_code,
                defaults={
                    'vat_rate': vat_rate,
                    'taxable_base': Decimal(str(data['base'])),
                    'vat_amount': Decimal(str(data['amount']))
                }
            )

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST.get('action')
            if action == 'get_client_data':
                client_id = request.POST.get('client_id')
                if not client_id:
                    return JsonResponse({'error': 'ID de cliente requerido'}, status=400)
                try:
                    client_obj = Client.objects.get(pk=client_id)
                    data = {
                        'id': client_obj.id,
                        'name': client_obj.names,
                        'cuit_cuil': client_obj.cuit_cuil or '',
                        'dni': client_obj.dni or '',
                        'condicion_iva': client_obj.condicion_iva or 'CF',
                        'condicion_iva_display': client_obj.get_condicion_iva_display() or 'Consumidor Final',
                        'address': client_obj.address or '',
                    }
                except Client.DoesNotExist:
                    return JsonResponse({'error': 'Cliente no encontrado'}, status=404)
            elif action == 'consult_afip_padron':
                cuit = request.POST.get('cuit')
                if not cuit:
                    return JsonResponse({'error': 'CUIT requerido'}, status=400)
                if request.user.is_superuser:
                    active_cid = request.session.get('company_id')
                else:
                    active_cid = getattr(request.user, 'company_id', None)
                try:
                    afip_client = AfipClient(company_id=active_cid)
                    # Usar RegisterScopeTen (no requiere autorización adicional)
                    result = afip_client.get_taxpayer_data(cuit)
                    if 'error' in result:
                        data = {'error': result['error']}
                    else:
                        # Mapear condición IVA desde respuesta AFIP
                        condicion_iva_map = {
                            'RI': 'RI',
                            'RESPONSABLE_INSCRIPTO': 'RI',
                            'M': 'M',
                            'MONOTRIBUTUTO': 'M',
                            'CF': 'CF',
                            'CONSUMIDOR_FINAL': 'CF',
                            'EX': 'EX',
                            'EXENTO': 'EX',
                            'NC': 'NC',
                            'NO_CATEGORIZADO': 'NC'
                        }
                        afip_condicion = result.get('condicion_iva', '').upper()
                        condicion_iva = condicion_iva_map.get(afip_condicion, 'CF')
                        data = {
                            'success': True,
                            'name': result.get('nombre', ''),
                            'cuit': result.get('cuit', cuit),
                            'condicion_iva': condicion_iva,
                            'condicion_iva_display': result.get('condicion_iva', 'Consumidor Final'),
                            'address': result.get('direccion', ''),
                            'impuestos': result.get('impuestos', [])
                        }
                except Exception as e:
                    data = {'error': f'No se pudo consultar AFIP: {str(e)}'}
            elif action == 'create_client_from_afip':
                afip_data = json.loads(request.POST.get('afip_data') or '{}')
                try:
                    # Verificar si ya existe cliente con ese CUIT
                    existing_client = Client.objects.filter(cuit_cuil=afip_data.get('cuit')).first()
                    if existing_client:
                        data = {
                            'success': True,
                            'client_id': existing_client.id,
                            'message': 'Cliente ya existe'
                        }
                    else:
                        # Crear nuevo cliente desde datos AFIP
                        if request.user.is_superuser:
                            active_cid = request.session.get('company_id')
                        else:
                            active_cid = getattr(request.user, 'company_id', None)

                        new_client = Client()
                        if active_cid:
                            new_client.company_id = active_cid
                        new_client.names = afip_data.get('name', '')
                        new_client.cuit_cuil = afip_data.get('cuit', '')
                        new_client.condicion_iva = afip_data.get('condicion_iva', 'CF')
                        new_client.address = afip_data.get('address', '')
                        new_client.save()

                        data = {
                            'success': True,
                            'client_id': new_client.id,
                            'message': 'Cliente creado exitosamente'
                        }
                except Exception as e:
                    data = {'error': f'Error al crear cliente: {str(e)}'}
            elif action == 'product_by_code':
                code = (request.POST.get('code') or '').strip()
                if not code:
                    return JsonResponse({'error': 'Código vacío'}, status=400)
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id
                qs = Product.objects.all()
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                else:
                    qs = qs.none()
                
                # Priorizar búsqueda por código exacto primero
                prod = qs.filter(code__iexact=code).first()
                
                # Si no encuentra por código, buscar por nombre exacto
                if not prod:
                    prod = qs.filter(name__iexact=code).first()
                
                # Si aún no encuentra, buscar por nombre que contenga el término
                if not prod:
                    prod = qs.filter(name__icontains=code).first()
                
                if not prod:
                    return JsonResponse({'error': 'Producto no encontrado'}, status=404)
                # Construir respuesta manualmente para asegurar que todos los campos lleguen
                data = {
                    'id': prod.id,
                    'name': prod.name,
                    'pvp': float(prod.pvp),
                    'pvp_final': float(prod.pvp_final),
                    'stock': float(prod.stock),
                    'code': prod.code,
                    'iva_rate': float(prod.iva_rate) if prod.iva_rate else 0.0,
                    'track_stock': prod.track_stock,
                    'is_out_of_stock': prod.is_out_of_stock(),
                    'has_low_stock': prod.has_low_stock(),
                    'unit': prod.unit,
                    'unit_display': prod.get_unit_display()
                }
                
                # Agregar advertencias de stock
                if prod.is_out_of_stock():
                    data['stock_warning'] = 'SIN STOCK - No hay unidades disponibles'
                    data['stock_warning_type'] = 'danger'
                elif prod.has_low_stock():
                    data['stock_warning'] = f'STOCK BAJO - Solo {prod.stock} {prod.get_unit_display()} disponibles'
                    data['stock_warning_type'] = 'warning'
                
                # Formatear valores monetarios con separadores de miles
                if 'pvp' in data:
                    data['pvp_formatted'] = "${:,.2f}".format(float(data['pvp']))
                if 'pvp_final' in data:
                    data['pvp_final_formatted'] = "${:,.2f}".format(float(data['pvp_final']))
            elif action == 'search_products':
                term = (request.POST.get('term') or '').strip()
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id
                qs = Product.objects.all()
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                else:
                    qs = qs.none()
                # Búsqueda simple por nombre o código
                if term:
                    qs = qs.filter(Q(name__icontains=term) | Q(code__icontains=term))
                qs = qs[:10]
                data = []
                for p in qs:
                    item = {
                        'id': p.id,
                        'name': p.name,
                        'pvp': float(p.pvp),
                        'pvp_final': float(p.pvp_final),
                        'stock': float(p.stock),
                        'code': p.code or '',
                        'iva_rate': float(getattr(p, 'iva_rate', 0) or 0),
                        'unit': p.unit,
                        'unit_display': p.get_unit_display()
                    }
                    data.append(item)
                return JsonResponse(data, safe=False)
            elif action == 'quick_create_product':
                from decimal import Decimal
                name = (request.POST.get('name') or 'PRODUCTO GENERICO').strip()
                raw_price = request.POST.get('price') or '0'
                raw_iva = request.POST.get('iva_rate') or '0'
                code = (request.POST.get('code') or '').strip() or None

                try:
                    price = Decimal(str(raw_price))
                    iva_rate = Decimal(str(raw_iva))
                except Exception:
                    raise Exception('Precio o IVA inválidos')

                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id

                # Obtener la categoría proporcionada o usar 'Varios' por defecto
                category_name = (request.POST.get('category') or 'Varios').strip()
                
                # Buscar la categoría o crearla si no existe
                cat, created = Category.objects.get_or_create(
                    name__iexact=category_name,
                    defaults={
                        'name': category_name,
                        'desc': f'Categoría para {category_name}'
                    }
                )

                # Reutilizar producto existente con el mismo nombre (y empresa), si existe
                prod_qs = Product.objects.filter(name=name)
                if active_cid:
                    prod_qs = prod_qs.filter(company_id=active_cid)

                prod = prod_qs.first()
                if prod is None:
                    prod = Product(
                        name=name,
                        code=code,
                        cat=cat,
                        pvp=price,
                        iva_rate=iva_rate,
                        track_stock=True,  # Activar control de stock por defecto
                    )
                    if active_cid:
                        prod.company_id = active_cid
                else:
                    # Actualizar datos básicos si ya existía
                    prod.code = code or prod.code
                    prod.pvp = price
                    prod.iva_rate = iva_rate
                    # No modificar track_stock al editar producto existente
                    prod.synced_to_server = False  # Marcar para sincronizar
                prod.save()
                data = prod.toJSON()
                
            elif action == 'list_categories':
                # Obtener categorías existentes
                categories = Category.objects.all().order_by('name')
                data = [{'id': cat.id, 'name': cat.name, 'desc': cat.desc or ''} for cat in categories]
            elif action == 'get_client_prices':
                client_id = request.POST.get('client_id')
                if not client_id:
                    data = {'has_price_list': False}
                else:
                    from core.erp.models import PriceList
                    client_obj = Client.objects.filter(pk=client_id).first()
                    if client_obj and client_obj.precio_lista_id and client_obj.precio_lista.is_active:
                        pl = client_obj.precio_lista
                        # Devolver info de la lista + precios ajustados para los productos del carrito
                        product_ids = request.POST.get('product_ids', '')
                        product_ids = [int(pid) for pid in product_ids.split(',') if pid]
                        prices = {}
                        for pid in product_ids:
                            prod = Product.objects.filter(pk=pid).first()
                            if prod:
                                adjusted = pl.get_price_for_product(prod)
                                prices[str(pid)] = float(adjusted)
                        data = {
                            'has_price_list': True,
                            'list_name': pl.name,
                            'discount_percentage': float(pl.discount_percentage),
                            'interest_percentage': float(pl.interest_percentage),
                            'prices': prices,
                        }
                    else:
                        data = {'has_price_list': False}
            elif action == 'get_price_lists':
                # Obtener listas de precios disponibles (filtradas por empresa activa)
                from core.erp.models import PriceList
                active_cid = request.session.get('company_id')
                if not active_cid:
                    active_cid = getattr(request.user, 'company_id', None)
                qs = PriceList.objects.filter(is_active=True)
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                price_lists = qs.order_by('name')
                data = [
                    {
                        'id': pl.id,
                        'name': pl.name,
                        'discount_percentage': float(pl.discount_percentage) if pl.discount_percentage else 0,
                        'interest_percentage': float(pl.interest_percentage) if pl.interest_percentage else 0
                    }
                    for pl in price_lists
                ]
            elif action == 'get_price_list_prices':
                # Obtener precios de una lista específica para los productos del carrito
                from core.erp.models import PriceList
                price_list_id = request.POST.get('price_list_id')
                product_ids = request.POST.get('product_ids', '')
                
                if not price_list_id:
                    data = {'has_price_list': False}
                else:
                    pl = PriceList.objects.filter(pk=price_list_id, is_active=True).first()
                    if not pl:
                        data = {'has_price_list': False}
                    else:
                        product_ids = [int(pid) for pid in product_ids.split(',') if pid]
                        prices = {}
                        for pid in product_ids:
                            prod = Product.objects.filter(pk=pid).first()
                            if prod:
                                adjusted = pl.get_price_for_product(prod)
                                prices[str(pid)] = float(adjusted)
                        data = {
                            'has_price_list': True,
                            'list_name': pl.name,
                            'discount_percentage': float(pl.discount_percentage) if pl.discount_percentage else 0,
                            'interest_percentage': float(pl.interest_percentage) if pl.interest_percentage else 0,
                            'prices': prices,
                        }
            elif action == 'get_employees':
                # Obtener lista de empleados para cuenta corriente
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                # Filtrar por empresa actual
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id
                
                employees = User.objects.filter(is_active=True).exclude(is_superuser=True)
                
                # Filtrar por empresa si está definida
                if active_cid:
                    employees = employees.filter(company_id=active_cid)
                
                employees = employees.order_by('first_name', 'last_name')
                data = []
                for emp in employees:
                    data.append({
                        'id': emp.id,
                        'name': emp.get_full_name() or emp.username,
                        'username': emp.username
                    })
                
            elif action == 'get_clients':
                # Obtener lista de clientes para cuenta corriente
                if request.user.is_superuser:
                    active_cid = request.session.get('company_id')
                else:
                    active_cid = getattr(request.user, 'company_id', None)

                clients = Client.objects.filter(is_active=True)
                if active_cid:
                    clients = clients.filter(company_id=active_cid)
                else:
                    clients = clients.none()

                clients = clients.order_by('names', 'surnames')
                data = []
                for cli in clients:
                    data.append({
                        'id': cli.id,
                        'name': f"{cli.names} {cli.surnames or ''}".strip(),
                    })

            elif action == 'search_clients':
                # Buscar clientes para el modal del POS
                if request.user.is_superuser:
                    active_cid = request.session.get('company_id')
                else:
                    active_cid = getattr(request.user, 'company_id', None)

                clients = Client.objects.filter(is_active=True)
                if active_cid:
                    clients = clients.filter(company_id=active_cid)
                else:
                    clients = clients.none()

                search_term = (request.POST.get('term') or '').strip()
                if search_term:
                    clients = clients.filter(
                        Q(names__icontains=search_term) |
                        Q(surnames__icontains=search_term) |
                        Q(dni__icontains=search_term) |
                        Q(cuit_cuil__icontains=search_term)
                    )

                data = []
                for cli in clients.order_by('names', 'surnames')[:50]:
                    data.append(cli.toJSON())

            elif action == 'create_category':
                name = (request.POST.get('name') or '').strip()
                if not name:
                    return JsonResponse({'error': 'El nombre de la categoría es requerido'}, status=400)
                    
                # Verificar si la categoría ya existe (case insensitive)
                if Category.objects.filter(name__iexact=name).exists():
                    return JsonResponse({'error': 'Ya existe una categoría con ese nombre'}, status=400)
                
                # Crear la nueva categoría
                category = Category(
                    name=name,
                    desc=request.POST.get('desc', '')
                )
                
                # Asignar empresa si es necesario
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id
                if active_cid and hasattr(Category, 'company'):
                    category.company_id = active_cid
                    
                category.save()
                data = {'id': category.id, 'name': category.name, 'desc': category.desc or ''}
            elif action == 'create_sale':
                from decimal import Decimal
                # Prevenir duplicación con token de sesión
                sale_token = request.POST.get('sale_token')
                if not sale_token:
                    return JsonResponse({'error': 'Token de venta requerido'}, status=400)
                
                # Verificar si este token ya fue procesado
                if request.session.get(f'processed_sale_{sale_token}'):
                    return JsonResponse({'error': 'Venta ya procesada', 'duplicate': True}, status=400)
                
                payload = json.loads(request.POST.get('sale') or '{}')
                is_budget = payload.get('is_budget', False)
                print(f"[DEBUG] create_sale: is_budget={is_budget}, payload keys={list(payload.keys())}")
                
                # Los presupuestos NO requieren caja abierta
                if not is_budget:
                    is_operator = request.user.groups.filter(name__in=['operadores', 'vendedor']).exists()
                    active_cid = request.session.get('company_id')
                    if not request.user.is_superuser:
                        if not active_cid:
                            company = getattr(request.user, 'company', None)
                            if company:
                                active_cid = company.id
                    cr_qs = CashRegister.objects.filter(user=request.user, is_closed=False)
                    if active_cid:
                        cr_qs = cr_qs.filter(company_id=active_cid)
                    current_cr = cr_qs.order_by('-created_at').first()
                    if is_operator and not current_cr:
                        return JsonResponse({'error': 'Debe abrir una caja antes de registrar ventas.'}, status=400)
                
                with transaction.atomic():
                    items = payload.get('products', payload.get('items', []))
                    # Validar stock solo si NO es presupuesto
                    if not is_budget:
                        for it in items:
                            prod = Product.objects.select_for_update().get(pk=it['id'])
                            raw_cant = it.get('cant', 1)
                            cant = Decimal(str(raw_cant or '1'))
                            if cant <= 0:
                                raise Exception("Cantidad inválida")
                            if getattr(prod, 'track_stock', True) and prod.stock < cant:
                                raise Exception(f"Stock insuficiente para {prod.name}. Disponible: {format(prod.stock, '.2f')} {prod.get_unit_display()}, requerido: {format(cant, '.2f')} {prod.get_unit_display()}")
                    
                    sale = Sale()
                    # Obtener empresa activa: primero de sesión, luego del usuario
                    active_cid = request.session.get('company_id')
                    if not active_cid:
                        active_cid = getattr(request.user, 'company', None)
                        if active_cid:
                            active_cid = active_cid.id
                    
                    # Si no hay empresa activa, usar la primera empresa disponible como fallback
                    if not active_cid:
                        from core.erp.models import Company
                        first_company = Company.objects.first()
                        if first_company:
                            active_cid = first_company.id
                            logger.warning(f"[POS] No hay empresa activa en sesión/usuario, usando empresa por defecto: {first_company.name}")
                    
                    if active_cid:
                        sale.company_id = active_cid
                    sale.cli_id = payload.get('cli') or None
                    sale.subtotal = float(payload.get('subtotal', 0))
                    sale.iva = float(payload.get('iva', 0))
                    sale.total = float(payload.get('total', 0))
                    sale.payment_method = payload.get('payment_method') or 'cash'
                    
                    # Guardar datos de tarjeta si corresponde
                    if payload.get('payment_method') == 'card':
                        sale.card_type = payload.get('card_type')
                        sale.card_brand = payload.get('card_brand')
                        sale.card_auth_code = payload.get('card_auth_code')
                        if payload.get('card_plan_id'):
                            from core.erp.models import CardInstallmentPlan
                            try:
                                card_plan = CardInstallmentPlan.objects.get(id=payload.get('card_plan_id'))
                                sale.card_plan = card_plan
                                sale.card_installments = card_plan.installments
                            except CardInstallmentPlan.DoesNotExist:
                                pass
                    
                    # Determinar tipo de comprobante según condición IVA del cliente
                    if payload.get('invoice_type'):
                        sale.invoice_type = payload.get('invoice_type')
                    else:
                        # Auto-detectar según condición IVA del cliente
                        client = Client.objects.filter(id=sale.cli_id).first() if sale.cli_id else None
                        client_cond_iva = client.condicion_iva if client else 'CF'
                        if client_cond_iva == 'RI':
                            sale.invoice_type = 'A'
                        elif client_cond_iva == 'EX':
                            sale.invoice_type = 'C'
                        else:
                            sale.invoice_type = 'B'
                    
                    sale.is_credit_note = payload.get('is_credit_note', False)

                    if is_budget:
                        sale.status = 'budget'
                        sale.is_budget = True
                        sale.budget_notes = payload.get('budget_notes', '')
                        import socket
                        sale.pos_id = socket.gethostname() or 'pos_default'
                        print(f"[DEBUG] Presupuesto configurado: pos_id={sale.pos_id}")
                    
                    if 'combined_payments' in payload and payload['combined_payments']:
                        sale.payment_details = payload['combined_payments']
                    
                    sale.save()
                    logger.info("pos_sale_saved", extra={
                        'sale_id': sale.id,
                        'is_budget': sale.is_budget,
                        'status': sale.status,
                        'total': float(sale.total)
                    })

                    request.session[f'processed_sale_{sale_token}'] = True
                    request.session.save()
                    
                    for it in items:
                        raw_cant = it.get('cant', 1)
                        cant = Decimal(str(raw_cant or '1'))
                        prod = Product.objects.select_for_update().get(pk=int(it['id']))
                        det = DetSale(
                            sale_id=sale.id,
                            prod_id=int(it['id']),
                            cant=cant,
                            price=float(it.get('price', it.get('pvp', 0))),
                            subtotal=float(it.get('subtotal', 0)),
                        )
                        # Calcular IVA basado en el producto
                        if prod and prod.iva_rate:
                            iva_rate = Decimal(str(prod.iva_rate))
                            if iva_rate > Decimal('1.0'):
                                iva_rate = iva_rate / Decimal('100.0')
                            det.iva_amount = float(Decimal(str(det.subtotal)) * iva_rate)
                        det.save()
                        if not is_budget:
                            if prod and getattr(prod, 'track_stock', True):
                                Product.objects.filter(pk=det.prod_id).update(
                                    stock=Greatest(F('stock') - cant, 0),
                                    stock_modified_locally=timezone.now(),
                                    synced_to_server=False
                                )
                    
                    # Calcular y guardar apertura de alícuotas de IVA
                    # Usar vat_breakdown del payload si está disponible, sino calcular desde detalles
                    vat_breakdown = payload.get('vat_breakdown')
                    if vat_breakdown:
                        self.create_vat_breakdown_from_payload(sale, vat_breakdown)
                    else:
                        self.calculate_vat_breakdown(sale)

                    # Actualizar Libro IVA con detalles ya cargados
                    sale._crear_registro_libro_iva_simple()

                    # Emitir factura AFIP una vez que los detalles están cargados
                    if not sale.is_budget and not sale.afip_cae:
                        sale.emitir_factura_afip(skip_afip_call_on_save=True)

                    data = {
                        'id': sale.id,
                        'is_budget': sale.is_budget,
                        'local_uuid': sale.local_uuid,
                        'afip_cae': sale.afip_cae or '',
                        'afip_cae_vto': sale.afip_cae_vto.strftime('%d/%m/%Y') if sale.afip_cae_vto else '',
                        'afip_qr': sale.afip_qr or '',
                        'afip_error': sale.afip_error or '',
                    }
            elif action == 'invoice':
                from decimal import Decimal
                # Prevenir duplicación con token de sesión
                sale_token = request.POST.get('sale_token')
                if not sale_token:
                    return JsonResponse({'error': 'Token de venta requerido'}, status=400)
                
                # Verificar si este token ya fue procesado
                if request.session.get(f'processed_invoice_{sale_token}'):
                    return JsonResponse({'error': 'Factura ya procesada', 'duplicate': True}, status=400)
                
                # Bloquear facturación para operadores sin caja abierta
                is_operator = request.user.groups.filter(name__in=['operadores', 'vendedor']).exists()
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id
                cr_qs = CashRegister.objects.filter(user=request.user, is_closed=False)
                if active_cid:
                    cr_qs = cr_qs.filter(company_id=active_cid)
                current_cr = cr_qs.order_by('-created_at').first()
                if is_operator and not current_cr:
                    return JsonResponse({'error': 'Debe abrir una caja antes de facturar.'}, status=400)
                payload = json.loads(request.POST.get('sale') or '{}')
                with transaction.atomic():
                    items = payload.get('items', [])
                    # Validar stock con cantidades decimales
                    for it in items:
                        prod = Product.objects.select_for_update().get(pk=it['id'])
                        raw_cant = it.get('cant', 1)
                        cant = Decimal(str(raw_cant or '1'))
                        if cant <= 0:
                            raise Exception("Cantidad inválida")
                        if prod.stock < cant:
                            raise Exception(f"Stock insuficiente para {prod.name}")
                    sale = Sale()
                    # Asignar empresa activa a la venta
                    active_cid = request.session.get('company_id')
                    if not request.user.is_superuser:
                        if not active_cid:
                            company = getattr(request.user, 'company', None)
                            if company:
                                active_cid = company.id
                    if active_cid:
                        sale.company_id = active_cid
                    sale.cli_id = payload.get('cli') or None
                    sale.subtotal = float(payload.get('subtotal', 0))
                    sale.iva = float(payload.get('iva', 0))
                    sale.total = float(payload.get('total', 0))
                    sale.payment_method = payload.get('payment_method') or 'cash'
                    
                    # Guardar datos de tarjeta si corresponde
                    if payload.get('payment_method') == 'card':
                        sale.card_type = payload.get('card_type')
                        sale.card_brand = payload.get('card_brand')
                        sale.card_auth_code = payload.get('card_auth_code')
                        if payload.get('card_plan_id'):
                            from core.erp.models import CardInstallmentPlan
                            try:
                                card_plan = CardInstallmentPlan.objects.get(id=payload.get('card_plan_id'))
                                sale.card_plan = card_plan
                                sale.card_installments = card_plan.installments
                            except CardInstallmentPlan.DoesNotExist:
                                pass
                    
                    # Determinar tipo de comprobante según condición IVA del cliente
                    if payload.get('invoice_type'):
                        sale.invoice_type = payload.get('invoice_type')
                    else:
                        # Auto-detectar según condición IVA del cliente
                        client = Client.objects.filter(id=sale.cli_id).first() if sale.cli_id else None
                        client_cond_iva = client.condicion_iva if client else 'CF'
                        if client_cond_iva == 'RI':
                            sale.invoice_type = 'A'
                        elif client_cond_iva == 'EX':
                            sale.invoice_type = 'C'
                        else:
                            sale.invoice_type = 'B'
                    
                    sale.is_credit_note = payload.get('is_credit_note', False)

                    # Generar facturación: usar el POS configurado en la empresa de la venta
                    company = sale.company or Company.objects.first()
                    sale.invoice_pos = (company.pos if company else sale.invoice_pos) or '0001'

                    # Verificar si se permite ventas sin AFIP
                    from core.erp.models import GlobalPosConfig, AfipConfig
                    allow_without_afip = GlobalPosConfig.allow_sales_without_afip()
                    afip_config = AfipConfig.objects.filter(company=company, is_active=True).first()

                    if afip_config:
                        # Hay configuración AFIP, usar flujo normal
                        # Determinar tipo de comprobante según condición IVA del cliente
                        client_cond_iva = sale.cli.condicion_iva if sale.cli else 'CF'
                        
                        # Mapeo según normativa AFIP RG 5616/2024
                        if client_cond_iva == 'RI':
                            # Responsable Inscripto → Factura A
                            sale.invoice_type = 'A'
                        elif client_cond_iva == 'EX':
                            # Exento → Factura C
                            sale.invoice_type = 'C'
                        else:
                            # Monotributista o Consumidor Final → Factura B
                            sale.invoice_type = 'B'
                        
                        sale.invoice_number = sale.next_sequential_for_pos_type()
                        sale.is_invoiced = True
                    elif allow_without_afip:
                        # No hay configuración AFIP pero está permitido: usar ticket X
                        sale.invoice_type = 'X'  # Ticket X sin valor fiscal
                        sale.invoice_number = sale.next_sequential_for_pos_type()
                        sale.is_invoiced = True
                        sale.is_ticket_x = True  # Marcar como ticket X
                    else:
                        # No hay configuración AFIP y no está permitido: error
                        data = {'error': 'No hay configuración AFIP. Configure AFIP o habilite ventas sin AFIP en configuración global.'}
                        return JsonResponse(data, status=400)

                    sale.save()
                    # Marcar token como procesado
                    request.session[f'processed_invoice_{sale_token}'] = True
                    request.session.save()
                    for it in items:
                        raw_cant = it.get('cant', 1)
                        cant = Decimal(str(raw_cant or '1'))
                        prod = Product.objects.filter(pk=int(it['id'])).first()
                        det = DetSale(
                            sale_id=sale.id,
                            prod_id=int(it['id']),
                            cant=cant,
                            price=float(it.get('price', it.get('pvp', 0))),
                            subtotal=float(it.get('subtotal', 0)),
                        )
                        # Calcular IVA basado en el producto
                        if prod and prod.iva_rate:
                            iva_rate = Decimal(str(prod.iva_rate))
                            if iva_rate > Decimal('1.0'):
                                iva_rate = iva_rate / Decimal('100.0')
                            det.iva_amount = float(Decimal(str(det.subtotal)) * iva_rate)
                        det.save()
                        if prod and getattr(prod, 'track_stock', True):
                            Product.objects.filter(pk=det.prod_id).update(
                                stock=Greatest(F('stock') - cant, 0),
                                stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                                synced_to_server=False  # Marcar para sincronizar
                            )
                    
                    # Calcular y guardar apertura de alícuotas de IVA
                    self.calculate_vat_breakdown(sale)

                    # Actualizar Libro IVA con detalles ya cargados
                    sale._crear_registro_libro_iva_simple()

                    # Emitir factura AFIP una vez que los detalles están cargados
                    if not sale.is_budget and not sale.afip_cae and afip_config:
                        sale.emitir_factura_afip(skip_afip_call_on_save=True)

                    data = {
                        'id': sale.id,
                        'invoice_url': reverse_lazy('erp:invoice_pdf', kwargs={'pk': sale.id}),
                        'afip_cae': sale.afip_cae or '',
                        'afip_cae_vto': sale.afip_cae_vto.strftime('%d/%m/%Y') if sale.afip_cae_vto else '',
                        'afip_qr': sale.afip_qr or '',
                        'afip_error': sale.afip_error or '',
                    }
            elif action == 'import_quickorder':
                qo_id = request.POST.get('quickorder_id') or ''
                pref_id = request.POST.get('preference_id') or ''
                qs = QuickOrder.objects.all()
                if pref_id:
                    qs = qs.filter(preference_id=pref_id)
                elif qo_id:
                    qs = qs.filter(id=qo_id)
                else:
                    raise Exception('Debe indicar un ID de orden rápida o un preference_id')

                qo = qs.select_for_update().first()
                if not qo:
                    raise Exception('Orden rápida no encontrada')

                if qo.status == 'paid':
                    raise Exception('Esta orden rápida ya fue importada como venta (estado pagada)')

                with transaction.atomic():
                    sale = Sale()
                    sale.company = qo.company
                    sale.cli_id = None
                    sale.subtotal = float(qo.total)
                    sale.iva = 0.0
                    sale.total = float(qo.total)
                    sale.payment_method = 'mp'
                    sale.save()

                    for it in qo.items:
                        prod_id = it.get('product_id')
                        if not prod_id:
                            continue
                        prod = Product.objects.select_for_update().get(pk=prod_id)
                        
                        # Determinar la cantidad según la unidad del producto
                        if prod.unit == 'kg':
                            cant = float(it.get('quantity', 1) or 1)
                        else:
                            cant = int(it.get('quantity', 1) or 1)
                            
                        if getattr(prod, 'track_stock', True) and prod.stock < cant:
                            raise Exception(f"Stock insuficiente para {prod.name}. Disponible: {format(prod.stock, '.2f')} {prod.get_unit_display()}, requerido: {format(cant, '.2f')} {prod.get_unit_display()}")
                        price = float(it.get('unit_price', 0))
                        subtotal = float(it.get('line_total', price * cant))
                        DetSale.objects.create(
                            sale=sale,
                            prod=prod,
                            cant=cant,
                            price=price,
                            subtotal=subtotal,
                        )
                        if getattr(prod, 'track_stock', True):
                            Product.objects.filter(pk=prod.id).update(
                                stock=Greatest(F('stock') - cant, 0),
                                stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                                synced_to_server=False  # Marcar para sincronizar
                            )

                    qo.status = 'paid'
                    qo.save(update_fields=['status'])
                    data = {'id': sale.id}
            elif action == 'create_employee_account_sale':
                from decimal import Decimal
                # Prevenir duplicación con token de sesión
                sale_token = request.POST.get('sale_token')
                if not sale_token:
                    return JsonResponse({'error': 'Token de venta requerido'}, status=400)
                
                # Verificar si este token ya fue procesado
                if request.session.get(f'processed_emp_sale_{sale_token}'):
                    return JsonResponse({'error': 'Venta de cuenta corriente ya procesada', 'duplicate': True}, status=400)
                
                # Bloquear registro de ventas para operadores sin caja abierta
                is_operator = request.user.groups.filter(name__in=['operadores', 'vendedor']).exists()
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id
                cr_qs = CashRegister.objects.filter(user=request.user, is_closed=False)
                if active_cid:
                    cr_qs = cr_qs.filter(company_id=active_cid)
                current_cr = cr_qs.order_by('-created_at').first()
                if is_operator and not current_cr:
                    return JsonResponse({'error': 'Debe abrir una caja antes de registrar ventas.'}, status=400)
                    
                payload = json.loads(request.POST.get('sale') or '{}')
                employee_id = payload.get('employee_id')
                client_id = payload.get('client_id')
                if not employee_id and not client_id:
                    return JsonResponse({'error': 'Debe seleccionar un cliente o empleado'}, status=400)

                with transaction.atomic():
                    items = payload.get('items', [])
                    # Validar stock con cantidades decimales
                    for it in items:
                        prod = Product.objects.select_for_update().get(pk=it['id'])
                        raw_cant = it.get('cant', 1)
                        cant = Decimal(str(raw_cant or '1'))
                        if cant <= 0:
                            raise Exception("Cantidad inválida")
                        if getattr(prod, 'track_stock', True) and prod.stock < cant:
                            raise Exception(f"Stock insuficiente para {prod.name}. Disponible: {format(prod.stock, '.2f')} {prod.get_unit_display()}, requerido: {format(cant, '.2f')} {prod.get_unit_display()}")

                    # Crear venta por cuenta corriente
                    emp_sale = EmployeeAccountSale()
                    if active_cid:
                        emp_sale.company_id = active_cid
                    if client_id:
                        emp_sale.client_id = client_id
                    if employee_id:
                        emp_sale.employee_id = employee_id
                    emp_sale.subtotal = float(payload.get('subtotal', 0))
                    emp_sale.iva = float(payload.get('iva', 0))
                    emp_sale.total = float(payload.get('total', 0))
                    emp_sale.notes = payload.get('notes', '')
                    
                    # Guardar detalles de pago combinado si existen
                    if 'payment_details' in payload and payload['payment_details']:
                        emp_sale.payment_details = payload['payment_details']
                        # Si hay pago parcial, marcar como pagado parcialmente
                        payment_amount = payload['payment_details'].get('amount', 0)
                        if payment_amount > 0:
                            emp_sale.is_paid = False  # Aún tiene deuda
                            # Podríamos agregar un campo para el monto pagado si fuera necesario
                    
                    # Establecer zona horaria local
                    import pytz
                    emp_sale.local_timezone = 'America/Argentina/Buenos_Aires'
                    
                    emp_sale.save()
                    
                    # Marcar token como procesado
                    request.session[f'processed_emp_sale_{sale_token}'] = True
                    request.session.save()
                    
                    # Crear detalles y descontar stock
                    for it in items:
                        raw_cant = it.get('cant', 1)
                        cant = Decimal(str(raw_cant or '1'))
                        price = Decimal(str(it.get('price', it.get('pvp', 0))))
                        subtotal = Decimal(str(it.get('subtotal', 0)))
                        
                        # Para empleados, no se calcula IVA
                        iva_amount = Decimal('0')
                        
                        det = DetEmployeeAccount(
                            employee_account_id=emp_sale.id,
                            prod_id=int(it['id']),
                            cant=cant,
                            price=price,
                            subtotal=subtotal,
                            iva_amount=iva_amount
                        )
                        det.save()
                        
                        # Obtener producto para actualizar stock
                        prod = Product.objects.get(pk=int(it['id']))
                        if getattr(prod, 'track_stock', True):
                            Product.objects.filter(pk=det.prod_id).update(
                                stock=Greatest(F('stock') - cant, 0),
                                stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                                synced_to_server=False  # Marcar para sincronizar
                            )
                    data = {'id': emp_sale.id, 'message': 'Venta por cuenta corriente registrada correctamente'}
            elif action == 'add_employee':
                # Agregar nuevo empleado
                from django.contrib.auth import get_user_model
                name = request.POST.get('name', '').strip()
                email = request.POST.get('email', '').strip()
                
                if not name:
                    data['error'] = 'Debe ingresar el nombre del empleado'
                    return JsonResponse(data, safe=False)
                
                try:
                    User = get_user_model()
                    # Verificar si ya existe un usuario con ese email
                    if email and User.objects.filter(email=email).exists():
                        data['error'] = 'Ya existe un usuario con ese email'
                        return JsonResponse(data, safe=False)
                    
                    # Crear nuevo usuario/empleado
                    username = name.lower().replace(' ', '_') + '_' + str(int(time.time()))
                    user = User.objects.create_user(
                        username=username,
                        email=email or '',
                        first_name=name,
                        password=User.objects.make_random_password(),  # Contraseña aleatoria
                        is_active=True
                    )
                    
                    # Asociar el empleado a la empresa activa
                    active_cid = request.session.get('company_id')
                    if not request.user.is_superuser:
                        if not active_cid:
                            company = getattr(request.user, 'company', None)
                            if company:
                                active_cid = company.id
                    
                    if active_cid:
                        user.company_id = active_cid
                        user.save()
                    
                    data = {
                        'id': user.id,
                        'name': name,
                        'message': 'Empleado agregado correctamente'
                    }
                except Exception as e:
                    data['error'] = f'Error al crear empleado: {str(e)}'
        except Exception as e:
            logger.error(f"Error en POST de POS: {str(e)}", exc_info=True)
            data['error'] = str(e)
        return JsonResponse(data, safe=False)


def ticket_print(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('cli', 'company'), pk=pk)
    dets = sale.detsale_set.select_related('prod').all()
    # Usar la empresa asociada a la venta; si no hay, caer a la primera definida
    company = sale.company or Company.objects.first()

    # Obtener punto de venta AFIP si está configurado
    punto_venta_afip = None
    if sale.company:
        from core.erp.models import AfipPuntoVenta
        punto_venta = AfipPuntoVenta.objects.filter(
            company=sale.company,
            is_active=True
        ).first()
        if punto_venta:
            punto_venta_afip = f"{punto_venta.numero:04d}"

    ctx = {
        'sale': sale,
        'dets': dets,
        'company': company,
        'punto_venta_afip': punto_venta_afip,
    }
    return render(request, 'sale/ticket_print.html', ctx)


def ticket_x_print(request, pk):
    """Imprimir ticket X (comprobante sin valor fiscal)"""
    sale = get_object_or_404(Sale.objects.select_related('cli', 'company'), pk=pk)
    dets = sale.detsale_set.select_related('prod').all()
    # Usar la empresa asociada a la venta; si no hay, caer a la primera definida
    company = sale.company or Company.objects.first()

    ctx = {
        'sale': sale,
        'dets': dets,
        'company': company,
    }
    return render(request, 'sale/ticket_x.html', ctx)


def ticket_budget_print(request, pk):
    """Imprimir ticket de presupuesto (sin valor fiscal)"""
    sale = get_object_or_404(Sale.objects.select_related('cli', 'company'), pk=pk, is_budget=True, status='budget')
    dets = sale.detsale_set.select_related('prod').all()
    company = sale.company or Company.objects.first()

    ctx = {
        'sale': sale,
        'dets': dets,
        'company': company,
    }
    return render(request, 'sale/ticket_budget.html', ctx)


class SaleCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    model = Sale
    form_class = SaleForm
    template_name = 'sale/create.html'
    success_url = reverse_lazy('erp:sale_list')
    permission_required = 'erp.add_sale'
    url_redirect = success_url

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            if not active_cid:
                company = getattr(self.request.user, 'company', None)
                if company:
                    active_cid = company.id
        qs = Client.objects.all()
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        form.fields['cli'].queryset = qs
        return form

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'search_products':
                data = []
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id
                prods = Product.objects.filter(name__icontains=request.POST['term'][0:10])
                if active_cid:
                    prods = prods.filter(company_id=active_cid)
                for i in prods:
                    item = i.toJSON()
                    item['text'] = f"{i.name} ({i.get_unit_display()}) - Stock: {format(i.stock, '.2f')}"
                    data.append(item)
            elif action == 'add':
                with transaction.atomic():
                    vents = json.loads(request.POST['vents'])
                    is_budget = vents.get('is_budget', False)
                    logger.info("sale_create_start", extra={
                        'user': request.user.username,
                        'is_budget': is_budget,
                        'products_count': len(vents.get('products', [])),
                        'total': vents.get('total', 0)
                    })

                    # Validación de stock suficiente (solo si no es presupuesto)
                    if not is_budget:
                        for i in vents['products']:
                            prod = Product.objects.select_for_update().get(pk=i['id'])

                            # Determinar la cantidad según la unidad del producto
                            if prod.unit == 'kg':
                                cant = float(i['cant'])
                            else:
                                cant = int(i['cant'])

                            if prod.stock < cant:
                                logger.warning("stock_insufficient", extra={
                                    'product_id': prod.id,
                                    'product_name': prod.name,
                                    'available': float(prod.stock),
                                    'required': cant
                                })
                                raise Exception(f"Stock insuficiente para {prod.name}. Disponible: {format(prod.stock, '.2f')}, requerido: {cant}")

                    sale = Sale()
                    # Parse the date string to a timezone-aware datetime
                    from django.utils import timezone

                    # Parse the date string (assuming it's in local time)
                    date_joined = datetime.strptime(vents['date_joined'], '%Y-%m-%d %H:%M:%S')

                    # Make it timezone-aware using the current timezone
                    date_joined = timezone.make_aware(date_joined, timezone.get_current_timezone())
                    
                    # Store the date and timezone
                    sale.date_joined = date_joined
                    sale.local_timezone = str(timezone.get_current_timezone())  # Store the timezone as string
                    sale.cli_id = vents.get('cli') or None
                    sale.subtotal = vents['subtotal']
                    sale.iva = vents['iva']
                    sale.total = vents['total']
                    sale.payment_method = vents.get('payment_method', 'cash')
                    
                    # Guardar información de lista de precios y descuento
                    sale.subtotal_original = vents.get('subtotal_original', 0)
                    sale.discount_amount = vents.get('discount_amount', 0)
                    price_list_id = vents.get('price_list_id')
                    if price_list_id:
                        from core.erp.models import PriceList
                        try:
                            sale.price_list = PriceList.objects.get(pk=price_list_id)
                        except PriceList.DoesNotExist:
                            pass
                    
                    # Asignar company_id explícitamente
                    active_cid = request.session.get('company_id')
                    if not request.user.is_superuser:
                        if not active_cid:
                            company = getattr(request.user, 'company', None)
                            if company:
                                active_cid = company.id
                    if active_cid:
                        sale.company_id = active_cid
                    
                    # Configurar como presupuesto si corresponde
                    if is_budget:
                        sale.status = 'budget'
                        sale.is_budget = True
                        sale.budget_notes = vents.get('budget_notes', '')
                        # Agregar pos_id para identificar qué POS creó el presupuesto
                        import socket
                        sale.pos_id = socket.gethostname() or 'pos_' + str(sale.id)
                        # Los presupuestos se marcan para sincronización automáticamente (synced_to_server=False por defecto)
                    
                    sale.save()

                    for i in vents['products']:
                        prod = Product.objects.get(pk=i['id'])
                        
                        # Determinar la cantidad según la unidad del producto
                        if prod.unit == 'kg':
                            cant = float(i['cant'])
                        else:
                            cant = int(i['cant'])
                            
                        det = DetSale()
                        det.sale_id = sale.id
                        det.prod_id = i['id']
                        det.cant = cant
                        det.price = float(i.get('pvp', i['price']))
                        det.subtotal = float(i['subtotal'])
                        det.save()
                        
                        # Descontar stock solo si no es presupuesto
                        if not is_budget:
                            from django.utils import timezone
                            Product.objects.filter(pk=det.prod_id).update(
                                stock=Greatest(F('stock') - det.cant, 0),
                                stock_modified_locally=timezone.now(),  # Marcar modificación local
                                synced_to_server=False  # Marcar para sincronizar
                            )
                    
                    # Calcular y guardar apertura de alícuotas de IVA
                    self.calculate_vat_breakdown(sale)

                    logger.info("sale_create_success", extra={
                        'sale_id': sale.id,
                        'is_budget': sale.is_budget,
                        'status': sale.status,
                        'pos_id': sale.pos_id,
                        'local_uuid': sale.local_uuid,
                        'total': float(sale.total)
                    })
                    data = {'id': sale.id, 'is_budget': sale.is_budget, 'local_uuid': sale.local_uuid}

            elif action == 'send_budget_to_local':
                from core.erp.services.budget_service import send_budget_to_local_server
                sale_id = request.POST.get('sale_id')
                result = send_budget_to_local_server(sale_id)
                data = result

            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            logger.error("sale_create_error", extra={
                'action': request.POST.get('action'),
                'user': request.user.username,
                'error': str(e)
            })
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Creación una Venta'
        context['entity'] = 'Ventas'
        context['list_url'] = reverse_lazy('erp:sale_list')
        context['action'] = 'add'
        context['det'] = json.dumps([])
        return context

class SaleUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = Sale
    form_class = SaleForm
    template_name = 'sale/create.html'
    success_url = reverse_lazy('erp:dashboard')
    permission_required = 'erp.change_sale'
    url_redirect = success_url

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'search_products':
                data = []
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id
                prods = Product.objects.filter(name__icontains=request.POST['term'][0:10])
                if active_cid:
                    prods = prods.filter(company_id=active_cid)
                for i in prods:
                    item = i.toJSON()
                    item['text'] = i.name
                    data.append(item)
            elif action == 'edit':
                from decimal import Decimal
                with transaction.atomic():
                    vents = json.loads(request.POST['vents'])

                    sale = self.get_object()
                    sale.date_joined = vents['date_joined']
                    sale.cli_id = vents.get('cli') or None
                    sale.subtotal = vents['subtotal']
                    sale.iva = vents['iva']
                    sale.total = vents['total']
                    sale.save()
                    # Restaurar stock de detalles anteriores
                    for d in sale.detsale_set.all():
                        Product.objects.filter(pk=d.prod_id).update(
                            stock=F('stock') + d.cant,
                            stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                            synced_to_server=False  # Marcar para sincronizar
                        )
                    sale.detsale_set.all().delete()

                    # Validación de stock suficiente para nuevos detalles (cantidades decimales)
                    for i in vents['products']:
                        prod = Product.objects.select_for_update().get(pk=i['id'])
                        raw_cant = i.get('cant', 1)
                        cant = Decimal(str(raw_cant or '1'))
                        if cant <= 0:
                            raise Exception("Cantidad inválida")
                        if prod.stock < cant:
                            raise Exception(f"Stock insuficiente para {prod.name}. Disponible: {format(prod.stock, '.2f')}, requerido: {cant}")

                    # Agregar nuevos detalles y descontar stock
                    for i in vents['products']:
                        raw_cant = i.get('cant', 1)
                        cant = Decimal(str(raw_cant or '1'))
                        det = DetSale()
                        det.sale_id = sale.id
                        det.prod_id = i['id']
                        det.cant = cant
                        det.price = float(i['pvp'])
                        det.subtotal = float(i['subtotal'])
                        det.save()
                        Product.objects.filter(pk=det.prod_id).update(
                            stock=Greatest(F('stock') - cant, 0),
                            stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                            synced_to_server=False  # Marcar para sincronizar
                        )
                    
                    # Calcular y guardar apertura de alícuotas de IVA
                    self.calculate_vat_breakdown(sale)
                
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def calculate_vat_breakdown_for_sale(self, sale):
        """Calcular y guardar la apertura de alícuotas de IVA para una venta (método auxiliar)"""
        from django.db.models import Sum
        
        # Eliminar aperturas existentes para esta venta
        SaleVatBreakdown.objects.filter(sale=sale).delete()
        
        # Agrupar detalles por código de IVA AFIP
        vat_breakdown = {}
        for det in sale.detsale_set.all():
            if det.prod and det.prod.vat_code:
                vat_code = det.prod.vat_code
                vat_rate = det.prod.iva_rate or Decimal('0.00')
                
                if vat_code not in vat_breakdown:
                    vat_breakdown[vat_code] = {
                        'vat_rate': vat_rate,
                        'taxable_base': Decimal('0.00'),
                        'vat_amount': Decimal('0.00')
                    }
                
                vat_breakdown[vat_code]['taxable_base'] += Decimal(str(det.subtotal))
                vat_breakdown[vat_code]['vat_amount'] += Decimal(str(det.iva_amount))
        
        # Crear registros de apertura de IVA
        for vat_code, data in vat_breakdown.items():
            SaleVatBreakdown.objects.create(
                sale=sale,
                vat_code=vat_code,
                vat_rate=data['vat_rate'],
                taxable_base=data['taxable_base'],
                vat_amount=data['vat_amount']
            )

    def get_details_product(self):
        data = []
        try:
            for i in DetSale.objects.filter(sale_id=self.get_object().id):
                item = i.prod.toJSON()
                # Convertir Decimal a float para que sea JSON serializable y compatible con el POS
                item['cant'] = float(i.cant)
                data.append(item)
        except:
            pass
        return data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edición de una Venta'
        context['entity'] = 'Ventas'
        context['list_url'] = self.success_url
        context['action'] = 'edit'
        context['det'] = json.dumps(self.get_details_product())
        return context

class SaleDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = Sale
    template_name = 'sale/delete.html'
    success_url = reverse_lazy('erp:sale_list')
    permission_required = 'erp.delete_sale'
    url_redirect = success_url


    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            with transaction.atomic():
                # Restaurar stock antes de eliminar
                from django.utils import timezone
                for d in self.object.detsale_set.all():
                    Product.objects.filter(pk=d.prod_id).update(
                        stock=F('stock') + d.cant,
                        stock_modified_locally=timezone.now(),  # Marcar modificación local
                        synced_to_server=False  # Marcar para sincronizar
                    )

                # Eliminar registros contables/IVA relacionados localmente
                # (los que tienen on_delete=SET_NULL y quedarían huérfanos)
                from core.erp.models import LibroIvaRegistro, CuentaCorrienteCliente, AsientoContable
                LibroIvaRegistro.objects.filter(sale=self.object).delete()
                CuentaCorrienteCliente.objects.filter(sale=self.object).delete()
                AsientoContable.objects.filter(sale=self.object).delete()

                # Eliminar venta y registros relacionados del servidor remoto
                sale_uuid = self.object.local_uuid
                sale_local_id = self.object.local_sale_id or self.object.id
                if sale_uuid or sale_local_id:
                    try:
                        from django.db import connections
                        with connections['remote'].cursor() as cursor:
                            # Construir condición para encontrar la venta remota
                            if sale_uuid:
                                where_clause = "local_uuid = %s"
                                where_params = [sale_uuid]
                            else:
                                where_clause = "local_sale_id = %s AND source = 'local_pos'"
                                where_params = [sale_local_id]

                            # Eliminar registros relacionados por FK en servidor
                            # 1. SaleVatBreakdown
                            cursor.execute(
                                f"DELETE FROM erp_salevatbreakdown WHERE sale_id IN ("
                                f"  SELECT id FROM erp_sale WHERE {where_clause}"
                                f")",
                                where_params
                            )
                            # 2. DetSale
                            cursor.execute(
                                f"DELETE FROM erp_detsale WHERE sale_id IN ("
                                f"  SELECT id FROM erp_sale WHERE {where_clause}"
                                f")",
                                where_params
                            )
                            # 3. LibroIvaRegistro
                            cursor.execute(
                                f"DELETE FROM erp_libroivaregistro WHERE sale_id IN ("
                                f"  SELECT id FROM erp_sale WHERE {where_clause}"
                                f")",
                                where_params
                            )
                            # 4. CuentaCorrienteCliente
                            cursor.execute(
                                f"DELETE FROM erp_cuentacorrientecliente WHERE sale_id IN ("
                                f"  SELECT id FROM erp_sale WHERE {where_clause}"
                                f")",
                                where_params
                            )
                            # 5. AsientoContable
                            cursor.execute(
                                f"DELETE FROM erp_asientocontable WHERE sale_id IN ("
                                f"  SELECT id FROM erp_sale WHERE {where_clause}"
                                f")",
                                where_params
                            )
                            # 6. Sale (finalmente)
                            cursor.execute(
                                f"DELETE FROM erp_sale WHERE {where_clause}",
                                where_params
                            )
                    except Exception as remote_err:
                        # Si falla la eliminación remota, no bloquear la local
                        import logging
                        logging.getLogger(__name__).warning(
                            f"No se pudo eliminar venta {self.object.id} del servidor remoto: {remote_err}"
                        )

                self.object.delete()
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminación de una venta'
        context['entity'] = 'Ventas'
        context['list_url'] = reverse_lazy('erp:sale_list')
        return context

class SaleListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = Sale
    template_name = 'sale/list.html'
    permission_required = 'erp.view_sale'
    ordering = ['-date_joined']

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            action = request.POST.get('action')
            
            if action == 'searchdata':
                data = []
                # Usuarios normales solo ven ventas de su propia empresa
                if request.user.is_superuser:
                    active_cid = request.session.get('company_id') if hasattr(request, 'session') else None
                else:
                    company = getattr(request.user, 'company', None)
                    if company:
                        active_cid = company.id
                
                # Debug logging
                print(f"[DEBUG] SaleListView searchdata: user={request.user.username}, is_superuser={request.user.is_superuser}, active_cid={active_cid}")
                
                try:
                    qs = Sale.objects.all().order_by('-date_joined')
                    print(f"[DEBUG] Total ventas sin filtro: {qs.count()}")
                    
                    if active_cid:
                        qs = qs.filter(company_id=active_cid)
                        print(f"[DEBUG] Total ventas con company_id={active_cid}: {qs.count()}")
                    else:
                        qs = qs.none()
                    
                    for sale in qs:
                        try:
                            sale_data = sale.toJSON()
                            # Los valores ya vienen formateados desde toJSON()
                            # Solo agregar versiones formateadas con separadores si se necesitan
                            if 'total' in sale_data:
                                try:
                                    total_float = float(sale_data['total'])
                                    sale_data['total_formatted'] = "${:,.2f}".format(total_float)
                                except (ValueError, TypeError):
                                    sale_data['total_formatted'] = sale_data['total']
                            
                            if 'subtotal' in sale_data:
                                try:
                                    subtotal_float = float(sale_data['subtotal'])
                                    sale_data['subtotal_formatted'] = "${:,.2f}".format(subtotal_float)
                                except (ValueError, TypeError):
                                    sale_data['subtotal_formatted'] = sale_data['subtotal']
                            
                            if 'iva' in sale_data:
                                try:
                                    iva_float = float(sale_data['iva'])
                                    sale_data['iva_formatted'] = "${:,.2f}".format(iva_float)
                                except (ValueError, TypeError):
                                    sale_data['iva_formatted'] = sale_data['iva']
                            
                            data.append(sale_data)
                            
                        except Exception as e:
                            print(f"Error procesando venta {getattr(sale, 'id', 'unknown')}: {str(e)}")
                            continue
                    
                    return JsonResponse(data, safe=False)
                    
                except Exception as e:
                    print(f"ERROR en query de ventas: {str(e)}")
                    return JsonResponse({'error': str(e)}, status=500)
                
            elif action == 'search_details_prod':
                data = []
                sale_id = request.POST.get('id')
                if sale_id:
                    try:
                        details = DetSale.objects.filter(sale_id=sale_id).select_related('prod', 'prod__cat')
                        for detail in details:
                            data.append(detail.toJSON())
                    except Exception as e:
                        data = []
                return JsonResponse(data, safe=False)
            
            elif action == 'search_vat_breakdown':
                data = []
                sale_id = request.POST.get('id')
                if sale_id:
                    try:
                        vat_breakdowns = SaleVatBreakdown.objects.filter(sale_id=sale_id)
                        for breakdown in vat_breakdowns:
                            data.append(breakdown.toJSON())
                    except Exception as e:
                        data = []
                return JsonResponse(data, safe=False)
                
            elif action == 'invoice':
                response_data = {'error': 'Error al facturar'}
                try:
                    sale_id = request.POST.get('id')
                    if not sale_id:
                        response_data = {'error': 'ID de venta no proporcionado'}
                    else:
                        sale = Sale.objects.get(pk=sale_id)
                        if not sale.is_invoiced:
                            company = Company.objects.first()
                            pos = request.POST.get('pos') or (company.pos if company else None) or getattr(sale, 'invoice_pos', '0001')
                            tipo = request.POST.get('tipo') or getattr(sale, 'invoice_type', 'B')
                            
                            sale.invoice_pos = pos
                            sale.invoice_type = tipo
                            sale.invoice_number = sale.next_sequential_for_pos_type()
                            sale.is_invoiced = True
                            sale.save()
                            
                            response_data = {
                                'id': sale.id,
                                'invoice_number': sale.invoice_number,
                            }
                        else:
                            response_data = {
                                'id': sale.id,
                                'invoice_number': sale.invoice_number,
                                'message': 'La venta ya estaba facturada'
                            }
                except Sale.DoesNotExist:
                    response_data = {'error': 'Venta no encontrada'}
                except Exception as e:
                    response_data = {'error': str(e)}
                
                return JsonResponse(response_data)
                
            elif action == 'delete_all':
                from django.db import transaction
                from django.db.models import F
                from django.utils import timezone
                try:
                    with transaction.atomic():
                        active_cid = request.session.get('company_id')
                        if not request.user.is_superuser:
                            if not active_cid:
                                company = getattr(request.user, 'company', None)
                                if company:
                                    active_cid = company.id
                        qs = Sale.objects.all()
                        if active_cid:
                            qs = qs.filter(company_id=active_cid)
                        else:
                            qs = qs.none()
                        count = 0
                        for sale in qs:
                            for d in sale.detsale_set.all():
                                prod = Product.objects.filter(pk=d.prod_id).first()
                                if prod and getattr(prod, 'track_stock', True):
                                    Product.objects.filter(pk=d.prod_id).update(
                                        stock=F('stock') + d.cant,
                                        stock_modified_locally=timezone.now(),
                                        synced_to_server=False
                                    )
                            sale.delete()
                            count += 1
                        data = {'success': True, 'count': count}
                except Exception as e:
                    data = {'error': str(e)}
                return JsonResponse(data)
                
            return JsonResponse({'error': 'Acción no válida'}, status=400)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Listado de Ventas'
        context['create_url'] = reverse_lazy('erp:sale_create')
        context['list_url'] = reverse_lazy('erp:sale_list')
        context['entity'] = 'Ventas'
        return context

class InvoiceListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = Sale
    template_name = 'sale/list.html'
    permission_required = 'erp.view_sale'

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'searchdata':
                data = []
                active_cid = request.session.get('company_id') if hasattr(request, 'session') else None
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id
                qs = Sale.objects.filter(is_invoiced=True)
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                for i in qs:
                    data.append(i.toJSON())
            elif action == 'search_details_prod':
                data = []
                for i in DetSale.objects.filter(sale_id=request.POST['id']):
                    data.append(i.toJSON())
            else:
                data = {'error': 'Ha ocurrido un error'}
        except Exception as e:
            data = {'error': str(e)}
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Listado de Facturación'
        context['create_url'] = reverse_lazy('erp:invoice_add')
        context['list_url'] = reverse_lazy('erp:invoice_list')
        context['entity'] = 'Facturación'
        return context


class InvoiceCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    model = Sale
    form_class = SaleForm
    template_name = 'sale/create.html'
    success_url = reverse_lazy('erp:invoice_list')
    permission_required = 'erp.add_sale'
    url_redirect = success_url

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            if not active_cid:
                company = getattr(self.request.user, 'company', None)
                if company:
                    active_cid = company.id
        qs = Client.objects.all()
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        form.fields['cli'].queryset = qs
        return form

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'search_products':
                data = []
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    if not active_cid:
                        company = getattr(request.user, 'company', None)
                        if company:
                            active_cid = company.id
                prods = Product.objects.filter(name__icontains=request.POST['term'][0:10])
                if active_cid:
                    prods = prods.filter(company_id=active_cid)
                for i in prods:
                    item = i.toJSON()
                    item['text'] = i.name
                    data.append(item)
            elif action == 'add_invoice':
                with transaction.atomic():
                    vents = json.loads(request.POST['vents'])

                    # Validación de stock suficiente
                    for i in vents['products']:
                        prod = Product.objects.select_for_update().get(pk=i['id'])
                        
                        # Determinar la cantidad según la unidad del producto
                        if prod.unit == 'kg':
                            cant = float(i['cant'])
                        else:
                            cant = int(i['cant'])
                            
                        if prod.stock < cant:
                            raise Exception(f"Stock insuficiente para {prod.name}. Disponible: {format(prod.stock, '.2f')}, requerido: {cant}")

                    # Calcular subtotal neto e IVA acumulado a partir de los productos
                    subtotal_neto = 0.0
                    iva_total = 0.0
                    detalles = []
                    for i in vents['products']:
                        prod = Product.objects.get(pk=i['id'])
                        
                        # Determinar la cantidad según la unidad del producto
                        if prod.unit == 'kg':
                            cant = float(i['cant'])
                        else:
                            cant = int(i['cant'])
                            
                        net = float(prod.pvp or 0)
                        rate = float(getattr(prod, 'iva_rate', 0) or 0)
                        final = float(getattr(prod, 'pvp_final', net * (1 + rate)) or (net * (1 + rate)))
                        sub_neto = net * cant
                        sub_final = final * cant
                        subtotal_neto += sub_neto
                        iva_total += (sub_final - sub_neto)
                        detalles.append({
                            'prod_id': prod.id,
                            'cant': cant,
                            'price_final': final,
                            'subtotal_final': sub_final,
                        })

                    sale = Sale()
                    sale.date_joined = vents['date_joined']
                    sale.cli_id = vents.get('cli') or None
                    # Cabecera: neto + IVA acumulado
                    sale.subtotal = subtotal_neto
                    sale.iva = iva_total
                    sale.total = subtotal_neto + iva_total
                    # Facturación inmediata
                    company = Company.objects.first()
                    sale.invoice_pos = (company.pos if company else sale.invoice_pos) or '0001'
                    sale.invoice_type = 'B'
                    sale.invoice_number = sale.next_sequential_for_pos_type()
                    sale.is_invoiced = True
                    sale.save()

                    for det_info in detalles:
                        det = DetSale()
                        det.sale_id = sale.id
                        det.prod_id = det_info['prod_id']
                        det.cant = det_info['cant']
                        det.price = det_info['price_final']            # precio final con IVA
                        det.subtotal = det_info['subtotal_final']      # subtotal con IVA
                        det.save()
                        Product.objects.filter(pk=det.prod_id).update(
                            stock=Greatest(F('stock') - det.cant, 0),
                            stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                            synced_to_server=False  # Marcar para sincronizar
                        )
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)


def invoice_pdf(request, pk):
    sale = Sale.objects.filter(pk=pk).first()
    if sale is None:
        return HttpResponse(status=404)

    try:
        # Intentar usar WeasyPrint primero
        template = get_template('sale/invoice_b.html')
        company_obj = sale.company or Company.objects.first()

        # Obtener punto de venta AFIP si está configurado
        punto_venta_afip = None
        if sale.company:
            from core.erp.models import AfipPuntoVenta
            punto_venta = AfipPuntoVenta.objects.filter(
                company=sale.company,
                is_active=True
            ).first()
            if punto_venta:
                punto_venta_afip = f"{punto_venta.numero:04d}"

        html_string = template.render({
            'sale': sale,
            'items': sale.detsale_set.all(),
            'company': company_obj,
            'punto_venta_afip': punto_venta_afip,
        })

        response = HttpResponse(content_type='application/pdf')
        filename = f"factura_{sale.invoice_number or sale.id}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        base_url = request.build_absolute_uri('/')
        css_path = os.path.join(settings.BASE_DIR, 'static', 'sale', 'invoice.css')
        styles = [CSS(filename=css_path)] if os.path.exists(css_path) else None

        HTML(string=html_string, base_url=base_url).write_pdf(
            response,
            stylesheets=styles
        )

        return response

    except Exception as e:
        # Si WeasyPrint falla, usar ReportLab como fallback
        try:
            from core.erp.utils.pdf_utils import invoice_pdf_reportlab
            return invoice_pdf_reportlab(request, sale)
        except ImportError:
            # Si ni ReportLab está disponible, devolver error
            return HttpResponse(f"Error generando PDF: {str(e)}", status=500)


@csrf_exempt
def sync_sales_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    sales = payload.get('sales', []) or []
    synced = []
    errors = []

    for s in sales:
        local_uuid = (s.get('local_uuid') or '').strip()
        if not local_uuid:
            errors.append({'local_uuid': None, 'error': 'Sin local_uuid'})
            continue

        # Verificación mejorada para evitar duplicados
        if Sale.objects.filter(local_uuid=local_uuid).exists():
            synced.append(local_uuid)
            continue

        # Verificación adicional por fecha, monto y cliente para mayor seguridad
        date_joined = s.get('date_joined')
        total = s.get('total', 0)
        cli_id = s.get('cli_id')
        
        if date_joined and total:
            try:
                # Parsear la fecha y buscar duplicados en un rango de 60 segundos
                from datetime import datetime, timedelta
                sale_date = datetime.fromisoformat(date_joined.replace('Z', '+00:00'))
                start_time = sale_date - timedelta(seconds=60)
                end_time = sale_date + timedelta(seconds=60)
                
                duplicate_check = Sale.objects.filter(
                    date_joined__range=[start_time, end_time],
                    total=total,
                    cli_id=cli_id
                ).exclude(local_uuid=local_uuid).exists()
                
                if duplicate_check:
                    synced.append(local_uuid)
                    continue
            except Exception:
                # Si hay error con la fecha, continuar con la verificación normal
                pass

        try:
            with transaction.atomic():
                sale = Sale()
                sale.local_uuid = local_uuid
                sale.source = 'local_pos'
                sale.company_id = s.get('company_id') or None
                sale.cli_id = s.get('cli_id') or None
                date_val = s.get('date_joined')
                if date_val:
                    try:
                        sale.date_joined = timezone.make_aware(timezone.datetime.fromisoformat(date_val))
                    except Exception:
                        pass
                sale.subtotal = s.get('subtotal', 0) or 0
                sale.iva = s.get('iva', 0) or 0
                sale.total = s.get('total', 0) or 0
                sale.payment_method = s.get('payment_method') or 'cash'
                sale.invoice_number = s.get('invoice_number') or None
                sale.invoice_pos = s.get('invoice_pos') or sale.invoice_pos
                sale.invoice_type = s.get('invoice_type') or sale.invoice_type
                sale.is_invoiced = bool(s.get('is_invoiced', False))
                sale.synced_at = timezone.now()
                sale.save()

                items = s.get('items', []) or []
                from decimal import Decimal
                for it in items:
                    prod_id = it.get('prod_id') or it.get('id')
                    if not prod_id:
                        continue
                    raw_cant = it.get('cant', 1)
                    cant = Decimal(str(raw_cant or '1'))
                    price = float(it.get('price', 0))
                    subtotal = float(it.get('subtotal', price * float(cant)))
                    det = DetSale.objects.create(
                        sale=sale,
                        prod_id=prod_id,
                        cant=cant,
                        price=price,
                        subtotal=subtotal,
                    )
                    prod = Product.objects.filter(pk=prod_id).first()
                    if prod and getattr(prod, 'track_stock', True):
                        Product.objects.filter(pk=prod_id).update(
                            stock=Greatest(F('stock') - cant, 0),
                            stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                            synced_to_server=False  # Marcar para sincronizar
                        )

                synced.append(local_uuid)
        except IntegrityError:
            # unique constraint violation: ya fue creada por otra ruta (ej: sync_sales_to_remote)
            synced.append(local_uuid)
        except Exception as e:
            errors.append({'local_uuid': local_uuid, 'error': str(e)})

    status = 207 if errors else 200
    return JsonResponse({'synced': synced, 'errors': errors}, status=status)


class EmployeeAccountListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = EmployeeAccountSale
    template_name = 'sale/employee_account_list.html'
    permission_required = 'erp.manage_employee_accounts'
    ordering = ['-date_joined']

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            if not active_cid:
                company = getattr(self.request.user, 'company', None)
                if company:
                    active_cid = company.id
        if active_cid:
            queryset = queryset.filter(company_id=active_cid)

        # Filtros
        client_id = self.request.GET.get('client')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        employee_id = self.request.GET.get('employee')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        is_paid = self.request.GET.get('is_paid')
        if is_paid == 'true':
            queryset = queryset.filter(is_paid=True)
        elif is_paid == 'false':
            queryset = queryset.filter(is_paid=False)

        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(date_joined__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_joined__date__lte=date_to)

        return queryset.select_related('client', 'employee')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Cuenta Corriente'
        context['entity'] = 'Cuenta Corriente'

        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            if not active_cid:
                company = getattr(self.request.user, 'company', None)
                if company:
                    active_cid = company.id

        # Clientes para el filtro
        clients = Client.objects.filter(is_active=True)
        if active_cid:
            clients = clients.filter(company_id=active_cid)
        context['clients'] = clients.order_by('names', 'surnames')

        # Empleados para el filtro (registros antiguos)
        User = get_user_model()
        employees = User.objects.filter(is_active=True).exclude(is_superuser=True)
        if active_cid:
            employees = employees.filter(company_id=active_cid)
        context['employees'] = employees.order_by('first_name', 'last_name')

        # Calcular totales
        queryset = self.get_queryset()
        from django.db.models import Sum
        context['total_debt'] = queryset.filter(is_paid=False).aggregate(
            total=Sum('total')
        )['total'] or 0
        context['total_paid'] = queryset.filter(is_paid=True).aggregate(
            total=Sum('total')
        )['total'] or 0
        context['total_general'] = queryset.aggregate(
            total=Sum('total')
        )['total'] or 0

        # Mantener filtros en el contexto
        context['filters'] = {
            'client': self.request.GET.get('client', ''),
            'employee': self.request.GET.get('employee', ''),
            'is_paid': self.request.GET.get('is_paid', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
        }

        return context

    def post(self, request, *args, **kwargs):
        try:
            action = request.POST.get('action')
            
            if action == 'get_details':
                account_id = request.POST.get('account_id')
                account = EmployeeAccountSale.objects.get(id=account_id)
                
                # Obtener detalles completos
                details = []
                for detail in account.detemployeeaccount_set.all().select_related('prod'):
                    details.append({
                        'product_name': detail.prod.name,
                        'code': detail.prod.code,
                        'quantity': detail.cant,
                        'unit': detail.prod.get_unit_display(),
                        'price': float(detail.price),
                        'subtotal': float(detail.subtotal),
                        'iva_amount': float(detail.iva_amount),
                    })
                
                return JsonResponse({
                    'success': True,
                    'account': {
                        'id': account.id,
                        'employee': account.account_holder_name(),
                        'client': account.account_holder_name(),
                        'date_joined': account.date_joined.strftime('%d/%m/%Y %H:%M'),
                        'total': float(account.total),
                        'subtotal': float(account.subtotal),
                        'iva': float(account.iva),
                        'notes': account.notes,
                        'is_paid': account.is_paid,
                        'paid_date': account.paid_date.strftime('%d/%m/%Y %H:%M') if account.paid_date else None,
                        'related_sale_id': account.related_sale_id,
                    },
                    'details': details
                })
            
            elif action == 'mark_as_paid':
                account_id = request.POST.get('account_id')
                account = EmployeeAccountSale.objects.get(id=account_id)
                
                # Verificar permisos
                if not request.user.has_perm('erp.manage_employee_accounts'):
                    return JsonResponse({'error': 'No tiene permisos para realizar esta acción'}, status=403)
                
                # Obtener método de pago para pagos simples
                payment_method = request.POST.get('payment_method', 'cash')
                
                # Obtener detalles de pago si existen (array para pagos combinados)
                payment_details_str = request.POST.get('payment_details')
                payment_details = None
                if payment_details_str:
                    try:
                        import json
                        payment_details = json.loads(payment_details_str)
                    except:
                        pass
                
                # Crear venta normal cuando se paga la cuenta corriente
                try:
                    with transaction.atomic():
                        # Obtener empresa activa
                        active_cid = request.session.get('company_id')
                        if not request.user.is_superuser:
                            if not active_cid:
                                company = getattr(request.user, 'company', None)
                                if company:
                                    active_cid = company.id
                        
                        sales_created = []
                        
                        if payment_details and isinstance(payment_details, list):
                            # Pago combinado - crear una sola venta con método combinado
                            # Construir string de método combinado (ej: "Efectivo + MercadoPago")
                            from core.erp.choices import payment_method_choices
                            pm_map = dict(payment_method_choices)
                            
                            method_names = []
                            for payment in payment_details:
                                method = payment.get('method', 'cash')
                                method_names.append(pm_map.get(method, method))
                            
                            combined_method = ' + '.join(method_names)
                            
                            # Crear una sola venta con el total completo
                            sale = Sale.objects.create(
                                company_id=active_cid,
                                cli=account.client,
                                subtotal=account.total,
                                iva=0,
                                total=account.total,
                                payment_method=combined_method,  # Ej: "Efectivo + MercadoPago"
                                is_invoiced=False,
                                date_joined=timezone.now(),
                                local_uuid=str(uuid.uuid4()),
                                synced_to_server=False
                            )
                            
                            # Guardar detalles de pago combinado
                            sale.payment_details = payment_details
                            sale.save()
                            
                            # Crear detalles de venta para que figure en reportes (sin descontar stock)
                            for detail in account.detemployeeaccount_set.all():
                                DetSale.objects.create(
                                    sale_id=sale.id,
                                    prod_id=detail.prod_id,
                                    cant=detail.cant,
                                    price=detail.price,
                                    subtotal=detail.subtotal,
                                    iva_amount=0
                                )
                            
                            sales_created.append(sale.id)
                            
                            # Marcar cuenta corriente como pagada
                            account.is_paid = True
                            account.paid_date = timezone.now()
                            account.related_sale_id = sale.id
                            account.payment_details = payment_details
                            account.save()
                            
                        else:
                            # Pago simple normal
                            sale = Sale.objects.create(
                                company_id=active_cid,
                                cli=account.client,
                                subtotal=account.total,
                                iva=0,
                                total=account.total,
                                payment_method=payment_method,
                                is_invoiced=False,
                                date_joined=timezone.now(),
                                local_uuid=str(uuid.uuid4()),
                                synced_to_server=False
                            )
                            
                            # Crear detalles de venta para que figure en reportes (sin descontar stock)
                            for detail in account.detemployeeaccount_set.all():
                                DetSale.objects.create(
                                    sale_id=sale.id,
                                    prod_id=detail.prod_id,
                                    cant=detail.cant,
                                    price=detail.price,
                                    subtotal=detail.subtotal,
                                    iva_amount=0
                                )
                            
                            sales_created.append(sale.id)
                            
                            # Marcar cuenta corriente como pagada
                            account.is_paid = True
                            account.paid_date = timezone.now()
                            account.related_sale_id = sale.id
                            account.save()
                        
                        return JsonResponse({
                            'success': True, 
                            'message': 'Pago registrado correctamente',
                            'sale_ids': sales_created,
                            'is_combined': bool(payment_details and isinstance(payment_details, list))
                        })
                        
                except Exception as e:
                    return JsonResponse({'error': f'Error al crear venta: {str(e)}'}, status=500)
            
            elif action == 'mark_as_unpaid':
                account_id = request.POST.get('account_id')
                account = EmployeeAccountSale.objects.get(id=account_id)
                
                # Verificar permisos
                if not request.user.has_perm('erp.manage_employee_accounts'):
                    return JsonResponse({'error': 'No tiene permisos para realizar esta acción'}, status=403)
                
                try:
                    with transaction.atomic():
                        # Si hay una venta relacionada, eliminarla sin restaurar stock
                        # (el stock ya se restauró cuando se creó la cuenta corriente)
                        if account.related_sale_id:
                            try:
                                sale = Sale.objects.get(id=account.related_sale_id)
                                # Eliminar la venta y sus detalles sin restaurar stock
                                sale.delete()
                            except Sale.DoesNotExist:
                                pass  # La venta ya no existe, continuar
                        
                        # Desmarcar cuenta corriente como pagada
                        account.is_paid = False
                        account.paid_date = None
                        account.related_sale_id = None
                        account.save()
                        
                        return JsonResponse({
                            'success': True, 
                            'message': 'Cuenta desmarcada como pagada y venta eliminada correctamente'
                        })
                        
                except Exception as e:
                    return JsonResponse({'error': f'Error al eliminar venta: {str(e)}'}, status=500)
            
            elif action == 'delete_account':
                account_id = request.POST.get('account_id')
                account = EmployeeAccountSale.objects.get(id=account_id)
                
                # Verificar permisos
                if not request.user.has_perm('erp.manage_employee_accounts'):
                    return JsonResponse({'error': 'No tiene permisos para realizar esta acción'}, status=403)
                
                # Restaurar stock antes de eliminar solo si la cuenta está impaga
                with transaction.atomic():
                    if not account.is_paid:
                        # Solo restaurar stock si la cuenta no está pagada
                        for detail in account.detemployeeaccount_set.all():
                            Product.objects.filter(pk=detail.prod_id).update(
                                stock=F('stock') + detail.cant,
                                stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                                synced_to_server=False
                            )
                    
                    # Si hay una venta relacionada, eliminarla
                    if account.related_sale_id:
                        try:
                            sale = Sale.objects.get(id=account.related_sale_id)
                            sale.delete()
                        except Sale.DoesNotExist:
                            pass  # La venta ya no existe, continuar
                    
                    account.delete()
                
                return JsonResponse({'success': True, 'message': 'Cuenta eliminada correctamente'})
            
            else:
                return JsonResponse({'error': 'Acción no soportada'}, status=400)
                
        except EmployeeAccountSale.DoesNotExist:
            return JsonResponse({'error': 'Cuenta no encontrada'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


def employee_account_pdf_export(request):
    """Exportar cuentas corrientes a PDF con formato optimizado A4"""
    if not request.user.has_perm('erp.manage_employee_accounts'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    
    try:
        # Obtener parámetros de filtro
        employee_id = request.GET.get('employee')
        is_paid = request.GET.get('is_paid')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Construir queryset
        queryset = EmployeeAccountSale.objects.all()
        active_cid = request.session.get('company_id')
        if not request.user.is_superuser:
            if not active_cid:
                company = getattr(request.user, 'company', None)
                if company:
                    active_cid = company.id
        if active_cid:
            queryset = queryset.filter(company_id=active_cid)
        
        # Aplicar filtros
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        if is_paid == 'true':
            queryset = queryset.filter(is_paid=True)
        elif is_paid == 'false':
            queryset = queryset.filter(is_paid=False)
        if date_from:
            queryset = queryset.filter(date_joined__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_joined__date__lte=date_to)
        
        queryset = queryset.select_related('employee').prefetch_related('detemployeeaccount_set__prod')
        
        # Generar PDF
        from django.http import HttpResponse
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, mm
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
        from core.erp.models import Company
        
        # Obtener nombre de la empresa
        company_name = "Empresa"
        try:
            if active_cid:
                company = Company.objects.get(id=active_cid)
                company_name = company.name
            else:
                company = Company.objects.filter(is_active=True).first()
                if company:
                    company_name = company.name
        except:
            pass
        
        # Registrar fuentes
        try:
            pdfmetrics.registerFont(TTFont('Arial', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
            font_name = 'Arial'
        except:
            font_name = 'Helvetica'
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="cuentas_corrientes_{timezone.now().strftime("%d%m%Y")}.pdf"'
        
        buffer = BytesIO()
        # Configuración optimizada para A4 con márgenes profesionales
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            rightMargin=15*mm,   # 15mm derecho
            leftMargin=15*mm,    # 15mm izquierdo
            topMargin=20*mm,     # 20mm superior
            bottomMargin=20*mm    # 20mm inferior
        )
        
        styles = getSampleStyleSheet()
        
        # Estilos personalizados optimizados
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=15,
            alignment=1,  # Center
            textColor=colors.black,
            bold=True
        )
        
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            alignment=1,  # Center
            textColor=colors.black,
            bold=True
        )
        
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=8,
            alignment=0,  # Left
            textColor=colors.black
        )
        
        # Construir contenido
        story = []
        
        # Encabezado
        story.append(Paragraph(company_name, header_style))
        story.append(Paragraph("Reporte de Cuentas Corrientes de Empleados", title_style))
        story.append(Spacer(1, 12))
        
        # Información del reporte
        story.append(Paragraph(f"Fecha: {timezone.now().strftime('%d/%m/%Y %H:%M')}", info_style))
        story.append(Paragraph(f"Generado por: {request.user.get_full_name() or request.user.username}", info_style))
        
        # Filtros aplicados
        filters = []
        if employee_id:
            from core.user.models import User
            employee = User.objects.get(id=employee_id)
            filters.append(f"Empleado: {employee.get_full_name() or employee.username}")
        if is_paid == 'true':
            filters.append("Estado: Pagados")
        elif is_paid == 'false':
            filters.append("Estado: Impagos")
        if date_from and date_to:
            filters.append(f"Período: {date_from} al {date_to}")
        elif date_from:
            filters.append(f"Desde: {date_from}")
        elif date_to:
            filters.append(f"Hasta: {date_to}")
        
        if filters:
            story.append(Paragraph(f"Filtros: {', '.join(filters)}", info_style))
        
        story.append(Spacer(1, 10))
        
        # Tabla de cuentas corrientes
        if queryset.exists():
            # Cabecera de la tabla
            headers = ['Empleado', 'Fecha', 'Productos', 'Subtotal', 'Total', 'Estado']
            table_data = [headers]
            
            total_general = 0
            total_debt = 0
            total_paid = 0
            
            for account in queryset:
                # Formatear productos
                productos = []
                for detail in account.detemployeeaccount_set.all()[:3]:  # Limitar a 3 productos
                    productos.append(f"{detail.prod.name} x{detail.cant}")
                
                if account.detemployeeaccount_set.count() > 3:
                    productos.append(f"...+{account.detemployeeaccount_set.count() - 3} más")
                
                productos_str = '\n'.join(productos)
                
                # Calcular totales
                subtotal = float(account.subtotal)
                total = float(account.total)
                total_general += total
                
                if account.is_paid:
                    total_paid += total
                    estado = 'Pagado'
                else:
                    total_debt += total
                    estado = 'Impago'
                
                table_data.append([
                    account.employee.get_full_name() or account.employee.username,
                    account.date_joined.strftime('%d/%m/%Y'),
                    productos_str,
                    f"${subtotal:,.2f}",
                    f"${total:,.2f}",
                    estado
                ])
            
            # Crear tabla con anchos ajustados para A4 (210mm ancho - 30mm márgenes = 180mm usable)
            # Distribución: Empleado(40mm), Fecha(30mm), Productos(55mm), Subtotal(25mm), Total(25mm), Estado(15mm) = 190mm total
            table = Table(table_data, colWidths=[1.6*inch, 1.2*inch, 2.2*inch, 1.0*inch, 1.0*inch, 0.8*inch])
            
            # Estilo de tabla mejorado
            table_style = TableStyle([
                # Cabecera
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), font_name),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOLD', (0, 0), (-1, 0), True),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                
                # Datos - todas las celdas
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), font_name),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                
                # Alineaciones específicas por columna
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),    # Empleado
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Fecha
                ('ALIGN', (2, 1), (-1, -1), 'LEFT'),    # Productos
                ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),   # Subtotal
                ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),   # Total
                ('ALIGN', (5, 1), (-1, -1), 'CENTER'),  # Estado
                
                # Grid para todas las filas de datos
                ('GRID', (0, 1), (-1, -1), 1, colors.black),
            ])
            
            table.setStyle(table_style)
            story.append(table)
            story.append(Spacer(1, 15))
            
            # Resumen
            summary_style = ParagraphStyle(
                'SummaryStyle',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                alignment=2,  # Right
                textColor=colors.black,
                bold=True
            )
            
            story.append(Paragraph(f"Deuda Total: ${total_debt:,.2f}", summary_style))
            story.append(Paragraph(f"Pagado: ${total_paid:,.2f}", summary_style))
            story.append(Paragraph(f"Total General: ${total_general:,.2f}", summary_style))
        
        else:
            story.append(Paragraph("No se encontraron cuentas corrientes con los filtros especificados.", info_style))
        
        # Generar PDF
        doc.build(story)
        
        pdf_value = buffer.getvalue()
        buffer.close()
        response.write(pdf_value)
        return response
        
    except Exception as e:
        return HttpResponse(f"Error al generar PDF: {str(e)}", content_type='text/plain')


class BudgetListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = Sale
    template_name = 'sale/budget_list.html'
    permission_required = 'erp.view_sale'
    context_object_name = 'budgets'

    def get_queryset(self):
        # Solo presupuestos pendientes (status='budget') filtrados por empresa del usuario
        queryset = Sale.objects.filter(status='budget', is_budget=True).order_by('-date_joined')
        user = self.request.user
        if user.is_authenticated and getattr(user, 'company_id', None):
            queryset = queryset.filter(company_id=user.company_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Presupuestos Pendientes'
        context['entity'] = 'Presupuestos'
        return context


class BudgetConvertView(LoginRequiredMixin, ValidatePermissionRequiredMixin, View):
    permission_required = 'erp.change_sale'

    def post(self, request, *args, **kwargs):
        from django.db import transaction
        budget_id = kwargs.get('pk')
        
        try:
            with transaction.atomic():
                budget = Sale.objects.get(pk=budget_id, status='budget', is_budget=True)
                
                # Convertir presupuesto en venta real
                budget.status = 'confirmed'
                budget.is_budget = False  # Ya no es presupuesto
                budget.save()
                
                # Descontar stock de los productos
                for det in budget.detsale_set.all():
                    from django.db.models import F
                    from django.utils import timezone
                    Product.objects.filter(pk=det.prod_id).update(
                        stock=Greatest(F('stock') - det.cant, 0),
                        stock_modified_locally=timezone.now(),
                        synced_to_server=False
                    )
                
                return JsonResponse({'success': True, 'message': 'Presupuesto convertido a venta correctamente'})
        except Sale.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Presupuesto no encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class BudgetDetailView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        budget_id = kwargs.get('pk')
        
        try:
            budget = Sale.objects.get(pk=budget_id)
            
            # Obtener detalles
            details = []
            for det in budget.detsale_set.all():
                details.append({
                    'prod_name': det.prod.name,
                    'cat_name': det.prod.cat.name if det.prod.cat else None,
                    'price': float(det.price),
                    'cant': det.cant,
                    'subtotal': float(det.subtotal)
                })
            
            data = {
                'id': budget.id,
                'cli': budget.cli.names if budget.cli else 'Anónimo',
                'pos_id': budget.pos_id or '-',
                'date_joined': budget.date_joined.strftime('%d/%m/%Y'),
                'time': budget.date_joined.strftime('%H:%M:%S'),
                'payment_method': budget.payment_method,
                'payment_method_display': budget.get_payment_method_display(),
                'budget_notes': budget.budget_notes or '',
                'subtotal': float(budget.subtotal),
                'iva': float(budget.iva),
                'total': float(budget.total),
                'items_count': budget.detsale_set.count(),
                'details': details
            }
            
            return JsonResponse(data)
        except Sale.DoesNotExist:
            return JsonResponse({'error': 'Presupuesto no encontrado'}, status=404)


class BudgetSendLocalView(LoginRequiredMixin, ValidatePermissionRequiredMixin, View):
    permission_required = 'erp.change_sale'

    def post(self, request, *args, **kwargs):
        budget_id = kwargs.get('pk')
        from core.erp.services.budget_service import send_budget_to_local_server

        success, error = send_budget_to_local_server(budget_id)
        if success:
            return JsonResponse({'success': True, 'message': 'Presupuesto enviado al POS local'})
        else:
            return JsonResponse({'success': False, 'error': error}, status=400)


class CardPlanListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = CardInstallmentPlan
    template_name = 'sale/card_plan_list.html'
    context_object_name = 'plans'
    permission_required = 'erp.view_cardinstallmentplan'

    def get_queryset(self):
        qs = CardInstallmentPlan.objects.all().order_by('name', 'installments')
        if self.request.user.is_superuser:
            active_cid = self.request.session.get('company_id')
        else:
            active_cid = getattr(self.request.user, 'company_id', None)
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Planes de Cuotas de Tarjeta'
        context['entity'] = 'Planes de Cuotas'
        return context


class CardPlanCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CompanyInitialMixin, CreateView):
    model = CardInstallmentPlan
    template_name = 'sale/card_plan_form.html'
    fields = ['company', 'name', 'installments', 'multiplier', 'afip_code', 'is_active']
    success_url = reverse_lazy('erp:card_plan_list')
    permission_required = 'erp.add_cardinstallmentplan'

    def form_valid(self, form):
        active_cid = self.request.session.get('company_id')
        if not active_cid:
            active_cid = getattr(self.request.user, 'company_id', None)
        form.instance.company_id = active_cid
        self.object = form.save()
        return JsonResponse({'success': True, 'redirect': str(self.success_url)})

    def form_invalid(self, form):
        return JsonResponse({'success': False, 'errors': form.errors})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Crear Plan de Cuotas'
        context['entity'] = 'Plan de Cuotas'
        context['list_url'] = self.success_url
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not self.request.user.is_superuser and 'company' in form.fields:
            form.fields['company'].widget = forms.HiddenInput()
            form.fields['company'].required = False
        return form


class CardPlanUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = CardInstallmentPlan
    template_name = 'sale/card_plan_form.html'
    fields = ['company', 'name', 'installments', 'multiplier', 'afip_code', 'is_active']
    success_url = reverse_lazy('erp:card_plan_list')
    permission_required = 'erp.change_cardinstallmentplan'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'success': True, 'redirect': str(self.success_url)})

    def form_invalid(self, form):
        return JsonResponse({'success': False, 'errors': form.errors})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Plan de Cuotas'
        context['entity'] = 'Plan de Cuotas'
        context['list_url'] = self.success_url
        return context


class CardPlanDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = CardInstallmentPlan
    template_name = 'sale/card_plan_delete.html'
    success_url = reverse_lazy('erp:card_plan_list')
    permission_required = 'erp.delete_cardinstallmentplan'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        return JsonResponse({'success': True, 'redirect': str(self.success_url)})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminar Plan de Cuotas'
        context['entity'] = 'Plan de Cuotas'
        context['list_url'] = self.success_url
        return context
