import os
import requests
import urllib3
from django.conf import settings

# El certificado del servidor remoto es autogestionado, por lo que no se puede
# verificar la cadena SSL. Silenciamos la advertencia correspondiente.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def download_remote_image(relative_path, timeout=30):
    """
    Descarga un archivo de /media/ del servidor remoto y lo guarda en
    MEDIA_ROOT respetando el path relativo (p. ej. company/logo.png).
    Devuelve True si se descargó correctamente, False en caso contrario.
    """
    if not relative_path:
        return False

    url = f"{settings.REMOTE_SERVER_URL.rstrip('/')}/media/{relative_path}"
    full_path = os.path.join(settings.MEDIA_ROOT, relative_path)

    try:
        response = requests.get(url, verify=False, timeout=timeout)
        if response.status_code == 200:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception:
        pass

    return False
