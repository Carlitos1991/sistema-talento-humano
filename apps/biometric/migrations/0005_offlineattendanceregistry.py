# Generated manually to add offline attendance registry for PWA/IndexedDB sync.
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('biometric', '0004_alter_biometricdevice_is_active'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfflineAttendanceRegistry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='Estado')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última Modificación')),
                ('offline_uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='UUID Offline')),
                ('punch_type', models.CharField(choices=[('INCOME', 'Ingreso'), ('EXIT', 'Salida')], max_length=20, verbose_name='Tipo de Marcación')),
                ('captured_at', models.DateTimeField(verbose_name='Fecha/Hora Capturada')),
                ('latitude', models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(-90), django.core.validators.MaxValueValidator(90)], verbose_name='Latitud')),
                ('longitude', models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)], verbose_name='Longitud')),
                ('accuracy_m', models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Precisión GPS (m)')),
                ('location_text', models.CharField(blank=True, max_length=255, null=True, verbose_name='Ubicación Referencial')),
                ('sync_status', models.CharField(choices=[('PENDING', 'Pendiente'), ('SYNCED', 'Sincronizado'), ('ERROR', 'Error')], default='PENDING', max_length=20, verbose_name='Estado de Sincronización')),
                ('synced_at', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de Sincronización')),
                ('sync_error', models.TextField(blank=True, null=True, verbose_name='Error de Sincronización')),
                ('source', models.CharField(choices=[('PWA', 'PWA'), ('WEB', 'Web'), ('MOBILE', 'Móvil')], default='PWA', max_length=20, verbose_name='Origen')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='offline_attendance_records', to='employee.employee', verbose_name='Empleado')),
            ],
            options={
                'verbose_name': 'Marcación Offline',
                'verbose_name_plural': 'Marcaciones Offline',
                'db_table': 'biometric_offline_attendance',
                'ordering': ['-captured_at'],
                'indexes': [
                    models.Index(fields=['sync_status', 'captured_at'], name='bio_offline_sync_captured_idx'),
                    models.Index(fields=['employee', 'captured_at'], name='bio_offline_employee_captured_idx'),
                ],
            },
        ),
    ]
