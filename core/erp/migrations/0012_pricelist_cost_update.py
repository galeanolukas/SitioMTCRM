# Generated manually - campos para listas de tipo actualización de costos

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0011_add_external_codes_and_brand'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='pricelist',
            name='list_type',
            field=models.CharField(choices=[('sale', 'Lista de venta'), ('cost_update', 'Actualización de costos')], default='sale', max_length=20, verbose_name='Tipo de lista'),
        ),
        migrations.AddField(
            model_name='pricelist',
            name='supplier',
            field=models.ForeignKey(blank=True, help_text='Si se indica, la actualización aplica a todos los productos del proveedor. Si no, aplica a los productos agregados a la lista.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='erp.supplier', verbose_name='Proveedor'),
        ),
        migrations.AddField(
            model_name='pricelist',
            name='cost_increase',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='Aumento de costo (%)'),
        ),
        migrations.AddField(
            model_name='pricelist',
            name='applied_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Aplicada el'),
        ),
        migrations.AddField(
            model_name='pricelist',
            name='applied_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Aplicada por'),
        ),
        migrations.AddField(
            model_name='pricelist',
            name='snapshot',
            field=models.JSONField(blank=True, null=True, verbose_name='Snapshot de precios anteriores'),
        ),
        migrations.AddField(
            model_name='pricelist',
            name='undone',
            field=models.BooleanField(default=False, verbose_name='Deshecha'),
        ),
    ]
