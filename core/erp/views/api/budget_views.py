from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.db import transaction
import json
import logging

from core.erp.models import Sale, DetSale, Company, Client, Product
from core.erp.sync_utils import _get_sync_destination

logger = logging.getLogger(__name__)
User = get_user_model()


@csrf_exempt
@require_http_methods(["POST"])
def receive_budget(request):
    """
    API endpoint para recibir presupuestos desde POS locales.
    
    Espera un JSON con la siguiente estructura:
    {
        "local_uuid": "uuid_local_del_presupuesto",
        "company_id": 1,
        "client_data": {...},
        "items": [
            {
                "product_id": 1,
                "quantity": 2,
                "price": 100.00
            },
            ...
        ],
        "subtotal": 200.00,
        "iva": 42.00,
        "total": 242.00,
        "payment_method": "cash",
        "budget_notes": "Notas del presupuesto"
    }
    """
    try:
        data = json.loads(request.body)
        
        # Validar campos requeridos
        required_fields = ['local_uuid', 'company_id', 'items', 'subtotal', 'iva', 'total']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'error': f'Campo requerido faltante: {field}'
                }, status=400)
        
        # Verificar si ya existe este presupuesto (por local_uuid)
        if Sale.objects.filter(local_uuid=data['local_uuid']).exists():
            return JsonResponse({
                'success': False,
                'error': 'El presupuesto ya existe en el servidor'
            }, status=409)
        
        # Obtener o crear empresa
        try:
            company = Company.objects.get(id=data['company_id'])
        except Company.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Empresa no encontrada'
            }, status=404)
        
        # Obtener o crear cliente
        client_data = data.get('client_data', {})
        if client_data.get('id'):
            try:
                client = Client.objects.get(id=client_data['id'])
            except Client.DoesNotExist:
                client = Client.objects.create(
                    company=company,
                    names=client_data.get('names', 'Cliente'),
                    dni=client_data.get('dni', ''),
                    address=client_data.get('address', ''),
                    phone=client_data.get('phone', '')
                )
        else:
            client = Client.objects.create(
                company=company,
                names=client_data.get('names', 'Cliente'),
                dni=client_data.get('dni', ''),
                address=client_data.get('address', ''),
                phone=client_data.get('phone', '')
            )
        
        # Crear el presupuesto
        with transaction.atomic():
            sale = Sale.objects.create(
                company=company,
                cli=client,
                subtotal=data['subtotal'],
                iva=data['iva'],
                total=data['total'],
                payment_method=data.get('payment_method', 'cash'),
                status='budget',
                is_budget=True,
                local_uuid=data['local_uuid'],
                source='server',
                budget_notes=data.get('budget_notes', ''),
                pos_id=data.get('pos_id', ''),
                synced_to_server=True  # Marcar como sincronizado
            )
            
            # Crear los items del presupuesto
            # Buscar producto por ID, luego por code, luego por nombre
            for item_data in data['items']:
                product = None
                # 1) Buscar por ID si coincide
                if item_data.get('product_id'):
                    product = Product.objects.filter(id=item_data['product_id']).first()
                # 2) Buscar por code
                if not product and item_data.get('product_code'):
                    product = Product.objects.filter(code=item_data['product_code']).first()
                # 3) Buscar por nombre exacto
                if not product and item_data.get('product_name'):
                    product = Product.objects.filter(name=item_data['product_name']).first()
                
                if product:
                    DetSale.objects.create(
                        sale=sale,
                        prod=product,
                        price=item_data['price'],
                        cant=item_data['quantity'],
                        subtotal=item_data.get('subtotal', item_data['price'] * item_data['quantity'])
                    )
                else:
                    logger.warning(
                        f"Producto no encontrado (id={item_data.get('product_id')}, "
                        f"code={item_data.get('product_code')}, name={item_data.get('product_name')}), omitiendo item"
                    )
            
            logger.info(f"Presupuesto recibido: {sale.local_uuid} - Total: {sale.total}")
        
        return JsonResponse({
            'success': True,
            'sale_id': sale.id,
            'local_uuid': sale.local_uuid,
            'message': 'Presupuesto recibido exitosamente'
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Error recibiendo presupuesto: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def confirm_budget(request, sale_id):
    """
    API endpoint para confirmar un presupuesto y convertirlo en venta.
    """
    try:
        # Verificar autenticación (puedes agregar token auth aquí)
        # Por ahora, solo verificamos que sea POST
        
        sale = Sale.objects.get(id=sale_id, is_budget=True, status='budget')
        
        # Convertir presupuesto en venta
        sale.status = 'confirmed'
        sale.is_budget = False
        sale.save(skip_afip_call_on_save=True)
        
        # Descontar stock de los productos
        from django.db.models import F
        from django.db.models.functions import Greatest
        from django.utils import timezone
        for det in sale.detsale_set.all():
            Product.objects.filter(pk=det.prod_id).update(
                stock=Greatest(F('stock') - det.cant, 0),
                stock_modified_locally=timezone.now(),
                synced_to_server=False
            )
        
        logger.info(f"Presupuesto confirmado: {sale.local_uuid} - ID: {sale.id}")
        
        return JsonResponse({
            'success': True,
            'sale_id': sale.id,
            'message': 'Presupuesto confirmado y convertido en venta'
        })
        
    except Sale.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Presupuesto no encontrado'
        }, status=404)
    except Exception as e:
        logger.error(f"Error confirmando presupuesto: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
