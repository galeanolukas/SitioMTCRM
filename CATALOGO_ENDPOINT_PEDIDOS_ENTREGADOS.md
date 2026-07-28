# Endpoint del Catálogo - Pedidos Entregados

## **Descripción**

Este documento describe el endpoint que debe implementarse en el catálogo online para que el ERP local pueda consultar los pedidos entregados y sincronizarlos automáticamente.

## **Información del Endpoint**

- **URL:** `/api/pedidos-entregados/`
- **Método:** `GET`
- **Content-Type:** `application/json`
- **Autenticación:** API Key (query parameter)

## **Parámetros de Consulta**

| Parámetro | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `api_key` | string | Sí | API Key configurada en el ERP |
| `desde_fecha` | string (YYYY-MM-DD) | No | Fecha desde la cual buscar pedidos (default: 7 días atrás) |

## **Respuesta Exitosa**

```json
{
  "success": true,
  "total": 2,
  "pedidos": [
    {
      "pedido_id": 12345,
      "fecha": "2026-07-27T12:00:00",
      "estado": "entregado",
      "cliente": {
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
        }
      ],
      "total": 160000,
      "costo_envio": 5000,
      "metodo_pago": "mercado_pago",
      "direccion_entrega": {
        "calle": "Av. Principal 123",
        "barrio": "Centro",
        "codigo_postal": "3000",
        "referencias": "Entre calles"
      },
      "observaciones": "Pedido especial"
    },
    {
      "pedido_id": 12346,
      "fecha": "2026-07-27T14:30:00",
      "estado": "entregado",
      "cliente": {
        "nombre": "María García",
        "email": "maria@email.com",
        "telefono": "+5493709876543"
      },
      "productos": [
        {
          "sku": "PROD-002",
          "nombre": "Batería Yamaha",
          "cantidad": 1,
          "precio_unitario": 200000,
          "subtotal": 200000
        }
      ],
      "total": 210000,
      "costo_envio": 5000,
      "metodo_pago": "efectivo",
      "direccion_entrega": {
        "calle": "Calle Test 456",
        "barrio": "Norte",
        "codigo_postal": "3000"
      },
      "observaciones": ""
    }
  ]
}
```

## **Respuesta de Error**

```json
{
  "success": false,
  "error": "API key inválida"
}
```

## **Implementación de Referencia (Python/Django)**

```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from datetime import datetime, timedelta
from .models import Pedido, ProductoPedido, CatalogoConfig

@csrf_exempt
@require_http_methods(["GET"])
def pedidos_entregados(request):
    """
    Endpoint para consultar pedidos entregados desde el ERP local
    """
    # Obtener parámetros
    api_key = request.GET.get('api_key')
    desde_fecha = request.GET.get('desde_fecha')
    
    # Validar API Key
    if not api_key:
        return JsonResponse({
            'success': False,
            'error': 'API key requerida'
        }, status=400)
    
    # Verificar API key en configuración
    config = CatalogoConfig.objects.filter(api_key=api_key).first()
    if not config:
        return JsonResponse({
            'success': False,
            'error': 'API key inválida'
        }, status=401)
    
    # Calcular fecha desde (default: 7 días atrás)
    if desde_fecha:
        try:
            fecha_desde = datetime.strptime(desde_fecha, '%Y-%m-%d')
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Formato de fecha inválido (use YYYY-MM-DD)'
            }, status=400)
    else:
        fecha_desde = datetime.now() - timedelta(days=7)
    
    # Consultar pedidos entregados
    pedidos = Pedido.objects.filter(
        estado='entregado',
        fecha_entrega__gte=fecha_desde
    ).order_by('-fecha_entrega')
    
    # Construir respuesta
    pedidos_data = []
    for pedido in pedidos:
        # Obtener productos del pedido
        productos = []
        for prod_pedido in pedido.productos.all():
            productos.append({
                'sku': prod_pedido.producto.sku,
                'nombre': prod_pedido.producto.nombre,
                'cantidad': prod_pedido.cantidad,
                'precio_unitario': float(prod_pedido.precio_unitario),
                'subtotal': float(prod_pedido.subtotal)
            })
        
        # Construir dirección de entrega
        direccion_entrega = {
            'calle': pedido.direccion_calle or '',
            'barrio': pedido.direccion_barrio or '',
            'codigo_postal': pedido.direccion_codigo_postal or '',
            'referencias': pedido.direccion_referencias or ''
        }
        
        pedidos_data.append({
            'pedido_id': pedido.id,
            'fecha': pedido.fecha_pedido.isoformat() if pedido.fecha_pedido else None,
            'estado': pedido.estado,
            'cliente': {
                'nombre': pedido.cliente_nombre or '',
                'email': pedido.cliente_email or '',
                'telefono': pedido.cliente_telefono or ''
            },
            'productos': productos,
            'total': float(pedido.total),
            'costo_envio': float(pedido.costo_envio) if pedido.costo_envio else 0,
            'metodo_pago': pedido.metodo_pago or 'mercado_pago',
            'direccion_entrega': direccion_entrega,
            'observaciones': pedido.observaciones or ''
        })
    
    return JsonResponse({
        'success': True,
        'total': len(pedidos_data),
        'pedidos': pedidos_data
    })
```

## **Implementación de Referencia (Node.js/Express)**

```javascript
const express = require('express');
const router = express.Router();
const Pedido = require('../models/Pedido');

router.get('/api/pedidos-entregados', async (req, res) => {
    try {
        const { api_key, desde_fecha } = req.query;
        
        // Validar API Key
        if (!api_key) {
            return res.status(400).json({
                success: false,
                error: 'API key requerida'
            });
        }
        
        // Verificar API key (ajustar según tu configuración)
        const config = await CatalogoConfig.findOne({ api_key });
        if (!config) {
            return res.status(401).json({
                success: false,
                error: 'API key inválida'
            });
        }
        
        // Calcular fecha desde
        let fechaDesde;
        if (desde_fecha) {
            fechaDesde = new Date(desde_fecha);
            if (isNaN(fechaDesde.getTime())) {
                return res.status(400).json({
                    success: false,
                    error: 'Formato de fecha inválido (use YYYY-MM-DD)'
                });
            }
        } else {
            fechaDesde = new Date();
            fechaDesde.setDate(fechaDesde.getDate() - 7);
        }
        
        // Consultar pedidos entregados
        const pedidos = await Pedido.find({
            estado: 'entregado',
            fecha_entrega: { $gte: fechaDesde }
        }).sort({ fecha_entrega: -1 }).populate('productos.producto');
        
        // Construir respuesta
        const pedidosData = pedidos.map(pedido => ({
            pedido_id: pedido._id,
            fecha: pedido.fecha_pedido,
            estado: pedido.estado,
            cliente: {
                nombre: pedido.cliente_nombre,
                email: pedido.cliente_email,
                telefono: pedido.cliente_telefono
            },
            productos: pedido.productos.map(prod => ({
                sku: prod.producto.sku,
                nombre: prod.producto.nombre,
                cantidad: prod.cantidad,
                precio_unitario: prod.precio_unitario,
                subtotal: prod.subtotal
            })),
            total: pedido.total,
            costo_envio: pedido.costo_envio || 0,
            metodo_pago: pedido.metodo_pago || 'mercado_pago',
            direccion_entrega: {
                calle: pedido.direccion_calle || '',
                barrio: pedido.direccion_barrio || '',
                codigo_postal: pedido.direccion_codigo_postal || '',
                referencias: pedido.direccion_referencias || ''
            },
            observaciones: pedido.observaciones || ''
        }));
        
        res.json({
            success: true,
            total: pedidosData.length,
            pedidos: pedidosData
        });
        
    } catch (error) {
        console.error('Error en pedidos_entregados:', error);
        res.status(500).json({
            success: false,
            error: 'Error interno del servidor'
        });
    }
});

module.exports = router;
```

## **Consideraciones Importantes**

### **1. Estados de Pedidos**
- Solo devolver pedidos con estado `entregado`
- No incluir pedidos pendientes, cancelados o en proceso

### **2. SKU de Productos**
- Los SKU deben coincidir con los del ERP
- Si un producto no tiene SKU, usar el código del producto

### **3. Fechas**
- Formato ISO 8601: `YYYY-MM-DDTHH:MM:SS`
- El parámetro `desde_fecha` usa formato `YYYY-MM-DD`

### **4. Paginación (Opcional)**
- Si hay muchos pedidos, implementar paginación
- Agregar parámetros `page` y `limit`

### **5. Seguridad**
- Validar siempre la API Key
- Limitar la cantidad de pedidos devueltos (ej: max 100 por consulta)
- Implementar rate limiting si es necesario

## **Pruebas del Endpoint**

### **Test con cURL:**
```bash
curl -X GET "https://tu-catalogo.com/api/pedidos-entregados/?api_key=TU_API_KEY&desde_fecha=2026-07-20"
```

### **Test con Python:**
```python
import requests

url = "https://tu-catalogo.com/api/pedidos-entregados/"
params = {
    'api_key': 'TU_API_KEY',
    'desde_fecha': '2026-07-20'
}

response = requests.get(url, params=params)
data = response.json()

print(f"Total pedidos: {data['total']}")
for pedido in data['pedidos']:
    print(f"Pedido {pedido['pedido_id']}: ${pedido['total']}")
```

## **Integración con ERP**

El ERP usará este endpoint a través del comando:
```bash
python manage.py sync_pedidos_catalogo --dias=7
```

Este comando:
1. Consulta este endpoint
2. Crea ventas locales automáticamente
3. Evita duplicados usando `catalogo_pedido_id`
