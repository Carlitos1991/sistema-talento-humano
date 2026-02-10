# --- vacation/models.py ---
import datetime
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

# Importaciones de otros módulos
from employee.models import Employee
from permitrequest.models import PermitRequest

# Constantes para lógica de cálculo
WORK_DAY_HOURS = 8
FACTOR_DAY = Decimal('1.0')
FACTOR_HOUR = Decimal('0.125')  # 1/8
FACTOR_MINUTE = Decimal('0.0020833')  # 1/480 aprox,


class VacationPeriod(models.Model):
    """
    Define los periodos fiscales o anuales (ej: 2023-2024).
    """
    name = models.CharField(max_length=9, verbose_name='Nombre Periodo', unique=True)
    is_active = models.BooleanField(verbose_name='Estado Periodo', default=True)

    class Meta:
        ordering = ['-pk']
        verbose_name = 'Periodo'
        verbose_name_plural = 'Periodos'

    def __str__(self):
        return self.name


class EmployeeVacationBalance(models.Model):
    """
    Tabla pivote que maneja el saldo de vacaciones de un empleado por periodo.
    """
    employee = models.ForeignKey(Employee, verbose_name='Empleado', on_delete=models.PROTECT)
    period = models.ForeignKey(VacationPeriod, verbose_name='Periodo', on_delete=models.PROTECT)
    is_active = models.BooleanField(verbose_name='Activo', default=True)

    # Usamos DecimalField para precisión financiera/contable
    total_days = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Total Días', default=0)
    balance_days = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Saldo Días', default=0)

    # Campos adicionales para el balance
    additional_days = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Días Adicionales (Balance Anterior)', default=0)
    vacation_days = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Días de Liquidación Vacaciones', default=0)
    permit_days = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Días de Permisos con Cargo', default=0)

    # Contadores históricos
    taken_days = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Días Tomados', default=0)
    
    # Observaciones automáticas
    observation = models.TextField(verbose_name='Observaciones', blank=True, default='')

    created_at = models.DateTimeField(verbose_name='Fecha creación', auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Creado por',
                                   null=True, blank=True)

    class Meta:
        ordering = ['-pk']
        verbose_name = 'Saldo Vacacional'
        verbose_name_plural = 'Saldos Vacacionales'
        unique_together = ('employee', 'period')  # Evita duplicados empleado-periodo

    def __str__(self):
        return f'{self.employee} - {self.period}'

    @property
    def days_int(self):
        return int(self.balance_days)

    @property
    def hours_int(self):
        remainder = self.balance_days - self.days_int
        return int(remainder / FACTOR_HOUR)

    @property
    def minutes_int(self):
        current_hours_dec = (self.balance_days - self.days_int)
        hours_only = int(current_hours_dec / FACTOR_HOUR)
        remainder_hours = current_hours_dec - (hours_only * FACTOR_HOUR)
        return int(remainder_hours * 60 * 8)


class VacationRequest(models.Model):
    """
    Solicitud específica de vacaciones.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pendiente')
        APPROVED = 'APPROVED', _('Aprobada')
        REJECTED = 'REJECTED', _('Rechazada')
        CANCELLED = 'CANCELLED', _('Anulada')

    employee = models.ForeignKey(Employee, verbose_name='Empleado', on_delete=models.PROTECT)
    balance_used = models.ForeignKey(EmployeeVacationBalance, verbose_name='Periodo Afectado', on_delete=models.PROTECT,
                                     null=True, blank=True)
    
    # Relación uno a uno con Acción de Personal
    personnel_action = models.OneToOneField('personnel_actions.PersonnelAction', 
                                           verbose_name='Acción de Personal',
                                           on_delete=models.PROTECT, 
                                           null=True, blank=True,
                                           related_name='vacation_request')

    start_date = models.DateField(verbose_name='Fecha Desde')
    end_date = models.DateField(verbose_name='Fecha Hasta')

    # Fechas de auditoría
    date_issued = models.DateField(default=datetime.date.today, verbose_name='Fecha Emisión')

    days_quantity = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Días Solicitados')

    # Auditoría real con ForeignKey
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='vacation_creator',
                                   verbose_name='Registrado por', on_delete=models.PROTECT, null=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='vacation_approver',
                                    verbose_name='Aprobado por', on_delete=models.PROTECT, null=True, blank=True)

    code = models.CharField(max_length=50, blank=True, null=True, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name='Estado')
    observation = models.TextField(verbose_name='Explicación/Motivo', blank=True, default="")

    class Meta:
        ordering = ['-pk']
        verbose_name = 'Solicitud de Vacación'
        verbose_name_plural = 'Solicitudes de Vacaciones'

    def __str__(self):
        return f'{self.employee} ({self.start_date})'


class VacationHistory(models.Model):
    """
    Log de auditoría de movimientos (Kárdex).
    """
    vacation_balance = models.ForeignKey(EmployeeVacationBalance, verbose_name='Saldo Afectado',
                                         on_delete=models.PROTECT)
    vacation_request = models.ForeignKey(VacationRequest, verbose_name='Solicitud Vacación', blank=True, null=True,
                                         on_delete=models.PROTECT)
    # Si integras permisos que descuentan vacaciones:
    permit_request = models.ForeignKey(PermitRequest, verbose_name='Permiso Relacionado', blank=True, null=True,
                                       on_delete=models.PROTECT)

    action_type = models.CharField(max_length=50, verbose_name='Tipo Acción')  # Ej: DESCUENTO, INCREMENTO, AJUSTE
    days_value = models.DecimalField(verbose_name='Valor en Días', max_digits=5, decimal_places=2)

    observation = models.TextField(verbose_name='Observaciones', blank=True, null=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Usuario', on_delete=models.PROTECT)
    created_at = models.DateTimeField(verbose_name='Fecha Registro', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Historial Vacación'
        verbose_name_plural = 'Historiales Vacaciones'

    def __str__(self):
        return f'{self.vacation_balance} - {self.action_type}'