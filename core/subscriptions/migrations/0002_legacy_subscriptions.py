"""Suscripción 'legacy' para empresas existentes.

Crea un plan estándar y una suscripción activa de 1 año para cada empresa
que ya exista, de modo que ninguna instalación quede bloqueada el día
del deploy. El superusuario ajusta planes y vencimientos después.
"""
from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def create_legacy_subscriptions(apps, schema_editor):
    Company = apps.get_model('erp', 'Company')
    SubscriptionPlan = apps.get_model('subscriptions', 'SubscriptionPlan')
    Subscription = apps.get_model('subscriptions', 'Subscription')

    plan, _ = SubscriptionPlan.objects.get_or_create(
        name='Plan Estándar',
        defaults={'price': 0, 'duration_days': 30, 'is_active': True},
    )
    today = timezone.localdate()
    for company in Company.objects.all():
        Subscription.objects.get_or_create(
            company=company,
            defaults={
                'plan': plan,
                'start_date': today,
                'end_date': today + timedelta(days=365),
                'grace_days': 7,
                'status': 'active',
                'notes': 'Suscripción inicial automática (migración legacy)',
            },
        )


def remove_legacy_subscriptions(apps, schema_editor):
    Subscription = apps.get_model('subscriptions', 'Subscription')
    Subscription.objects.filter(
        notes='Suscripción inicial automática (migración legacy)'
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0001_initial'),
        ('erp', '0015_sale_rounding_amount'),
    ]

    operations = [
        migrations.RunPython(create_legacy_subscriptions, remove_legacy_subscriptions),
    ]
