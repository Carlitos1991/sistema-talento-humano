# Generated manually on 2026-04-09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_authority_model_migration'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE core_authority ADD COLUMN IF NOT EXISTS status boolean NOT NULL DEFAULT true;",
                    reverse_sql="ALTER TABLE core_authority DROP COLUMN IF EXISTS status;",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='authority',
                    name='status',
                    field=models.BooleanField(default=True, verbose_name='Estado legado'),
                ),
            ],
        ),
    ]
