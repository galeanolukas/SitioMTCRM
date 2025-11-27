from django.core.management.base import BaseCommand
from django.conf import settings
import os
import shutil
import datetime
import pathlib

class Command(BaseCommand):
    help = "Genera un backup de la base de datos SQLite en la carpeta 'backups' del proyecto."

    def handle(self, *args, **options):
        db_path = settings.DATABASES['default']['NAME']
        if not db_path or not os.path.isfile(db_path):
            self.stderr.write(self.style.ERROR("Base de datos SQLite no encontrada."))
            return

        # Determinar carpeta de backups: <base_dir>/backups
        base_dir = pathlib.Path(db_path).parent
        backup_dir = base_dir / "backups"
        backup_dir.mkdir(exist_ok=True)

        # Nombre con timestamp: db-YYYYMMDD-HHMM.sqlite3
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        dst = backup_dir / f"db-{ts}.sqlite3"

        try:
            shutil.copy2(db_path, dst)
            self.stdout.write(self.style.SUCCESS(f"Backup creado: {dst}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error al crear backup: {e}"))
