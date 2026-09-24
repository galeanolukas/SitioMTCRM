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


def _sync_productos_a_catalogo(catalogo_config):
    """
    Envía los productos de la empresa de la config a su catálogo.
    Retorna (status_code, dict) con la respuesta para el cliente.
    """
    catalogo_url = catalogo_config.catalogo_url.rstrip('/')
    catalogo_api_key = catalogo_config.api_key
    logger.info(f"URL del catálogo: {catalogo_url}")

    # Obtener productos del modelo Product en SitioMTCRM
    # Filtrar por la empresa de la CONFIG (no la del usuario), así el
    # superuser puede sincronizar el catálogo de cualquier empresa
    productos_db = Product.objects.all()
    if catalogo_config.company:
        productos_db = productos_db.filter(company=catalogo_config.company)

    logger.info(f"Total de productos a sincronizar: {productos_db.count()}")

    productos = []
    for prod in productos_db:
        productos.append({
            'codigo': prod.code if prod.code else '',
            'nombre': prod.name,
            'descripcion': '',  # Product model doesn't have description field
            'precio': float(prod.pvp_final),
            'stock': int(prod.stock),
            'marca': '',  # Product model doesn't have marca field
            'imagen_url': prod.image.url if prod.image else '',
            'fecha_actualizacion': prod.last_server_sync.isoformat() if prod.last_server_sync else ''
        })

    logger.info(f"Payload JSON preparado con {len(productos)} productos")

    if not productos:
        return 200, {
            'success': True,
            'message': 'No hay productos para sincronizar',
            'response': {}
        }

    # Enviar productos al catálogo en lotes para evitar timeouts con
    # catálogos grandes (un solo POST con miles de productos puede cortar)
    sync_url = f"{catalogo_url}/api/sincronizar-productos-crm/"
    batch_size = 200
    total_lotes = (len(productos) + batch_size - 1) // batch_size
    enviados = 0
    ultima_respuesta = None

    for i in range(0, len(productos), batch_size):
        lote = productos[i:i + batch_size]
        num_lote = i // batch_size + 1
        payload = {
            'api_key': catalogo_api_key,
            'productos': lote
        }
        logger.info(f"Enviando lote {num_lote}/{total_lotes} ({len(lote)} productos) a {sync_url}")

        # allow_redirects=False: si el catálogo responde 301/302 (ej: dominio
        # sin www → con www), requests seguiría el redirect convirtiendo el
        # POST en GET y el catálogo devuelve 405. Seguimos el Location
        # manualmente preservando el método y el body.
        current_url = sync_url
        response = None
        for _ in range(4):
            response = requests.post(
                current_url,
                headers={
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=60,
                verify=False,  # Deshabilitar verificación SSL temporalmente
                allow_redirects=False
            )
            if response.is_redirect:
                redirect_url = response.headers.get('Location')
                if not redirect_url:
                    break
                logger.info(f"Redirect {response.status_code} a {redirect_url}, reintentando POST")
                current_url = redirect_url
                continue
            break

        logger.info(f"Lote {num_lote}/{total_lotes} - Status: {response.status_code}, Content: {response.text[:500]}")

        if response.status_code != 200:
            error_msg = f'Error al enviar productos (lote {num_lote}/{total_lotes}): HTTP {response.status_code}'
            if response.status_code == 302:
                error_msg += f' - Redirigido a: {response.headers.get("Location", "desconocido")}'

            # Intentar parsear la respuesta del servidor para más detalles
            try:
                response_data = response.json()
                detalle = response_data.get('error') or response_data.get('detail') or response_data.get('message')
                if detalle:
                    error_msg = f'Error del servidor (lote {num_lote}/{total_lotes}): {detalle}'
            except:
                if response.text:
                    error_msg += f' - Detalles: {response.text[:200]}'

            logger.error(f"Error en sincronización: {error_msg}")
            return 500, {
                'success': False,
                'error': error_msg,
                'status_code': response.status_code,
                'response': response.text[:500],
                'enviados': enviados
            }

        enviados += len(lote)
        try:
            ultima_respuesta = response.json()
        except:
            pass

    # Actualizar last_sync solo si se enviaron todos los lotes
    catalogo_config.last_sync = timezone.now()
    catalogo_config.save()

    logger.info(f"Sincronización exitosa. {enviados} productos enviados en {total_lotes} lotes")

    return 200, {
        'success': True,
        'message': f'{enviados} productos enviados correctamente',
        'response': ultima_respuesta
    }


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def enviar_productos_catalogo(request):
    """
    Vista para enviar productos desde el CRM al catálogo en el VPS
    Método: POST
    Body opcional: {"catalogo_id": N} para sincronizar una config puntual.
    Sin catalogo_id: superuser sincroniza TODAS las configs activas;
    el resto, la config de su empresa (o la global).
    """
    try:
        logger.info(f"Iniciando sincronización de productos. Usuario: {request.user.username}, Empresa: {request.user.company.name if request.user.company else 'N/A'}")

        # Leer catalogo_id del body (el botón de sync por fila lo envía)
        catalogo_id = None
        try:
            body = json.loads(request.body) if request.body else {}
            catalogo_id = body.get('catalogo_id')
        except json.JSONDecodeError:
            pass

        # Obtener configuraciones de sincronización desde la DB
        configs = []

        if catalogo_id:
            # Sync de una config específica (botón por fila del listado)
            qs = CatalogoConfig.objects.filter(id=catalogo_id, is_active=True)
            # No superuser: solo configs de su empresa o globales
            if not request.user.is_superuser:
                if hasattr(request.user, 'company') and request.user.company:
                    qs = qs.filter(
                        models.Q(company=request.user.company) |
                        models.Q(company__isnull=True)
                    )
                else:
                    qs = qs.none()
            catalogo_config = qs.first()
            logger.info(f"Config por ID {catalogo_id} encontrada: {catalogo_config is not None}")
            if catalogo_config:
                configs = [catalogo_config]
        elif request.user.is_superuser:
            # "Sincronizar Inventario": el superuser sincroniza todas las
            # configs activas (cada catálogo recibe los productos de su empresa)
            configs = list(CatalogoConfig.objects.filter(is_active=True))
            logger.info(f"Superuser: {len(configs)} configs activas a sincronizar")
        else:
            # Sin ID: buscar config de la empresa del usuario, sino global
            catalogo_config = None
            if hasattr(request.user, 'company') and request.user.company:
                catalogo_config = CatalogoConfig.objects.filter(
                    company=request.user.company,
                    is_active=True
                ).first()
                logger.info(f"Config específica de empresa encontrada: {catalogo_config is not None}")

            if not catalogo_config:
                catalogo_config = CatalogoConfig.objects.filter(
                    company__isnull=True,
                    is_active=True
                ).first()
                logger.info(f"Config global encontrada: {catalogo_config is not None}")

            if catalogo_config:
                configs = [catalogo_config]

        if not configs:
            logger.error("No hay configuración de catálogo activa")
            return JsonResponse({
                'success': False,
                'error': 'No hay configuración de catálogo activa para esta empresa'
            }, status=500)

        if len(configs) == 1:
            status, data = _sync_productos_a_catalogo(configs[0])
            return JsonResponse(data, status=status)

        # Múltiples configs: agregar un resultado por catálogo
        resultados = []
        all_ok = True
        for cfg in configs:
            label = cfg.company.name if cfg.company else 'Global'
            try:
                status, data = _sync_productos_a_catalogo(cfg)
            except Exception as e:
                status, data = 500, {'success': False, 'error': str(e)}
            if data.get('success'):
                resultados.append(f"{label}: {data['message']}")
            else:
                all_ok = False
                resultados.append(f"{label}: {data.get('error', 'Error desconocido')}")

        msg = ' | '.join(resultados)
        if all_ok:
            return JsonResponse({'success': True, 'message': msg})
        return JsonResponse({'success': False, 'error': msg}, status=500)

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

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors = {}
            for field in form:
                if field.errors:
                    errors[field.name] = [str(e) for e in field.errors]
            return JsonResponse({'error': 'Error de validación', 'errors': errors}, status=400)
        return super().form_invalid(form)


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

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors = {}
            for field in form:
                if field.errors:
                    errors[field.name] = [str(e) for e in field.errors]
            return JsonResponse({'error': 'Error de validación', 'errors': errors}, status=400)
        return super().form_invalid(form)


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
