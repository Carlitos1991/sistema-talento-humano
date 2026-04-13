import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from core.models import BaseModel
from employee.models import Employee


class BiometricDevice(BaseModel):
    """Representa el hardware físico de marcación."""
    name = models.CharField(max_length=250, unique=True, verbose_name="Nombre del Dispositivo")
    port = models.PositiveIntegerField(default=4370, verbose_name="Puerto")
    ip_address = models.GenericIPAddressField(verbose_name="Dirección IP")
    location = models.CharField(max_length=250, verbose_name="Ubicación Física")
    serial_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Serie")
    model_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Modelo")
    is_active = models.BooleanField(default=True, verbose_name="¿Está Activo?")

    class Meta:
        verbose_name = "Biométrico"
        verbose_name_plural = "Biométricos"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.ip_address})"


class BiometricLoad(BaseModel):
    """Log de cada vez que se descargan datos del dispositivo."""
    biometric = models.ForeignKey(BiometricDevice, on_delete=models.PROTECT, related_name='loads',
                                  verbose_name="Biométrico")
    num_records = models.IntegerField(default=0, verbose_name="Registros Cargados")
    reason = models.TextField(blank=True, null=True, verbose_name="Motivo/Observación")
    load_type = models.CharField(max_length=50, default="AUTOMATIC", verbose_name="Tipo de Carga")

    class Meta:
        verbose_name = "Carga de Biométrico"
        verbose_name_plural = "Cargas de Biométricos"
        ordering = ['-created_at']


class AttendanceRegistry(BaseModel):
    """Registro individual de cada marcación."""
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='attendance_records',
                                 verbose_name="Empleado")
    biometric_load = models.ForeignKey(BiometricLoad, on_delete=models.CASCADE, related_name='details')
    employee_id_bio = models.CharField(max_length=20, verbose_name="ID en Biométrico")
    registry_date = models.DateTimeField(verbose_name="Fecha/Hora de Marcación")

    class Meta:
        verbose_name = "Registro de Asistencia"
        verbose_name_plural = "Registros de Asistencia"
        ordering = ['-registry_date']


class OfflineAttendanceRegistry(BaseModel):
    """Bitácora de marcaciones capturadas en PWA/IndexedDB y sincronizadas después."""

    class PunchType(models.TextChoices):
        INCOME = 'INCOME', 'Ingreso'
        EXIT = 'EXIT', 'Salida'

    class SyncStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        SYNCED = 'SYNCED', 'Sincronizado'
        ERROR = 'ERROR', 'Error'

    class SourceType(models.TextChoices):
        PWA = 'PWA', 'PWA'
        WEB = 'WEB', 'Web'
        MOBILE = 'MOBILE', 'Móvil'

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='offline_attendance_records',
        verbose_name='Empleado',
    )
    punch_type = models.CharField(
        max_length=20,
        choices=PunchType.choices,
        verbose_name='Tipo de Marcación',
    )
    offline_uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name='UUID Offline',
    )
    captured_at = models.DateTimeField(verbose_name='Fecha/Hora Capturada')
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        verbose_name='Latitud',
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        verbose_name='Longitud',
    )
    accuracy_m = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Precisión GPS (m)',
    )
    location_text = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Ubicación Referencial',
    )
    sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
        verbose_name='Estado de Sincronización',
    )
    synced_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de Sincronización',
    )
    sync_error = models.TextField(
        blank=True,
        null=True,
        verbose_name='Error de Sincronización',
    )
    source = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.PWA,
        verbose_name='Origen',
    )

    class Meta:
        db_table = 'biometric_offline_attendance'
        verbose_name = 'Marcación Offline'
        verbose_name_plural = 'Marcaciones Offline'
        ordering = ['-captured_at']
        indexes = [
            models.Index(fields=['sync_status', 'captured_at']),
            models.Index(fields=['employee', 'captured_at']),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.latitude is None:
            errors['latitude'] = 'La latitud es obligatoria.'
        if self.longitude is None:
            errors['longitude'] = 'La longitud es obligatoria.'
        if self.captured_at is None:
            errors['captured_at'] = 'La fecha y hora de captura son obligatorias.'
        if self.accuracy_m is not None and self.accuracy_m < 0:
            errors['accuracy_m'] = 'La precisión GPS no puede ser negativa.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.location_text:
            self.location_text = self.location_text.strip()
        if self.sync_error:
            self.sync_error = self.sync_error.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.employee_id} - {self.get_punch_type_display()} - {self.captured_at}'


class BiometricCommand(BaseModel):
    """Cola de comandos enviados al dispositivo via ADMS"""
    device = models.ForeignKey(BiometricDevice, on_delete=models.CASCADE, related_name='commands')
    command = models.TextField(verbose_name="Comando Técnico")  # Ej: DATA QUERY ATTLOG
    status = models.CharField(max_length=20, default='PENDING', verbose_name="Estado")  # PENDING, SENT, SUCCESS, ERROR
    execution_time = models.DateTimeField(null=True, blank=True)
    return_value = models.TextField(null=True, blank=True)  # Lo que responde el reloj

    def __str__(self):
        return f"{self.device.name} - {self.command} ({self.status})"
