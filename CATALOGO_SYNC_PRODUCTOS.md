# Sincronización de Productos ERP → Catálogo

## **Descripción**

Documento de referencia para implementar/actualizar el endpoint en el catálogo (SitioCatalogoJP) que recibe los productos enviados desde el ERP (SitioMTCRM).

El ERP envía una **foto completa** del catálogo de productos de la empresa: código, nombre, precio y stock. **Las categorías NO se sincronizan** — la organización/categorización se gestiona exclusivamente en el catálogo.

---

## **Información del Endpoint (lado catálogo)**

- **URL que debe exponer el catálogo:** `/api/sincronizar-productos-crm/`
- **Método:** `POST`
- **Content-Type:** `application/json`
- **Autenticación:** `api_key` enviada **en el body** del JSON (no en headers)
- **Timeout del cliente (ERP):** 60 segundos

La `api_key` es la configurada en el ERP (`/erp/catalogo/list/` → campo "API Key del Catálogo"). El catálogo debe validarla contra su propia configuración.

---

## **Estructura del JSON Enviado**

### **Request completo**

```json
{
  "api_key": "CLAVE_DE_API_DEL_CATALOGO",
  "productos": [
    {
      "codigo": "PROD-001",
      "nombre": "Guitarra Fender Stratocaster",
      "descripcion": "",
      "precio": 150000.0,
      "stock": 5,
      "marca": "",
      "imagen_url": "/media/products/fender.jpg",
      "fecha_actualizacion": "2026-09-24T10:30:00+00:00"
    },
    {
      "codigo": "PROD-002",
      "nombre": "Cuerdas Guitarra",
      "descripcion": "",
      "precio": 5000.0,
      "stock": 0,
      "marca": "",
      "imagen_url": "",
      "fecha_actualizacion": ""
    }
  ]
}
```

### **Campos de cada producto**

| Campo | Tipo | Siempre presente | Descripción |
|-------|------|------------------|-------------|
| `codigo` | String | Sí | **Clave de match.** Es el `code` del producto en el ERP. Puede venir vacío si el producto no tiene código cargado. |
| `nombre` | String | Sí | Nombre del producto. |
| `descripcion` | String | Sí | Actualmente siempre `""` (el ERP no tiene descripción). |
| `precio` | Float | Sí | Precio de venta final (`pvp_final`, con IVA y ajustes aplicados). |
| `stock` | Integer | Sí | Stock actual del ERP. **Puede ser 0** — el producto debe quedar como "sin stock", no eliminarse. |
| `marca` | String | Sí | Actualmente siempre `""` (el ERP no envía marca). |
| `imagen_url` | String | Sí | **Ruta relativa** tipo `/media/...`. Para descargarla hay que anteponer el dominio del ERP. Vacío si no tiene imagen. |
| `fecha_actualizacion` | String | Sí | ISO 8601 de la última sync del producto. Puede venir `""`. |

> **Nota:** el campo `categoria` **ya no se envía**. El catálogo no debe requerirlo ni usarlo para reorganizar productos.

---

## **Comportamiento Esperado del Endpoint**

### **1. Validación**

- Verificar `api_key` → si es inválida, responder `401` con `{"error": "..."}`.
- Verificar que `productos` sea una lista → si falta o es inválida, responder `400`.

### **2. Match de productos**

- Buscar cada producto del catálogo por `codigo` (equivale al SKU del catálogo).
- **Si existe:** actualizar `nombre`, `precio` y `stock`. **NO tocar la categoría** asignada en el catálogo.
- **Si no existe:** crear el producto **sin categoría** (o en una categoría genérica "Sin categorizar") para que luego se ordene manualmente en el catálogo.
- Los productos con `stock: 0` se crean/actualizan igual — solo deben mostrarse como sin stock.

### **3. Idempotencia**

- El ERP envía **todos los productos en cada sync** (snapshot completo, no delta).
- El endpoint debe ser idempotente: recibir el mismo producto dos veces no debe duplicarlo.
- Recomendado: `update_or_create` por `codigo`.

### **4. Productos que ya no vienen**

- Si un producto existe en el catálogo pero **no viene en el payload**, el ERP no envía instrucción de borrado. Decisión del catálogo: dejarlo, ocultarlo o desactivarlo (recomendado: marcar `activo=False` si no vino en N syncs consecutivos).

---

## **Respuesta Esperada por el ERP**

El ERP evalúa `response.status_code`:

### **Éxito (200)**

```json
{
  "success": true,
  "recibidos": 150,
  "creados": 10,
  "actualizados": 135,
  "omitidos": 5
}
```

El ERP solo loguea el contenido; los nombres de campos de la respuesta son libres.

### **Error (4xx/5xx)**

El ERP intenta leer, en este orden: `error`, `detail`, `message`. Si no hay JSON, muestra el texto plano.

```json
{"error": "API key inválida"}
```

---

## **Ejemplo de Implementación (Django, lado catálogo)**

```python
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

@csrf_exempt
@require_POST
def sincronizar_productos_crm(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    # Validar API key (viene en el body, no en headers)
    if data.get('api_key') != settings.CRM_API_KEY:
        return JsonResponse({'error': 'API key inválida'}, status=401)

    productos = data.get('productos')
    if not isinstance(productos, list):
        return JsonResponse({'error': 'Campo productos inválido'}, status=400)

    creados = actualizados = omitidos = 0
    for p in productos:
        codigo = (p.get('codigo') or '').strip()
        if not codigo:
            omitidos += 1
            continue

        _, created = Producto.objects.update_or_create(
            sku=codigo,
            defaults={
                'nombre': p.get('nombre', ''),
                'precio': p.get('precio', 0),
                'stock': p.get('stock', 0),
                # NO tocar 'categoria' — la gestiona el catálogo
            }
        )
        creados += created
        actualizados += not created

    return JsonResponse({
        'success': True,
        'recibidos': len(productos),
        'creados': creados,
        'actualizados': actualizados,
        'omitidos': omitidos,
    })
```

---

## **Cómo se Dispara el Sync**

- **Manual:** botón "Sincronizar" en `/erp/catalogo/list/` (llama a `POST /erp/catalogo/sync/`).
- **Automático:** los campos `auto_sync` / `sync_interval_hours` existen en la config pero actualmente **no ejecutan nada** — hace falta un cron/scheduler que llame al endpoint del ERP.

---

## **Notas Técnicas**

- El ERP deshabilita la verificación SSL (`verify=False`) — funciona con certificados autofirmados.
- Si el catálogo responde un redirect (302), el ERP lo reporta como error mostrando el `Location`.
- `imagen_url` es relativa: para usarla hay que concatenar el dominio del ERP (ej: `https://erp.example.com` + `/media/products/fender.jpg`).

---

## **Versión**

- **Versión del contrato:** 1.1
- **Fecha:** 24/09/2026
- **Cambios v1.1:** se eliminó el campo `categoria` del payload (la categorización se gestiona en el catálogo).
- **Código fuente del envío:** `core/erp/views/catalogo/views.py` → `enviar_productos_catalogo`
