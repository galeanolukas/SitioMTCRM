from core.erp.mixins import ValidatePermissionRequiredMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from core.erp.models import Sale, Product, DetSale, Company, Client, QuickOrder, Category, CashRegister, EmployeeAccountSale, DetEmployeeAccount, SaleVatBreakdown
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.conf import settings
from weasyprint import HTML, CSS
import os
from core.erp.forms import SaleForm
from django.views.generic import CreateView, ListView, DeleteView, UpdateView, TemplateView, View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
import pytz
from decimal import Decimal
import time
import uuid
from core.erp.afip.client import AfipClient

@method_decorator(csrf_exempt, name='dispatch')
class POSView(LoginRequiredMixin, ValidatePermissionRequiredMixin, TemplateView):
    template_name = 'sale/pos.html'
    permission_required = 'erp.add_sale'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'POS / API de Ventas'
        context['entity'] = 'Ventas'
        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)

        # Obtener tipo de factura por defecto desde configuración AFIP
        from core.erp.afip.config import get_afip_config
        afip_config = get_afip_config(active_cid)
        tipo_map = {1: 'A', 6: 'B', 11: 'C'}
        default_invoice_type = tipo_map.get(afip_config.get('tipo_comprobante', 6), 'B') if afip_config else 'B'
        context['default_invoice_type'] = default_invoice_type
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
        is_operator = self.request.user.groups.filter(name='operadores').exists()
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
                active_cid = request.session.get('company_id')
                if not active_cid:
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
                        active_cid = request.session.get('company_id')
                        if not request.user.is_superuser:
                            active_cid = active_cid or getattr(request.user, 'company_id', None)

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
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
                qs = Product.objects.all()
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                
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
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
                qs = Product.objects.all()
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
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
                    active_cid = active_cid or getattr(request.user, 'company_id', None)

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
                            'prices': prices,
                        }
                    else:
                        data = {'has_price_list': False}
            elif action == 'get_employees':
                # Obtener lista de empleados para cuenta corriente
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                # Filtrar por empresa actual
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
                
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
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
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
                    is_operator = request.user.groups.filter(name='operadores').exists()
                    active_cid = request.session.get('company_id')
                    if not request.user.is_superuser:
                        active_cid = active_cid or getattr(request.user, 'company_id', None)
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
                    active_cid = request.session.get('company_id')
                    if not request.user.is_superuser:
                        active_cid = active_cid or getattr(request.user, 'company_id', None)
                    if active_cid:
                        sale.company_id = active_cid
                    sale.cli_id = payload.get('cli') or None
                    sale.subtotal = float(payload.get('subtotal', 0))
                    sale.iva = float(payload.get('iva', 0))
                    sale.total = float(payload.get('total', 0))
                    sale.payment_method = payload.get('payment_method') or 'cash'
                    sale.invoice_type = payload.get('invoice_type') or 'B'
                    sale.is_credit_note = payload.get('is_credit_note', False)

                    if is_budget:
                        sale.status = 'budget'
                        sale.is_budget = True
                        sale.budget_notes = payload.get('budget_notes', '')
                        import socket
                        sale.pos_id = socket.gethostname() or 'pos_default'
                        print(f"[DEBUG] Presupuesto configurado: pos_id={sale.pos_id}")
                    else:
                        if not payload.get('invoice_number'):
                            sale.iva = 0.0
                            sale.total = sale.subtotal
                    
                    if 'combined_payments' in payload and payload['combined_payments']:
                        sale.payment_details = payload['combined_payments']
                    
                    sale.save()
                    print(f"[DEBUG] Sale guardada: id={sale.id}, is_budget={sale.is_budget}, status={sale.status}")
                    
                    request.session[f'processed_sale_{sale_token}'] = True
                    request.session.save()
                    
                    for it in items:
                        raw_cant = it.get('cant', 1)
                        cant = Decimal(str(raw_cant or '1'))
                        det = DetSale(
                            sale_id=sale.id,
                            prod_id=int(it['id']),
                            cant=cant,
                            price=float(it.get('price', it.get('pvp', 0))),
                            subtotal=float(it.get('subtotal', 0)),
                        )
                        det.save()
                        if not is_budget:
                            prod = Product.objects.filter(pk=det.prod_id).first()
                            if prod and getattr(prod, 'track_stock', True):
                                Product.objects.filter(pk=det.prod_id).update(
                                    stock=F('stock') - cant,
                                    stock_modified_locally=timezone.now(),
                                    synced_to_server=False
                                )
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
                is_operator = request.user.groups.filter(name='operadores').exists()
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
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
                        active_cid = active_cid or getattr(request.user, 'company_id', None)
                    else:
                        active_cid = active_cid or getattr(request.user, 'company_id', None)
                    if active_cid:
                        sale.company_id = active_cid
                    sale.cli_id = payload.get('cli') or None
                    sale.subtotal = float(payload.get('subtotal', 0))
                    sale.iva = float(payload.get('iva', 0))
                    sale.total = float(payload.get('total', 0))
                    sale.payment_method = payload.get('payment_method') or 'cash'
                    sale.invoice_type = payload.get('invoice_type') or 'B'
                    sale.is_credit_note = payload.get('is_credit_note', False)

                    # Para tickets (sin factura), asegurar que IVA sea 0 y total sea igual a subtotal
                    if not payload.get('invoice_number'):
                        sale.iva = 0.0
                        sale.total = sale.subtotal
                    # Generar facturación: usar el POS configurado en la empresa de la venta
                    company = sale.company or Company.objects.first()
                    sale.invoice_pos = (company.pos if company else sale.invoice_pos) or '0001'

                    # Verificar si se permite ventas sin AFIP
                    from core.erp.models import GlobalPosConfig, AfipConfig
                    allow_without_afip = GlobalPosConfig.allow_sales_without_afip()
                    afip_config = AfipConfig.objects.filter(company=company, is_active=True).first()

                    if afip_config:
                        # Hay configuración AFIP, usar flujo normal
                        # Mapear tipo de comprobante numérico a letra
                        tipo_map = {1: 'A', 6: 'B', 11: 'C'}
                        sale.invoice_type = tipo_map.get(afip_config.tipo_comprobante, 'B')
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
                        det = DetSale(
                            sale_id=sale.id,
                            prod_id=int(it['id']),
                            cant=cant,
                            price=float(it.get('price', it.get('pvp', 0))),
                            subtotal=float(it.get('subtotal', 0)),
                        )
                        det.save()
                        prod = Product.objects.filter(pk=det.prod_id).first()
                        if prod and getattr(prod, 'track_stock', True):
                            Product.objects.filter(pk=det.prod_id).update(
                                stock=F('stock') - cant,
                                stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                                synced_to_server=False  # Marcar para sincronizar
                            )
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
                                stock=F('stock') - cant,
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
                is_operator = request.user.groups.filter(name='operadores').exists()
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
                cr_qs = CashRegister.objects.filter(user=request.user, is_closed=False)
                if active_cid:
                    cr_qs = cr_qs.filter(company_id=active_cid)
                current_cr = cr_qs.order_by('-created_at').first()
                if is_operator and not current_cr:
                    return JsonResponse({'error': 'Debe abrir una caja antes de registrar ventas.'}, status=400)
                    
                payload = json.loads(request.POST.get('sale') or '{}')
                employee_id = payload.get('employee_id')
                if not employee_id:
                    return JsonResponse({'error': 'Debe seleccionar un empleado'}, status=400)
                    
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
                                stock=F('stock') - cant,
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
                        active_cid = active_cid or getattr(request.user, 'company_id', None)
                    
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
            import logging
            logger = logging.getLogger(__name__)
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
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)
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
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
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
                    print(f"[DEBUG] action=add, is_budget={is_budget}, vents keys={list(vents.keys())}, products={vents.get('products', 'MISSING')}, date_joined={vents.get('date_joined', 'MISSING')}")

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
                    
                    # Asignar company_id explícitamente
                    active_cid = request.session.get('company_id')
                    if not request.user.is_superuser:
                        active_cid = active_cid or getattr(request.user, 'company_id', None)
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
                                stock=F('stock') - det.cant,
                                stock_modified_locally=timezone.now(),  # Marcar modificación local
                                synced_to_server=False  # Marcar para sincronizar
                            )
                    
                    # Calcular y guardar apertura de alícuotas de IVA
                    self.calculate_vat_breakdown(sale)
                
                print(f"[DEBUG] Presupuesto creado OK: id={sale.id}, is_budget={sale.is_budget}, status={sale.status}, pos_id={sale.pos_id}, local_uuid={sale.local_uuid}")
                data = {'id': sale.id, 'is_budget': sale.is_budget, 'local_uuid': sale.local_uuid}
            
            elif action == 'send_budget_to_local':
                from core.erp.services.budget_service import send_budget_to_local_server
                sale_id = request.POST.get('sale_id')
                result = send_budget_to_local_server(sale_id)
                data = result
                
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            print(f"[DEBUG] ERROR en POS post action={request.POST.get('action')}: {e}")
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
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
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
                            stock=F('stock') - cant,
                            stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                            synced_to_server=False  # Marcar para sincronizar
                        )
                    
                    # Calcular y guardar apertura de alícuotas de IVA
                    self.calculate_vat_breakdown_for_sale(sale)
                
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
            # Restaurar stock antes de eliminar
            from django.utils import timezone
            for d in self.object.detsale_set.all():
                Product.objects.filter(pk=d.prod_id).update(
                    stock=F('stock') + d.cant,
                    stock_modified_locally=timezone.now(),  # Marcar modificación local
                    synced_to_server=False  # Marcar para sincronizar
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
                active_cid = request.session.get('company_id') if hasattr(request, 'session') else None
                
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
                
                try:
                    qs = Sale.objects.all().order_by('-date_joined')
                    if active_cid:
                        qs = qs.filter(company_id=active_cid)
                    
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
                            active_cid = active_cid or getattr(request.user, 'company_id', None)
                        qs = Sale.objects.all()
                        if active_cid:
                            qs = qs.filter(company_id=active_cid)
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
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
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
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)
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
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
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
                            stock=F('stock') - det.cant,
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
                            stock=F('stock') - cant,
                            stock_modified_locally=timezone.now(),  # Marcar modificación de stock
                            synced_to_server=False  # Marcar para sincronizar
                        )

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
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)
        if active_cid:
            queryset = queryset.filter(company_id=active_cid)
        
        # Filtros
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
        
        return queryset.select_related('employee')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Cuenta Corriente de Empleados'
        context['entity'] = 'Cuenta Corriente'
        
        # Obtener empleados para el filtro (solo de la misma empresa)
        User = get_user_model()
        employees = User.objects.filter(is_active=True).exclude(is_superuser=True)
        
        # Filtrar por empresa del usuario
        active_cid = self.request.session.get('company_id')
        if not self.request.user.is_superuser:
            active_cid = active_cid or getattr(self.request.user, 'company_id', None)
        if active_cid:
            employees = employees.filter(company_id=active_cid)
        
        employees = employees.order_by('first_name', 'last_name')
        context['employees'] = employees
        
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
                        'employee': account.employee.get_full_name() or account.employee.username,
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
                            active_cid = active_cid or getattr(request.user, 'company_id', None)
                        
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
                                cli_id=None,
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
                                cli_id=None,
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
            active_cid = active_cid or getattr(request.user, 'company_id', None)
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
        # Solo presupuestos pendientes (status='budget')
        queryset = Sale.objects.filter(status='budget', is_budget=True).order_by('-date_joined')
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
                        stock=F('stock') - det.cant,
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
