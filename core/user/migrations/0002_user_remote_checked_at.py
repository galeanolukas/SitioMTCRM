from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='remote_checked_at',
            field=models.DateTimeField(blank=True, null=True, help_text='Última vez que se verificó el estado del usuario contra el servidor central', verbose_name='Última verificación remota'),
        ),
    ]
