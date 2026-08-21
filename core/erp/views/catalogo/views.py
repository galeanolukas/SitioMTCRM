"""
Vistas para sincronización con SitioCatalogoMarcos
"""
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db import transaction
import logging
import urllib3
import json
from core.erp.mixins import ValidatePermissionRequiredMixin
from core.erp.models import Product, CatalogoConfig, Company, Client, Sale, DetSale
from django.db import models
import requests

# Deshabilitar advertencias de SSL para desarrollo
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def enviar_productos_catalogo(request):
    """
    Vista para enviar productos desde el CRM al catálogo en el VPS
    Método: POST
    """
    try:
        logger.info(f"Iniciando sincronización de productos. Usuario: {request.user.username}, Empresa: {request.user.company.name if request.user.company else 'N/A'}")
        
        # Obtener configuración de sincronización desde la DB
        # Primero buscar configuración específica de la empresa del usuario
        catalogo_config = None
        
        if hasattr(request.user, 'company') and request.user.company:
            catalogo_config = CatalogoConfig.objects.filter(
                company=request.user.company,
                is_active=True
            ).first()
            logger.info(f"Config específica de empresa encontrada: {catalogo_config is not None}")
        
        # Si no hay config específica, buscar global
        if not catalogo_config:
            catalogo_config = CatalogoConfig.objects.filter(
                company__isnull=True,
                is_active=True
            ).first()
            logger.info(f"Config global encontrada: {catalogo_config is not None}")
        
        if not catalogo_config:
            logger.error("No hay configuración de catálogo activa")
            return JsonResponse({
                'success': False,
                'error': 'No hay configuración de catálogo activa para esta empresa'
            }, status=500)
        
        catalogo_url = catalogo_config.catalogo_url
        catalogo_api_key = catalogo_config.api_key
        logger.info(f"URL del catálogo: {catalogo_url}")
        
        # Asegurar que la URL no tenga barra al final
        catalogo_url = catalogo_url.rstrip('/')
        
        # Obtener productos del modelo Product en SitioMTCRM
        # Filtrar por empresa si el usuario tiene company
        productos_db = Product.objects.all()
        if hasattr(request.user, 'company') and request.user.company:
            productos_db = productos_db.filter(company=request.user.company)
        
        logger.info(f"Total de productos a sincronizar: {productos_db.count()}")
        
        productos = []
        for prod in productos_db:
            productos.append({
                'codigo': prod.code if prod.code else '',
                'nombre': prod.name,
                'descripcion': '',  # Product model doesn't have description field
                'precio': float(prod.pvp_final),
                'stock': int(prod.stock),
                'categoria': prod.cat.name if prod.cat else '',
                'marca': '',  # Product model doesn't have marca field
                'imagen_url': prod.image.url if prod.image else '',
                'fecha_actualizacion': prod.last_server_sync.isoformat() if prod.last_server_sync else ''
            })
        
        logger.info(f"Payload JSON preparado con {len(productos)} productos")
        
        # Enviar productos al catálogo
        sync_url = f"{catalogo_url}/api/sincronizar-productos-crm/"
        logger.info(f"Enviando a URL: {sync_url}")
        
        response = requests.post(
            sync_url,
            headers={
                'Content-Type': 'application/json'
            },
            json={
                'api_key': catalogo_api_key,
                'productos': productos
            },
            timeout=60,
            verify=False  # Deshabilitar verificación SSL temporalmente
        )
        
        logger.info(f"Respuesta del catálogo - Status: {response.status_code}, Content: {response.text[:500]}")
        
        if response.status_code == 200:
            # Actualizar last_sync
            catalogo_config.last_sync = timezone.now()
            catalogo_config.save()
            
            logger.info(f"Sincronización exitosa. {len(productos)} productos enviados")
            
            return JsonResponse({
                'success': True,
                'message': f'{len(productos)} productos enviados correctamente',
                'response': response.json()
            })
        else:
            error_msg = f'Error al enviar productos: {response.status_code}'
            if response.status_code == 302:
                error_msg += f' - Redirigido a: {response.headers.get("Location", "desconocido")}'
            
            # Intentar parsear la respuesta del servidor para obtener más detalles
            try:
                response_data = response.json()
                if 'error' in response_data:
                    error_msg = f'Error del servidor: {response_data["error"]}'
                elif 'detail' in response_data:
                    error_msg = f'Error del servidor: {response_data["detail"]}'
                elif 'message' in response_data:
                    error_msg = f'Error del servidor: {response_data["message"]}'
            except:
                # Si no es JSON, usar el texto de la respuesta
                if response.text:
                    error_msg += f' - Detalles: {response.text[:200]}'
            
            logger.error(f"Error en sincronización: {error_msg}")
            return JsonResponse({
                'success': False,
                'error': error_msg,
                'status_code': response.status_code,
                'response': response.text[:500]
            }, status=500)
            
    except requests.Timeout:
        return JsonResponse({'error': 'Timeout al conectar con el catálogo'}, status=504)
    except requests.RequestException as e:
        return JsonResponse({'error': f'Error de conexión: {str(e)}'}, status=502)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


class CatalogoConfigListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    """Lista de configuraciones de catálogo"""
    model = CatalogoConfig
    template_name = 'catalogo/list.html'
    permission_required = 'erp.view_catalogoconfig'
    
    def get_queryset(self):
        qs = CatalogoConfig.objects.select_related('company').all()
        
        # Si no es superusuario, filtrar por empresa del usuario
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'company') and self.request.user.company:
                qs = qs.filter(company=self.request.user.company)
            else:
                qs = qs.none()
        
        return qs


class CatalogoConfigCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CreateView):
    """Crear configuración de catálogo"""
    model = CatalogoConfig
    template_name = 'catalogo/form.html'
    permission_required = 'erp.add_catalogoconfig'
    fields = ['company', 'catalogo_url', 'api_key', 'is_active', 'auto_sync', 'sync_interval_hours']
    success_url = reverse_lazy('erp:catalogo_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'add'
        context['title'] = 'Nueva Configuración de Catálogo'
        context['list_url'] = reverse_lazy('erp:catalogo_list')
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Si no es superusuario, limitar empresas
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'company') and self.request.user.company:
                form.fields['company'].queryset = Company.objects.filter(id=self.request.user.company.id)
                form.fields['company'].initial = self.request.user.company.id
            else:
                form.fields['company'].queryset = Company.objects.none()
        
        return form
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Configuración creada correctamente'})
        return response


class CatalogoConfigUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    """Actualizar configuración de catálogo"""
    model = CatalogoConfig
    template_name = 'catalogo/form.html'
    permission_required = 'erp.change_catalogoconfig'
    fields = ['company', 'catalogo_url', 'api_key', 'is_active', 'auto_sync', 'sync_interval_hours']
    success_url = reverse_lazy('erp:catalogo_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'edit'
        context['title'] = 'Editar Configuración de Catálogo'
        context['list_url'] = reverse_lazy('erp:catalogo_list')
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Si no es superusuario, filtrar por empresa del usuario
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'company') and self.request.user.company:
                qs = qs.filter(company=self.request.user.company)
            else:
                qs = qs.none()
        
        return qs
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        
        # Si no es superusuario, limitar empresas
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'company') and self.request.user.company:
                form.fields['company'].queryset = Company.objects.filter(id=self.request.user.company.id)
            else:
                form.fields['company'].queryset = Company.objects.none()
        
        return form
    
    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Configuración actualizada correctamente'})
        return response


class CatalogoConfigDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    """Eliminar configuración de catálogo"""
    model = CatalogoConfig
    template_name = 'catalogo/delete.html'
    permission_required = 'erp.delete_catalogoconfig'
    success_url = reverse_lazy('erp:catalogo_list')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        try:
            self.object.delete()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Configuración eliminada correctamente'})
        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'error': f'Error al eliminar: {str(e)}'}, status=500)
            raise
        return HttpResponseRedirect(success_url)
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Si no es superusuario, filtrar por empresa del usuario
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'company') and self.request.user.company:
                qs = qs.filter(company=self.request.user.company)
            else:
                qs = qs.none()
        
        return qs


@login_required
def get_catalogo_config(request, catalogo_id):
    """
    Endpoint para obtener la configuración de un catálogo en formato JSON
    Método: GET
    """
    try:
        catalogo_config = CatalogoConfig.objects.filter(id=catalogo_id).first()
        
        if not catalogo_config:
            return JsonResponse({
                'success': False,
                'error': 'Configuración de catálogo no encontrada'
            }, status=404)
        
        # Verificar permisos
        if not request.user.is_superuser:
            if hasattr(request.user, 'company') and request.user.company:
                if catalogo_config.company and catalogo_config.company != request.user.company:
                    return JsonResponse({
                        'success': False,
                        'error': 'No tienes permiso para ver esta configuración'
                    }, status=403)
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'No tienes permiso para ver esta configuración'
                }, status=403)
        
        config_data = {
            'id': catalogo_config.id,
            'company': {
                'id': catalogo_config.company.id,
                'name': catalogo_config.company.name
            } if catalogo_config.company else None,
            'catalogo_url': catalogo_config.catalogo_url,
            'api_key': catalogo_config.api_key,
            'is_active': catalogo_config.is_active,
            'auto_sync': catalogo_config.auto_sync,
            'sync_interval_hours': catalogo_config.sync_interval_hours,
            'last_sync': catalogo_config.last_sync.isoformat() if catalogo_config.last_sync else None,
            'created_at': catalogo_config.created_at.isoformat() if catalogo_config.created_at else None,
            'updated_at': catalogo_config.updated_at.isoformat() if catalogo_config.updated_at else None,
        }
        
        return JsonResponse(config_data)
        
    except Exception as e:
        logger.error(f"Error al obtener configuración de catálogo: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }, status=500)
