"""Configuración principal de Django.

Se apoyan las variables de entorno (incluyendo un archivo .env local) para
parametrizar claves sensibles como credenciales de base de datos.
"""

from pathlib import Path
import config.db as db
import os
import socket  # necesario para gethostbyname
import subprocess

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Obtener versión automáticamente desde Git
def get_version():
    """Obtener versión desde git tags o commit hash"""
    try:
        # Intentar obtener el último tag
        result = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], 
                              capture_output=True, text=True, cwd=BASE_DIR)
        if result.returncode == 0:
            return result.stdout.strip().lstrip('v')  # Remover 'v' prefix si existe
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    
    try:
        # Si no hay tags, usar el commit hash
        result = subprocess.run(['git', 'log', '-1', '--format="%h"'], 
                              capture_output=True, text=True, cwd=BASE_DIR)
        if result.returncode == 0:
            return f"dev-{result.stdout.strip()}"
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    
    # Si todo falla, versión por defecto
    return "1.0.0"

VERSION = get_version()

# Cargar variables desde .env si python-dotenv está disponible
if load_dotenv is not None:
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        load_dotenv(env_path)

# Ambiente actual: 'production' o 'development'
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

# Versión de la aplicación (usada para mostrar en UI y para futuros módulos de actualización)
APP_VERSION = VERSION

# Intervalo de sincronización automática del POS (en segundos).
# 300 segundos = 5 minutos.
POS_SYNC_INTERVAL_SECONDS = int(os.getenv('POS_SYNC_INTERVAL_SECONDS', '300'))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-f*fp460!*um-87*_#!+1sko-1#-$j)(^-c3hm=j#s26_f7i!bp'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    #app
    'core.erp',
    'core.homepage',
    'core.login',
    'core.user'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'crum.CurrentRequestUserMiddleware'  # Temporalmente deshabilitado para pruebas
    'core.erp.middleware.ActivityLogMiddleware',  # Registro de actividades (solo en producción)
    
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.brand',
                'core.context_processors.superuser_perms',
                'core.context_processors.app_version',

            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

# ===== CONFIGURACIÓN DE BASE DE DATOS MEJORADA =====

# Esquema híbrido:
# - PRODUCCIÓN (VPS): default = PostgreSQL local
# - DESARROLLO / POS LOCAL: default = SQLite local, y una BD secundaria 'remote' a PostgreSQL


def get_default_database():
    """Base de datos principal según entorno."""
    if ENVIRONMENT == 'production':
        # PRODUCCIÓN (VPS) - Base de datos LOCAL PostgreSQL.
        # Las credenciales se toman EXCLUSIVAMENTE desde variables de entorno.
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST', 'localhost'),  # LOCAL en VPS
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': 600,
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }

    # DESARROLLO / POS LOCAL: usar siempre SQLite como default
    return {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }


def get_remote_database():
    """Base de datos remota PostgreSQL (servidor central)."""
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('REMOTE_DB_NAME'),
        'USER': os.getenv('REMOTE_DB_USER'),
        'PASSWORD': os.getenv('REMOTE_DB_PASSWORD'),
        'HOST': os.getenv('REMOTE_DB_HOST'),
        'PORT': os.getenv('REMOTE_DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': os.getenv('REMOTE_DB_SSLMODE', 'require'),
            'connect_timeout': 30,
        },
        'CONN_MAX_AGE': 300,
    }


DATABASES = {
    'default': get_default_database(),
}

# En entornos que no sean producción (ej. POS local), añadimos la BD remota
if ENVIRONMENT != 'production':
    DATABASES['remote'] = get_remote_database()


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'es-ar'

TIME_ZONE = 'America/Argentina/Buenos_Aires'

DATE_FORMAT = '%d %b %Y'

DATE_INPUT_FORMATS = ['%d %b %Y']

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGIN_URL = '/login/'

LOGIN_REDIRECT_URL = '/erp/launcher/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

MEDIA_URL = '/media/'

AUTH_USER_MODEL = 'user.User'

# Configuración de sesiones
# Tiempo de expiración de la cookie de sesión (en segundos)
# 604800 segundos = 7 días (aumentado para evitar cierre prematuro)
SESSION_COOKIE_AGE = 604800

# La sesión NO expira al cerrar el navegador
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Guardar la sesión en cada solicitud para mantenerla activa
SESSION_SAVE_EVERY_REQUEST = True

# Configuración adicional para mayor duración de sesión
# No requerir renovación de sesión por inactividad
SESSION_INACTIVITY_TIMEOUT = None  # Desactivado