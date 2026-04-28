from django.db import models
from django.core.validators import MinValueValidator
from core.models import BaseModel, User
from employee.models import Employee
from django.db.models import Q

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


def get_employee_schedule_for_date(employee, target_date):
    """Devuelve el objeto `Schedule` asignado al `employee` para la fecha `target_date`.
    Busca en `EmployeeScheduleHistory` la última asignación cuyo `start_date` sea
    menor o igual a `target_date` y cuyo `end_date` sea nulo o mayor o igual a
    `target_date`. Retorna `None` si no hay coincidencias.
    """
    try:
        qs = EmployeeScheduleHistory.objects.filter(employee=employee).filter(
            start_date__lte=target_date
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=target_date)).select_related('schedule').order_by('-start_date')
        row = qs.first()
        sched = row.schedule if row else None
        # Si no hay asignación, retornar None
        if not sched:
            return None

        # Buscar cambios del propio horario (versiones) aplicables a la fecha
        try:
            class_name = 'ScheduleChangeHistory'
            SCH = globals().get('ScheduleChangeHistory', None)
            if SCH is None:
                # import dinámico si el modelo se definió más abajo
                from .models import ScheduleChangeHistory as SCH2
                SCH = SCH2
        except Exception:
            SCH = None

        if SCH:
            try:
                hist = SCH.objects.filter(schedule=sched, effective_from__lte=target_date).order_by('-effective_from').first()
                if hist:
                    # Construir objeto ligero con atributos esperados por el código (compatibilidad)
                    from types import SimpleNamespace
                    obj = SimpleNamespace()
                    # Copiar campos relevantes
                    obj.id = sched.id
                    obj.name = sched.name
                    obj.morning_start = hist.morning_start
                    obj.morning_end = hist.morning_end
                    obj.morning_crosses_midnight = hist.morning_crosses_midnight
                    obj.afternoon_start = hist.afternoon_start
                    obj.afternoon_end = hist.afternoon_end
                    obj.afternoon_crosses_midnight = hist.afternoon_crosses_midnight
                    obj.monday = hist.monday
                    obj.tuesday = hist.tuesday
                    obj.wednesday = hist.wednesday
                    obj.thursday = hist.thursday
                    obj.friday = hist.friday
                    obj.saturday = hist.saturday
                    obj.sunday = hist.sunday
                    obj.late_tolerance_minutes = hist.late_tolerance_minutes
                    obj.daily_hours = hist.daily_hours
                    # is_continuous property
                    obj.is_continuous = (obj.afternoon_start is None)
                    return obj
            except Exception:
                pass

        return sched
    except Exception:
        return None


class ScheduleChangeHistory(BaseModel):
    """Historial de cambios de una definición de `Schedule`.
    Permite registrar la versión del horario vigente desde una fecha.
    """
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='change_history')
    effective_from = models.DateField(verbose_name='Vigente Desde')

    # Copia de campos de Schedule
    morning_start = models.TimeField(verbose_name='Inicio (Jornada 1)')
    morning_end = models.TimeField(verbose_name='Fin (Jornada 1)')
    morning_crosses_midnight = models.BooleanField(default=False, verbose_name='Cruza medianoche (J1)')
    afternoon_start = models.TimeField(blank=True, null=True, verbose_name='Inicio (Jornada 2)')
    afternoon_end = models.TimeField(blank=True, null=True, verbose_name='Fin (Jornada 2)')
    afternoon_crosses_midnight = models.BooleanField(default=False, verbose_name='Cruza medianoche (J2)')
    monday = models.BooleanField(default=True, verbose_name='Lun')
    tuesday = models.BooleanField(default=True, verbose_name='Mar')
    wednesday = models.BooleanField(default=True, verbose_name='Mié')
    thursday = models.BooleanField(default=True, verbose_name='Jue')
    friday = models.BooleanField(default=True, verbose_name='Vie')
    saturday = models.BooleanField(default=False, verbose_name='Sáb')
    sunday = models.BooleanField(default=False, verbose_name='Dom')
    late_tolerance_minutes = models.IntegerField(default=15, validators=[MinValueValidator(0)], verbose_name='Tolerancia (min)')
    daily_hours = models.DecimalField(max_digits=4, decimal_places=2, default=8.00, verbose_name='Horas Diarias')
    reason = models.TextField(blank=True, null=True, verbose_name='Motivo del Cambio')

    class Meta:
        db_table = 'schedule_change_history'
        verbose_name = 'Historial de Cambio de Horario'
        verbose_name_plural = 'Historial de Cambios de Horarios'
        ordering = ['-effective_from']

    def __str__(self):
        return f"{self.schedule.name} - Vigente desde {self.effective_from}"