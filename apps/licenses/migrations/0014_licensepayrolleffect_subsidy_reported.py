from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0013_licensepayrolleffect_created_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='licensepayrolleffect',
            name='target_year',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name='Año de Aplicación',
            ),
        ),
        migrations.AlterField(
            model_name='licensepayrolleffect',
            name='target_month',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name='Mes de Aplicación (1-12)',
            ),
        ),
        migrations.RenameField(
            model_name='licensepayrolleffect',
            old_name='subsidy_calculated',
            new_name='subsidy_reported',
        ),
        migrations.RenameField(
            model_name='licensepayrolleffect',
            old_name='subsidy_calculated_at',
            new_name='subsidy_reported_at',
        ),
    ]
