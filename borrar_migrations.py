"""Script utilitario para resetear el proyecto a "punto 0" en local.

Acciones:
- Eliminar todos los archivos de migración (.py y .pyc) de todas las apps, dejando solo __init__.py.
- Eliminar la base de datos SQLite local (db.sqlite3) ubicada en la raíz del proyecto.

NO toca ninguna base de datos remota (PostgreSQL) ni otros archivos.
"""

import os
import shutil


def borrar_migraciones_y_db(proyecto_path: str) -> None:
    """Elimina migraciones y la BD SQLite local en el proyecto dado."""

    print(f"Proyecto: {proyecto_path}")

    # 1) Eliminar archivos de migraciones en todas las apps
    for root, dirs, files in os.walk(proyecto_path):
        if 'migrations' in dirs:
            migrations_path = os.path.join(root, 'migrations')
            print(f"Procesando migraciones en: {migrations_path}")

            for filename in os.listdir(migrations_path):
                file_path = os.path.join(migrations_path, filename)

                # Mantener solo __init__.py
                if filename == '__init__.py':
                    continue

                # Borrar archivos .py y .pyc de migraciones
                if filename.endswith('.py') or filename.endswith('.pyc'):
                    os.remove(file_path)
                    print(f"  Eliminado archivo: {file_path}")
                # Borrar posibles carpetas __pycache__ dentro de migrations
                elif os.path.isdir(file_path) and filename == '__pycache__':
                    shutil.rmtree(file_path, ignore_errors=True)
                    print(f"  Eliminada carpeta: {file_path}")

    # 2) Eliminar base de datos SQLite local (db.sqlite3)
    db_path = os.path.join(proyecto_path, 'db.sqlite3')
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Base de datos SQLite eliminada: {db_path}")
    else:
        print(f"No se encontró db.sqlite3 en {proyecto_path}; nada que borrar.")


if __name__ == "__main__":
    proyecto_path = os.path.dirname(os.path.abspath(__file__))  # Ruta del proyecto
    borrar_migraciones_y_db(proyecto_path)
