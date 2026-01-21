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