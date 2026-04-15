import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


def migrate_personnel_action_signers(apps, schema_editor):
    PersonnelAction = apps.get_model('personnel_actions', 'PersonnelAction')
    Authority = apps.get_model('core', 'Authority')
    User = apps.get_model('core', 'User')

    # 1) Garantizar que exista Authority para cada created_by usado como fallback de firma.
    created_by_ids = list(
        PersonnelAction.objects
        .exclude(created_by_id__isnull=True)
        .values_list('created_by_id', flat=True)
        .distinct()
    )

    if created_by_ids:
        existing_authority_ids = set(
            Authority.objects.filter(id__in=created_by_ids).values_list('id', flat=True)
        )
        missing_ids = [uid for uid in created_by_ids if uid not in existing_authority_ids]

        if missing_ids:
            users = {
                u.id: u for u in User.objects.filter(id__in=missing_ids).only('id', 'username', 'first_name', 'last_name')
            }
            authorities_to_create = []
            now = timezone.now()
            for uid in missing_ids:
                user = users.get(uid)
                if not user:
                    continue
                full_name = f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()
                display_name = full_name or user.username or f"USUARIO {uid}"
                authorities_to_create.append(
                    Authority(
                        id=uid,
                        name=display_name,
                        position='REGISTRO MIGRADO',
                        status=True,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )

            if authorities_to_create:
                Authority.objects.bulk_create(authorities_to_create)

    # 2) authority_1 es obligatorio: usar created_by como respaldo cuando falte.
    PersonnelAction.objects.filter(
        authority_1_id__isnull=True,
        created_by_id__isnull=False,
    ).update(authority_1_id=models.F('created_by_id'))

    # 3) Limpiar campos opcionales antes del cambio de FKs.
    PersonnelAction.objects.filter(~Q(authority_2_id=None) | ~Q(reviewer_id=None) | ~Q(register_id=None)).update(
        authority_2_id=None,
        reviewer_id=None,
        register_id=None,
    )


def reverse_migrate_personnel_action_signers(apps, schema_editor):
    # No revertimos para evitar pérdida de información histórica de firmantes.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_user_custom_signature_fields'),
        ('personnel_actions', '0005_personnelaction_elaboration_user'),
    ]

    operations = [
        migrations.RunPython(
            migrate_personnel_action_signers,
            reverse_migrate_personnel_action_signers,
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
