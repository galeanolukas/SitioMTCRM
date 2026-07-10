#!/usr/bin/env python
"""
Script para probar la generación de certificados AFIP usando la configuración existente.

Uso:
    python scripts/test_generate_certificate.py --config-id 3 --type dev
    python scripts/test_generate_certificate.py --config-id 3 --type prod

Opciones:
    --config-id: ID de la configuración AFIP (obligatorio)
    --type: Tipo de certificado (dev o prod, default: dev)
    --username: Usuario de Clave Fiscal (opcional, usa el de la config si está guardado)
    --password: Contraseña de Clave Fiscal (opcional, usa la de la config si está guardada)
    --alias: Alias del certificado (opcional, default: 'afipsdk')
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from core.erp.models import AfipConfig
from core.erp.afip.client import AfipClient


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Probar generación de certificados AFIP')
    parser.add_argument('--config-id', type=int, required=True, help='ID de la configuración AFIP')
    parser.add_argument('--type', type=str, default='dev', choices=['dev', 'prod'], help='Tipo de certificado (dev o prod)')
    parser.add_argument('--username', type=str, help='Usuario de Clave Fiscal (opcional)')
    parser.add_argument('--password', type=str, help='Contraseña de Clave Fiscal (opcional)')
    parser.add_argument('--alias', type=str, default='afipsdk', help='Alias del certificado (default: afipsdk)')

    args = parser.parse_args()

    try:
        # Obtener configuración AFIP
        config = AfipConfig.objects.get(id=args.config_id)
        print(f"✓ Configuración AFIP encontrada: {config.company.name} (CUIT: {config.cuit})")
        print(f"  Ambiente: {config.environment}")
        print(f"  Access Token: {'Configurado' if config.access_token else 'No configurado'}")
        print(f"  Usuario Clave Fiscal: {'Configurado' if config.clave_fiscal_username else 'No configurado'}")
        print()

        # Determinar credenciales a usar
        username = args.username or config.clave_fiscal_username
        password = args.password or config.clave_fiscal_password

        if not username or not password:
            print("✗ Error: Faltan credenciales de Clave Fiscal")
            print("  - Debe configurar Usuario Clave Fiscal y Contraseña Clave Fiscal en la configuración AFIP")
            print("  - O pasarlas como argumentos --username y --password")
            return 1

        print(f"✓ Usando credenciales de Clave Fiscal")
        print(f"  Usuario: {username}")
        print(f"  Alias: {args.alias}")
        print()

        # Crear cliente AFIP
        client = AfipClient(company_id=config.company_id if config.company else None)
        print("✓ Cliente AFIP inicializado")
        print()

        # Generar certificado según tipo
        print(f"Generando certificado de {args.type.upper()}...")
        print()

        if args.type == 'prod':
            result = client.create_prod_certificate(
                cuit=config.cuit,
                username=username,
                password=password,
                alias=args.alias
            )
        else:
            result = client.create_dev_certificate(
                cuit=config.cuit,
                username=username,
                password=password,
                alias=args.alias
            )

        if 'error' in result:
            print(f"✗ Error al generar certificado: {result['error']}")
            return 1

        # Guardar certificado en la configuración
        if 'cert' in result and 'key' in result:
            config.cert = result['cert']
            config.key = result['key']
            config.save(update_fields=['cert', 'key'])
            print("✓ Certificado generado exitosamente")
            print(f"  Certificado guardado en configuración AFIP (ID: {config.id})")
            print(f"  Automation ID: {result.get('automation_id', 'N/A')}")
            print()
            print("✓ Certificado:")
            print(f"  {result['cert'][:100]}...")
            print()
            print("✓ Key:")
            print(f"  {result['key'][:100]}...")
            print()
            print("✓ Configuración AFIP actualizada con certificados")
            return 0
        else:
            print(f"✗ Error: La respuesta no contiene cert y key")
            print(f"  Respuesta: {result}")
            return 1

    except AfipConfig.DoesNotExist:
        print(f"✗ Error: No existe configuración AFIP con ID {args.config_id}")
        return 1
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
