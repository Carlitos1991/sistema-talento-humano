from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0014_licensepayrolleffect_subsidy_reported'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "UPDATE licenses_payroll_effect "
                "SET target_year = NULL, target_month = NULL "
                "WHERE labor_regime = 'CT' AND subsidy_reported = FALSE"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
