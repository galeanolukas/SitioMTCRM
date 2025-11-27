from django.contrib import admin
from django.apps import apps

# Obtener todos los modelos de la aplicación
app_models = apps.get_app_config('erp').get_models()

# Registrar todos los modelos en el admin
for model in app_models:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        # Si el modelo ya está registrado, lo omitimos
        pass

# Importar los archivos de admin personalizados para modelos específicos
from .admin.cash_register import *