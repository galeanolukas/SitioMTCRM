import json
import time
from collections import defaultdict
from django.http import JsonResponse, HttpResponseForbidden
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

# In-memory scan queue: { session_key: [ {code, timestamp}, ... ] }
_scan_queue = defaultdict(list)


@method_decorator([csrf_exempt, login_required], name='dispatch')
class ScannerMobileView(TemplateView):
    """Vista móvil para escanear códigos de barras/QR desde un celular.
    Acceso: superusuarios o usuarios del grupo 'scanner'."""
    template_name = 'scanner/mobile.html'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.groups.filter(name='scanner').exists()):
            return HttpResponseForbidden('No tiene permiso para usar el escáner móvil.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Escáner Móvil'
        return ctx


@method_decorator(csrf_exempt, name='dispatch')
class ScanSubmitView(View):
    """Recibe un código escaneado desde el celular y lo encola."""

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'No autenticado'}, status=403)

        try:
            data = json.loads(request.body)
            code = str(data.get('code', '')).strip()
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'JSON inválido'}, status=400)

        if not code:
            return JsonResponse({'error': 'Código vacío'}, status=400)

        session_key = request.session.session_key or str(request.user.id)
        _scan_queue[session_key].append({
            'code': code,
            'timestamp': time.time(),
        })

        return JsonResponse({'success': True, 'code': code})


@method_decorator(csrf_exempt, name='dispatch')
class ScanPollView(View):
    """El POS consulta si hay códigos nuevos escaneados."""

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'No autenticado'}, status=403)

        session_key = request.session.session_key or str(request.user.id)
        codes = _scan_queue.pop(session_key, [])

        return JsonResponse({
            'codes': [item['code'] for item in codes],
            'count': len(codes),
        })
