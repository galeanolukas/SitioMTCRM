# Manual de Configuración de Sincronización Local vs Nube

## Descripción General

Este sistema permite configurar diferentes destinos de sincronización para los POS locales, permitiendo que algunos puntos de venta se sincronicen únicamente con servidores locales en la red LAN, mientras otros se sincronicen con el servidor central en la nube.

## Conceptos Clave

### Modos de Sincronización

El sistema soporta tres modos de sincronización:

1. **Nube (Cloud)**: Sincronización con el servidor central en la nube (configuración por defecto)
2. **Servidor Local**: Sincronización con un servidor local en la red LAN
3. **Ambos**: Sincronización simultánea con nube y servidor local

### Grupo "Servidor Local"

Grupo especial de usuarios que forzará la sincronización local independientemente de la configuración de la empresa.

## Configuración Paso a Paso

### Paso 1: Aplicar Migraciones

Primero, asegúrese de aplicar las migraciones para agregar los nuevos campos al modelo Company:

```bash
cd /ruta/al/proyecto
source DJENV/bin/activate
python manage.py migrate
```

Esto agregará los campos:
- `sync_destination`: Destino de sincronización de la empresa
- `local_server_url`: URL del servidor local para sincronización

### Paso 2: Crear el Grupo "Servidor Local"

Ejecute el comando para crear el grupo especial:

```bash
python manage.py create_local_server_group
```

Este comando creará el grupo "Servidor Local" en el sistema.

### Paso 3: Configurar Empresas

#### Opción A: Desde el Panel de Administración

1. Inicie sesión como superusuario
2. Vaya a `/erp/company/list/`
3. Edite la empresa deseada
4. Configure los campos:
   - **Destino de Sincronización**: Seleccione entre:
     - "Nube (Servidor Central)" - para sincronización con la nube
     - "Servidor Local" - para sincronización con servidor local
     - "Ambos" - para sincronización con ambos destinos
   - **URL del Servidor Local**: Ingrese la URL del servidor local (ej: `http://192.168.1.100:8000`)
     - Este campo es obligatorio si selecciona "Servidor Local" o "Ambos"

#### Opción B: Desde la Consola de Django

```python
from core.erp.models import Company

# Configurar empresa para sincronización local
company = Company.objects.get(name="Nombre de la Empresa")
company.sync_destination = 'local'
company.local_server_url = 'http://192.168.1.100:8000'
company.save()

# Configurar empresa para sincronización con nube
company.sync_destination = 'cloud'
company.local_server_url = ''
company.save()

# Configurar empresa para sincronización con ambos
company.sync_destination = 'both'
company.local_server_url = 'http://192.168.1.100:8000'
company.save()
```

### Paso 4: Asignar Usuarios al Grupo "Servidor Local"

#### Opción A: Desde el Panel de Administración

1. Inicie sesión como superusuario
2. Vaya a `/user/users/`
3. Edite el usuario deseado
4. En la sección de grupos, seleccione "Servidor Local"
5. Guarde los cambios

#### Opción B: Desde la Consola de Django

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()
user = User.objects.get(username="nombre_usuario")
group = Group.objects.get(name="Servidor Local")
user.groups.add(group)
user.save()
```

### Paso 5: Configurar Servidor Local (Opcional)

Si va a utilizar sincronización local, necesita configurar un servidor Django en la red LAN:

1. **Instalar Django en el servidor local:**
   ```bash
   # Clonar el repositorio
   git clone https://github.com/galeanolukas/SitioMTCRM.git
   cd SitioMTCRM
   
   # Crear entorno virtual
   python3 -m venv DJENV
   source DJENV/bin/activate
   
   # Instalar dependencias
   pip install -r requirements.txt
   ```

2. **Configurar el servidor local:**
   - Ejecute `python activar_pos_local.py` para configurar como POS local
   - Configure la base de datos local (SQLite por defecto)

3. **Iniciar el servidor:**
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
   
   El servidor estará accesible en `http://IP_DEL_SERVIDOR:8000`

## Casos de Uso

### Caso 1: POS que solo se sincroniza con la nube

**Configuración:**
- Empresa: `sync_destination = 'cloud'`
- Usuario: No pertenece al grupo "Servidor Local"

**Resultado:**
- El POS solo intentará sincronizar con el servidor remoto en la nube
- Si no hay conexión a la nube, la sincronización fallará

### Caso 2: POS que solo se sincroniza con servidor local

**Configuración:**
- Empresa: `sync_destination = 'local'`, `local_server_url = 'http://192.168.1.100:8000'`
- Usuario: No pertenece al grupo "Servidor Local"

**Resultado:**
- El POS solo intentará sincronizar con el servidor local especificado
- Ideal para redes LAN sin conexión a internet

### Caso 3: Usuario forzado a sincronización local

**Configuración:**
- Empresa: Cualquier configuración
- Usuario: Pertenece al grupo "Servidor Local"

**Resultado:**
- Independientemente de la configuración de la empresa, este usuario solo sincronizará con servidores locales
- Útil para administradores de red local que no deben enviar datos a la nube

### Caso 4: Sincronización dual (nube + local)

**Configuración:**
- Empresa: `sync_destination = 'both'`, `local_server_url = 'http://192.168.1.100:8000'`
- Usuario: No pertenece al grupo "Servidor Local"

**Resultado:**
- El POS intentará sincronizar con ambos destinos
- Si uno falla, continuará con el otro
- Máxima redundancia de datos

## Verificación de Configuración

### Verificar el destino de sincronización actual

```python
from core.erp.sync_utils import _get_sync_destination

# Esto mostrará el destino actual basado en el usuario y empresa
print(_get_sync_destination())
```

### Verificar disponibilidad de conexiones

```python
from core.erp.sync_utils import _can_reach_remote_db, _can_reach_local_server

# Verificar conexión a la nube
print("Conexión a nube:", _can_reach_remote_db())

# Verificar conexión a servidor local
print("Conexión a local:", _can_reach_local_server())
```

### Ver logs de sincronización

Los logs de sincronización se guardan en:
- Archivo de log: `/ruta/al/proyecto/log/` (si está configurado)
- Base de datos: Tabla `SyncLog`

Para ver los logs recientes:

```python
from core.erp.models import SyncLog

logs = SyncLog.objects.all().order_by('-timestamp')[:10]
for log in logs:
    print(f"{log.timestamp} - {log.node_name} - {'OK' if log.success else 'ERROR'}")
    print(f"  {log.message}")
```

## Solución de Problemas

### Problema: "No hay conexión disponible para destino 'local'"

**Causa:** El servidor local no está accesible o la URL está mal configurada.

**Solución:**
1. Verifique que el servidor local esté ejecutándose: `python manage.py runserver 0.0.0.0:8000`
2. Verifique la URL configurada en la empresa
3. Pruebe la conexión desde el POS: `curl http://IP_DEL_SERVIDOR:8000`
4. Verifique que el firewall no esté bloqueando el puerto 8000

### Problema: "No hay conexión disponible para destino 'cloud'"

**Causa:** No hay conexión a la base de datos remota.

**Solución:**
1. Verifique la configuración de la conexión 'remote' en `settings.py`
2. Verifique que el servidor remoto esté accesible
3. Verifique las credenciales de la base de datos remota

### Problema: El usuario se sincroniza con la nube a pesar de estar en "Servidor Local"

**Causa:** El usuario no está correctamente asignado al grupo.

**Solución:**
1. Verifique que el usuario pertenezca al grupo "Servidor Local"
2. Verifique que no haya otros grupos que puedan interferir
3. Revise los logs para ver qué destino se está usando

### Problema: La sincronización no se ejecuta automáticamente

**Causa:** El intervalo de sincronización puede estar desactivado o configurado incorrectamente.

**Solución:**
1. Verifique `POS_SYNC_INTERVAL_SECONDS` en `settings.py` (default: 300 segundos = 5 minutos)
2. Verifique que la sincronización no esté desactivada globalmente
3. Revise los logs de la aplicación

## Consideraciones de Seguridad

1. **Servidores Locales:** Asegúrese de que los servidores locales estén en una red segura y no sean accesibles desde internet
2. **Credenciales:** No exponga credenciales de base de datos en URLs públicas
3. **Firewall:** Configure firewalls para permitir solo conexiones desde IPs confiables
4. **HTTPS:** Si es posible, use HTTPS para conexiones a servidores locales

## Mantenimiento

### Actualizar configuración de empresas

Cuando cambie la configuración de una empresa, los cambios se aplican inmediatamente en la próxima sincronización.

### Monitoreo

Monitoree regularmente:
- Logs de sincronización
- Disponibilidad de servidores locales
- Espacio en disco de las bases de datos locales

### Backups

Mantenga backups regulares de:
- Base de datos local
- Base de datos remota
- Archivos de configuración

## Soporte

Para problemas o preguntas:
1. Revise los logs de la aplicación
2. Verifique la configuración en `settings.py`
3. Consulte este manual
4. Revise la documentación general del proyecto
