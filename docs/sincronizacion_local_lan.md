# Sincronización Local LAN entre Múltiples POS y Servidor Central

## Arquitectura Propuesta

### Topología de Red
```
                    [Servidor Central]
                    - Django App
                    - PostgreSQL DB
                    - API REST
                    - WebSockets (opcional)
                           |
                           | (Red Local LAN)
                           |
        +------------------+------------------+
        |                  |                  |
    [POS 1]            [POS 2]            [POS N]
    - Vendedor A       - Vendedor B       - Vendedor C
    - Terminal 1       - Terminal 2       - Terminal N
    - SQLite/Cache     - SQLite/Cache     - SQLite/Cache
```

### Componentes

#### 1. Servidor Central (Master)
- **Base de datos principal:** PostgreSQL con todos los datos
- **API REST:** Endpoints para sincronización de datos
- **Gestión de conflictos:** Lógica para resolver colisiones
- **Autenticación:** Tokens JWT o API keys para cada POS
- **Logging:** Registro de todas las operaciones de sync

#### 2. Terminales POS (Slaves)
- **Base de datos local:** SQLite para operación offline
- **Caché de productos:** Datos necesarios para venta rápida
- **Cliente de sincronización:** Servicio que periódicamente sync con servidor
- **Modo offline:** Capacidad de operar sin conexión
- **Cola de cambios:** Pendientes de sincronizar

## Estrategias de Sincronización

### Opción 1: Sincronización por Polling (Recomendada)

**Cómo funciona:**
- Cada POS hace peticiones periódicas al servidor (ej: cada 30 segundos)
- El servidor responde con cambios desde la última sync
- El POS envía sus cambios pendientes al servidor

**Ventajas:**
- Simple de implementar
- Funciona con firewalls restrictivos
- Fácil de debuggear
- Bajo consumo de recursos

**Desventajas:**
- Latencia entre cambios y sync
- Puede generar tráfico de red innecesario

**Implementación:**

```python
# En el POS (Cliente)
class SyncClient:
    def __init__(self, server_url, api_key, pos_id):
        self.server_url = server_url
        self.api_key = api_key
        self.pos_id = pos_id
        self.last_sync = self.get_last_sync_timestamp()
    
    def sync(self):
        """Sincronizar con servidor central"""
        try:
            # 1. Enviar cambios locales pendientes
            local_changes = self.get_local_changes()
            if local_changes:
                self.send_changes_to_server(local_changes)
            
            # 2. Recibir cambios del servidor
            server_changes = self.fetch_server_changes()
            if server_changes:
                self.apply_server_changes(server_changes)
            
            # 3. Actualizar timestamp de última sync
            self.update_last_sync()
            
            return True, "Sincronización exitosa"
        except Exception as e:
            return False, f"Error en sincronización: {str(e)}"
    
    def get_local_changes(self):
        """Obtener cambios locales desde última sync"""
        from core.erp.models import Sale, Product, Client
        
        changes = {
            'sales': [],
            'products': [],
            'clients': []
        }
        
        # Ventas creadas localmente
        changes['sales'] = Sale.objects.filter(
            synced_to_server=False,
            source='local_pos'
        ).values()
        
        # Productos modificados localmente
        changes['products'] = Product.objects.filter(
            stock_modified_locally__gt=self.last_sync
        ).values()
        
        # Clientes creados localmente
        changes['clients'] = Client.objects.filter(
            synced_to_server=False
        ).values()
        
        return changes
    
    def send_changes_to_server(self, changes):
        """Enviar cambios al servidor"""
        import requests
        
        response = requests.post(
            f"{self.server_url}/api/sync/receive/",
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'pos_id': self.pos_id,
                'changes': changes
            },
            timeout=30
        )
        
        if response.status_code == 200:
            # Marcar cambios como sincronizados
            self.mark_changes_as_synced(changes)
        else:
            raise Exception(f"Error del servidor: {response.status_code}")
    
    def fetch_server_changes(self):
        """Obtener cambios del servidor"""
        import requests
        
        response = requests.get(
            f"{self.server_url}/api/sync/changes/",
            headers={
                'Authorization': f'Bearer {self.api_key}'
            },
            params={
                'since': self.last_sync.isoformat(),
                'pos_id': self.pos_id
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error del servidor: {response.status_code}")
    
    def apply_server_changes(self, changes):
        """Aplicar cambios recibidos del servidor"""
        from core.erp.models import Product, Client
        
        # Actualizar productos
        for prod_data in changes.get('products', []):
            Product.objects.filter(id=prod_data['id']).update(
                stock=prod_data['stock'],
                pvp_final=prod_data['pvp_final'],
                synced_from_server=True,
                last_server_sync=timezone.now()
            )
        
        # Actualizar clientes
        for client_data in changes.get('clients', []):
            Client.objects.update_or_create(
                id=client_data['id'],
                defaults=client_data
            )
```

```python
# En el Servidor (API)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def receive_sync_changes(request):
    """Recibir cambios de un POS"""
    pos_id = request.data.get('pos_id')
    changes = request.data.get('changes')
    
    # Procesar ventas
    for sale_data in changes.get('sales', []):
        # Crear o actualizar venta en servidor central
        Sale.objects.update_or_create(
            local_uuid=sale_data['local_uuid'],
            defaults=sale_data
        )
    
    # Procesar cambios de stock
    for prod_data in changes.get('products', []):
        Product.objects.filter(id=prod_data['id']).update(
            stock=prod_data['stock'],
            stock_modified_locally=prod_data['stock_modified_locally']
        )
    
    return Response({'status': 'success'})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sync_changes(request):
    """Enviar cambios a un POS"""
    since = request.GET.get('since')
    pos_id = request.GET.get('pos_id')
    
    since_dt = datetime.fromisoformat(since)
    
    changes = {
        'products': [],
        'clients': [],
        'sales': []
    }
    
    # Productos modificados desde 'since'
    changes['products'] = list(Product.objects.filter(
        last_server_sync__gt=since_dt
    ).exclude(
        synced_from_server_by=pos_id  # No enviar cambios que vino de este POS
    ).values())
    
    # Clientes nuevos o modificados
    changes['clients'] = list(Client.objects.filter(
        date_updated__gt=since_dt
    ).values())
    
    return Response(changes)
```

### Opción 2: WebSockets (Tiempo Real)

**Cómo funciona:**
- Conexión persistente entre POS y servidor
- El servidor push cambios inmediatamente cuando ocurren
- Bidireccional: POS puede enviar cambios en tiempo real

**Ventajas:**
- Sincronización en tiempo real
- Menos latencia
- Push de cambios inmediatos

**Desventajas:**
- Más complejo de implementar
- Requiere conexión estable
- Mayor consumo de recursos

**Implementación:**

```python
# Usando Django Channels
# consumers.py
class SyncConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.pos_id = self.scope['url_route']['kwargs']['pos_id']
        await self.accept()
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        # Procesar cambios del POS
        await self.process_changes(data)
    
    async def sync_changes(self, event):
        # Enviar cambios al POS
        await self.send(text_data=json.dumps(event['changes']))
```

### Opción 3: Base de Datos Distribuida (PostgreSQL Logical Replication)

**Cómo funciona:**
- PostgreSQL replica datos entre servidor y POS
- Replicación lógica de tablas específicas
- Conflictos resueltos por reglas

**Ventajas:**
- Transparencia para la aplicación
- Alta consistencia
- Performance nativa de DB

**Desventajas:**
- Complejo de configurar
- Requiere PostgreSQL en todos los nodos
- Difícil de resolver conflictos de negocio

## Resolución de Conflictos

### Tipos de Conflictos

1. **Conflictos de stock:**
   - POS A vende 5 unidades (stock: 10 → 5)
   - POS B vende 8 unidades (stock: 10 → 2)
   - **Resolución:** FIFO (primero en llegar, primero en servir) o último gana

2. **Conflictos de datos maestros:**
   - POS A modifica precio de producto
   - POS B modifica mismo producto
   - **Resolución:** Última modificación gana, o merge manual

3. **Conflictos de ventas:**
   - Mismo UUID de venta en múltiples POS
   - **Resolución:** Usar UUID único por POS + timestamp

### Estrategia de Resolución

```python
class ConflictResolver:
    @staticmethod
    def resolve_stock_conflict(local_stock, server_stock, local_changes, server_changes):
        """
        Resolver conflicto de stock
        Estrategia: Calcular stock basado en todas las ventas
        """
        # Obtener todas las ventas de ambos sistemas
        all_sales = local_changes['sales'] + server_changes['sales']
        
        # Calcular stock total vendido
        total_sold = sum(sale['quantity'] for sale in all_sales)
        
        # Stock final = stock inicial - total vendido
        final_stock = max(0, local_stock - total_sold)
        
        return final_stock
    
    @staticmethod
    def resolve_price_conflict(local_price, server_price, last_modified_local, last_modified_server):
        """
        Resolver conflicto de precio
        Estrategia: Última modificación gana
        """
        if last_modified_local > last_modified_server:
            return local_price
        else:
            return server_price
```

## Configuración de Red

### 1. Direcciones IP Estáticas
- Servidor: IP fija (ej: 192.168.1.100)
- POS: IPs en el mismo rango (ej: 192.168.1.101-110)

### 2. Configuración Django
```python
# settings.py del POS
SYNC_CONFIG = {
    'SERVER_URL': 'http://192.168.1.100:8000',
    'API_KEY': 'pos-001-secret-key',
    'POS_ID': 'POS-001',
    'SYNC_INTERVAL': 30,  # segundos
    'OFFLINE_MODE': True,  # Permitir operación offline
}

# settings.py del Servidor
ALLOWED_HOSTS = ['192.168.1.100', 'localhost']
CORS_ALLOWED_ORIGINS = [
    'http://192.168.1.101:8000',
    'http://192.168.1.102:8000',
    # ... más POS
]
```

### 3. Firewall
- Puerto 8000 (Django) abierto en servidor
- Puerto 5432 (PostgreSQL) solo para localhost (no exponer)

## Implementación en Proyecto Actual

### 1. Modelo POS (Registrar terminales)
```python
class POS(models.Model):
    """Terminal POS en la red local"""
    ESTADO_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('maintenance', 'Mantenimiento'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    ubicacion = models.CharField(max_length=200, verbose_name='Ubicación')
    ip_address = models.CharField(max_length=15, verbose_name='Dirección IP')
    api_key = models.CharField(max_length=64, unique=True, verbose_name='API Key')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='online')
    last_sync = models.DateTimeField(null=True, blank=True, verbose_name='Última Sync')
    last_heartbeat = models.DateTimeField(auto_now=True, verbose_name='Último Heartbeat')
    
    def is_online(self):
        """Verificar si el POS está online (heartbeat < 2 minutos)"""
        from django.utils import timezone
        if not self.last_heartbeat:
            return False
        return (timezone.now() - self.last_heartbeat).total_seconds() < 120
```

### 2. Endpoint de Heartbeat
```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def heartbeat(request):
    """Heartbeat para verificar estado de POS"""
    pos_id = request.data.get('pos_id')
    pos = POS.objects.filter(api_key=request.auth.key).first()
    
    if pos:
        pos.last_heartbeat = timezone.now()
        pos.estado = 'online'
        pos.save()
        return Response({'status': 'ok'})
    
    return Response({'status': 'error'}, status=404)
```

### 3. Servicio de Sync en POS
```python
# management command para sync
class Command(BaseCommand):
    help = 'Sincronizar con servidor central'
    
    def handle(self, *args, **options):
        from core.sync.sync_client import SyncClient
        
        client = SyncClient(
            server_url=settings.SYNC_CONFIG['SERVER_URL'],
            api_key=settings.SYNC_CONFIG['API_KEY'],
            pos_id=settings.SYNC_CONFIG['POS_ID']
        )
        
        success, message = client.sync()
        
        if success:
            self.stdout.write(self.style.SUCCESS(f'✓ {message}'))
        else:
            self.stdout.write(self.style.ERROR(f'✗ {message}'))
```

### 4. Cron Job para Sync Automático
```bash
# crontab del POS
*/1 * * * * cd /path/to/pos && source DJENV/bin/activate && python manage.py sync_with_server
```

## Monitoreo y Logging

### 1. Dashboard de Sync
- Vista de todos los POS y su estado
- Última sync de cada POS
- Cambios pendientes
- Errores de sincronización

### 2. Logs Detallados
```python
logger.info(f"Sync iniciado - POS: {pos_id}")
logger.info(f"Enviando {len(local_changes['sales'])} ventas")
logger.info(f"Recibiendo {len(server_changes['products'])} productos")
logger.info(f"Sync completado - Duración: {duration}s")
```

### 3. Alertas
- POS offline por más de X minutos
- Conflictos no resueltos
- Errores recurrentes de sync

## Consideraciones de Seguridad

1. **Autenticación:**
   - API keys únicas por POS
   - Rotación periódica de keys
   - HTTPS en producción

2. **Autorización:**
   - Cada POS solo accede a sus datos
   - Validación de empresa (multi-tenant)

3. **Encriptación:**
   - Datos sensibles encriptados en tránsito
   - Considerar encriptación en reposo

## Rendimiento y Optimización

1. **Batching:**
   - Enviar cambios en lotes (no uno por uno)
   - Límite de tamaño de payload (ej: 1MB)

2. **Compresión:**
   - Comprimir payloads JSON con gzip
   - Reducir ancho de banda

3. **Diferencial Sync:**
   - Solo enviar campos modificados
   - Usar hashes para detectar cambios

4. **Caché:**
   - Caché de productos en POS
   - Invalidar solo cuando hay cambios

## Plan de Implementación

### Fase 1: Infraestructura
- Configurar servidor central con IP fija
- Configurar red LAN
- Crear modelo POS
- Generar API keys

### Fase 2: API de Sync
- Endpoint receive_sync_changes
- Endpoint get_sync_changes
- Endpoint heartbeat
- Sistema de autenticación

### Fase 3: Cliente de Sync
- Implementar SyncClient
- Management command para sync
- Configuración de settings
- Sistema de cola de cambios

### Fase 4: Resolución de Conflictos
- Implementar ConflictResolver
- Lógica de stock
- Lógica de precios
- Logging de conflictos

### Fase 5: Monitoreo
- Dashboard de estado de POS
- Logs detallados
- Sistema de alertas
- Métricas de sync

### Fase 6: Testing
- Pruebas de sync con un POS
- Pruebas con múltiples POS
- Pruebas de conflictos
- Pruebas de modo offline

### Fase 7: Despliegue
- Desplegar en primer POS
- Monitorear por período de prueba
- Desplegar en POS restantes
- Documentación para operadores

## Archivos a Crear/Modificar

### Nuevos archivos:
- `core/erp/models.py` - Agregar modelo POS
- `core/sync/sync_client.py` - Cliente de sincronización
- `core/erp/api/sync_views.py` - Endpoints de sync
- `core/erp/management/commands/sync_with_server.py` - Command de sync
- `core/erp/templates/sync/dashboard.html` - Dashboard de monitoreo
- `core/erp/views/sync/views.py` - Vistas de dashboard

### Archivos a modificar:
- `config/settings.py` - Configuración de sync
- `core/erp/urls.py` - URLs de sync
- `templates/vtc/sidebar.html` - Ítem de menú para dashboard

## Ventajas de esta Implementación

1. **Operación Offline:** POS pueden funcionar sin conexión
2. **Consistencia Eventual:** Datos eventualmente consistentes
3. **Escalabilidad:** Fácil agregar más POS
4. **Resiliencia:** Si un POS falla, otros siguen operando
5. **Performance:** Operaciones locales rápidas (SQLite)
6. **Flexibilidad:** Configurable intervalo de sync
7. **Auditoría:** Registro completo de cambios
8. **Monitoreo:** Visibilidad del estado de toda la red

## Limitaciones y Consideraciones

1. **Latencia:** No es tiempo real (según intervalo de sync)
2. **Conflictos:** Requiere estrategia clara de resolución
3. **Red:** Depende de estabilidad de red LAN
4. **Mantenimiento:** Requiere monitoreo continuo
5. **Capacidad:** Servidor central debe escalar con número de POS
