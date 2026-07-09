import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SQLITE = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        'OPTIONS': {
            'timeout': 30,  # Aumentar timeout de 5 a 30 segundos
            'init_command': "PRAGMA journal_mode=WAL;",  # Habilitar WAL mode para mejor concurrencia
        },
    }
}
POSTGRESQL = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'db',
        'USER': 'postgres',
        'PASSWORD': '41733140',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}