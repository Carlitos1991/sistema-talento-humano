from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q

PREDEFINED_ARCHIVE_TYPES = [
    {
        'code': 'EXPEDIENTE_INICIAL',
        'name': 'Expediente Inicial',
        'description': 'Documentos iniciales de ingreso del empleado.',
        'is_required': True,
        'has_expiration': False,
        'max_size_mb': 10,
    },
    {
        'code': 'ACCIONES_PERSONAL',
        'name': 'Acciones de Personal',
        'description': 'Acciones de personal para digitalizacion y resguardo.',
        'is_required': True,
        'has_expiration': False,
        'max_size_mb': 10,
    },
    {
        'code': 'CONTRATOS',
        'name': 'Contratos',
        'description': 'Contratos y adendas del empleado para digitalizacion y resguardo.',
        'is_required': True,
        'has_expiration': False,
        'max_size_mb': 10,
    },
]


def create_predefined_types(apps, schema_editor):
    EmployeeDocumentType = apps.get_model('employee_archive', 'EmployeeDocumentType')

    for type_data in PREDEFINED_ARCHIVE_TYPES:
        desired_code = type_data['code']
        desired_name = type_data['name']

        code_item = EmployeeDocumentType.objects.filter(code=desired_code).first()
        name_item = EmployeeDocumentType.objects.filter(name=desired_name).first()

        if code_item and name_item and code_item.pk != name_item.pk:
            legacy_name = f"{name_item.name} LEGACY {name_item.pk}"
            name_item.name = legacy_name[:120]
            name_item.save(update_fields=['name'])

        item = code_item or name_item
        if item:
            item.code = desired_code
            item.name = desired_name
            item.description = type_data['description']
            item.is_required = type_data['is_required']
            item.has_expiration = type_data['has_expiration']
            item.max_size_mb = type_data['max_size_mb']
            item.is_active = True
            item.save()
        else:
            EmployeeDocumentType.objects.create(
                code=desired_code,
                name=desired_name,
                description=type_data['description'],
                is_required=type_data['is_required'],
                has_expiration=type_data['has_expiration'],
                max_size_mb=type_data['max_size_mb'],
                is_active=True,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('employee_archive', '0003_loans_notifications_audit'),
        ('employee', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeArchiveScanTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado')),
                ('source_type', models.CharField(choices=[('INITIAL', 'Expediente Inicial'), ('CONTRACT', 'Contrato'), ('PERSONNEL_ACTION', 'Accion de Personal')], max_length=30, verbose_name='Origen')),
                ('source_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id del registro origen')),
                ('source_reference', models.CharField(blank=True, max_length=120, null=True, verbose_name='Referencia origen')),
                ('title', models.CharField(max_length=255, verbose_name='Titulo')),
                ('source_date', models.DateField(blank=True, null=True, verbose_name='Fecha del registro origen')),
                ('is_scanned', models.BooleanField(default=False, verbose_name='Digitalizado')),
                ('scanned_at', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de digitalizacion')),
                ('archive_document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scan_tasks', to='employee_archive.employeearchivedocument', verbose_name='Documento de archivo')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employee_archive_employeearchivescantask_created', to='core.user', verbose_name='Creado por')),
                ('document_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='scan_tasks', to='employee_archive.employeedocumenttype', verbose_name='Tipo de documento destino')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='archive_scan_tasks', to='employee.employee', verbose_name='Empleado')),
                ('scanned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='archive_scan_tasks_done', to='core.user', verbose_name='Digitalizado por')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employee_archive_employeearchivescantask_updated', to='core.user', verbose_name='Actualizado por')),
                ('version', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scan_tasks', to='employee_archive.employeearchiveversion', verbose_name='Version')),
            ],
            options={
                'verbose_name': 'Tarea de Digitalizacion de Archivo',
                'verbose_name_plural': 'Tareas de Digitalizacion de Archivo',
                'ordering': ['-source_date', '-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='employeearchivescantask',
            constraint=models.UniqueConstraint(condition=Q(('source_id__isnull', False)), fields=('employee', 'source_type', 'source_id'), name='unique_archive_scan_task_per_source'),
        ),
        migrations.RunPython(create_predefined_types, migrations.RunPython.noop),
    ]
