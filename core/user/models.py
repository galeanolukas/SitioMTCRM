from django.contrib.auth.models import AbstractUser
from django.db import models

from config.settings import MEDIA_URL, STATIC_URL


class User(AbstractUser):
    company = models.ForeignKey('erp.Company', null=True, blank=True, on_delete=models.SET_NULL, related_name='users')
    image = models.ImageField(upload_to='users/%Y/%m/%d', null=True, blank=True)
    image_remote_url = models.CharField(max_length=500, blank=True, null=True, verbose_name='URL Remota de Imagen', help_text='URL remota de la imagen para usar en servidores locales')
    phone = models.CharField(max_length=30, null=True, blank=True, verbose_name='Teléfono')

    def get_image(self):
        # Prioridad 1: imagen local si el archivo realmente existe
        if self.image:
            try:
                if self.image.storage.exists(self.image.name):
                    return '{}{}'.format(MEDIA_URL, self.image)
            except Exception:
                pass
            # Prioridad 2: URL remota registrada
            if self.image_remote_url:
                return self.image_remote_url
            # Construir URL remota a partir del path
            from django.conf import settings
            return f"{settings.REMOTE_SERVER_URL.rstrip('/')}/media/{self.image.name}"
        # Imagen remota ya registrada
        if self.image_remote_url:
            return self.image_remote_url
        return '{}{}'.format(STATIC_URL, 'img/empty.png')
