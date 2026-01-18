#!/usr/bin/env python3
"""
Herramienta para ejecutar actualización, subir cambios a Git y crear nueva versión
"""
import os
import sys
import django
import subprocess
import json
import re
from datetime import datetime

# Configurar Django
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django.setup()

from django.conf import settings


class VersionManager:
    """Gestor de versiones para el sistema POS"""
    
    def __init__(self):
        self.base_dir = BASE_DIR
        self.version_file = os.path.join(self.base_dir, 'VERSION')
        self.current_version = self._get_current_version()
    
    def _get_current_version(self):
        """Obtiene la versión actual desde el archivo VERSION"""
        try:
            if os.path.exists(self.version_file):
                with open(self.version_file, 'r') as f:
                    version = f.read().strip()
                    return version
            else:
                # Si no existe, crear versión inicial
                return self._create_initial_version()
        except Exception as e:
            print(f"❌ Error leyendo versión actual: {e}")
            return "1.0.0"
    
    def _create_initial_version(self):
        """Crea una versión inicial si no existe"""
        initial_version = "1.0.0"
        try:
            with open(self.version_file, 'w') as f:
                f.write(initial_version)
            print(f"✅ Archivo VERSION creado con versión inicial: {initial_version}")
            return initial_version
        except Exception as e:
            print(f"❌ Error creando archivo VERSION: {e}")
            return "1.0.0"
    
    def _increment_version(self, increment_type='patch'):
        """
        Incrementa la versión según el tipo:
        - patch: 1.0.0 -> 1.0.1 (corrección de errores)
        - minor: 1.0.1 -> 1.1.0 (nuevas características)
        - major: 1.1.0 -> 2.0.0 (cambios importantes)
        """
        try:
            # Parsear versión actual
            version_parts = self.current_version.split('.')
            major = int(version_parts[0])
            minor = int(version_parts[1])
            patch = int(version_parts[2])
            
            # Incrementar según tipo
            if increment_type == 'patch':
                patch += 1
            elif increment_type == 'minor':
                minor += 1
                patch = 0
            elif increment_type == 'major':
                major += 1
                minor = 0
                patch = 0
            
            # Nueva versión
            new_version = f"{major}.{minor}.{patch}"
            
            # Guardar nueva versión
            with open(self.version_file, 'w') as f:
                f.write(new_version)
            
            print(f"✅ Versión actualizada: {self.current_version} -> {new_version}")
            self.current_version = new_version
            return new_version
            
        except Exception as e:
            print(f"❌ Error incrementando versión: {e}")
            return self.current_version
    
    def _run_command(self, command, description, check=True):
        """Ejecuta un comando y maneja errores"""
        print(f"\n🔄 {description}...")
        try:
            result = subprocess.run(
                command,
                cwd=self.base_dir,
                shell=True,
                capture_output=True,
                text=True,
                check=check
            )
            
            if result.stdout:
                print(f"✅ {description} completado")
                if result.stdout.strip():
                    print(f"   Output: {result.stdout.strip()}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error en {description}: {e}")
            if e.stdout:
                print(f"   stdout: {e.stdout}")
            if e.stderr:
                print(f"   stderr: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ Error ejecutando {description}: {e}")
            return False
    
    def _check_git_status(self):
        """Verifica el estado de Git"""
        try:
            # Verificar si hay cambios
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )
            
            if result.stdout.strip():
                print("📋 Cambios detectados:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        print(f"   {line}")
                return True
            else:
                print("✅ No hay cambios pendientes")
                return False
                
        except Exception as e:
            print(f"❌ Error verificando estado de Git: {e}")
            return False
    
    def _get_git_remote(self):
        """Obtiene el remote de Git"""
        try:
            result = subprocess.run(
                ['git', 'remote', '-v'],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.split('\n'):
                if 'origin' in line and '(fetch)' in line:
                    remote = line.split()[1]
                    print(f"📡 Remote detectado: {remote}")
                    return remote
            
            return None
            
        except Exception as e:
            print(f"❌ Error obteniendo remote: {e}")
            return None
    
    def execute_update_system(self):
        """Ejecuta el sistema de actualización"""
        print("\n" + "="*60)
        print("🔄 PASO 1: EJECUTANDO SISTEMA DE ACTUALIZACIÓN")
        print("="*60)
        
        # Ejecutar el script de actualización
        update_script = os.path.join(self.base_dir, 'update_system.py')
        
        if os.path.exists(update_script):
            success = self._run_command(
                f"python3 {update_script}",
                "Sistema de actualización"
            )
            
            if not success:
                print("❌ Falló la actualización del sistema")
                return False
        else:
            print("❌ No se encuentra el script de actualización")
            return False
        
        return True
    
    def commit_changes(self, commit_message=None):
        """Realiza commit de los cambios"""
        print("\n" + "="*60)
        print("📝 PASO 2: REALIZANDO COMMIT DE CAMBIOS")
        print("="*60)
        
        # Verificar si hay cambios
        if not self._check_git_status():
            print("✅ No hay cambios para commitear")
            return True
        
        # Agregar todos los cambios
        if not self._run_command('git add .', 'Agregando cambios al staging'):
            return False
        
        # Crear mensaje de commit
        if not commit_message:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            commit_message = f"Release v{self.current_version} - {timestamp}"
        
        # Realizar commit
        if not self._run_command(
            f'git commit -m "{commit_message}"',
            'Realizando commit'
        ):
            return False
        
        print(f"✅ Commit realizado: {commit_message}")
        return True
    
    def create_git_tag(self):
        """Crea un tag en Git para la nueva versión"""
        print("\n" + "="*60)
        print("🏷️ PASO 3: CREANDO TAG DE VERSIÓN")
        print("="*60)
        
        tag_name = f"v{self.current_version}"
        
        # Crear tag
        if not self._run_command(
            f'git tag -a {tag_name} -m "Release {tag_name}"',
            f'Creando tag {tag_name}'
        ):
            return False
        
        print(f"✅ Tag creado: {tag_name}")
        return True
    
    def push_to_remote(self):
        """Sube cambios y tags al remote"""
        print("\n" + "="*60)
        print("📤 PASO 4: SUBIENDO CAMBIOS AL REMOTO")
        print("="*60)
        
        # Obtener remote
        remote = self._get_git_remote()
        if not remote:
            print("❌ No se detectó remote de Git")
            return False
        
        # Subir cambios
        if not self._run_command(
            f'git push {remote} main',
            'Subiendo cambios al remote'
        ):
            return False
        
        # Subir tags
        if not self._run_command(
            f'git push {remote} --tags',
            'Subiendo tags al remote'
        ):
            return False
        
        print("✅ Cambios y tags subidos exitosamente")
        return True
    
    def create_release_notes(self):
        """Crea notas de release"""
        print("\n" + "="*60)
        print("📋 PASO 5: CREANDO NOTAS DE RELEASE")
        print("="*60)
        
        release_notes_file = os.path.join(self.base_dir, 'RELEASE_NOTES.md')
        
        try:
            # Obtener cambios desde el último tag
            result = subprocess.run(
                ['git', 'log', '--oneline', '--decorate', '--graph'],
                cwd=self.base_dir,
                capture_output=True,
                text=True
            )
            
            notes = f"""# Release Notes v{self.current_version}

**Fecha:** {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

## Cambios incluidos:

```
{result.stdout[:1000]}  # Limitar a 1000 caracteres
```

## Instalación:

1. Descargar la versión v{self.current_version}
2. Ejecutar el script de actualización
3. Seguir las instrucciones en pantalla

---

Para ver el historial completo, visite: [Repositorio Git]({self._get_git_remote() or '#'})
"""
            
            with open(release_notes_file, 'w') as f:
                f.write(notes)
            
            print(f"✅ Notas de release creadas: {release_notes_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error creando notas de release: {e}")
            return False
    
    def run_full_release_process(self, increment_type='patch', commit_message=None):
        """Ejecuta el proceso completo de release"""
        print("🚀 INICIANDO PROCESO DE RELEASE COMPLETO")
        print("="*60)
        print(f"📦 Versión actual: {self.current_version}")
        print(f"📈 Tipo de incremento: {increment_type}")
        print("="*60)
        
        steps = [
            ("Incrementar versión", lambda: self._increment_version(increment_type)),
            ("Ejecutar actualización del sistema", self.execute_update_system),
            ("Realizar commit de cambios", lambda: self.commit_changes(commit_message)),
            ("Crear tag de versión", self.create_git_tag),
            ("Subir cambios al remote", self.push_to_remote),
            ("Crear notas de release", self.create_release_notes)
        ]
        
        for i, (step_name, step_func) in enumerate(steps, 1):
            print(f"\n📍 PASO {i}/6: {step_name}")
            
            if not step_func():
                print(f"\n❌ Falló el paso {i}: {step_name}")
                print("🛑 Proceso de release detenido")
                return False
        
        print("\n" + "="*60)
        print("🎉 PROCESO DE RELEASE COMPLETADO EXITOSAMENTE")
        print("="*60)
        print(f"✅ Nueva versión: {self.current_version}")
        print("✅ Cambios subidos al repositorio")
        print("✅ Tag creado y subido")
        print("✅ Notas de release generadas")
        print("✅ Sistema actualizado")
        print("="*60)
        
        return True


def main():
    """Función principal"""
    print("🔧 HERRAMIENTA DE RELEASE AUTOMÁTICO")
    print("="*60)
    
    # Parsear argumentos
    increment_type = 'patch'  # por defecto
    commit_message = None
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ['patch', 'minor', 'major']:
            increment_type = sys.argv[1]
        else:
            print("❌ Tipo de incremento inválido. Use: patch, minor, o major")
            print("   patch: 1.0.0 -> 1.0.1 (corrección de errores)")
            print("   minor: 1.0.1 -> 1.1.0 (nuevas características)")
            print("   major: 1.1.0 -> 2.0.0 (cambios importantes)")
            return 1
    
    if len(sys.argv) > 2:
        commit_message = ' '.join(sys.argv[2:])
    
    try:
        # Crear gestor de versiones
        version_manager = VersionManager()
        
        # Ejecutar proceso completo
        success = version_manager.run_full_release_process(
            increment_type=increment_type,
            commit_message=commit_message
        )
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"❌ Error durante el proceso: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
