# Listas de Precios

## Descripción

Sistema de listas de precios con descuento porcentual por defecto y posibilidad de override por producto (precio fijo, descuento específico o excepción).

## Funcionalidades

- **Listas de precios**: Crear listas con un descuento porcentual general aplicado a todos los productos
- **Overrides por producto**: Para cada lista, se puede configurar:
  - **Precio fijo**: Reemplaza el descuento general con un precio específico
  - **Descuento override**: Reemplaza el descuento general con un porcentaje específico
  - **Excepción**: El producto mantiene el precio base (sin descuento)
- **Asignación a clientes**: Cada cliente puede tener una lista de precios asignada
- **Aplicación automática en POS**: Al seleccionar un cliente con lista, los precios del carrito se ajustan automáticamente

## Modelos

### PriceList
- `name`: Nombre de la lista (ej: "Mayorista", "Distribuidor")
- `discount_percentage`: Descuento general (%) aplicado a todos los productos
- `is_active`: Estado de la lista
- `company`: Empresa a la que pertenece la lista

### PriceListProduct
- `price_list`: FK a PriceList
- `product`: FK a Product
- `fixed_price`: Precio fijo opcional (override)
- `discount_override`: Descuento específico opcional (%)
- `is_exception`: Marca el producto como excepción (no aplica descuento)

### Client
- `precio_lista`: FK a PriceList (null/blank)

## URLs

| URL | Acción |
|-----|--------|
| `/erp/price-list/` | Listar listas de precios |
| `/erp/price-list/add/` | Crear nueva lista |
| `/erp/price-list/edit/<pk>/` | Editar lista + gestionar overrides |
| `/erp/price-list/delete/<pk>` | Eliminar lista |
| `/erp/price-list/<pk>/manage/` | AJAX para agregar/quitar productos |

## Uso

### 1. Crear una lista de precios

1. Entrar a `/erp/price-list/add/`
2. Completar:
   - **Nombre**: ej: "Mayorista"
   - **Descuento general (%)**: ej: 10
   - **Lista activa**: marcar
3. Guardar

### 2. Configurar productos con precio especial

1. Entrar a `/erp/price-list/edit/<id>/`
2. En el panel "Productos con Precio Especial":
   - Buscar producto por nombre
   - Clic en el producto encontrado
   - En el modal, configurar:
     - **Precio fijo**: Si se setea, ignora el descuento general
     - **Descuento override %**: Descuento específico para este producto
     - **Excepción**: Marcar para que el producto mantenga el precio base
   - Clic en "Agregar"
3. Los overrides se muestran en la tabla con opción de quitar

### 3. Asignar lista a un cliente

1. Entrar a editar un cliente
2. En el campo "Lista de precios", seleccionar la lista deseada
3. Guardar

### 4. Vender en el POS

1. Abrir el POS (`/erp/pos/`)
2. Agregar productos al carrito
3. Seleccionar cliente
4. Si el cliente tiene una lista de precios activa:
   - Los precios del carrito se ajustan automáticamente
   - Aparece notificación: "Lista de precios aplicada: Mayorista (10%)"
5. Al limpiar el cliente, los precios se restauran a los originales

## Lógica de cálculo de precios

El método `PriceList.get_price_for_product(product)` determina el precio:

1. **Si hay un PriceListProduct con precio fijo**: usa ese precio
2. **Si hay un PriceListProduct marcado como excepción**: usa el precio base del producto
3. **Si hay un PriceListProduct con descuento override**: aplica ese descuento
4. **Si no hay override**: aplica el descuento general de la lista

## Ejemplos

### Ejemplo 1: Lista con descuento general
- Lista "Mayorista": 10% de descuento
- Producto A: precio base $100 → precio ajustado $90
- Producto B: precio base $50 → precio ajustado $45

### Ejemplo 2: Producto con precio fijo
- Lista "Mayorista": 10% de descuento
- Producto A: precio base $100, precio fijo $80 → precio ajustado $80 (ignora el 10%)

### Ejemplo 3: Producto como excepción
- Lista "Mayorista": 10% de descuento
- Producto A: marcado como excepción → precio ajustado $100 (precio base)

### Ejemplo 4: Producto con descuento override
- Lista "Mayorista": 10% de descuento
- Producto A: descuento override 5% → precio ajustado $95 (5% en lugar de 10%)

## Notas técnicas

- Los precios se calculan en el frontend (POS) y se guardan en `DetSale.price` al momento de la venta
- El método `get_price_for_product` usa aritmética Decimal para precisión
- Las relaciones `unique_together` aseguran que no haya duplicados en `PriceListProduct`
- Al eliminar una lista, los clientes con esa lista asignada quedan con `precio_lista = NULL`
