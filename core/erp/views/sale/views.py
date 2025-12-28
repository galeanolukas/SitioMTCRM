from core.erp.mixins import ValidatePermissionRequiredMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from core.erp.models import Sale, Product, DetSale, Company, Client, QuickOrder, Category, CashRegister
from django.template.loader import get_template
from django.conf import settings
from weasyprint import HTML, CSS
import os
from core.erp.forms import SaleForm
from django.views.generic import CreateView, ListView, DeleteView, UpdateView, TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json 
from django.db import transaction
from django.db.models import F
from django.db import models
from django.utils import timezone
import pytz

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
        qs = Sale.objects.all().select_related('cli')
        if active_cid:
            qs = qs.filter(company_id=active_cid)
        context['recent_sales'] = qs.annotate(items=models.Sum('detsale__cant')).order_by('-id')[:10]
        # Estado de caja para el usuario/empresa actual
        cr_qs = CashRegister.objects.filter(user=self.request.user, is_closed=False)
        if active_cid:
            cr_qs = cr_qs.filter(company_id=active_cid)
        current_cr = cr_qs.order_by('-created_at').first()
        context['cash_register'] = current_cr
        context['cash_register_is_open'] = bool(current_cr)
        # Determinar si el usuario es operador y debe requerir caja abierta
        is_operator = self.request.user.groups.filter(name='operadores').exists()
        context['is_operator'] = is_operator
        context['pos_locked_by_cash'] = is_operator and not current_cr
        return context

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST.get('action')
            if action == 'product_by_code':
                code = (request.POST.get('code') or '').strip()
                if not code:
                    return JsonResponse({'error': 'Código vacío'}, status=400)
                active_cid = request.session.get('company_id')
                if not request.user.is_superuser:
                    active_cid = active_cid or getattr(request.user, 'company_id', None)
                qs = Product.objects.all()
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                prod = qs.filter(models.Q(code__iexact=code) | models.Q(name__icontains=code)).first()
                if not prod:
                    return JsonResponse({'error': 'Producto no encontrado'}, status=404)
                data = prod.toJSON()
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
                    qs = qs.filter(models.Q(name__icontains=term) | models.Q(code__icontains=term))
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
                        track_stock=False,
                    )
                    if active_cid:
                        prod.company_id = active_cid
                else:
                    # Actualizar datos básicos si ya existía
                    prod.code = code or prod.code
                    prod.pvp = price
                    prod.iva_rate = iva_rate
                    prod.track_stock = False

                prod.save()
                data = prod.toJSON()
                
            elif action == 'list_categories':
                # Obtener categorías existentes
                categories = Category.objects.all().order_by('name')
                data = [{'id': cat.id, 'name': cat.name, 'desc': cat.desc or ''} for cat in categories]
                
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
                with transaction.atomic():
                    items = payload.get('items', [])
                    # Validar stock con cantidades decimales (solo si el producto controla stock)
                    for it in items:
                        prod = Product.objects.select_for_update().get(pk=it['id'])
                        raw_cant = it.get('cant', 1)
                        cant = Decimal(str(raw_cant or '1'))
                        if cant <= 0:
                            raise Exception("Cantidad inválida")
                        if getattr(prod, 'track_stock', True) and prod.stock < cant:
                            raise Exception(f"Stock insuficiente para {prod.name}. Disponible: {format(prod.stock, '.2f')} {prod.get_unit_display()}, requerido: {format(cant, '.2f')} {prod.get_unit_display()}")
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
                    
                    # Guardar detalles de pagos combinados si existen
                    if 'combined_payments' in payload and payload['combined_payments']:
                        sale.payment_details = payload['combined_payments']
                    
                    # Establecer zona horaria local
                    import pytz
                    sale.local_timezone = 'America/Argentina/Buenos_Aires'
                    
                    sale.save()
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
                            Product.objects.filter(pk=det.prod_id).update(stock=F('stock') - cant)
                    data = {'id': sale.id}
            elif action == 'invoice':
                from decimal import Decimal
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
                    # Generar facturación: usar el POS configurado en la empresa de la venta
                    company = sale.company or Company.objects.first()
                    sale.invoice_pos = (company.pos if company else sale.invoice_pos) or '0001'
                    sale.invoice_type = 'B'
                    sale.invoice_number = sale.next_sequential_for_pos_type()
                    sale.is_invoiced = True
                    sale.save()
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
                        Product.objects.filter(pk=det.prod_id).update(stock=F('stock') - cant)
                    data = {'id': sale.id, 'invoice_url': reverse_lazy('erp:invoice_pdf', kwargs={'pk': sale.id})}
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
                            Product.objects.filter(pk=prod.id).update(stock=F('stock') - cant)

                    qo.status = 'paid'
                    qo.save(update_fields=['status'])
                    data = {'id': sale.id}
            else:
                data['error'] = 'Acción no soportada'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)


def ticket_print(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('cli', 'company'), pk=pk)
    dets = sale.detsale_set.select_related('prod').all()
    # Usar la empresa asociada a la venta; si no hay, caer a la primera definida
    company = sale.company or Company.objects.first()
    ctx = {
        'sale': sale,
        'dets': dets,
        'company': company,
    }
    return render(request, 'sale/ticket_print.html', ctx)


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

                    # Validación de stock suficiente
                    for i in vents['products']:
                        prod = Product.objects.select_for_update().get(pk=i['id'])
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
                    sale.save()

                    for i in vents['products']:
                        det = DetSale()
                        det.sale_id = sale.id
                        det.prod_id = i['id']
                        det.cant = int(i['cant'])
                        det.price = float(i['pvp'])
                        det.subtotal = float(i['subtotal'])
                        det.save()
                        # Descontar stock
                        Product.objects.filter(pk=det.prod_id).update(stock=F('stock') - det.cant)
                
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
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
                        Product.objects.filter(pk=d.prod_id).update(stock=F('stock') + d.cant)
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
                        Product.objects.filter(pk=det.prod_id).update(stock=F('stock') - cant)
                
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

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
            for d in self.object.detsale_set.all():
                Product.objects.filter(pk=d.prod_id).update(stock=F('stock') + d.cant)
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
                
                qs = Sale.objects.all().order_by('-date_joined')
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                
                for sale in qs:
                    try:
                        sale_data = sale.toJSON()
                        # Formatear valores monetarios con separadores de miles
                        if 'total' in sale_data:
                            sale_data['total_formatted'] = "${:,.2f}".format(float(sale_data['total']))
                        if 'subtotal' in sale_data:
                            sale_data['subtotal_formatted'] = "${:,.2f}".format(float(sale_data['subtotal']))
                        if 'iva' in sale_data:
                            sale_data['iva_formatted'] = "${:,.2f}".format(float(sale_data['iva']))
                        # El método toJSON ya maneja el formateo de la fecha
                        data.append(sale_data)
                    except Exception as e:
                        print(f"Error procesando venta {getattr(sale, 'id', 'unknown')}: {str(e)}")
                        continue
                
                return JsonResponse(data, safe=False)
                
            elif action == 'search_details_prod':
                data = {}
                sale_id = request.POST.get('id')
                if sale_id:
                    try:
                        sale = Sale.objects.get(id=sale_id)
                        data = sale.toJSON()
                        # Agregar detalles de productos
                        details = DetSale.objects.filter(sale_id=sale_id)
                        data['det'] = [detail.toJSON() for detail in details]
                    except Sale.DoesNotExist:
                        data = {'error': 'Venta no encontrada'}
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
                        cant = int(i['cant'])
                        if prod.stock < cant:
                            raise Exception(f"Stock insuficiente para {prod.name}. Disponible: {format(prod.stock, '.2f')}, requerido: {cant}")

                    # Calcular subtotal neto e IVA acumulado a partir de los productos
                    subtotal_neto = 0.0
                    iva_total = 0.0
                    detalles = []
                    for i in vents['products']:
                        prod = Product.objects.get(pk=i['id'])
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
                        Product.objects.filter(pk=det.prod_id).update(stock=F('stock') - det.cant)
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Crear Factura'
        context['entity'] = 'Facturación'
        context['list_url'] = self.success_url
        context['action'] = 'add_invoice'
        context['det'] = json.dumps([])
        return context


def invoice_pdf(request, pk):
    sale = Sale.objects.filter(pk=pk).first()
    if sale is None:
        return HttpResponse(status=404)

    template = get_template('sale/invoice_b.html')
    # Usar la empresa asociada a la venta; si no hay, caer a la primera definida
    company_obj = sale.company or Company.objects.first()
    html_string = template.render({
        'sale': sale,
        'items': sale.detsale_set.all(),
        'company': {
            'name': company_obj.name if company_obj else 'Empresa no configurada',
            'address': company_obj.address if company_obj else '',
            'cuit': company_obj.cuit if company_obj else '',
            'iibb': company_obj.iibb if company_obj else '',
            'start': company_obj.start.strftime('%d/%m/%Y') if company_obj and company_obj.start else '',
            'pos': company_obj.pos if company_obj else sale.invoice_pos,
            'email': company_obj.email if company_obj else '',
            'phone': company_obj.phone if company_obj else '',
            'logo': company_obj.get_logo_url() if company_obj else '',
        }
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f"factura_{sale.invoice_number or sale.id}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    base_url = request.build_absolute_uri('/')
    # Si tuvieras un CSS de impresión, puedes colocarlo en static/sale/invoice.css
    css_path = os.path.join(settings.BASE_DIR, 'static', 'sale', 'invoice.css')
    styles = [CSS(filename=css_path)] if os.path.exists(css_path) else None

    HTML(string=html_string, base_url=base_url).write_pdf(
        response,
        stylesheets=styles
    )

    return response


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

        if Sale.objects.filter(local_uuid=local_uuid).exists():
            synced.append(local_uuid)
            continue

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
                        Product.objects.filter(pk=prod_id).update(stock=F('stock') - cant)

                synced.append(local_uuid)
        except Exception as e:
            errors.append({'local_uuid': local_uuid, 'error': str(e)})

    status = 207 if errors else 200
    return JsonResponse({'synced': synced, 'errors': errors}, status=status)
