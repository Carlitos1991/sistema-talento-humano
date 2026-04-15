import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_user_custom_signature_fields'),
        ('personnel_actions', '0005_personnelaction_elaboration_user'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'UPDATE personnel_actions_personnelaction '
                'SET authority_1_id = NULL, authority_2_id = NULL, reviewer_id = NULL, register_id = NULL;'
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='personnelaction',
            name='authority_1',
            field=models.ForeignKey(
                limit_choices_to={'is_active': True},
                on_delete=django.db.models.deletion.PROTECT,
                related_name='actions_signed_auth1',
                to='core.user',
                verbose_name='Primera Autoridad',
            ),
        ),
        migrations.AlterField(
            model_name='personnelaction',
            name='authority_2',
            field=models.ForeignKey(
                blank=True,
                null=True,
                limit_choices_to={'is_active': True},
                on_delete=django.db.models.deletion.PROTECT,
                related_name='actions_signed_auth2',
                to='core.user',
                verbose_name='Segunda Autoridad',
            ),
        ),
        migrations.AlterField(
            model_name='personnelaction',
            name='reviewer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                limit_choices_to={'is_active': True},
                on_delete=django.db.models.deletion.PROTECT,
                related_name='actions_reviewed',
                to='core.user',
                verbose_name='Revisado por',
            ),
        ),
        migrations.AlterField(
            model_name='personnelaction',
            name='register',
            field=models.ForeignKey(
                blank=True,
                null=True,
                limit_choices_to={'is_active': True},
                on_delete=django.db.models.deletion.PROTECT,
                related_name='actions_register',
                to='core.user',
                verbose_name='Registrado   por',
            ),
        ),
    ]
