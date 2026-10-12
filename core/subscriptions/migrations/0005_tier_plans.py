"""Crea los 3 planes mensuales por niveles y oculta el plan legacy.

- 'Plan Estándar' (creado por la migración 0002 para empresas existentes)
  queda INACTIVO: sigue asignado a las suscripciones actuales pero no se
  vende ni aparece en la página pública.
- Se crean Básico / Profesional / Premium (30 días) con límites y
  características iniciales. Los precios son placeholder editables.
"""
from django.db import migrations


TIER_PLANS = [
    {
        'name': 'Básico',
        'price': 8000,
        'duration_days': 30,
        'sort_order': 1,
        'is_featured': False,
        'description': 'Para empezar a vender',
        'features': (
            'Hasta 100 productos\n'
            'POS + control de stock\n'
            'Caja diaria, gastos y remitos\n'
            'Cobro con QR Mercado Pago\n'
            'Hasta 2 usuarios\n'
            'Backup en el servidor'
        ),
        'max_products': 100,
        'max_users': 2,
        'allow_mp_qr': True,
        'allow_invoicing': False,
        'allow_catalog': False,
    },
    {
        'name': 'Profesional',
        'price': 16000,
        'duration_days': 30,
        'sort_order': 2,
        'is_featured': True,
        'description': 'El más elegido',
        'features': (
            'Hasta 2.000 productos\n'
            'Todo lo del plan Básico\n'
            'Facturación electrónica AFIP\n'
            'Catálogo online de productos\n'
            'Hasta 5 usuarios\n'
            'Soporte prioritario'
        ),
        'max_products': 2000,
        'max_users': 5,
        'allow_mp_qr': True,
        'allow_invoicing': True,
        'allow_catalog': True,
    },
    {
        'name': 'Premium',
        'price': 28000,
        'duration_days': 30,
        'sort_order': 3,
        'is_featured': False,
        'description': 'Sin límites, para crecer',
        'features': (
            'Productos ilimitados\n'
            'Todo lo del plan Profesional\n'
            'Multi-sucursal / múltiples POS\n'
            'Usuarios ilimitados\n'
            'Soporte dedicado'
        ),
        'max_products': None,
        'max_users': None,
        'allow_mp_qr': True,
        'allow_invoicing': True,
        'allow_catalog': True,
    },
]


def create_tier_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model('subscriptions', 'SubscriptionPlan')

    # El plan legacy de las empresas existentes queda oculto de la vitrina
    SubscriptionPlan.objects.filter(name='Plan Estándar').update(
        is_active=False,
        description='Plan de cortesía para clientes existentes',
    )

    for data in TIER_PLANS:
        SubscriptionPlan.objects.get_or_create(
            name=data['name'],
            defaults={**data, 'is_active': True},
        )


def remove_tier_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model('subscriptions', 'SubscriptionPlan')
    SubscriptionPlan.objects.filter(
        name__in=[p['name'] for p in TIER_PLANS]
    ).delete()
    SubscriptionPlan.objects.filter(name='Plan Estándar').update(
        is_active=True, description='',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0004_subscriptionplan_allow_catalog_and_more'),
    ]

    operations = [
        migrations.RunPython(create_tier_plans, remove_tier_plans),
    ]
