from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0005_alter_managementperiod_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='managementperiod',
            name='manual_position',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Cargo Manual'),
        ),
        migrations.AddField(
            model_name='managementperiod',
            name='manual_remuneration',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Remuneración Manual'),
        ),
    ]
