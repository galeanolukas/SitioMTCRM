"""
Middleware para registro automático de actividades de usuarios
"""
import json
from django.utils import timezone
from django.conf import settings
from .models import ActivityLog


class ActivityLogMiddleware:
    """Middleware para registrar actividades de usuarios"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Acciones a registrar automáticamente
        self.monitored_paths = [
            '/erp/sale/',
            '/erp/product/',
            '/erp/client/',
            '/erp/provider/',
            '/erp/expense/',
            '/erp/transfer/',
            '/erp/sync/',
            '/login/',
            '/logout/',
        ]
        
        # Acciones a ignorar (archivos estáticos, admin, etc.)
        self.ignored_paths = [
            '/static/',
            '/media/',
            '/admin/',
            '/favicon.ico',
            '/erp/activity/',
        ]
    
    def __call__(self, request):
        response = self.get_response(request)

        # Ignorar paths que no queremos monitorear
        if any(request.path.startswith(path) for path in self.ignored_paths):
            return response

        # Solo registrar usuarios autenticados
        if not request.user.is_authenticated:
            return response

        # Solo registrar paths monitoreados
        if not any(request.path.startswith(path) for path in self.monitored_paths):
            return response

        # Determinar acción basada en método y path
        action = self._get_action(request)
        if not action:
            return response
            
        # Crear registro de actividad
        try:
            from .mixins import get_active_company_id
            ActivityLog.objects.create(
                user=request.user,
                action=action,
                description=self._get_description(request, response),
                model_name=self._get_model_name(request),
                object_id=self._get_object_id(request),
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                company_id=get_active_company_id(request)
            )
        except Exception:
            # Silenciosamente ignorar errores para no afectar la aplicación
            pass
            
        return response
    
    def _get_action(self, request):
        """Determinar la acción basada en el método HTTP y path"""
        method = request.method.upper()
        path = request.path
        
        if method == 'POST':
            if 'create' in path or 'add' in path:
                return 'CREATE'
            elif 'update' in path or 'edit' in path:
                return 'UPDATE'
            elif 'delete' in path:
                return 'DELETE'
            elif 'sale' in path:
                return 'SALE'
            elif 'sync' in path:
                return 'SYNC'
            elif 'invoice' in path:
                return 'INVOICE'
        elif method == 'GET':
            if 'export' in path:
                return 'EXPORT'
            elif 'login' in path:
                return 'LOGIN'
            elif 'logout' in path:
                return 'LOGOUT'
            # No registrar VIEW para no inundar el log con navegacion
                
        return None
    
    def _get_description(self, request, response):
        """Generar descripción de la actividad"""
        try:
            if request.method == 'POST':
                # Intentar obtener datos del POST
                if hasattr(request, 'POST') and request.POST:
                    data = dict(request.POST)
                    # Remover campos sensibles
                    sensitive_fields = ['password', 'csrfmiddlewaretoken', 'secret']
                    for field in sensitive_fields:
                        data.pop(field, None)
                    # Manejar datos no serializables de forma segura
                    try:
                        json_data = json.dumps(data, default=str, ensure_ascii=False)
                        return f"{request.method} {request.path} - Datos: {json_data[:200]}..."
                    except (TypeError, ValueError):
                        # Si hay error de serialización, usar representación simple
                        data_str = {k: str(v)[:100] for k, v in data.items()}
                        return f"{request.method} {request.path} - Datos: {str(data_str)[:200]}..."
                else:
                    return f"{request.method} {request.path}"
            else:
                return f"{request.method} {request.path} - Status: {response.status_code}"
        except Exception:
            return f"{request.method} {request.path}"
    
    def _get_model_name(self, request):
        """Extraer nombre del modelo del path"""
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) >= 2:
            return path_parts[1].capitalize()
        return ''
    
    def _get_object_id(self, request):
        """Extraer ID del objeto del path"""
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) >= 3 and path_parts[-1].isdigit():
            return int(path_parts[-1])
        return None
    
    def _get_client_ip(self, request):
        """Obtener IP real del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
