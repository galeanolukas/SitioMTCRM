#!/usr/bin/env python
"""
Script para probar la autorización de Web Services AFIP usando la configuración existente.

Uso:
    python scripts/test_auth_web_service.py --config-id 3 --service wsfe
    python scripts/test_auth_web_service.py --config-id 3 --service wsct

Opciones:
    --config-id: ID de la configuración AFIP (obligatorio)
    --service: Web Service a autorizar (wsfe, wsct, wscdc, default: wsfe)
    --username: Usuario de Clave Fiscal (opcional, usa el de la config si está guardado)
    --password: Contraseña de Clave Fiscal (opcional, usa la de la config si está guardada)
    --alias: Alias del certificado (opcional, default: 'afipsdk')
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.erp.models import AfipConfig
from core.erp.afip.client import AfipClient


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Probar autorización de Web Services AFIP')
    parser.add_argument('--config-id', type=int, required=True, help='ID de la configuración AFIP')
    parser.add_argument('--service', type=str, default='wsfe', choices=['wsfe', 'wsct', 'wscdc'], help='Web Service a autorizar')
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
        print(f"  Certificado: {'Configurado' if config.cert else 'No configurado'}")
        print(f"  Key: {'Configurada' if config.key else 'No configurada'}")
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

        # Verificar que tenga certificados
        if not config.cert or not config.key:
            print("⚠ Advertencia: La configuración no tiene certificados")
            print("  Debe generar certificados antes de autorizar el Web Service")
            print("  Use: python scripts/test_generate_certificate.py --config-id {args.config_id} --type {config.environment}")
            print()

        # Crear cliente AFIP
        client = AfipClient(company_id=config.company_id if config.company else None)
        print("✓ Cliente AFIP inicializado")
        print()

        # Autorizar Web Service
        service_names = {
            'wsfe': 'WSFE (Facturación Electrónica)',
            'wsct': 'WSCT (Constatación de Comprobantes)',
            'wscdc': 'WSCDC (Comprobantes en PDF)'
        }
        print(f"Autorizando Web Service: {service_names.get(args.service, args.service)}")
        print()

        result = client.auth_web_service(
            cuit=config.cuit,
            username=username,
            password=password,
            alias=args.alias,
            service=args.service
        )

        if 'error' in result:
            print(f"✗ Error al autorizar Web Service: {result['error']}")
            return 1

        # Actualizar estado de autorización WSFE
        if args.service == 'wsfe':
            config.wsfe_authorized = True
            config.wsfe_authorized_at = django.utils.timezone.now()
            config.save(update_fields=['wsfe_authorized', 'wsfe_authorized_at'])
            print("✓ WSFE autorizado exitosamente")
            print(f"  Estado WSFE actualizado en configuración AFIP (ID: {config.id})")
            print(f"  Fecha de autorización: {config.wsfe_authorized_at}")
        else:
            print(f"✓ Web Service {args.service.upper()} autorizado exitosamente")

        print(f"  Automation ID: {result.get('automation_id', 'N/A')}")
        print()
        print("✓ Web Service autorizado correctamente")
        return 0

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
