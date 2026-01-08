from django.db import models
from django.core.validators import MinValueValidator
from core.models import BaseModel, User
from employee.models import Employee

class Schedule(BaseModel):
    """
    Define horarios institucionales (diurnos, nocturnos o partidos).
    Hereda auditoría de core.BaseModel.
    """
    name = models.CharField(max_length=200, verbose_name='Nombre del Horario')
    description = models.TextField(blank=True, null=True, verbose_name='Descripción')

    # Jornada 1
    morning_start = models.TimeField(verbose_name='Inicio (Jornada 1)')
    morning_end = models.TimeField(verbose_name='Fin (Jornada 1)')
    morning_crosses_midnight = models.BooleanField(default=False, verbose_name='Cruza medianoche (J1)')

    # Jornada 2 (Opcional)
    afternoon_start = models.TimeField(blank=True, null=True, verbose_name='Inicio (Jornada 2)')
    afternoon_end = models.TimeField(blank=True, null=True, verbose_name='Fin (Jornada 2)')
    afternoon_crosses_midnight = models.BooleanField(default=False, verbose_name='Cruza medianoche (J2)')

    # Días Laborales
    monday = models.BooleanField(default=True, verbose_name='Lun')
    tuesday = models.BooleanField(default=True, verbose_name='Mar')
    wednesday = models.BooleanField(default=True, verbose_name='Mié')
    thursday = models.BooleanField(default=True, verbose_name='Jue')
    friday = models.BooleanField(default=True, verbose_name='Vie')
    saturday = models.BooleanField(default=False, verbose_name='Sáb')
    sunday = models.BooleanField(default=False, verbose_name='Dom')

    late_tolerance_minutes = models.IntegerField(default=15, validators=[MinValueValidator(0)], verbose_name='Tolerancia (min)')
    daily_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8.00, verbose_name='Horas Diarias')

    class Meta:
        db_table = 'schedule'
        verbose_name = 'Horario'
        verbose_name_plural = 'Horarios'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_continuous(self):
        return self.afternoon_start is None

class EmployeeScheduleHistory(BaseModel):
    """Rastrea la asignación de horarios a empleados."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='schedule_history')
    schedule = models.ForeignKey(Schedule, on_delete=models.PROTECT, related_name='assignments')
    start_date = models.DateField(verbose_name='Fecha Inicio')
    end_date = models.DateField(blank=True, null=True, verbose_name='Fecha Fin')
    reason = models.TextField(blank=True, null=True, verbose_name='Motivo')
    is_current = models.BooleanField(default=True, verbose_name='Actual')

    class Meta:
        db_table = 'employee_schedule_history'
        verbose_name = 'Asignación de Horario'
        ordering = ['-start_date']

    def save(self, *args, **kwargs):
        if self.is_current:
            EmployeeScheduleHistory.objects.filter(employee=self.employee, is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class ScheduleObservation(BaseModel):
    """Feriados u observaciones especiales."""
    name = models.CharField(max_length=200, verbose_name='Nombre')

    # REINCORPORADO: Campo faltante que causa el FieldError
    description = models.TextField(blank=True, null=True, verbose_name='Detalle/Descripción')

    start_date = models.DateField(verbose_name='Desde')
    end_date = models.DateField(verbose_name='Hasta')
    is_holiday = models.BooleanField(default=True, verbose_name='Es Feriado')

    class Meta:
        db_table = 'schedule_observation'
        verbose_name = 'Feriado/Observación'
        verbose_name_plural = 'Feriados y Observaciones'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date})"