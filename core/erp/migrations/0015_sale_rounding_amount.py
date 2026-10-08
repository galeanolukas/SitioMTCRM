# Generated manually - ajuste de redondeo en ventas POS
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0014_remito_stock_applied'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='rounding_amount',
            field=models.DecimalField(decimal_places=2, default=0.0, help_text='Positivo = recargo al cliente, negativo = descuento. El total ya lo incluye.', max_digits=9, verbose_name='Ajuste por redondeo'),
        ),
    ]
