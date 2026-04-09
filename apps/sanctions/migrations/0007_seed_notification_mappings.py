from django.db import migrations


def seed_notification_mappings(apps, schema_editor):
    SanctionNotificationMapping = apps.get_model('sanctions', 'SanctionNotificationMapping')
    user_model = migrations.swappable_dependency

    defaults = [
        ('[FULL_NAME]', 'Nombre completo', 'person.first_name + " " + person.last_name', 'Nombres y apellidos del empleado', 1),
        ('[NAME]', 'Nombres', 'person.first_name', 'Solo los nombres del empleado', 2),
        ('[LAST_NAME]', 'Apellidos', 'person.last_name', 'Solo los apellidos del empleado', 3),
        ('[DOCUMENT_NUMBER]', 'Documento', 'person.document_number', 'Número de cédula o identificación', 4),
        ('[POSITION]', 'Cargo', 'employee_position', 'Cargo del empleado', 5),
        ('[UNIT]', 'Unidad', 'employee_unit', 'Área o unidad administrativa', 6),
        ('[REGIME_CODE]', 'Código de régimen', 'regime.code', 'Código del régimen laboral', 7),
        ('[REGIME_NAME]', 'Nombre de régimen', 'regime.name', 'Nombre del régimen laboral', 8),
        ('[MONTH_NAME]', 'Mes en texto', 'month_name', 'Nombre del mes de la notificación', 9),
        ('[YEAR]', 'Año', 'year', 'Año de la notificación', 10),
        ('[REGISTRATION_DATE]', 'Fecha de registro', 'today', 'Fecha actual', 11),
        ('[AUTHORITY_1_NAME]', 'Autoridad 1', 'authority_1.name', 'Nombre de la autoridad 1', 12),
        ('[AUTHORITY_1_POSITION]', 'Cargo autoridad 1', 'authority_1.position', 'Cargo de la autoridad 1', 13),
        ('[AUTHORITY_2_NAME]', 'Autoridad 2', 'authority_2.name', 'Nombre de la autoridad 2', 14),
        ('[AUTHORITY_2_POSITION]', 'Cargo autoridad 2', 'authority_2.position', 'Cargo de la autoridad 2', 15),
        ('[MINUTES_LATE]', 'Minutos de atraso', 'minutes_late', 'Cantidad de minutos de atraso', 16),
        ('[REGS_WITHOUT_MARK]', 'Regs. sin marcar', 'regs_without_mark', 'Cantidad de registros sin marcar', 17),
        ('[OBSERVATIONS]', 'Observaciones', 'observations', 'Observaciones libres', 18),
    ]

    for placeholder, label, expression, description, order in defaults:
        SanctionNotificationMapping.objects.update_or_create(
            placeholder=placeholder,
            defaults={
                'label': label,
                'expression': expression,
                'description': description,
                'is_active': True,
                'order': order,
            },
        )


def unseed_notification_mappings(apps, schema_editor):
    SanctionNotificationMapping = apps.get_model('sanctions', 'SanctionNotificationMapping')
    SanctionNotificationMapping.objects.filter(placeholder__in=[
        '[FULL_NAME]', '[NAME]', '[LAST_NAME]', '[DOCUMENT_NUMBER]', '[POSITION]', '[UNIT]',
        '[REGIME_CODE]', '[REGIME_NAME]', '[MONTH_NAME]', '[YEAR]', '[REGISTRATION_DATE]',
        '[AUTHORITY_1_NAME]', '[AUTHORITY_1_POSITION]', '[AUTHORITY_2_NAME]', '[AUTHORITY_2_POSITION]',
        '[MINUTES_LATE]', '[REGS_WITHOUT_MARK]', '[OBSERVATIONS]'
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('sanctions', '0006_sanctionnotificationmapping'),
    ]

    operations = [
        migrations.RunPython(seed_notification_mappings, unseed_notification_mappings),
    ]
