# Guía de Pruebas para Integración AFIP

## Estado Actual del Sistema

✅ **Librería instalada:** `afip.py` versión 1.0.0  
✅ **Modelos configurados:** `AfipConfig` para configuración por empresa  
✅ **Cliente AFIP:** `AfipClient` wrapper para AFIP SDK  
✅ **Vistas disponibles:** Configuración, pruebas y dashboard  
✅ **Configuración settings:** Variables de entorno en `config/settings.py`

## Pasos para Probar en Modo Desarrollo

### 1. Obtener Access Token

1. Ir a https://app.afipsdk.com
2. Registrarse o iniciar sesión
3. Obtener el `access_token` gratuito para desarrollo

### 2. Configurar Variables de Entorno

En el archivo `.env` o configurar las variables en `config/settings.py`:

```bash
# AFIP SDK Configuration
AFIP_ACCESS_TOKEN=tu_access_token_de_afipsdk
AFIP_CUIT=20409378472  # CUIT de prueba de AFIP SDK
AFIP_ENVIRONMENT=dev  # 'dev' para desarrollo, 'prod' para producción
```

**Nota:** En modo desarrollo no se necesitan certificados digitales.

### 3. Configurar Empresa para AFIP

1. Iniciar sesión en el sistema como superusuario
2. Ir a **Configuración AFIP** (`/erp/afip/dashboard/`)
3. Crear una configuración AFIP:
   - Seleccionar la empresa
   - El CUIT se cargará automáticamente de la empresa
   - El access token se cargará de la configuración global
   - Ambiente: `Desarrollo` (dev)
   - Dejar certificado y key vacíos (solo para producción)

### 4. Probar Conexión

1. Ir a **Pruebas AFIP** (`/erp/afip/test/`)
2. Seleccionar la empresa configurada
3. **Probar conexión:**
   - Click en "Probar Conexión"
   - Debería mostrar estado del servidor AFIP

4. **Consultar contribuyente:**
   - Ingresar un CUIT (ej: 20111111112)
   - Click en "Consultar Contribuyente"
   - Debería mostrar información del contribuyente

5. **Obtener tipos de comprobantes:**
   - Click en "Obtener Tipos de Comprobantes"
   - Debería mostrar lista de tipos disponibles

## CUIT de Prueba

Para desarrollo, AFIP SDK proporciona el CUIT de prueba:
- **CUIT:** 20-40937847-2
- **Uso:** Funciona sin certificado digital en modo desarrollo

## Modo Producción

Para pasar a producción:

### 1. Obtener Certificado Digital

Seguir la guía: https://afipsdk.com/blog/como-obtener-certificado-para-web-services-arca/

### 2. Configurar Variables de Entorno

```bash
AFIP_ENVIRONMENT=prod
AFIP_CERT_PATH=/ruta/a/certificado.crt
AFIP_KEY_PATH=/ruta/a/key.key
```

### 3. Actualizar Configuración AFIP

1. Ir a la configuración AFIP de la empresa
2. Cambiar ambiente a `Producción` (prod)
3. Cargar el contenido del certificado y key
4. Guardar configuración

## Funcionalidades Disponibles

### Vistas del Sistema

- **Dashboard AFIP:** `/erp/afip/dashboard/` - Vista general de configuraciones
- **Lista de Configuraciones:** `/erp/afip/list/` - CRUD de configuraciones AFIP
- **Pruebas AFIP:** `/erp/afip/test/` - Pruebas de conexión y funcionalidad

### Métodos del Cliente AFIP

```python
from core.erp.afip.client import AfipClient

# Inicializar cliente
client = AfipClient(company_id=1)

# Verificar estado del servidor
status = client.get_server_status()

# Consultar información de contribuyente
taxpayer = client.get_taxpayer_info(cuit='20111111112')

# Obtener tipos de comprobantes
types = client.get_invoice_types()

# Registrar factura (cuando esté implementado)
invoice = client.register_invoice(invoice_data)
```

## Troubleshooting

### Error: "No module named 'afip'"
```bash
source DJENV/bin/activate
pip install afip.py
```

### Error: "Access token inválido"
- Verificar que el access token sea correcto
- Obtener nuevo token en https://app.afipsdk.com

### Error: "CUIT inválido"
- Usar CUIT de prueba 20-40937847-2 para desarrollo
- Verificar formato sin guiones: 20409378472

### Error: "Certificado requerido"
- Solo ocurre en modo producción
- Configurar certificado y key en la configuración AFIP
- O usar modo desarrollo para pruebas

## Referencias

- **Documentación oficial:** https://docs.afipsdk.com/integracion/python
- **Access token:** https://app.afipsdk.com
- **Obtener certificado:** https://afipsdk.com/blog/como-obtener-certificado-para-web-services-arca/
- **Ejemplo de facturación:** https://github.com/AfipSDK/afip-sdk-billing-example-python
- **Referencia API:** https://afipsdk.com/docs/api-reference/introduction/

## Pruebas Recomendadas

1. ✅ Probar conexión con servidor AFIP (FEDummy)
2. ✅ Consultar información de contribuyente
3. ✅ Obtener tipos de comprobantes
4. ✅ Obtener tipos de conceptos
5. ✅ Obtener tipos de documentos
6. ✅ Obtener tipos de alícuotas de IVA
7. ✅ Obtener tipos de monedas
8. ✅ Registrar factura de prueba (createVoucher)
9. ✅ Integración automática con ventas (emitir_factura_afip)
10. ⏳ Consultar factura registrada (pendiente de implementación)

## Integración Automática con Ventas

El sistema ahora emite automáticamente facturas AFIP cuando se crea una venta confirmada.

### Configuración Requerida

1. **Crear configuración AFIP por empresa:**
   - Ir a `/erp/afip/dashboard/`
   - Seleccionar empresa
   - Configurar CUIT (se pre-llena con el CUIT de la empresa)
   - Configurar punto de venta (default: 1)
   - Configurar tipo de comprobante (default: 6 = Factura B)
   - Seleccionar ambiente (dev/prod)
   - Crear configuración

2. **Campos agregados al modelo Sale:**
   - `afip_cae`: Código de Autorización Electrónico
   - `afip_cae_vto`: Fecha de vencimiento del CAE
   - `afip_voucher_number`: Número de comprobante AFIP
   - `afip_result`: Resultado completo de AFIP (JSON)
   - `afip_error`: Error si falla la emisión

### Flujo de Emisión Automática

1. Cuando se crea una venta con `status='confirmed'` y no es presupuesto
2. El método `save()` del modelo Sale llama a `emitir_factura_afip()`
3. Se verifica que exista configuración AFIP activa para la empresa
4. Se calculan las alícuotas de IVA de los detalles de venta
5. Se preparan los datos del voucher según configuración
6. Se llama a `client.create_voucher()` para obtener el CAE
7. Se guardan los resultados en la venta

### Campos del Voucher

El sistema prepara automáticamente:
- **Punto de venta:** Desde configuración AFIP
- **Tipo de comprobante:** Desde configuración AFIP
- **Documento del cliente:** CUIT si está disponible, sino documento exterior
- **Importes:** Total, subtotal, IVA calculado de los detalles
- **Alícuotas de IVA:** Calculadas automáticamente según porcentaje (21%, 10.5%, 0%)
- **Fecha:** Fecha actual en formato AFIP (yyyymmdd)

### Manejo de Errores

Si falla la emisión AFIP:
- El error se guarda en `afip_error`
- La venta se crea normalmente (no se bloquea)
- Se puede reintentar manualmente si es necesario

## Facturación Electrónica

### Método createVoucher

El sistema ahora incluye el método `create_voucher()` para crear comprobantes electrónicos con CAE.

**Ejemplo de datos para crear una factura:**

```python
from core.erp.afip.client import AfipClient

# Inicializar cliente
client = AfipClient(company_id=1)

# Datos del comprobante
voucher_data = {
    'CantReg': 1,              # Cantidad de comprobantes
    'PtoVta': 1,              # Punto de venta
    'CbteTipo': 6,            # Tipo de comprobante (6 = Factura B)
    'Concepto': 1,            # Concepto (1 = Productos, 2 = Servicios, 3 = Productos y Servicios)
    'DocTipo': 80,            # Tipo de documento (80 = CUIT)
    'DocNro': 20111111112,    # Número de documento del comprador
    'CbteDesde': 1,           # Número de comprobante desde
    'CbteHasta': 1,           # Número de comprobante hasta
    'CbteFch': 20240616,      # Fecha del comprobante (yyyymmdd)
    'ImpTotal': 121.00,       # Importe total
    'ImpTotConc': 0,          # Importe neto no gravado
    'ImpNeto': 100.00,        # Importe neto gravado
    'ImpOpEx': 0,             # Importe exento de IVA
    'ImpIVA': 21.00,          # Importe total de IVA
    'ImpTrib': 0,             # Importe total de tributos
    'MonId': 'PES',           # Tipo de moneda (PES = Pesos argentinos)
    'MonCotiz': 1,            # Cotización de la moneda
    'Iva': [                  # Alícuotas de IVA
        {
            'Id': 5,           # Tipo de IVA (5 = 21%)
            'BaseImp': 100.00, # Base imponible
            'Importe': 21.00   # Importe de IVA
        }
    ]
}

# Crear voucher
result = client.create_voucher(voucher_data, full_response=True)

# Respuesta esperada:
# {
#     'CAE': '12345678901234',
#     'CAEFchVto': '2024-06-30',
#     ...
# }
```

### Métodos Auxiliares Disponibles

- `get_invoice_types()` - Obtener tipos de comprobantes disponibles
- `get_concept_types()` - Obtener tipos de conceptos disponibles
- `get_document_types()` - Obtener tipos de documentos disponibles
- `get_aliquote_types()` - Obtener tipos de alícuotas de IVA disponibles
- `get_currency_types()` - Obtener tipos de monedas disponibles

### Tipos de Comprobantes Comunes

- **1:** Factura A
- **6:** Factura B
- **11:** Factura C
- **51:** Nota de Crédito A
- **56:** Nota de Crédito B
- **61:** Nota de Crédito C

### Tipos de Documentos Comunes

- **80:** CUIT
- **86:** CUIL
- **96:** DNI
- **99:** Documento del exterior

### Tipos de IVA Comunes

- **3:** 0%
- **4:** 10.5%
- **5:** 21%
- **6:** 27%
