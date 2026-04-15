from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_authority_status_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='custom_name',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Nombre personalizado'),
        ),
        migrations.AddField(
            model_name='user',
            name='custom_position',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Cargo personalizado'),
        ),
    ]
