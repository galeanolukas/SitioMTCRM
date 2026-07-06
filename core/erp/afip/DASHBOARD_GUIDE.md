# Guía del Dashboard AFIP

## Ubicación
`http://localhost:8000/erp/afip/dashboard/`

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
- Se crean independientemente de la configuración AFIP
- Se usan al emitir comprobantes

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
5. Probar conexión
6. Emitir comprobantes con validez fiscal

## Errores Comunes

1. **"Ya existe una configuración AFIP para esta empresa"**:
   - Solo una configuración por empresa
   - Editar la existente en lugar de crear nueva

2. **"La empresa no tiene CUIT configurado"**:
   - Configurar CUIT en el modelo Company primero

3. **"Faltan credenciales de Clave Fiscal"**:
   - Ingresar usuario y contraseña de Clave Fiscal
   - Verificar que sean correctos

4. **"La automatización no completó exitosamente"**:
   - Verificar access_token válido
   - Verificar credenciales de Clave Fiscal
   - Revisar logs de AFIP SDK

## Seguridad

- **Access Token**: Se guarda en la base de datos (encriptar en producción)
- **Certificados**: Se guardan como texto en la base de datos
- **Clave Fiscal**: No se guarda, solo se usa para generar certificados
- **Permisos**: Requiere permiso `erp.view_afipconfig`

## URLs Relacionadas

- Dashboard: `/erp/afip/dashboard/`
- Lista empresas: `/erp/company/list/`
- Probar conexión: `/erp/afip/test/`
- Comprobantes: `/erp/afip/vouchers/`
- Crear config: `/erp/afip/create/`
- Editar config: `/erp/afip/update/{id}/`
- Eliminar config: `/erp/afip/delete/{id}/`
