"""
Vistas para sincronización con SitioCatalogoMarcos
"""
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from core.erp.mixins import ValidatePermissionRequiredMixin
from core.erp.models import Product, CatalogoConfig, Company
import requests


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def enviar_productos_catalogo(request):
    """
    Vista para enviar productos desde el CRM al catálogo en el VPS
    Método: POST
    """
    try:
        # Obtener configuración de sincronización desde la DB
        # Primero buscar configuración específica de la empresa del usuario
        catalogo_config = None
        
        if hasattr(request.user, 'company') and request.user.company:
            catalogo_config = CatalogoConfig.objects.filter(
                company=request.user.company,
                is_active=True
            ).first()
        
        # Si no hay config específica, buscar global
        if not catalogo_config:
            catalogo_config = CatalogoConfig.objects.filter(
                company__isnull=True,
                is_active=True
            ).first()
        
        if not catalogo_config:
            return JsonResponse({
                'success': False,
                'error': 'No hay configuración de catálogo activa para esta empresa'
            }, status=500)
        
        catalogo_url = catalogo_config.catalogo_url
        catalogo_api_key = catalogo_config.api_key
        
        # Obtener productos del modelo Product en SitioMTCRM
        # Filtrar por empresa si el usuario tiene company
        productos_db = Product.objects.all()
        if hasattr(request.user, 'company') and request.user.company:
            productos_db = productos_db.filter(company=request.user.company)
        
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
        
        # Enviar productos al catálogo
        response = requests.post(
            f"{catalogo_url}/api/sincronizar-productos-crm/",
            headers={
                'Content-Type': 'application/json'
            },
            json={
                'api_key': catalogo_api_key,
                'productos': productos
            },
            timeout=60
        )
        
        if response.status_code == 200:
            # Actualizar last_sync
            catalogo_config.last_sync = timezone.now()
            catalogo_config.save()
            
            return JsonResponse({
                'success': True,
                'message': f'{len(productos)} productos enviados correctamente',
                'response': response.json()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Error al enviar productos: {response.status_code}',
                'response': response.text
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


class CatalogoConfigUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    """Actualizar configuración de catálogo"""
    model = CatalogoConfig
    template_name = 'catalogo/form.html'
    permission_required = 'erp.change_catalogoconfig'
    fields = ['company', 'catalogo_url', 'api_key', 'is_active', 'auto_sync', 'sync_interval_hours']
    success_url = reverse_lazy('erp:catalogo_list')
    
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


class CatalogoConfigDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    """Eliminar configuración de catálogo"""
    model = CatalogoConfig
    template_name = 'catalogo/delete.html'
    permission_required = 'erp.delete_catalogoconfig'
    success_url = reverse_lazy('erp:catalogo_list')
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Si no es superusuario, filtrar por empresa del usuario
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'company') and self.request.user.company:
                qs = qs.filter(company=self.request.user.company)
            else:
                qs = qs.none()
        
        return qs
