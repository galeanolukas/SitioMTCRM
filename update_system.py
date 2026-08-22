#!/usr/bin/env python3
"""
Script unificado de actualización para SitioMTCRM.
Funciona tanto en Windows como en Linux.

Uso:
    python update_system.py              # Actualizar normalmente
    python update_system.py --force      # Forzar actualización (descarta cambios locales)
    python update_system.py --status     # Solo mostrar estado
    python update_system.py --status --json  # Estado en formato JSON

Requisitos:
    - Git instalado y accesible desde la línea de comandos
    - Python 3.x
    - El proyecto debe ser un repositorio Git con remote configurado
"""

import os
import sys
import subprocess
import platform
import json
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_command(cmd, cwd=BASE_DIR, capture=False):
    """Ejecuta un comando y retorna el resultado."""
    try:
        if capture:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=False)
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        else:
            print(f"  > {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=cwd, shell=False)
            return result.returncode == 0, '', ''
    except Exception as e:
        return False, '', str(e)


def get_git_executable():
    """Retorna el ejecutable de git según el SO."""
    # En Windows, intentar usar git del PATH o PortableGit
    if platform.system().lower() == 'windows':
        portable_git = os.path.join(BASE_DIR, 'tools', 'PortableGit', 'bin', 'git.exe')
        if os.path.exists(portable_git):
            return portable_git
    return 'git'


def check_status():
    """Verifica el estado del sistema para actualización."""
    git_exe = get_git_executable()
    
    status = {
        'script_available': True,
        'git_available': False,
        'git_repo': False,
        'has_changes': False,
        'has_remote': False,
        'current_branch': '',
        'system_os': platform.system().lower(),
        'base_dir': BASE_DIR,
        'python_version': platform.python_version(),
    }
    
    # Verificar Git
    ok, out, err = run_command([git_exe, '--version'], capture=True)
    if ok:
        status['git_available'] = True
    
    # Verificar repositorio
    git_dir = os.path.join(BASE_DIR, '.git')
    if os.path.exists(git_dir):
        status['git_repo'] = True
        
        # Rama actual
        ok, out, err = run_command([git_exe, 'rev-parse', '--abbrev-ref', 'HEAD'], capture=True)
        if ok:
            status['current_branch'] = out
        
        # Verificar remote
        ok, out, err = run_command([git_exe, 'remote'], capture=True)
        if ok and out.strip():
            status['has_remote'] = True
        
        # Verificar cambios locales
        ok, out, err = run_command([git_exe, 'status', '--porcelain'], capture=True)
        if ok and out.strip():
            status['has_changes'] = True
    
    return status


def update_status_json():
    """Imprime el estado en formato JSON."""
    status = check_status()
    print(json.dumps(status, indent=2))


def update_status_human():
    """Imprime el estado en formato legible."""
    status = check_status()
    
    print("=" * 50)
    print("ESTADO DEL SISTEMA")
    print("=" * 50)
    print(f"  Sistema Operativo: {status['system_os']}")
    print(f"  Python: {status['python_version']}")
    print(f"  Directorio: {status['base_dir']}")
    print(f"  Git disponible: {'SI' if status['git_available'] else 'NO'}")
    print(f"  Repositorio Git: {'SI' if status['git_repo'] else 'NO'}")
    
    if status['git_repo']:
        print(f"  Rama actual: {status['current_branch']}")
        print(f"  Remote configurado: {'SI' if status['has_remote'] else 'NO'}")
        print(f"  Cambios locales: {'SI' if status['has_changes'] else 'NO'}")
    
    print()
    
    if not status['git_available']:
        print("[ERROR] Git no está instalado o no está en el PATH.")
        if status['system_os'] == 'windows':
            print("  Instale Git desde https://git-scm.com o use Git Portable.")
        else:
            print("  Instale Git con: sudo apt install git  (Debian/Ubuntu)")
        return False
    
    if not status['git_repo']:
        print("[ERROR] Este directorio no es un repositorio Git.")
        return False
    
    if not status['has_remote']:
        print("[ERROR] No hay remote configurado para el repositorio.")
        return False
    
    if status['has_changes']:
        print("[ADVERTENCIA] Hay cambios locales sin commitear.")
        print("  Use --force para descartar los cambios y actualizar igual.")
    
    print("[OK] El sistema está listo para actualizar.")
    return True


def do_update(force=False):
    """Ejecuta el proceso de actualización completo."""
    git_exe = get_git_executable()
    is_windows = platform.system().lower() == 'windows'
    
    print("=" * 50)
    print("ACTUALIZACIÓN DEL SISTEMA - SitioMTCRM")
    print("=" * 50)
    print(f"  SO: {platform.system()}")
    print(f"  Directorio: {BASE_DIR}")
    print(f"  Forzar: {force}")
    print()
    
    # 1) Verificar estado
    status = check_status()
    
    if not status['git_available']:
        print("[ERROR] Git no está disponible. No se puede actualizar.")
        return False
    
    if not status['git_repo']:
        print("[ERROR] No es un repositorio Git. No se puede actualizar.")
        return False
    
    if not status['has_remote']:
        print("[ERROR] No hay remote configurado. No se puede actualizar.")
        return False
    
    # 2) Manejar cambios locales
    if status['has_changes']:
        if force:
            print("[PASS] Descartando cambios locales (--force)...")
            ok, out, err = run_command([git_exe, 'checkout', '--', '.'])
            if not ok:
                print(f"[ERROR] No se pudieron descartar los cambios: {err}")
                return False
            # También limpiar archivos sin trackear
            ok, out, err = run_command([git_exe, 'clean', '-fd'])
            if not ok:
                print(f"[ADVERTENCIA] No se pudieron limpiar archivos sin trackear: {err}")
        else:
            print("[ERROR] Hay cambios locales sin commitear.")
            print("  Haga commit de sus cambios o use --force para descartarlos.")
            return False
    
    # 3) Git fetch
    print("\n[1/5] Obteniendo cambios del repositorio remoto...")
    ok, out, err = run_command([git_exe, 'fetch', '--all'])
    if not ok:
        print(f"[ERROR] No se pudo hacer fetch: {err}")
        return False
    print("  OK")
    
    # 4) Git pull
    print("\n[2/5] Descargando cambios...")
    ok, out, err = run_command([git_exe, 'pull', '--force'])
    if not ok:
        # Intentar con reset si pull falla
        print("  Pull falló, intentando reset...")
        branch = status.get('current_branch', 'main')
        ok, out, err = run_command([git_exe, 'reset', '--hard', f'origin/{branch}'])
        if not ok:
            print(f"[ERROR] No se pudo actualizar: {err}")
            return False
    print("  OK")
    
    # 5) Pip install
    print("\n[3/5] Instalando dependencias...")
    req_file = os.path.join(BASE_DIR, 'requirements.txt')
    if os.path.exists(req_file):
        pip_cmd = [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt']
        ok, out, err = run_command(pip_cmd)
        if ok:
            print("  OK")
        else:
            print(f"  [ADVERTENCIA] Error instalando dependencias: {err}")
    else:
        print("  No se encontró requirements.txt, saltando...")
    
    # 6) Migrations
    print("\n[4/5] Ejecutando migraciones...")
    manage_py = os.path.join(BASE_DIR, 'manage.py')
    if os.path.exists(manage_py):
        ok, out, err = run_command([sys.executable, 'manage.py', 'migrate', '--noinput'])
        if ok:
            print("  OK")
        else:
            print(f"  [ADVERTENCIA] Error en migraciones: {err}")
    else:
        print("  No se encontró manage.py, saltando...")
    
    # 7) Collect static
    print("\n[5/5] Recopilando archivos estáticos...")
    if os.path.exists(manage_py):
        ok, out, err = run_command([sys.executable, 'manage.py', 'collectstatic', '--noinput'])
        if ok:
            print("  OK")
        else:
            print(f"  [ADVERTENCIA] Error en collectstatic: {err}")
    
    # 8) Mensaje final
    print("\n" + "=" * 50)
    print("ACTUALIZACIÓN COMPLETADA")
    print("=" * 50)
    print("\nEl sistema se ha actualizado correctamente.")
    print("Si hay un servidor Django corriendo, debe reiniciarse.")
    print()
    
    # Obtener la nueva versión
    ok, out, err = run_command([git_exe, 'describe', '--tags', '--abbrev=0'], capture=True)
    if ok:
        print(f"Nueva versión: {out}")
    else:
        ok, out, err = run_command([git_exe, 'log', '-1', '--format=%h'], capture=True)
        if ok:
            print(f"Commit actual: {out}")
    
    return True


def main():
    args = sys.argv[1:]
    
    # Parsear argumentos
    show_status = '--status' in args
    json_output = '--json' in args
    force = '--force' in args
    
    if show_status:
        if json_output:
            update_status_json()
        else:
            update_status_human()
        return
    
    if not update_status_human():
        sys.exit(1)
    
    print()
    response = input("¿Desea continuar con la actualización? (s/N): ")
    if response.lower() not in ('s', 'si', 'y', 'yes'):
        print("Actualización cancelada.")
        return
    
    success = do_update(force=force)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
