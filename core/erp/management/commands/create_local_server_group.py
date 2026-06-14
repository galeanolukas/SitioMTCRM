from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.erp.models import Company


class Command(BaseCommand):
    help = 'Crea el grupo "Servidor Local" para usuarios que solo sincronizan con servidores locales'

    def handle(self, *args, **options):
        # Crear el grupo si no existe
        group, created = Group.objects.get_or_create(name='Servidor Local')
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Grupo "Servidor Local" creado exitosamente'))
        else:
            self.stdout.write(self.style.WARNING(f'El grupo "Servidor Local" ya existe'))
        
        # El grupo ya está configurado en sync_utils.py para forzar sincronización local
        # No se necesitan permisos específicos ya que la lógica está en el código
        self.stdout.write(self.style.SUCCESS('Configuración completada'))
        self.stdout.write(self.style.SUCCESS('Los usuarios en este grupo solo sincronizarán con servidores locales'))
