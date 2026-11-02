# Generated for cancelled-state support on employee accounts

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0020_remito_ajuste_costo_pct'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeeaccountsale',
            name='is_cancelled',
            field=models.BooleanField(default=False, verbose_name='Anulada'),
        ),
        migrations.AddField(
            model_name='employeeaccountsale',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha de anulación'),
        ),
    ]
