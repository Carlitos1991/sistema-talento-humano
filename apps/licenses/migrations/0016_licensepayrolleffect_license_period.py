from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0015_clear_ct_subsidy_report_period'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensepayrolleffect',
            name='license_month',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name='Mes de Licencia (1-12)',
            ),
        ),
        migrations.AddField(
            model_name='licensepayrolleffect',
            name='license_year',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name='Año de Licencia',
            ),
        ),
    ]
