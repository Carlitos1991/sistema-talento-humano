from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sanctions', '0017_sanctionnotification_is_notified_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sanctionnotification',
            name='days_without_mark',
            field=models.PositiveIntegerField(
                blank=True,
                default=0,
                null=True,
                verbose_name='Dias sin marcar',
            ),
        ),
    ]
