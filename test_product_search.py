#!/usr/bin/env python
import os
import django
import requests

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from core.erp.models import Product, Company, Category

def test_product_search():
    """Probar la búsqueda de productos como lo hace el POS"""
    
    # Crear cliente de prueba
    client = Client()
    
    # Crear usuario de prueba si no existe
    User = get_user_model()
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@example.com', 'is_active': True, 'is_superuser': True, 'is_staff': True}
    )
    if created:
        user.set_password('testpass123')
        user.save()
    
    # Crear empresa de prueba
    company, created = Company.objects.get_or_create(
        name='Test Company',
        defaults={'cuit': '20-12345678-9', 'pos': '0001'}
    )
    
    # Crear categoría de prueba
    category, created = Category.objects.get_or_create(
        name='Test Category',
        defaults={'desc': 'Categoría de prueba'}
    )
    
    # Crear producto de prueba
    product, created = Product.objects.get_or_create(
        name='Producto de Prueba',
        defaults={
            'code': 'TEST001',
            'cat': category,
            'company': company,
            'pvp': 100.00,
            'iva_rate': 0.21,
            'stock': 10.00,
            'min_stock': 5.00
        }
    )
    
    # Login
    client.login(username='testuser', password='testpass123')
    
    # Establecer compañía en sesión
    session = client.session
    session['company_id'] = company.id
    session.save()
    
    print("=== Probando búsqueda de productos ===")
    
    # Test 1: search_products action
    print("\n1. Test search_products:")
    response = client.post('/erp/pos/', {
        'action': 'search_products',
        'term': 'prueba'
    })
    print(f"Status: {response.status_code}")
    if response.status_code == 302:
        print(f"Redirect to: {response.url}")
    else:
        try:
            print(f"Response: {response.json()}")
        except:
            print(f"Response content: {response.content.decode()[:500]}")
    
    # Test 2: product_by_code action
    print("\n2. Test product_by_code:")
    response = client.post('/erp/pos/', {
        'action': 'product_by_code',
        'code': 'TEST001'
    })
    print(f"Status: {response.status_code}")
    if response.status_code == 302:
        print(f"Redirect to: {response.url}")
    else:
        try:
            print(f"Response: {response.json()}")
        except:
            print(f"Response content: {response.content.decode()[:500]}")
    
    # Test 3: Búsqueda con término vacío
    print("\n3. Test con término vacío:")
    response = client.post('/erp/pos/', {
        'action': 'search_products',
        'term': ''
    })
    print(f"Status: {response.status_code}")
    if response.status_code == 302:
        print(f"Redirect to: {response.url}")
    else:
        try:
            print(f"Response: {response.json()}")
        except:
            print(f"Response content: {response.content.decode()[:500]}")
    
    # Test 4: Búsqueda que no encuentra resultados
    print("\n4. Test sin resultados:")
    response = client.post('/erp/pos/', {
        'action': 'search_products',
        'term': 'xyz123'
    })
    print(f"Status: {response.status_code}")
    if response.status_code == 302:
        print(f"Redirect to: {response.url}")
    else:
        try:
            print(f"Response: {response.json()}")
        except:
            print(f"Response content: {response.content.decode()[:500]}")

if __name__ == "__main__":
    test_product_search()
