# Generated manually - flag stock_applied en Remito

from django.db import migrations, models


def mark_stock_applied(apps, schema_editor):
    Remito = apps.get_model('erp', 'Remito')
    # Remitos ya procesados/facturados movieron stock al procesarse
    Remito.objects.filter(estado__in=['processed', 'facturado']).update(stock_applied=True)


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0013_remito_iva_modo'),
    ]

    operations = [
        migrations.AddField(
            model_name='remito',
            name='stock_applied',
            field=models.BooleanField(default=False, help_text='True si el remito ya movió stock (al procesarse). Se usa para revertir solo si corresponde.', verbose_name='Stock aplicado'),
        ),
        migrations.RunPython(mark_stock_applied, migrations.RunPython.noop),
    ]
