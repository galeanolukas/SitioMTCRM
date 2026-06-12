# Propuesta de Implementación: Listas de Precios

## Estado Actual
- El modelo `Client` tiene un campo `descuento_habitual` (%) que aplica un descuento general a todos los productos
- Es un descuento simple y uniforme para todo el catálogo

## Objetivo
Implementar un sistema de listas de precios que permita:
- Descuentos por producto específico
- Descuentos globales por lista
- Asignación de listas a clientes específicos
- Vigencia temporal de las listas
- Flexibilidad en la aplicación de descuentos

## Estructura de Modelos Propuesta

### 1. Modelo `ListaPrecios` (PriceList)

```python
class ListaPrecios(models.Model):
    TIPO_DESCUENTO_CHOICES = [
        ('porcentaje', 'Porcentaje'),
        ('fijo', 'Precio Fijo'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name='Empresa')
    nombre = models.CharField(max_length=150, verbose_name='Nombre')
    descripcion = models.TextField(null=True, blank=True, verbose_name='Descripción')
    tipo_descuento = models.CharField(
        max_length=10,
        choices=TIPO_DESCUENTO_CHOICES,
        default='porcentaje',
        verbose_name='Tipo de Descuento'
    )
    descuento_global = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name='Descuento Global (%)',
        help_text='Descuento aplicado a todos los productos sin precio específico'
    )
    is_active = models.BooleanField(default=True, verbose_name='Activa')
    fecha_desde = models.DateField(null=True, blank=True, verbose_name='Válido desde')
    fecha_hasta = models.DateField(null=True, blank=True, verbose_name='Válido hasta')
    synced_to_server = models.BooleanField(default=False, verbose_name='Sincronizado con servidor')
    
    def __str__(self):
        return f"{self.nombre} ({self.company.name if self.company else 'Global'})"
    
    def is_vigente(self):
        """Verificar si la lista está vigente según las fechas"""
        from django.utils import timezone
        hoy = timezone.now().date()
        if self.fecha_desde and hoy < self.fecha_desde:
            return False
        if self.fecha_hasta and hoy > self.fecha_hasta:
            return False
        return True
    
    class Meta:
        verbose_name = 'Lista de Precios'
        verbose_name_plural = 'Listas de Precios'
        ordering = ['company', 'nombre']
```

### 2. Modelo `DetalleListaPrecios` (PriceListDetail)

```python
class DetalleListaPrecios(models.Model):
    TIPO_PRECIO_CHOICES = [
        ('porcentaje', 'Porcentaje de Descuento'),
        ('fijo', 'Precio Fijo'),
    ]
    
    lista = models.ForeignKey(ListaPrecios, on_delete=models.CASCADE, related_name='detalles', verbose_name='Lista')
    producto = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Producto')
    tipo_precio = models.CharField(
        max_length=10,
        choices=TIPO_PRECIO_CHOICES,
        default='porcentaje',
        verbose_name='Tipo de Precio'
    )
    valor = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='Valor',
        help_text='Porcentaje de descuento o precio fijo según el tipo'
    )
    precio_final = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name='Precio Final Calculado',
        help_text='Precio final aplicando el descuento al precio original'
    )
    
    def save(self, *args, **kwargs):
        """Calcular automáticamente el precio final"""
        if self.tipo_precio == 'porcentaje':
            # Aplicar descuento porcentual al precio original del producto
            descuento = self.producto.pvp_final * (self.valor / 100)
            self.precio_final = self.producto.pvp_final - descuento
        else:
            # Usar precio fijo
            self.precio_final = self.valor
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.producto.name} - {self.lista.nombre}"
    
    class Meta:
        verbose_name = 'Detalle de Lista de Precios'
        verbose_name_plural = 'Detalles de Listas de Precios'
        ordering = ['lista', 'producto']
        unique_together = [['lista', 'producto']]  # Un producto solo puede aparecer una vez por lista
```

### 3. Modificación del modelo `Client`

```python
# Agregar campo al modelo Client
lista_precios = models.ForeignKey(
    ListaPrecios, 
    on_delete=models.SET_NULL, 
    null=True, 
    blank=True,
    verbose_name='Lista de Precios',
    related_name='clientes'
)
```

## Lógica de Aplicación en el POS

### Prioridad de Precios
1. **Precio específico en lista:** Si el producto tiene un precio definido en la lista del cliente
2. **Descuento global de lista:** Si el producto no tiene precio específico pero la lista tiene descuento global
3. **Descuento habitual del cliente:** Si no hay lista de precios asignada
4. **Precio normal del producto:** Si no aplica ningún descuento

### Algoritmo de Cálculo

```python
def obtener_precio_para_cliente(producto, cliente):
    """
    Calcular el precio final de un producto para un cliente específico
    considerando listas de precios y descuentos
    """
    # 1. Verificar si el cliente tiene una lista de precios asignada y vigente
    if cliente and cliente.lista_precios and cliente.lista_precios.is_vigente():
        lista = cliente.lista_precios
        
        # 2. Buscar precio específico del producto en la lista
        try:
            detalle = DetalleListaPrecios.objects.get(lista=lista, producto=producto)
            return detalle.precio_final
        except DetalleListaPrecios.DoesNotExist:
            # 3. Si no tiene precio específico, aplicar descuento global de la lista
            if lista.descuento_global:
                descuento = producto.pvp_final * (lista.descuento_global / 100)
                return producto.pvp_final - descuento
    
    # 4. Si no hay lista o no es vigente, aplicar descuento habitual del cliente
    if cliente and cliente.descuento_habitual:
        descuento = producto.pvp_final * (cliente.descuento_habitual / 100)
        return producto.pvp_final - descuento
    
    # 5. Precio normal del producto
    return producto.pvp_final
```

## Interfaz Administrativa

### 1. CRUD para Listas de Precios
- **Vista de lista:** `/erp/lista_precios/list/`
  - Mostrar todas las listas de precios
  - Indicar estado (activa/inactiva, vigente/no vigente)
  - Mostrar cantidad de productos en cada lista
  - Mostrar cantidad de clientes asignados

- **Vista de creación:** `/erp/lista_precios/add/`
  - Formulario con campos: nombre, descripción, tipo de descuento, descuento global, fechas de vigencia
  - Selección de empresa (para multi-tenant)

- **Vista de edición:** `/erp/lista_precios/edit/<id>/`
  - Mismo formulario que creación
  - Opción de activar/desactivar

- **Vista de eliminación:** `/erp/lista_precios/delete/<id>/`
  - Confirmación antes de eliminar
  - Verificar que no esté asignada a clientes activos

### 2. Gestión de Detalles de Lista
- **Vista para agregar productos:** `/erp/lista_precios/<id>/agregar_productos/`
  - Buscador de productos
  - Selección múltiple
  - Configuración de tipo de precio (porcentaje o fijo)
  - Configuración de valor
  - Vista previa de precio final calculado

- **Vista de lista de productos:** `/erp/lista_precios/<id>/productos/`
  - Tabla con productos asignados
  - Opción de editar precio individual
  - Opción de eliminar producto de la lista
  - Importación masiva desde CSV/Excel

### 3. Asignación a Clientes
- **Campo en formulario de cliente:** Selector de lista de precios
- **Vista de asignación masiva:** `/erp/lista_precios/<id>/asignar_clientes/`
  - Buscador de clientes
  - Selección múltiple
  - Asignación en lote

### 4. Vista Previa de Precios
- **Vista de simulación:** `/erp/lista_precios/<id>/simular/`
  - Seleccionar cliente
  - Mostrar catálogo completo con precios aplicados
  - Comparación: precio original vs precio con descuento
  - Exportar a PDF/Excel

## Beneficios de esta Implementación

1. **Flexibilidad:** Descuentos por producto específico
2. **Temporalidad:** Listas con fechas de vigencia para promociones
3. **Segmentación:** Diferentes listas para diferentes tipos de clientes (mayoristas, VIP, etc.)
4. **Prioridad clara:** Sistema de precedencia en la aplicación de precios
5. **Control:** Activar/desactivar listas sin eliminarlas
6. **Auditoría:** Historial de cambios en precios
7. **Escalabilidad:** Fácil agregar nuevos tipos de descuentos
8. **Multi-tenant:** Soporte para múltiples empresas

## Consideraciones Técnicas

### Migraciones
- Crear modelo `ListaPrecios`
- Crear modelo `DetalleListaPrecios`
- Agregar campo `lista_precios` a `Client`
- Crear índices para optimizar búsquedas

### Rendimiento
- Usar `select_related` y `prefetch_related` en consultas
- Cachear precios calculados si es necesario
- Considerar uso de signals para actualizar precios cuando cambian

### Sincronización
- Sincronizar listas de precios con servidor remoto
- Incluir en el sistema de sync existente
- Marcar con `synced_to_server` y `synced_at`

### Permisos
- `view_listaprecios`: Ver listas de precios
- `add_listaprecios`: Crear listas de precios
- `change_listaprecios`: Editar listas de precios
- `delete_listaprecios`: Eliminar listas de precios
- `manage_listaprecios`: Gestión completa (opcional)

## Pasos de Implementación

1. **Fase 1: Modelos y Migraciones**
   - Crear modelos `ListaPrecios` y `DetalleListaPrecios`
   - Agregar campo a `Client`
   - Crear y aplicar migraciones localmente
   - Aplicar migraciones en servidor remoto

2. **Fase 2: Formularios**
   - Crear `ListaPreciosForm`
   - Crear `DetalleListaPreciosForm`
   - Actualizar `ClientForm` para incluir selector de lista

3. **Fase 3: Vistas CRUD**
   - ListView, CreateView, UpdateView, DeleteView para listas
   - Vista para agregar productos a lista
   - Vista para asignar clientes a lista

4. **Fase 4: Templates**
   - Template de lista de listas
   - Template de formulario de lista
   - Template de gestión de productos en lista
   - Template de asignación de clientes

5. **Fase 5: Integración con POS**
   - Modificar lógica de cálculo de precios en POS
   - Aplicar algoritmo de prioridad de precios
   - Mostrar precio original y precio con descuento

6. **Fase 6: Sincronización**
   - Integrar con sistema de sync existente
   - Sincronizar listas y detalles con servidor remoto

7. **Fase 7: Pruebas**
   - Probar creación de listas
   - Probar asignación de productos
   - Probar asignación a clientes
   - Probar cálculo de precios en POS
   - Probar vigencia temporal

## Archivos a Crear/Modificar

### Nuevos archivos:
- `core/erp/models.py` - Agregar modelos `ListaPrecios` y `DetalleListaPrecios`
- `core/erp/forms.py` - Agregar formularios para listas
- `core/erp/views/listaprecios/views.py` - Vistas CRUD
- `core/erp/urls.py` - URLs para listas de precios
- `core/erp/templates/listaprecios/list.html` - Template de lista
- `core/erp/templates/listaprecios/form.html` - Template de formulario
- `core/erp/templates/listaprecios/productos.html` - Template de productos
- `templates/vtc/sidebar.html` - Agregar ítem de menú

### Archivos a modificar:
- `core/erp/models.py` - Agregar campo `lista_precios` a `Client`
- `core/erp/forms.py` - Actualizar `ClientForm`
- `core/erp/views/sale/views.py` - Modificar cálculo de precios en POS
- `sync_smart.py` - Agregar sincronización de listas

## Notas Adicionales

- Mantener compatibilidad con el sistema actual de `descuento_habitual`
- El campo `descuento_habitual` seguirá funcionando como fallback
- Considerar agregar historial de precios para auditoría
- Posible extensión: listas de precios por categoría de productos
- Posible extensión: reglas de descuento dinámicas (compra X, obtén Y% de descuento)
