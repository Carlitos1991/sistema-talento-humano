import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_user_custom_signature_fields'),
        ('personnel_actions', '0004_actionmovement_new_budget_line_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql='UPDATE personnel_actions_personnelaction SET elaboration_id = NULL;',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='personnelaction',
            name='elaboration',
            field=models.ForeignKey(
                blank=True,
                null=True,
                limit_choices_to={'is_active': True},
                on_delete=django.db.models.deletion.PROTECT,
                related_name='actions_elaboration',
                to='core.user',
                verbose_name='Elaborado por',
            ),
        ),
    ]
