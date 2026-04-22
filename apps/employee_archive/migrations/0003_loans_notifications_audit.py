import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee_archive', '0002_alter_employeearchivedocument_created_by_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeArchiveLoan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='Estado')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última Modificación')),
                ('expediente_number', models.CharField(max_length=50, verbose_name='Numero de expediente')),
                ('status', models.CharField(choices=[('REQUESTED', 'Solicitado'), ('ON_LOAN', 'En prestamo'), ('RETURN_REPORTED', 'Devolucion reportada'), ('RETURN_VALIDATED', 'Devuelto')], default='REQUESTED', max_length=20, verbose_name='Estado')),
                ('requested_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Fecha de solicitud')),
                ('delivered_at', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de entrega')),
                ('return_reported_at', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de reporte de devolucion')),
                ('returned_at', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de devolucion validada')),
                ('request_observation', models.TextField(blank=True, null=True, verbose_name='Observacion de solicitud')),
                ('delivery_observation', models.TextField(blank=True, null=True, verbose_name='Observacion de entrega')),
                ('return_observation', models.TextField(blank=True, null=True, verbose_name='Observacion de devolucion')),
                ('validation_observation', models.TextField(blank=True, null=True, verbose_name='Observacion de validacion')),
                ('borrower_user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='archive_loans_as_borrower', to=settings.AUTH_USER_MODEL, verbose_name='Usuario que tiene el expediente')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('delivered_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='archive_loans_delivered', to=settings.AUTH_USER_MODEL, verbose_name='Entregado por')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='archive_loans', to='employee.employee', verbose_name='Empleado')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='archive_loans_requested', to=settings.AUTH_USER_MODEL, verbose_name='Solicitado por')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='%(app_label)s_%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
            ],
            options={
                'verbose_name': 'Prestamo de Expediente Fisico',
                'verbose_name_plural': 'Prestamos de Expediente Fisico',
                'ordering': ['-requested_at'],
                'permissions': [('can_manage_archive_loans', 'Puede gestionar prestamos de archivo'), ('can_validate_archive_returns', 'Puede validar devoluciones de archivo'), ('can_create_archive_manual_loan', 'Puede registrar prestamos manuales de archivo')],
            },
        ),
        migrations.CreateModel(
            name='EmployeeArchiveNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=180, verbose_name='Titulo')),
                ('message', models.TextField(verbose_name='Mensaje')),
                ('url', models.CharField(blank=True, max_length=255, null=True, verbose_name='URL destino')),
                ('is_read', models.BooleanField(default=False, verbose_name='Leida')),
                ('read_at', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de lectura')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creacion')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='employee_archive_notifications', to=settings.AUTH_USER_MODEL, verbose_name='Destinatario')),
            ],
            options={
                'verbose_name': 'Notificacion de Archivo Digital',
                'verbose_name_plural': 'Notificaciones de Archivo Digital',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EmployeeArchiveLoanLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=60, verbose_name='Accion')),
                ('observation', models.TextField(blank=True, null=True, verbose_name='Observacion')),
                ('ip_address', models.CharField(blank=True, max_length=64, null=True, verbose_name='IP')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha')),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='archive_loan_logs', to=settings.AUTH_USER_MODEL, verbose_name='Usuario')),
                ('loan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='employee_archive.employeearchiveloan', verbose_name='Prestamo')),
            ],
            options={
                'verbose_name': 'Bitacora de Prestamo de Expediente',
                'verbose_name_plural': 'Bitacora de Prestamos de Expediente',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EmployeeArchiveAccessLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('VIEW_EMPLOYEE_ARCHIVE', 'Visualizo archivo digital del empleado'), ('VIEW_PDF', 'Visualizo PDF'), ('UPLOAD_PDF', 'Subio PDF')], max_length=40, verbose_name='Accion')),
                ('ip_address', models.CharField(blank=True, max_length=64, null=True, verbose_name='IP')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha')),
                ('archive_document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_logs', to='employee_archive.employeearchivedocument', verbose_name='Documento de archivo')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='archive_access_logs', to='employee.employee', verbose_name='Empleado')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='employee_archive_access_logs', to=settings.AUTH_USER_MODEL, verbose_name='Usuario')),
                ('version', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_logs', to='employee_archive.employeearchiveversion', verbose_name='Version')),
            ],
            options={
                'verbose_name': 'Auditoria de Archivo Digital',
                'verbose_name_plural': 'Auditoria de Archivo Digital',
                'ordering': ['-created_at'],
            },
        ),
    ]
