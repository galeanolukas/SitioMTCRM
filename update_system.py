#!/usr/bin/env python3
"""
Script de actualización simplificado para SitioMTCRM
Puede ser ejecutado manualmente o llamado desde la API del sistema
"""
import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path


class SimpleUpdater:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.system_os = platform.system().lower()
        
    def log(self, message):
        """Función de logging simple"""
        print(f"[UPDATER] {message}")
        
    def check_git(self):
        """Verificar si Git está disponible"""
        try:
            subprocess.run(['git', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def check_git_repo(self):
        """Verificar si estamos en un repositorio Git"""
        return (self.base_dir / '.git').exists()
    
    def has_uncommitted_changes(self):
        """Verificar si hay cambios sin commitear"""
        try:
            result = subprocess.run(
                ['git', 'diff-index', '--quiet', 'HEAD', '--'],
                cwd=self.base_dir,
                capture_output=True
            )
            return result.returncode != 0
        except:
            return False
    
    def backup_important_files(self):
        """Hacer backup de archivos importantes"""
        backups = []
        
        # Backup de entorno virtual
        venv_path = self.base_dir / 'venv'
        if venv_path.exists():
            backup_path = self.base_dir / 'venv_backup'
            self.log("Haciendo backup del entorno virtual...")
            if backup_path.exists():
                shutil.rmtree(backup_path)
            shutil.move(str(venv_path), str(backup_path))
            backups.append(('venv', str(backup_path)))
        
        # Backup de base de datos SQLite
        db_path = self.base_dir / 'db.sqlite3'
        if db_path.exists():
            backup_path = self.base_dir / 'db.sqlite3_backup'
            self.log("Haciendo backup de la base de datos...")
            if backup_path.exists():
                backup_path.unlink()
            shutil.copy2(str(db_path), str(backup_path))
            backups.append(('db', str(backup_path)))
        
        return backups
    
    def restore_backups(self, backups):
        """Restaurar backups si falla la actualización"""
        self.log("Restaurando backups...")
        for backup_type, backup_path in backups:
            if backup_type == 'venv':
                original_path = self.base_dir / 'venv'
                if original_path.exists():
                    shutil.rmtree(original_path)
                shutil.move(backup_path, str(original_path))
            elif backup_type == 'db':
                original_path = self.base_dir / 'db.sqlite3'
                if original_path.exists():
                    original_path.unlink()
                shutil.copy2(backup_path, str(original_path))
    
    def run_git_pull(self):
        """Ejecutar git pull"""
        try:
            result = subprocess.run(
                ['git', 'pull', 'origin', 'main'],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                check=True
            )
            self.log("Código actualizado desde GitHub")
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr
    
    def setup_virtual_env(self):
        """Crear o activar entorno virtual"""
        venv_path = self.base_dir / 'venv'
        
        if not venv_path.exists():
            self.log("Creando entorno virtual...")
            subprocess.run([
                sys.executable, '-m', 'venv', 'venv'
            ], cwd=self.base_dir, check=True)
        
        # Determinar cómo activar el entorno virtual
        if self.system_os == 'windows':
            activate_script = venv_path / 'Scripts' / 'activate.bat'
            python_exe = venv_path / 'Scripts' / 'python.exe'
            pip_exe = venv_path / 'Scripts' / 'pip.exe'
        else:
            activate_script = venv_path / 'bin' / 'activate'
            python_exe = venv_path / 'bin' / 'python'
            pip_exe = venv_path / 'bin' / 'pip'
        
        return python_exe, pip_exe
    
    def install_dependencies(self, pip_exe):
        """Instalar dependencias"""
        self.log("Actualizando pip...")
        subprocess.run([
            str(pip_exe), 'install', '--upgrade', 'pip'
        ], cwd=self.base_dir, capture_output=True)
        
        self.log("Instalando dependencias...")
        subprocess.run([
            str(pip_exe), 'install', '-r', 'requirements.txt'
        ], cwd=self.base_dir, check=True)
    
    def run_migrations(self, python_exe):
        """Ejecutar migraciones de Django"""
        self.log("Creando migraciones...")
        subprocess.run([
            str(python_exe), 'manage.py', 'makemigrations', 'user', 'erp'
        ], cwd=self.base_dir, check=True)
        
        self.log("Ejecutando migraciones...")
        subprocess.run([
            str(python_exe), 'manage.py', 'migrate'
        ], cwd=self.base_dir, check=True)
    
    def clean_backups(self):
        """Limpiar backups si la actualización fue exitosa"""
        venv_backup = self.base_dir / 'venv_backup'
        if venv_backup.exists():
            shutil.rmtree(venv_backup)
        
        db_backup = self.base_dir / 'db.sqlite3_backup'
        if db_backup.exists():
            db_backup.unlink()
    
    def update(self, force=False):
        """Ejecutar actualización completa"""
        self.log("Iniciando actualización del sistema...")
        
        # Verificaciones previas
        if not self.check_git():
            return False, "Git no está instalado o no está en el PATH"
        
        if not self.check_git_repo():
            return False, "No se encuentra el repositorio Git. Debe clonar el proyecto con Git"
        
        if not force and self.has_uncommitted_changes():
            return False, "Hay cambios locales sin commitear. Use force=True para sobreescribirlos"
        
        # Backup de archivos importantes
        backups = self.backup_important_files()
        
        try:
            # Actualizar código
            success, output = self.run_git_pull()
            if not success:
                self.restore_backups(backups)
                return False, f"Error al actualizar desde GitHub: {output}"
            
            # Configurar entorno virtual
            python_exe, pip_exe = self.setup_virtual_env()
            
            # Instalar dependencias
            self.install_dependencies(pip_exe)
            
            # Ejecutar migraciones
            self.run_migrations(python_exe)
            
            # Limpiar backups
            self.clean_backups()
            
            self.log("Actualización completada exitosamente!")
            return True, "Sistema actualizado correctamente"
            
        except Exception as e:
            self.restore_backups(backups)
            return False, f"Error durante la actualización: {str(e)}"
    
    def get_status(self):
        """Obtener estado actual del sistema"""
        status = {
            'git_available': self.check_git(),
            'git_repo': self.check_git_repo(),
            'has_changes': self.has_uncommitted_changes(),
            'system_os': self.system_os,
            'base_dir': str(self.base_dir)
        }
        return status


def main():
    """Función principal para ejecución manual"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Actualizador simplificado de SitioMTCRM')
    parser.add_argument('--force', action='store_true', help='Forzar actualización ignorando cambios locales')
    parser.add_argument('--status', action='store_true', help='Mostrar estado actual')
    parser.add_argument('--json', action='store_true', help='Salida en formato JSON')
    
    args = parser.parse_args()
    
    updater = SimpleUpdater()
    
    if args.status:
        status = updater.get_status()
        if args.json:
            import json
            print(json.dumps(status, indent=2))
        else:
            print("Estado del sistema:")
            for key, value in status.items():
                print(f"  {key}: {value}")
        return
    
    success, message = updater.update(force=args.force)
    
    if args.json:
        import json
        result = {'success': success, 'message': message}
        print(json.dumps(result, indent=2))
    else:
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
            sys.exit(1)


if __name__ == '__main__':
    main()
