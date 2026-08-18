# Integración con Catálogo de Ventas (SitioCatalogoJP)

## **Propósito**

Este documento describe cómo implementar un endpoint en el ERP (SitioMTCRM) para recibir ventas desde el catálogo online (SitioCatalogoJP) usando autenticación por API key.

---

## **Arquitectura de la Integración**

```
SitioCatalogoJP (Catálogo)          SitioMTCRM (ERP)
      |                                   |
      |  POST /api/ventas/receive/        |
      |  + JSON con datos de venta        |
      |  + Authorization: Bearer {key}   |
      |---------------------------------->|
      |                                   |
      |                            Procesar venta
      |                            - Crear/actualizar cliente
      |                            - Crear venta
      |                            - Agregar detalles
      |                            - Registrar en sistema
      |                                   |
      |  Response: {success: true}        |
      |<----------------------------------|
```

---

## **1. Configuración de API Key**

### **Opción A: Usar configuración existente**

El ERP ya tiene un sistema de configuración. Puedes agregar la API key en:

**Archivo:** `core/erp/models.py`

```python
class ConfiguracionCatalogo(models.Model):
    """Configuración para integración con catálogo"""
    api_key = models.CharField(max_length=255, unique=True, help_text="API key para autenticar ventas del catálogo")
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    @staticmethod
    def generar_api_key():
        """Genera una API key segura"""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = self.generar_api_key()
        super().save(*args, **kwargs)
```

**Crear migración:**
```bash
python manage.py makemigrations
python manage.py migrate
```

**Crear configuración inicial:**
```python
# En Django shell
from core.erp.models import ConfiguracionCatalogo
config = ConfiguracionCatalogo.objects.create()
print(f"API Key generada: {config.api_key}")
```

### **Opción B: Usar settings.py**

**Archivo:** `config/settings.py`

```python
# Agregar al final del archivo
CATALOGO_API_KEY = "tu-api-key-aqui"  # Generar con secrets.token_urlsafe(32)
```

---

## **2. Estructura del JSON Esperado**

El catálogo enviará el siguiente formato:

```json
{
  "pedido_id": 123,
  "fecha": "2026-07-27T12:00:00",
  "cliente": {
    "id": 456,
    "nombre": "Juan Pérez",
    "email": "juan@email.com",
    "telefono": "+5493701234567"
  },
  "productos": [
    {
      "sku": "PROD-001",
      "nombre": "Guitarra Fender Stratocaster",
      "cantidad": 1,
      "precio_unitario": 150000,
      "subtotal": 150000
    },
    {
      "sku": "PROD-002",
      "nombre": "Cuerdas Guitarra",
      "cantidad": 2,
      "precio_unitario": 5000,
      "subtotal": 10000
    }
  ],
  "total": 160000,
  "costo_envio": 5000,
  "estado": "pendiente",
  "metodo_pago": "mercado_pago",
  "direccion_entrega": {
    "calle": "Av. Principal 123",
    "barrio": "Centro",
    "codigo_postal": "3000",
    "referencias": "Entre calles"
  },
  "observaciones": "Pedido especial"
}
```

---

## **3. Implementación del Endpoint**

### **Paso 1: Crear vista del endpoint**

**Archivo:** `core/erp/views/api/ventas.py` (crear si no existe)

```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from core.erp.models import Client, Sale, SaleDetail, Product
import json

@csrf_exempt
@require_POST
def receive_venta_catalogo(request):
    """
    Endpoint para recibir ventas desde el catálogo online.
    
    Autenticación: Bearer token en header Authorization
    Content-Type: application/json
    """
    # Validar API key
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    # Opción A: Validar contra modelo
    from core.erp.models import ConfiguracionCatalogo
    config = ConfiguracionCatalogo.objects.filter(api_key=api_key, activo=True).first()
    if not config:
        return JsonResponse({
            'success': False,
            'error': 'API key inválida o no autorizada'
        }, status=401)
    
    # Opción B: Validar contra settings
    # from django.conf import settings
    # if api_key != settings.CATALOGO_API_KEY:
    #     return JsonResponse({'success': False, 'error': 'API key inválida'}, status=401)
    
    try:
        data = json.loads(request.body)
        
        # Validar datos requeridos
        campos_requeridos = ['pedido_id', 'cliente', 'productos', 'total']
        for campo in campos_requeridos:
            if campo not in data:
                return JsonResponse({
                    'success': False,
                    'error': f'Campo requerido faltante: {campo}'
                }, status=400)
        
        with transaction.atomic():
            # Buscar o crear cliente
            cliente_data = data['cliente']
            cliente, created = Client.objects.get_or_create(
                email=cliente_data.get('email', ''),
                defaults={
                    'name': cliente_data.get('nombre', ''),
                    'phone': cliente_data.get('telefono', ''),
                    'address': data.get('direccion_entrega', {}).get('calle', '')
                }
            )
            
            # Si el cliente ya existe, actualizar datos
            if not created:
                cliente.name = cliente_data.get('nombre', cliente.name)
                cliente.phone = cliente_data.get('telefono', cliente.phone)
                cliente.save()
            
            # Calcular subtotal
            subtotal = sum(p['subtotal'] for p in data['productos'])
            
            # Mapear método de pago
            metodo_pago_map = {
                'mercado_pago': 'mp',
                'efectivo': 'cash',
                'transferencia': 'transfer',
                'tarjeta': 'card'
            }
            metodo_pago = metodo_pago_map.get(data.get('metodo_pago', 'mercado_pago'), 'mp')
            
            # Crear venta
            venta = Sale.objects.create(
                client=cliente,
                subtotal=subtotal,
                total=data['total'],
                payment_method=metodo_pago,
                observations=data.get('observaciones', ''),
                # Agregar campos adicionales según tu modelo
                catalogo_pedido_id=data['pedido_id']  # ID del pedido del catálogo
            )
            
            # Agregar detalles de productos
            productos_creados = 0
            productos_errores = 0
            
            for prod_data in data['productos']:
                # Buscar producto por SKU
                producto = Product.objects.filter(sku=prod_data.get('sku')).first()
                
                if producto:
                    SaleDetail.objects.create(
                        sale=venta,
                        product=producto,
                        quantity=prod_data['cantidad'],
                        price=prod_data['precio_unitario'],
                        subtotal=prod_data['subtotal']
                    )
                    productos_creados += 1
                else:
                    # Producto no encontrado - crear o loggear error
                    productos_errores += 1
                    # Opcional: Crear producto automáticamente
                    # Product.objects.create(
                    #     sku=prod_data['sku'],
                    #     name=prod_data['nombre'],
                    #     price=prod_data['precio_unitario']
                    # )
            
            return JsonResponse({
                'success': True,
                'sale_id': venta.id,
                'catalogo_pedido_id': data['pedido_id'],
                'productos_creados': productos_creados,
                'productos_errores': productos_errores,
                'message': 'Venta registrada correctamente'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON inválido'
        }, status=400)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }, status=500)
```

### **Paso 2: Agregar URL**

**Archivo:** `core/erp/urls.py`

```python
# Agregar en las importaciones
from core.erp.views.api.ventas import receive_venta_catalogo

# Agregar en urlpatterns
urlpatterns = [
    # ... otras URLs ...
    path('api/ventas/receive/', receive_venta_catalogo, name='api_ventas_receive'),
]
```

### **Paso 3: Crear archivo de vistas (si no existe)**

**Archivo:** `core/erp/views/api/__init__.py`

```python
# Archivo vacío para que sea un paquete Python
```

---

## **4. Pruebas del Endpoint**

### **Test con cURL**

```bash
# Reemplazar TU_API_KEY con la key generada
curl -X POST http://localhost:8000/erp/api/ventas/receive/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TU_API_KEY" \
  -d '{
    "pedido_id": 123,
    "fecha": "2026-07-27T12:00:00",
    "cliente": {
      "nombre": "Juan Pérez",
      "email": "juan@email.com",
      "telefono": "+5493701234567"
    },
    "productos": [
      {
        "sku": "PROD-001",
        "nombre": "Producto Test",
        "cantidad": 1,
        "precio_unitario": 1000,
        "subtotal": 1000
      }
    ],
    "total": 1000,
    "metodo_pago": "mercado_pago"
  }'
```

### **Test con Python**

```python
import requests
import json

url = "http://localhost:8000/erp/api/ventas/receive/"
api_key = "TU_API_KEY"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

data = {
    "pedido_id": 123,
    "fecha": "2026-07-27T12:00:00",
    "cliente": {
        "nombre": "Juan Pérez",
        "email": "juan@email.com",
        "telefono": "+5493701234567"
    },
    "productos": [
        {
            "sku": "PROD-001",
            "nombre": "Producto Test",
            "cantidad": 1,
            "precio_unitario": 1000,
            "subtotal": 1000
        }
    ],
    "total": 1000,
    "metodo_pago": "mercado_pago"
}

response = requests.post(url, json=data, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

---

## **5. Configuración en el Catálogo**

En el catálogo (SitioCatalogoJP), configurar:

**Archivo:** `core/templates/configuracion_sincronizacion_crm.html`

- **URL del ERP:** `http://localhost:8000/erp/api/ventas/receive/` (o tu dominio)
- **API Key:** La key generada en el ERP
- **Usuario/Contraseña:** Para autenticación adicional (opcional)

---

## **6. Flujo Completo**

1. **Cliente hace pedido** en el catálogo
2. **Catálogo confirma pedido** y genera venta
3. **Catálogo envía POST** al ERP con datos de venta
4. **ERP valida API key**
5. **ERP crea/actualiza cliente**
6. **ERP crea venta** con detalles
7. **ERP responde** con `{success: true, sale_id: X}`
8. **Catálogo registra log** de sincronización

---

## **7. Consideraciones Adicionales**

### **Manejo de Errores**

- Si el producto no existe por SKU, puedes:
  - Opción A: Rechazar la venta completa
  - Opción B: Crear el producto automáticamente
  - Opción C: Loggear error y continuar con otros productos

### **Sincronización de Productos**

Para que los SKU coincidan, puedes:
- Sincronizar productos del ERP al catálogo
- O viceversa, del catálogo al ERP
- Usar un campo SKU común en ambos sistemas

### **Seguridad**

- Usar HTTPS en producción
- Rotar API keys periódicamente
- Limitar por IP si es posible
- Agregar rate limiting

### **Logging**

Agregar logging para auditoría:

```python
import logging
logger = logging.getLogger(__name__)

# En el endpoint
logger.info(f"Venta recibida del catálogo: pedido_id={data['pedido_id']}")
```

---

## **8. Troubleshooting**

### **Error 401: API key inválida**
- Verificar que la API key coincida
- Verificar que la configuración esté activa

### **Error 400: Campo requerido faltante**
- Verificar que el JSON tenga todos los campos requeridos
- Validar Content-Type: application/json

### **Error 500: Error interno**
- Verificar logs del servidor
- Validar que los modelos existan
- Verificar conexión a base de datos

---

## **9. Próximos Pasos**

1. ✅ Implementar endpoint en ERP
2. ✅ Configurar API key
3. ✅ Probar endpoint con cURL/Python
4. ⏳ Implementar envío desde catálogo
5. ⏳ Configurar sincronización automática
6. ⏳ Agregar logging y monitoreo

---

## **Contacto**

Para dudas o problemas con la integración, contactar al equipo de desarrollo.
