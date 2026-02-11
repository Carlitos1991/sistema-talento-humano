from django.db import models
from django.conf import settings

from employee.models import Employee
from personnel_actions.models import PersonnelAction


class SanctionType(models.Model):
    """
    Define the configuration of sanction types (Amonestación, Suspensión, etc.)
    """
    name = models.CharField(verbose_name='Tipo de sanción', max_length=100)
    description = models.TextField(verbose_name='Descripción', blank=True, null=True)
    is_active = models.BooleanField(verbose_name='Estado', default=True)
    requires_attachment = models.BooleanField(verbose_name='¿Requiere adjunto?', default=False)

    class Meta:
        ordering = ['name']
        verbose_name = 'Tipo de Sanción'
        verbose_name_plural = 'Tipos de Sanciones'

    def __str__(self):
        return self.name


class Sanction(models.Model):
    """
    Records a sanction applied to an employee.
    """
    STATUS_CHOICES = [
        ('REGISTERED', 'Registrada'),
        ('ACTIVE', 'Activa'),
        ('COMPLETED', 'Cumplida'),
        ('CANCELED', 'Anulada'),
    ]

    SEVERITY_CHOICES = [
        ('MINOR', 'Leve'),
        ('MODERATE', 'Moderada'),
        ('SEVERE', 'Grave'),
        ('VERY_SEVERE', 'Muy Grave'),
    ]

    employee = models.ForeignKey(
        Employee, 
        verbose_name='Empleado', 
        on_delete=models.PROTECT, 
        related_name='sanctions'
    )
    sanction_type = models.ForeignKey(
        SanctionType, 
        verbose_name='Tipo de Sanción', 
        on_delete=models.PROTECT
    )

    # Sanction details
    sanction_number = models.CharField(
        verbose_name='Número de sanción', 
        max_length=50, 
        unique=True
    )
    severity = models.CharField(
        verbose_name='Gravedad', 
        max_length=20, 
        choices=SEVERITY_CHOICES, 
        default='MINOR'
    )
    description = models.TextField(verbose_name='Descripción de la falta')
    legal_basis = models.TextField(verbose_name='Base legal', blank=True, null=True)

    # Dates
    incident_date = models.DateField(verbose_name='Fecha del incidente')
    sanction_date = models.DateField(verbose_name='Fecha de la sanción')
    start_date = models.DateField(verbose_name='Fecha de inicio', blank=True, null=True)
    end_date = models.DateField(verbose_name='Fecha de fin', blank=True, null=True)

    # Duration (for suspensions)
    days = models.IntegerField(verbose_name='Días de suspensión', default=0)

    # Status
    status = models.CharField(
        verbose_name='Estado', 
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='REGISTERED'
    )

    # Attachment
    attachment_file = models.FileField(
        upload_to='documents/sanctions/%Y/%m/', 
        verbose_name='Documento adjunto',
        blank=True, 
        null=True
    )

    # Related Personnel Action
    personnel_action = models.ForeignKey(
        PersonnelAction,
        verbose_name='Acción de Personal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_sanctions'
    )

    # Observations
    observations = models.TextField(verbose_name='Observaciones', blank=True, null=True)

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de registro')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última modificación')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name='Registrado por',
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sanctions_created'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name='Modificado por',
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sanctions_updated'
    )

    class Meta:
        ordering = ['-sanction_date', '-sanction_number']
        verbose_name = 'Sanción'
        verbose_name_plural = 'Sanciones'
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['sanction_date']),
        ]

    def __str__(self):
        return f"{self.sanction_number} - {self.employee}"
