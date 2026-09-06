from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.db import transaction
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from core.erp.models import Remito, DetalleRemito, Product, Supplier, FacturaProveedor, CONDICION_IVA_CHOICES
from core.erp.forms import RemitoForm
from core.erp.mixins import get_active_company_id
from decimal import Decimal
import json
import logging

logger = logging.getLogger(__name__)


class RemitoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Remito
    template_name = 'remito/list.html'
    permission_required = 'erp.view_remito'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filtrar por empresa activa
        active_cid = get_active_company_id(self.request)
        if active_cid:
            queryset = queryset.filter(company_id=active_cid)
        else:
            queryset = queryset.none()
        # Filtros
        tipo = self.request.GET.get('tipo')
        supplier_id = self.request.GET.get('supplier')
        estado = self.request.GET.get('estado')
        
        if tipo:
            queryset = queryset.filter(tipo=tipo)
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        if estado:
            queryset = queryset.filter(estado=estado)
        
        return queryset.select_related('supplier', 'company', 'created_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Remitos'
        context['entity'] = 'Remito'
        context['create_url'] = reverse_lazy('erp:remito_create')
        context['list_url'] = reverse_lazy('erp:remito_list')
        context['suppliers'] = Supplier.objects.filter(is_active=True)
        active_cid = get_active_company_id(self.request)
        if active_cid:
            context['suppliers'] = context['suppliers'].filter(company_id=active_cid)
        context['estados'] = Remito.ESTADO_CHOICES
        context['tipos'] = Remito.TIPO_CHOICES
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        if action == 'searchdata':
            data = []
            queryset = self.get_queryset()
            for obj in queryset:
                item = {
                    'id': obj.id,
                    'numero': obj.numero,
                    'tipo': obj.tipo,
                    'supplier': {'name': obj.supplier.name if obj.supplier else '-'},
                    'fecha': obj.fecha.isoformat() if obj.fecha else None,
                    'estado': obj.estado,
                    'created_by': {'username': obj.created_by.username if obj.created_by else '-'},
                }
                data.append(item)
            return JsonResponse(data, safe=False)
        return JsonResponse({'error': 'Acción no válida'}, status=400)


class RemitoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Remito
    template_name = 'remito/create.html'
    form_class = RemitoForm
    permission_required = 'erp.add_remito'
    success_url = reverse_lazy('erp:remito_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        if not form.instance.company_id:
            form.instance.company_id = get_active_company_id(self.request)

        with transaction.atomic():
            self.object = form.save()

            # Procesar detalles enviados en JSON
            detalles_json = self.request.POST.get('detalles_json', '')
            if detalles_json:
                try:
                    detalles = json.loads(detalles_json)
                    for det in detalles:
                        producto = Product.objects.get(pk=det['prod_id'])
                        DetalleRemito.objects.create(
                            remito=self.object,
                            prod=producto,
                            cantidad=det['cantidad'],
                            precio_unitario=det['precio_unitario']
                        )
                except Exception as e:
                    messages.error(self.request, f'Error al guardar detalles: {e}')
                    raise

        messages.success(self.request, 'Remito creado exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nuevo Remito'
        context['entity'] = 'Remito'
        context['list_url'] = self.success_url
        return context


class RemitoDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Remito
    template_name = 'remito/detail.html'
    permission_required = 'erp.view_remito'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Detalle Remito {self.object.numero}'
        context['entity'] = 'Remito'
        detalles = list(self.object.detalleremito_set.select_related('prod'))
        total = sum(d.subtotal for d in detalles)
        context['total'] = total
        if self.object.iva_incluido:
            for d in detalles:
                d.neto = (d.subtotal / Decimal('1.21')).quantize(Decimal('0.01'))
                d.iva_monto = d.subtotal - d.neto
            context['total_neto'] = sum(d.neto for d in detalles)
            context['total_iva'] = sum(d.iva_monto for d in detalles)
        context['detalles'] = detalles
        return context


class RemitoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Remito
    template_name = 'remito/create.html'
    form_class = RemitoForm
    permission_required = 'erp.change_remito'
    success_url = reverse_lazy('erp:remito_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Remito actualizado exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Editar Remito'
        context['entity'] = 'Remito'
        context['list_url'] = self.success_url
        return context


class RemitoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Remito
    template_name = 'remito/delete.html'
    permission_required = 'erp.delete_remito'
    success_url = reverse_lazy('erp:remito_list')

    def delete(self, request, *args, **kwargs):
        remito = self.get_object()
        if remito.estado in ('processed', 'facturado'):
            messages.error(request, 'No se puede eliminar un remito procesado o facturado.')
            return JsonResponse({'error': 'No se puede eliminar un remito procesado o facturado'}, status=400)
        messages.success(request, 'Remito eliminado exitosamente.')
        return super().delete(request, *args, **kwargs)


def procesar_remito(request, pk):
    """Procesar un remito: actualizar stock de productos"""
    if not request.user.has_perm('erp.manage_remitos'):
        logger.warning("remito_process_permission_denied", extra={
            'user': request.user.username,
            'remito_id': pk
        })
        return JsonResponse({'error': 'No tiene permisos'}, status=403)

    remito = get_object_or_404(Remito, pk=pk)

    if remito.estado not in ('pending',):
        logger.warning("remito_process_invalid_state", extra={
            'remito_id': pk,
            'current_state': remito.estado
        })
        return JsonResponse({'error': f'El remito está {remito.get_estado_display()}, no se puede procesar'}, status=400)

    try:
        with transaction.atomic():
            for detalle in remito.detalleremito_set.all():
                # Usar select_for_update para evitar race conditions
                producto = Product.objects.select_for_update().get(pk=detalle.prod_id)
                if remito.tipo == 'entrada':
                    # Entrada: sumar stock
                    producto.stock += detalle.cantidad
                else:
                    # Salida: restar stock
                    producto.stock -= detalle.cantidad
                    if producto.stock < 0:
                        logger.warning("remito_process_stock_insufficient", extra={
                            'remito_id': pk,
                            'product_id': producto.id,
                            'product_name': producto.name,
                            'available': float(producto.stock),
                            'required': float(detalle.cantidad)
                        })
                        return JsonResponse({'error': f'Stock insuficiente para {producto.name}'}, status=400)
                producto.save()

            remito.estado = 'processed'
            remito.save()

            logger.info("remito_process_success", extra={
                'remito_id': pk,
                'tipo': remito.tipo,
                'user': request.user.username
            })

        return JsonResponse({'success': True, 'message': 'Remito procesado exitosamente'})
    except Exception as e:
        logger.error("remito_process_error", extra={
            'remito_id': pk,
            'user': request.user.username,
            'error': str(e)
        })
        return JsonResponse({'error': str(e)}, status=500)


def anular_remito(request, pk):
    """Anular un remito: revertir stock si está procesado, solo cancelar si está pendiente"""
    if not request.user.has_perm('erp.manage_remitos'):
        logger.warning("remito_anular_permission_denied", extra={
            'user': request.user.username,
            'remito_id': pk
        })
        return JsonResponse({'error': 'No tiene permisos'}, status=403)

    remito = get_object_or_404(Remito, pk=pk)

    if remito.estado == 'cancelled':
        logger.warning("remito_anular_already_cancelled", extra={
            'remito_id': pk
        })
        return JsonResponse({'error': 'El remito ya está anulado'}, status=400)

    try:
        with transaction.atomic():
            # Solo revertir stock si estaba procesado o facturado
            if remito.estado in ('processed', 'facturado'):
                for detalle in remito.detalleremito_set.all():
                    # Usar select_for_update para evitar race conditions
                    producto = Product.objects.select_for_update().get(pk=detalle.prod_id)
                    if remito.tipo == 'entrada':
                        # Entrada anulado: restar stock
                        producto.stock -= detalle.cantidad
                        if producto.stock < 0:
                            logger.warning("remito_anular_stock_insufficient", extra={
                                'remito_id': pk,
                                'product_id': producto.id,
                                'product_name': producto.name,
                                'available': float(producto.stock),
                                'required': float(detalle.cantidad)
                            })
                            return JsonResponse({'error': f'Stock insuficiente para {producto.name}'}, status=400)
                    else:
                        # Salida anulado: sumar stock
                        producto.stock += detalle.cantidad
                    producto.save()

            remito.estado = 'cancelled'
            remito.save()

            logger.info("remito_anular_success", extra={
                'remito_id': pk,
                'previous_state': remito.estado,
                'user': request.user.username
            })

        return JsonResponse({'success': True, 'message': 'Remito anulado exitosamente'})
    except Exception as e:
        logger.error("remito_anular_error", extra={
            'remito_id': pk,
            'user': request.user.username,
            'error': str(e)
        })
        return JsonResponse({'error': str(e)}, status=500)


def agregar_detalle_remito(request):
    """Agregar un producto al remito (AJAX)"""
    if not request.user.has_perm('erp.manage_remitos'):
        return JsonResponse({'error': 'No tiene permisos'}, status=403)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        remito_id = data.get('remito_id')
        prod_id = data.get('prod_id')
        cantidad = data.get('cantidad')
        precio_unitario = data.get('precio_unitario')
        
        try:
            remito = Remito.objects.get(pk=remito_id)
            producto = Product.objects.get(pk=prod_id)
            
            # Si es entrada y no se especifica precio, usar precio de costo
            if remito.tipo == 'entrada' and not precio_unitario:
                precio_unitario = producto.cost_price or 0
            
            detalle = DetalleRemito(
                remito=remito,
                prod=producto,
                cantidad=cantidad,
                precio_unitario=precio_unitario
            )
            detalle.save()
            
            return JsonResponse({'success': True, 'detalle': detalle.toJSON()})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


def eliminar_detalle_remito(request, detalle_id):
    """Eliminar un detalle del remito (AJAX)"""
    if not request.user.has_perm('erp.manage_remitos'):
        return JsonResponse({'error': 'No tiene permisos'}, status=403)
    
    try:
        detalle = DetalleRemito.objects.get(pk=detalle_id)
        if detalle.remito.estado != 'pending':
            return JsonResponse({'error': 'No se puede modificar un remito procesado'}, status=400)
        
        detalle.delete()
        return JsonResponse({'success': True})
    except DetalleRemito.DoesNotExist:
        return JsonResponse({'error': 'Detalle no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def facturar_remito(request, pk):
    """Facturar un remito procesado: crear FacturaProveedor, ajustar cost_price, marcar remito como facturado"""
    if not request.user.has_perm('erp.manage_remitos'):
        return JsonResponse({'error': 'No tiene permisos'}, status=403)

    remito = get_object_or_404(Remito, pk=pk)

    if remito.estado != 'processed':
        return JsonResponse({'error': f'El remito debe estar procesado para facturarlo (estado actual: {remito.get_estado_display()})'}, status=400)

    if remito.tipo != 'entrada':
        return JsonResponse({'error': 'Solo se pueden facturar remitos de entrada'}, status=400)

    detalles = list(remito.detalleremito_set.select_related('prod').all())
    if remito.iva_incluido:
        neto_remito = sum(d.subtotal / Decimal('1.21') for d in detalles)
        for d in detalles:
            d.neto = (d.subtotal / Decimal('1.21')).quantize(Decimal('0.01'))
    else:
        neto_remito = sum(d.subtotal for d in detalles)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                tipo_comprobante = int(request.POST.get('tipo_comprobante', 6))
                punto_venta = int(request.POST.get('punto_venta', 0))
                numero_comprobante = int(request.POST.get('numero_comprobante', 0))
                fecha = request.POST.get('fecha')
                cuit_proveedor = request.POST.get('cuit_proveedor', '').strip()
                condicion_iva = request.POST.get('condicion_iva', 'RI').strip()
                neto_gravado = Decimal(request.POST.get('neto_gravado', '0') or '0')
                neto_no_gravado = Decimal(request.POST.get('neto_no_gravado', '0') or '0')
                neto_exento = Decimal(request.POST.get('neto_exento', '0') or '0')
                iva_21 = Decimal(request.POST.get('iva_21', '0') or '0')
                iva_10_5 = Decimal(request.POST.get('iva_10_5', '0') or '0')
                iva_27 = Decimal(request.POST.get('iva_27', '0') or '0')
                iva_2_5 = Decimal(request.POST.get('iva_2_5', '0') or '0')
                iva_0 = Decimal(request.POST.get('iva_0', '0') or '0')
                impuesto_interno = Decimal(request.POST.get('impuesto_interno', '0') or '0')
                total = Decimal(request.POST.get('total', '0') or '0')
                cae = request.POST.get('cae', '').strip() or None
                cae_vto = request.POST.get('cae_vto') or None

                if not punto_venta or not numero_comprobante or not fecha:
                    return JsonResponse({'error': 'Faltan datos obligatorios (punto de venta, número, fecha)'}, status=400)

                # Crear la factura
                factura = FacturaProveedor.objects.create(
                    company_id=remito.company_id,
                    supplier=remito.supplier,
                    fecha=fecha,
                    tipo_comprobante=tipo_comprobante,
                    punto_venta=punto_venta,
                    numero_comprobante=numero_comprobante,
                    cuit_proveedor=cuit_proveedor,
                    condicion_iva=condicion_iva,
                    neto_gravado=neto_gravado,
                    neto_no_gravado=neto_no_gravado,
                    neto_exento=neto_exento,
                    iva_21=iva_21,
                    iva_10_5=iva_10_5,
                    iva_27=iva_27,
                    iva_2_5=iva_2_5,
                    iva_0=iva_0,
                    impuesto_interno=impuesto_interno,
                    total=total,
                    cae=cae,
                    cae_vto=cae_vto,
                    remito=remito,
                )

                # Ajustar cost_price de los productos si el neto de la factura difiere del remito
                # Distribuir el neto_gravado proporcionalmente entre los productos del remito
                ajustes = []
                # Calcular neto_remito: si iva_incluido, el precio ya tiene IVA, hay que sacarlo
                if remito.iva_incluido:
                    neto_remito = sum(d.subtotal / Decimal('1.21') for d in detalles)
                else:
                    neto_remito = sum(d.subtotal for d in detalles)
                if neto_gravado > 0 and neto_remito > 0 and neto_gravado != neto_remito:
                    factor = neto_gravado / neto_remito
                    for detalle in detalles:
                        if detalle.prod:
                            # Si iva_incluido, el precio_unitario incluye IVA, calcular neto
                            if remito.iva_incluido:
                                precio_neto = detalle.precio_unitario / Decimal('1.21')
                            else:
                                precio_neto = detalle.precio_unitario
                            nuevo_costo = (precio_neto * factor).quantize(Decimal('0.01'))
                            costo_anterior = detalle.prod.cost_price or Decimal('0')
                            if nuevo_costo != costo_anterior:
                                detalle.prod.cost_price = nuevo_costo
                                detalle.prod.save()
                                ajustes.append({
                                    'producto': detalle.prod.name,
                                    'costo_anterior': str(costo_anterior),
                                    'costo_nuevo': str(nuevo_costo),
                                })

                # Marcar remito como facturado
                remito.estado = 'facturado'
                remito.save()

                logger.info("remito_facturado", extra={
                    'remito_id': pk,
                    'factura_id': factura.id,
                    'user': request.user.username,
                    'ajustes_costo': len(ajustes),
                })

                return JsonResponse({
                    'success': True,
                    'factura_id': factura.id,
                    'ajustes': ajustes,
                    'message': f'Remito facturado correctamente. {len(ajustes)} producto(s) con costo ajustado.' if ajustes else 'Remito facturado correctamente.',
                })
        except Exception as e:
            logger.error("remito_facturar_error", extra={
                'remito_id': pk,
                'user': request.user.username,
                'error': str(e)
            })
            return JsonResponse({'error': str(e)}, status=500)

    # GET: mostrar formulario con datos pre-cargados
    context = {
        'title': f'Facturar Remito {remito.numero}',
        'entity': 'Remito',
        'remito': remito,
        'detalles': detalles,
        'neto_remito': neto_remito,
        'list_url': reverse_lazy('erp:remito_list'),
        'tipo_choices': FacturaProveedor.TIPO_COMPROBANTE_CHOICES,
        'condicion_iva_choices': CONDICION_IVA_CHOICES,
    }
    return render(request, 'remito/facturar.html', context)
