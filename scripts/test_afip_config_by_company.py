#!/usr/bin/env python
"""
Script para verificar la configuración AFIP por empresa
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.erp.models import AfipConfig, Company, User
from core.erp.afip.config import get_afip_config

def test_afip_config_by_company():
    """Verificar que la configuración AFIP es única por empresa"""
    print("=" * 80)
    print("🧪 VERIFICACIÓN DE CONFIGURACIÓN AFIP POR EMPRESA")
    print("=" * 80)
    
    # 1. Listar todas las empresas
    print("\n📋 1. Empresas en el sistema:")
    companies = Company.objects.all()
    for company in companies:
        print(f"   - ID: {company.id}, Nombre: {company.name}, CUIT: {company.cuit}")
    
    # 2. Listar todas las configuraciones AFIP
    print("\n📋 2. Configuraciones AFIP en el sistema:")
    afip_configs = AfipConfig.objects.all()
    for config in afip_configs:
        company_name = config.company.name if config.company else "Sin empresa"
        print(f"   - ID: {config.id}, Empresa: {company_name}, CUIT: {config.cuit}, Environment: {config.environment}, Activa: {config.is_active}")
    
    # 3. Verificar configuración por empresa
    print("\n📋 3. Configuración AFIP por empresa (usando get_afip_config):")
    for company in companies:
        config = get_afip_config(company_id=company.id)
        if config:
            print(f"   ✅ Empresa {company.name} (ID: {company.id}):")
            print(f"      - CUIT: {config.get('CUIT')}")
            print(f"      - Environment: {config.get('environment')}")
            print(f"      - Company ID: {config.get('company_id')}")
            print(f"      - Usar contingencia: {config.get('usar_contingencia')}")
        else:
            print(f"   ❌ Empresa {company.name} (ID: {company.id}): Sin configuración AFIP")
    
    # 4. Verificar fallback a configuración de pruebas
    print("\n📋 4. Verificar fallback a configuración de pruebas:")
    # Usar un company_id que no existe
    fake_company_id = 999999
    config = get_afip_config(company_id=fake_company_id)
    if config:
        print(f"   ✅ Fallback funcionó para company_id inexistente {fake_company_id}:")
        print(f"      - CUIT: {config.get('CUIT')}")
        print(f"      - Environment: {config.get('environment')}")
        print(f"      - Usar contingencia: {config.get('usar_contingencia')}")
    else:
        print(f"   ❌ Fallback no funcionó para company_id inexistente {fake_company_id}")
    
    # 5. Verificar configuración sin company_id (debería usar global o fallback)
    print("\n📋 5. Verificar configuración sin company_id:")
    config = get_afip_config(company_id=None)
    if config:
        print(f"   ✅ Configuración sin company_id:")
        print(f"      - CUIT: {config.get('CUIT')}")
        print(f"      - Environment: {config.get('environment')}")
        print(f"      - Company ID: {config.get('company_id')}")
    else:
        print(f"   ❌ No hay configuración sin company_id")
    
    print("\n" + "=" * 80)
    print("✅ VERIFICACIÓN COMPLETADA")
    print("=" * 80)

if __name__ == '__main__':
    test_afip_config_by_company()
