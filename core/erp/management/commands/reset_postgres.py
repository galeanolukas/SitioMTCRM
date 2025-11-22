from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
from django.db import connections, DEFAULT_DB_ALIAS


class Command(BaseCommand):
    help = "Resetea COMPLETAMENTE la base de datos PostgreSQL por defecto (solo entornos no productivos)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Confirma que entiendes que TODOS los datos se van a borrar.',
        )

    def handle(self, *args, **options):
        env = getattr(settings, 'ENVIRONMENT', 'development')
        if env == 'production':
            raise CommandError('Este comando NO puede ejecutarse en ENVIRONMENT=production.')

        if not options.get('force'):
            raise CommandError('Usa --force para confirmar el reseteo de la base de datos.')

        self.stdout.write(self.style.WARNING(
            'ATENCIÓN: se va a borrar TODO el contenido de la base de datos por defecto y recrear el esquema.'
        ))

        # Verificar que la base por defecto sea PostgreSQL
        conn = connections[DEFAULT_DB_ALIAS]
        engine = conn.settings_dict.get('ENGINE', '')
        if 'postgresql' not in engine:
            raise CommandError(f'Este comando solo está pensado para PostgreSQL. ENGINE actual: {engine}')

        with conn.cursor() as cursor:
            self.stdout.write('Dropping schema public ...')
            cursor.execute('DROP SCHEMA public CASCADE;')
            self.stdout.write('Creating schema public ...')
            cursor.execute('CREATE SCHEMA public;')

        self.stdout.write(self.style.NOTICE('Ejecutando migraciones ...'))
        call_command('migrate')

        self.stdout.write(self.style.SUCCESS('Base de datos PostgreSQL reseteada y migraciones aplicadas.'))
