# Endpoint para Recepción de Ventas del Catálogo

## **Descripción**

Este documento describe cómo integrar el catálogo online (SitioCatalogoJP) con el ERP (SitioMTCRM) para enviar automáticamente las ventas generadas en el catálogo.

---

## **Información del Endpoint**

- **URL:** `/erp/api/ventas/receive/`
- **Método:** `POST`
- **Content-Type:** `application/json`
- **Autenticación:** Bearer Token (API Key)

---

## **Configuración**

### **1. Obtener API Key**

La API Key se configura en el ERP a través del modelo `CatalogoConfig`:

- Acceder al ERP: `/erp/catalogo/list/`
- Crear o editar una configuración de catálogo
- Copiar la `API Key` generada

### **2. Configurar URL del ERP**

En el catálogo, configurar:
- **URL del ERP:** `https://tu-dominio.com/erp/api/ventas/receive/`
- **API Key:** La key copiada del ERP

---

## **Formato del JSON a Enviar**

### **Estructura Completa**

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

### **Campos Requeridos**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `pedido_id` | Integer | ID único del pedido en el catálogo |
| `cliente` | Object | Datos del cliente |
| `productos` | Array | Lista de productos del pedido |
| `total` | Decimal | Monto total del pedido |

### **Campos Opcionales**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `fecha` | DateTime | Fecha del pedido (ISO 8601) |
| `costo_envio` | Decimal | Costo de envío |
| `estado` | String | Estado del pedido |
| `metodo_pago` | String | Método de pago (ver tabla abajo) |
| `direccion_entrega` | Object | Dirección de entrega |
| `observaciones` | String | Observaciones adicionales |

### **Métodos de Pago Soportados**

| Valor del catálogo | Valor en ERP |
|-------------------|--------------|
| `mercado_pago` | `mp` |
| `efectivo` | `cash` |
| `transferencia` | `transfer` |
| `tarjeta` | `card` |

---

## **Ejemplos de Implementación**

### **Python (requests)**

```python
import requests
import json

# Configuración
erp_url = "https://tu-dominio.com/erp/api/ventas/receive/"
api_key = "TU_API_KEY_AQUI"

# Datos de la venta
venta_data = {
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

# Headers
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

# Enviar solicitud
try:
    response = requests.post(erp_url, json=venta_data, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Venta registrada exitosamente")
        print(f"   Sale ID: {result['sale_id']}")
        print(f"   Pedido ID: {result['catalogo_pedido_id']}")
        print(f"   Productos creados: {result['productos_creados']}")
        if result['productos_errores']:
            print(f"   Errores: {result['productos_errores']}")
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   {response.json()}")
        
except requests.exceptions.RequestException as e:
    print(f"❌ Error de conexión: {e}")
```

### **JavaScript (fetch)**

```javascript
const erpUrl = "https://tu-dominio.com/erp/api/ventas/receive/";
const apiKey = "TU_API_KEY_AQUI";

const ventaData = {
    pedido_id: 123,
    fecha: "2026-07-27T12:00:00",
    cliente: {
        nombre: "Juan Pérez",
        email: "juan@email.com",
        telefono: "+5493701234567"
    },
    productos: [
        {
            sku: "PROD-001",
            nombre: "Producto Test",
            cantidad: 1,
            precio_unitario: 1000,
            subtotal: 1000
        }
    ],
    total: 1000,
    metodo_pago: "mercado_pago"
};

fetch(erpUrl, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify(ventaData)
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        console.log('✅ Venta registrada exitosamente');
        console.log('Sale ID:', data.sale_id);
        console.log('Pedido ID:', data.catalogo_pedido_id);
        console.log('Productos creados:', data.productos_creados);
        if (data.productos_errores.length > 0) {
            console.log('Errores:', data.productos_errores);
        }
    } else {
        console.log('❌ Error:', data.error);
    }
})
.catch(error => {
    console.error('❌ Error de conexión:', error);
});
```

### **cURL**

```bash
curl -X POST https://tu-dominio.com/erp/api/ventas/receive/ \
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

---

## **Respuesta del Endpoint**

### **Respuesta Exitosa (200)**

```json
{
  "success": true,
  "sale_id": 456,
  "catalogo_pedido_id": 123,
  "productos_creados": 2,
  "productos_errores": [],
  "message": "Venta registrada correctamente"
}
```

### **Respuesta con Errores de Producto (200)**

```json
{
  "success": true,
  "sale_id": 456,
  "catalogo_pedido_id": 123,
  "productos_creados": 1,
  "productos_errores": [
    "Producto no encontrado: SKU=PROD-002"
  ],
  "message": "Venta registrada correctamente"
}
```

### **Error de Autenticación (401)**

```json
{
  "success": false,
  "error": "API key inválida o no autorizada"
}
```

### **Error de Validación (400)**

```json
{
  "success": false,
  "error": "Campo requerido faltante: pedido_id"
}
```

### **Error Interno (500)**

```json
{
  "success": false,
  "error": "Error interno: [descripción del error]"
}
```

---

## **Comportamiento del Endpoint**

### **1. Procesamiento de Clientes**

- Si el cliente existe por email: actualiza datos (nombre, teléfono)
- Si el cliente no existe: crea nuevo cliente con los datos proporcionados
- El cliente se asigna a la empresa configurada en `CatalogoConfig`

### **2. Procesamiento de Productos**

- Busca productos por `sku` o `code` en el ERP
- Si encuentra el producto: crea detalle de venta
- Si no encuentra el producto: registra error pero continúa con otros productos
- La venta se crea aunque algunos productos no se encuentren

### **3. Creación de Venta**

- Crea registro en modelo `Sale`
- Asigna `catalogo_pedido_id` para tracking
- Marca `source='catalogo'` para identificar origen
- Calcula subtotal automáticamente desde los productos

### **4. Transaccionalidad**

- Todo el proceso es atómico (transaction.atomic)
- Si hay error, se hace rollback completo
- Garantiza integridad de datos

---

## **Consideraciones Importantes**

### **SKU de Productos**

- Los SKU del catálogo deben coincidir con los `sku` o `code` del ERP
- Se recomienda sincronizar productos del ERP al catálogo
- Si un producto no existe, la venta se crea pero sin ese detalle

### **Duplicados**

- El campo `catalogo_pedido_id` permite identificar ventas duplicadas
- Se recomienda verificar si ya existe una venta con el mismo `pedido_id` antes de enviar

### **Stock**

- El endpoint NO actualiza el stock automáticamente
- El stock debe gestionarse por separado o implementarse lógica adicional

### **Facturación**

- Las ventas del catálogo se crean como ventas normales
- La facturación AFIP debe realizarse manualmente o implementarse lógica adicional

---

## **Troubleshooting**

### **Error 401: API key inválida**

- Verificar que la API Key sea correcta
- Verificar que la configuración de catálogo esté activa en el ERP
- Verificar que no haya espacios extra en el header Authorization

### **Error 400: Campo requerido faltante**

- Verificar que el JSON incluya todos los campos requeridos
- Validar que el Content-Type sea `application/json`
- Verificar que el JSON sea válido (sintaxis correcta)

### **Productos no encontrados**

- Verificar que los SKU coincidan entre catálogo y ERP
- Sincronizar productos del ERP al catálogo
- Revisar logs del ERP para ver qué SKUs fallaron

### **Error 500: Error interno**

- Revisar logs del servidor del ERP
- Verificar conexión a base de datos
- Validar que los modelos existan y estén migrados

---

## **Flujo Completo de Integración**

```
1. Cliente realiza pedido en catálogo
2. Catálogo confirma pago/pedido
3. Catálogo prepara JSON con datos de venta
4. Catálogo envía POST al ERP con API Key
5. ERP valida API Key
6. ERP busca/crea cliente
7. ERP crea venta con detalles
8. ERP responde con sale_id y resultado
9. Catálogo guarda sale_id para tracking
10. Catálogo muestra confirmación al cliente
```

---

## **Soporte**

Para dudas o problemas con la integración:
- Revisar logs del ERP: `/var/log/django/` o logs de la aplicación
- Contactar al equipo de desarrollo del ERP
- Verificar documentación adicional en `/INTEGRACION_CATALOGO.md`

---

## **Version**

- **Versión del endpoint:** 1.0
- **Fecha:** 27/07/2026
- **ERP:** SitioMTCRM
