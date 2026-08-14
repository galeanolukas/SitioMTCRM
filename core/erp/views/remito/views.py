from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.db import transaction
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from core.erp.models import Remito, DetalleRemito, Product, Supplier
from core.erp.forms import RemitoForm
import json


class RemitoListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Remito
    template_name = 'remito/list.html'
    permission_required = 'erp.view_remito'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
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

    def form_valid(self, form):
        form.instance.created_by = self.request.user

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
        context['detalles'] = self.object.detalleremito_set.select_related('prod')
        context['total'] = sum(d.subtotal for d in context['detalles'])
        return context


class RemitoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Remito
    template_name = 'remito/create.html'
    form_class = RemitoForm
    permission_required = 'erp.change_remito'
    success_url = reverse_lazy('erp:remito_list')

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
        if remito.estado == 'processed':
            messages.error(request, 'No se puede eliminar un remito procesado.')
            return JsonResponse({'error': 'No se puede eliminar un remito procesado'}, status=400)
        messages.success(request, 'Remito eliminado exitosamente.')
        return super().delete(request, *args, **kwargs)


def procesar_remito(request, pk):
    """Procesar un remito: actualizar stock de productos"""
    if not request.user.has_perm('erp.manage_remitos'):
        return JsonResponse({'error': 'No tiene permisos'}, status=403)
    
    remito = get_object_or_404(Remito, pk=pk)
    
    if remito.estado != 'pending':
        return JsonResponse({'error': 'El remito ya fue procesado'}, status=400)
    
    try:
        with transaction.atomic():
            for detalle in remito.detalleremito_set.all():
                producto = detalle.prod
                if remito.tipo == 'entrada':
                    # Entrada: sumar stock
                    producto.stock += detalle.cantidad
                else:
                    # Salida: restar stock
                    producto.stock -= detalle.cantidad
                    if producto.stock < 0:
                        return JsonResponse({'error': f'Stock insuficiente para {producto.name}'}, status=400)
                producto.save()
            
            remito.estado = 'processed'
            remito.save()
        
        return JsonResponse({'success': True, 'message': 'Remito procesado exitosamente'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def anular_remito(request, pk):
    """Anular un remito: revertir stock si está procesado, solo cancelar si está pendiente"""
    if not request.user.has_perm('erp.manage_remitos'):
        return JsonResponse({'error': 'No tiene permisos'}, status=403)

    remito = get_object_or_404(Remito, pk=pk)

    if remito.estado == 'cancelled':
        return JsonResponse({'error': 'El remito ya está anulado'}, status=400)

    try:
        with transaction.atomic():
            # Solo revertir stock si estaba procesado
            if remito.estado == 'processed':
                for detalle in remito.detalleremito_set.all():
                    producto = detalle.prod
                    if remito.tipo == 'entrada':
                        # Entrada anulado: restar stock
                        producto.stock -= detalle.cantidad
                        if producto.stock < 0:
                            return JsonResponse({'error': f'Stock insuficiente para {producto.name}'}, status=400)
                    else:
                        # Salida anulado: sumar stock
                        producto.stock += detalle.cantidad
                    producto.save()

            remito.estado = 'cancelled'
            remito.save()

        return JsonResponse({'success': True, 'message': 'Remito anulado exitosamente'})
    except Exception as e:
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
