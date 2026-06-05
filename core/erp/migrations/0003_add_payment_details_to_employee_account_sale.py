# Generated migration to add payment_details to EmployeeAccountSale

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeeaccountsale',
            name='payment_details',
            field=models.JSONField(blank=True, default=dict, verbose_name='Detalles de pago combinado'),
        ),
    ]
