import datetime
from django.db import models
from django.conf import settings  # Para referenciar al usuario correctamente
from employee.models import Employee


from core.models import CatalogItem

class PermitType(models.Model):
    """
    Define la configuración de los tipos de permisos (Calamidad, Vacaciones, etc.)
    """
    name = models.CharField(verbose_name='Tipo de permiso', max_length=100)
    is_active = models.BooleanField(verbose_name='Estado', default=True)

    parent = models.ForeignKey('self', verbose_name='Dependiente de',
                               on_delete=models.CASCADE,
                               blank=True, null=True,
                               related_name='sub_types')

    needs_justification = models.BooleanField(verbose_name='¿Necesita justificar?', default=True)
    affects_vacation = models.BooleanField(verbose_name='¿Descuento a vacaciones?', default=False)
    requires_attachment = models.BooleanField(verbose_name='¿Adjuntar PDF?', default=False)

    class Meta:
        ordering = ['name']
        verbose_name = 'Tipo de permiso'
        verbose_name_plural = 'Tipos de permiso'

    def __str__(self):
        return self.name


class PermitRequest(models.Model):
    """
    Registra la solicitud de un permiso por parte de un empleado.
    """
    STATUS_CHOICES = [
        ('REQUESTED', 'Solicitado'),
        ('APPROVED', 'Aprobado'),
        ('REJECTED', 'Rechazado'),
        ('CANCELED', 'Anulado'),
    ]

    employee = models.ForeignKey(Employee, verbose_name='Empleado', on_delete=models.PROTECT, related_name='permits')
    permit_type = models.ForeignKey(PermitType, verbose_name='Tipo de Permiso', on_delete=models.PROTECT)

    # Fechas y Tiempos
    start_date = models.DateField(verbose_name='Fecha de inicio')
    end_date = models.DateField(verbose_name='Fecha fin', blank=True, null=True)
    start_time = models.TimeField(verbose_name='Hora de inicio', blank=True, null=True)
    end_time = models.TimeField(verbose_name='Hora de fin', blank=True, null=True)

    # Duración calculada o ingresada
    days = models.IntegerField(verbose_name='Días', default=0)
    hours = models.IntegerField(verbose_name='Horas', default=0)
    minutes = models.IntegerField(verbose_name='Minutos', default=0)

    status = models.CharField(verbose_name='Estado', max_length=20, choices=STATUS_CHOICES, default='REQUESTED')
    justification_file = models.FileField(upload_to='documents/permits/%Y/%m/', verbose_name='Justificativo PDF',
                                          blank=True, null=True)
    
    # Respuesta de aprobación o rechazo
    response_note = models.TextField(verbose_name='Motivo de aceptación/negativa', blank=True, null=True)
    response_date = models.DateTimeField(verbose_name='Fecha de respuesta', blank=True, null=True)
    response_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Respondido por',
                                   on_delete=models.SET_NULL, null=True, blank=True, related_name='permits_responded')

    # Auditoría (Mejor práctica: Usar User Model)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de registro')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última modificación')

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Registrado por',
                                   on_delete=models.SET_NULL, null=True, blank=True, related_name='permits_created')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Modificado por',
                                   on_delete=models.SET_NULL, null=True, blank=True, related_name='permits_updated')

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Solicitud de Permiso'
        verbose_name_plural = 'Solicitudes de Permisos'
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['start_date']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.permit_type}"

    @property
    def total_hours(self):
        """Propiedad calculada para reportes"""
        return (self.days * 8) + self.hours