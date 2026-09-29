# Generated manually - modo de IVA en Remito (incluido vs adicional)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0012_pricelist_cost_update'),
    ]

    operations = [
        migrations.AddField(
            model_name='remito',
            name='iva_modo',
            field=models.CharField(choices=[('incluido', 'IVA incluido en los precios'), ('agregado', 'IVA adicional sobre el neto')], default='incluido', help_text='"Incluido": los precios cargados ya traen IVA (se extrae). "Agregado": los precios son netos y el IVA se suma al total.', max_length=10, verbose_name='Modo de IVA'),
        ),
    ]
