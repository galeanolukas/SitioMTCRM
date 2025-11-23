# SitioMTCRM – POS + CRM con sincronización remota

SitioMTCRM es una aplicación web basada en Django enfocada en:

- Gestión de inventario, ventas y facturación.
- Administración de empresas, clientes, proveedores y gastos.
- Punto de Venta (POS) local para sucursales / nodos.
- Sincronización periódica de datos con un servidor central PostgreSQL.
- Módulo de actualizaciones integrado con GitHub.

Está pensada para funcionar en dos roles:

- **Servidor central (VPS / producción)** con PostgreSQL.
- **POS locales (Windows)** que usan SQLite local y se sincronizan con la base remota.

---

## Características principales

- Panel de administración / Dashboard con métricas básicas.
- Gestión de:
  - Empresas
  - Productos (con códigos QR)
  - Clientes y proveedores
  - Ventas, facturas y gastos
- POS web (API de ventas) para uso diario en el local.
- Sincronización automática y manual de:
  - Empresas, categorías, productos, ventas, clientes, proveedores, gastos y usuarios.
- Configuración del intervalo de sync automática (por POS) desde la interfaz.
- Módulo de **Actualizaciones**:
  - Detecta la última versión publicada en GitHub.
  - Informa si hay *“Actualización disponible”*.
  - Documenta el flujo de actualización del código en los POS.
- Integración opcional con Mercado Pago.

---

## Requisitos

- Python 3.10+ (recomendado)
- Git (para clonar/actualizar desde GitHub, especialmente en POS)
- PostgreSQL (en el servidor central / producción)
- Navegador web moderno (Chrome, Edge, etc.)

---

## Instalación en Windows (POS local)

Estas instrucciones son para instalar un **POS local** en Windows, usando el instalador que trae el proyecto.

### 1. Descargar el proyecto

En el POS (PC con Windows):

1. Instalar **Git for Windows** (si no está):
   - https://git-scm.com/download/win
2. Clonar el repositorio:

   ```bash
   git clone [https://github.com/galeanolukas/SitioMTCRM.git](https://github.com/galeanolukas/SitioMTCRM.git)
