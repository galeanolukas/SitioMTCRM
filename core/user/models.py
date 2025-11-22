from django.contrib.auth.models import AbstractUser
from django.db import models

from config.settings import MEDIA_URL, STATIC_URL
from core.erp.models import Company


class User(AbstractUser):
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL, related_name='users')
    image = models.ImageField(upload_to='users/%Y/%m/%d', null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True, verbose_name='Teléfono')

    def get_image(self):
        if self.image:
            return '{}{}'.format(MEDIA_URL, self.image)
        return '{}{}'.format(STATIC_URL, 'img/empty.png')
