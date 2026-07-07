# Guía del Dashboard AFIP

## Ubicación
`http://localhost:8000/erp/afip/dashboard/`

## Configuración para Desarrollo (Testing)

AFIP SDK permite probar en modo desarrollo sin necesidad de certificados reales usando un CUIT de prueba.

### CUIT de Prueba de AFIP SDK
- **CUIT:** `20-40937847-2` (sin guiones: `20409378472`)
- **Uso:** Exclusivo para modo desarrollo
- **Ventajas:** No requiere certificados ni Clave Fiscal
- **Limitaciones:** Comprobantes emitidos no tienen validez fiscal

### Pasos para Configurar Desarrollo

1. **Obtener Access Token:**
   - Ir a https://app.afipsdk.com
   - Registrarse y obtener un `access_token` gratuito
   - Configurar en `.env` como `AFIP_ACCESS_TOKEN` (opcional, se puede configurar por empresa)

2. **Crear Empresa de Prueba:**
   - Ir a `/erp/company/list/`
   - Crear nueva empresa o usar una existente
   - Configurar CUIT: `20409378472`
   - Guardar empresa

3. **Crear Configuración AFIP en Modo Desarrollo:**
   - Ir a `/erp/afip/dashboard/`
   - Clic en "Nueva Configuración" o "Crear Config para [Empresa]"
   - Seleccionar la empresa con CUIT de prueba
   - Configurar:
     - **Access Token:** Token de AFIP SDK (o dejar vacío para usar global)
     - **Ambiente:** `Desarrollo` (dev)
     - **Tipo de Comprobante:** `6` (Factura B) u otro
     - **Concepto:** `1` (Productos), `2` (Servicios) o `3` (Ambos)
     - **Moneda:** `PES` (Pesos)
     - **Cotización:** `1` (si es PES)
   - **NO configurar certificados** (no se necesitan en desarrollo con el CUIT de prueba)
   - Guardar configuración

   > **Nota importante:** El botón "Generar Certificado" en modo desarrollo genera un certificado de prueba, pero **no es obligatorio** para probar. El CUIT de prueba de AFIP SDK permite emitir comprobantes de prueba sin certificado. El certificado solo es obligatorio en **producción** con un CUIT real.

4. **Autorizar Web Service (WSFE):**
   - Antes de probar la conexión, es necesario autorizar el uso del Web Service WSFE en AFIP SDK
   - Ir a https://afipsdk.com/docs/automations/auth-web-service-dev/?integration=python
   - Seleccionar el Web Service: `WSFE` (Facturación Electrónica)
   - Ingresar el CUIT de prueba: `20409378472`
   - Ejecutar la automatización de autorización
   - Esto autoriza el uso del Web Service para el CUIT de prueba en modo desarrollo
   - **Importante:** Este paso es obligatorio, de lo contrario obtendrás el error "Debe autorizar el uso del web service"

5. **Probar Conexión:**
   - Clic en "Probar Conexión" en el dashboard
   - Ir a `/erp/afip/test/`
   - Seleccionar la empresa y ejecutar `test_connection`
   - Debería mostrar conexión exitosa con AFIP

6. **Configurar Punto de Venta:**
   - Ir a `/erp/afip/punto-venta/list/` (o al admin de Django)
   - Crear un `AfipPuntoVenta` para la empresa de prueba
   - Usar un número simple, por ejemplo `1`
   - El punto de venta se usa al emitir comprobantes

7. **Emitir Comprobantes de Prueba:**
   - Crear una venta (`/erp/sale/add/`) con:
     - Cliente con DNI/CUIT válido
     - Al menos un producto
     - Tipo de comprobante A, B o C según corresponda
   - Confirmar la venta
   - El sistema intenta emitir la factura AFIP automáticamente
   - Si la venta no se emitió automáticamente, ir a `/erp/afip/vouchers/`, buscar la venta y clic en "Emitir Factura"
   - Los comprobantes tendrán CAE de prueba y no validez fiscal real

   **Flujo técnico:** El sistema usa el Web Service `WSFE` de AFIP a través de `afip.py`, llama a `FEAutorizar` y obtiene `CAE` + `CAEFchVto`.

### Diferencias: Desarrollo vs Producción

| Característica | Desarrollo | Producción |
|----------------|------------|------------|
| CUIT | 20409378472 (prueba) | CUIT real de la empresa |
| Certificados | No necesarios | Obligatorios (generados con Clave Fiscal) |
| Clave Fiscal | No necesaria | Necesaria para generar certificados |
| CAE | CAE de prueba | CAE real con validez fiscal |
| Comprobantes | Sin validez fiscal | Con validez fiscal |
| Web Services | Servidores de prueba | Servidores de producción |

## Funcionamiento General

El dashboard AFIP permite configurar la integración con los Web Services de ARCA (AFIP) utilizando el SDK de AFIP SDK. Está diseñado para trabajar con configuraciones por empresa, permitiendo gestionar múltiples empresas con sus propias credenciales AFIP.

## Integración con AFIP SDK Python

### Librería Utilizada
- **afip.py**: Librería oficial de AFIP SDK para Python
- **Documentación**: https://afipsdk.com/docs/automations/integrations/python/

### Instalación
```bash
pip install afip.py
```

### Inicialización
```python
from afip import Afip

afip = Afip({
    "access_token": "TU_ACCESS_TOKEN",
    "CUIT": "20111111112",
    "cert": "contenido_certificado",  # Solo producción
    "key": "contenido_clave_privada",  # Solo producción
    "production": False  # True para producción
})
```

## Flujo de Configuración AFIP por Empresa

### 1. Crear Configuración AFIP

**Desde el Dashboard:**
1. Clic en "Nueva Configuración" o "Crear Config para [Empresa]"
2. Seleccionar empresa de la lista
3. El CUIT se autocompleta desde la empresa seleccionada
4. Configurar:
   - **Access Token**: Token de AFIP SDK (opcional, usa global si está vacío)
   - **Ambiente**: Desarrollo (dev) o Producción (prod)
   - **Tipo de Comprobante**: 6=Factura B (default), 1=Factura A, etc.
5. Guardar configuración

**Desde Lista de Empresas:**
1. Ir a `/erp/company/list/`
2. Clic en botón "Configurar AFIP" (icono de factura)
3. Redirige al dashboard con `?company_id={id}` preseleccionado

### 2. Generar Certificados (Automatizaciones AFIP SDK)

**Requisitos:**
- Configuración AFIP creada
- Access Token válido de AFIP SDK
- Credenciales de Clave Fiscal (usuario y contraseña)

**Pasos:**
1. Clic en botón "Generar Certificado" en el dashboard
2. Seleccionar configuración AFIP existente
3. Elegir tipo de certificado:
   - **Desarrollo**: Para testing (create-cert-dev)
   - **Producción**: Para ambiente real (create-cert-prod)
4. Ingresar credenciales de Clave Fiscal:
   - Usuario Clave Fiscal
   - Contraseña Clave Fiscal
   - Alias (opcional, default: 'afipsdk')
5. AFIP SDK genera automáticamente:
   - Certificado (.crt)
   - Clave privada (.key)
6. Se guardan en la configuración AFIP

**Automatizaciones Utilizadas:**
- `create-cert-dev`: Genera certificado de desarrollo
- `create-cert-prod`: Genera certificado de producción

## Ambientes: Desarrollo vs Producción

### Desarrollo (dev)
- **Uso**: Testing y desarrollo
- **Certificado**: Generado con `create-cert-dev`
- **Web Services**: Servidores de prueba de AFIP
- **Sin efectos legales**: Comprobantes no tienen validez fiscal
- **Indicador**: Badge azul "Desarrollo"

### Producción (prod)
- **Uso**: Operaciones reales con validez fiscal
- **Certificado**: Generado con `create-cert-prod`
- **Web Services**: Servidores de producción de AFIP
- **Con efectos legales**: Comprobantes emitidos son válidos
- **Indicador**: Badge amarillo "Producción"
- **Requiere**: Certificados válidos (cert y key)

## Campos del Modelo AfipConfig

| Campo | Descripción | Obligatorio |
|-------|-------------|-------------|
| company | Empresa relacionada | Sí |
| cuit | CUIT del contribuyente | Sí |
| access_token | Token de AFIP SDK | Sí |
| cert | Certificado (solo producción) | No (sí en prod) |
| key | Clave privada (solo producción) | No (sí en prod) |
| environment | Ambiente (dev/prod) | Sí |
| tipo_comprobante | Tipo de comprobante default | Sí |
| concepto | Concepto (1=Productos, 2=Servicios, 3=Ambos) | Sí |
| moneda | Moneda (PES, DOL, EUR, BRL) | Sí |
| cotizacion | Cotización si no es PES | Sí |
| usar_contingencia | Modo contingencia (sin AFIP) | No |
| is_active | Configuración activa | Sí |

## Puntos de Venta

Los puntos de venta se gestionan en un modelo separado `AfipPuntoVenta`:
- Cada empresa puede tener múltiples puntos de venta
- Se crean automáticamente al crear una configuración AFIP si la empresa no tiene ninguno activo (número `1` por defecto)
- También se pueden crear, editar y eliminar desde el CRUD: `/erp/afip/punto-venta/list/`
- Se usan al emitir comprobantes

### URLs de Puntos de Venta
- Listado: `/erp/afip/punto-venta/list/`
- Crear: `/erp/afip/punto-venta/create/`
- Editar: `/erp/afip/punto-venta/update/{id}/`
- Eliminar: `/erp/afip/punto-venta/delete/{id}/`

## Funciones del Dashboard

### Botones Disponibles
- **Nueva Configuración**: Crear configuración AFIP para una empresa
- **Generar Certificado**: Generar certificados usando Clave Fiscal
- **Probar Conexión**: Verificar conexión con AFIP
- **Comprobantes**: Ver comprobantes electrónicos emitidos
- **Actualizar**: Recargar la lista de configuraciones

### Acciones por Configuración
- **Editar**: Modificar configuración existente
- **Eliminar**: Borrar configuración AFIP

## Requisitos Previos

1. **Access Token de AFIP SDK**:
   - Obtener en https://app.afipsdk.com
   - Configurar en `.env` como `AFIP_ACCESS_TOKEN` (global)
   - O configurar por empresa en el dashboard

2. **CUIT de la Empresa**:
   - Configurar en el modelo Company
   - Se usa automáticamente al crear configuración AFIP

3. **Clave Fiscal** (para generar certificados):
   - Usuario de Clave Fiscal
   - Contraseña de Clave Fiscal
   - Se usa solo para generar certificados, no se guarda

## Ejemplo de Flujo Completo

### Para Testing (Desarrollo)
1. Crear empresa con CUIT
2. Ir a dashboard AFIP
3. Crear configuración con ambiente "Desarrollo"
4. Generar certificado de desarrollo con Clave Fiscal
5. Probar conexión
6. Emitir comprobantes de prueba

### Para Producción
1. Crear empresa con CUIT real
2. Ir a dashboard AFIP
3. Crear configuración con ambiente "Producción"
4. Generar certificado de producción con Clave Fiscal real
5. **Autorizar Web Service WSFE** en https://app.afipsdk.com/automations/auth-web-service-prod con el CUIT real
6. Probar conexión
7. Emitir comprobantes con validez fiscal

## Errores Comunes

1. **"Ya existe una configuración AFIP para esta empresa"**:
   - Solo una configuración por empresa
   - Editar la existente en lugar de crear nueva

2. **"La empresa no tiene CUIT configurado"**:
   - Configurar CUIT en el modelo Company primero

3. **"Debe autorizar el uso del web service" (ns1:coe.notAuthorized)**:
   - El Web Service WSFE no está autorizado para el CUIT
   - Ir a https://afipsdk.com/docs/automations/auth-web-service-dev/?integration=python (desarrollo) o https://afipsdk.com/docs/automations/auth-web-service-prod/?integration=python (producción)
   - Seleccionar WSFE e ingresar el CUIT
   - Ejecutar la automatización de autorización

4. **"Faltan credenciales de Clave Fiscal"**:
   - Ingresar usuario y contraseña de Clave Fiscal
   - Verificar que sean correctos

5. **"La automatización no completó exitosamente"**:
   - Verificar access_token válido
   - Verificar credenciales de Clave Fiscal
   - Revisar logs de AFIP SDK

## Facturación según Método de Pago

El sistema emite comprobantes fiscales electrónicos AFIP **independientemente del método de pago** seleccionado en el POS. El método de pago se registra como información interna para:

- Control de caja
- Libro IVA
- Asientos contables
- Historial de transacciones

### Comportamiento por método de pago

- **Efectivo**: Emite factura normal inmediatamente.
- **Tarjeta**: Emite factura normal inmediatamente.
- **Transferencia**: Emite factura normal inmediatamente.
- **Mercado Pago**: Emite factura normal inmediatamente.
- **Cheque**: Emite factura normal inmediatamente.
- **Cuenta Corriente (Deuda)**: Emite factura normal inmediatamente. La deuda queda registrada como pago pendiente, pero el comprobante fiscal ya existe.
- **Pago Combinado**: Emite una sola factura por el total. Los medios de pago se registran en el campo `payment_details` (JSON).

### Identificación del cliente en AFIP

El sistema determina el tipo de documento según los datos del cliente:

- **CUIT**: DocTipo `80`, DocNro con el CUIT sin guiones (ej: `20333444555`)
- **DNI**: DocTipo `96`, DocNro con el DNI (ej: `12345678`)
- **Sin datos**: DocTipo `99`, DocNro `0` (Consumidor Final)

Esto permite una identificación más precisa en los comprobantes electrónicos.

## Seguridad

- **Access Token**: Se guarda en la base de datos (encriptar en producción)
- **Certificados**: Se guardan como texto en la base de datos
- **Clave Fiscal**: No se guarda, solo se usa para generar certificados
- **Permisos**: Requiere permiso `erp.view_afipconfig`

## Web Services Utilizados

El sistema se integra con los siguientes Web Services de ARCA/AFIP mediante la librería `afip.py`:

- **WSFE (Web Service de Facturación Electrónica)**:
  - `FEDummy`: Verifica estado del servidor
  - `FEAutorizar`: Crea comprobantes y obtiene CAE
  - `FECompUltimoAutorizado`: Obtiene último número de comprobante autorizado
  - `FEParamGetTiposCbte`: Obtiene tipos de comprobantes disponibles

- **PDF de comprobantes**: AFIP SDK permite generar el PDF fiscal del comprobante usando la API de afipsdk.com.

## Documentación Oficial de Referencia

- **Introducción a AFIP SDK**: https://afipsdk.com/docs/pdfs/introduction/
- **Integración Python**: https://afipsdk.com/docs/automations/integrations/python/
- **Automatización create-cert-dev**: https://afipsdk.com/docs/automations/create-cert-dev/?integration=python
- **API Reference**: https://afipsdk.com/docs/api-reference/introduction/
- **Automatizaciones**: https://afipsdk.com/docs/automations/introduction/

## URLs Relacionadas

- Dashboard: `/erp/afip/dashboard/`
- Lista empresas: `/erp/company/list/`
- Probar conexión: `/erp/afip/test/`
- Comprobantes: `/erp/afip/vouchers/`
- Crear config: `/erp/afip/create/`
- Editar config: `/erp/afip/update/{id}/`
- Eliminar config: `/erp/afip/delete/{id}/`
- Puntos de venta: `/erp/afip/punto-venta/list/`
