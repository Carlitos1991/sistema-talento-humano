from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='created_by',
            field=models.ForeignKey(
                related_name='documents_created',
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                verbose_name='Creado por',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
