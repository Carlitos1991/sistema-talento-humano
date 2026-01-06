from django.db import models
from django.core.exceptions import ValidationError
from core.models import BaseModel, CatalogItem
from person.models import Person
from institution.models import AdministrativeUnit


class Employee(BaseModel):
    """
    Vincula una Persona con la estructura organizacional.
    """
    person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        related_name='employee_profile',
        verbose_name="Persona"
    )

    area = models.ForeignKey(
        AdministrativeUnit,
        on_delete=models.PROTECT,
        related_name='employees',
        verbose_name="Área / Departamento",
        null=True, blank=True
    )

    employment_status = models.ForeignKey(
        CatalogItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'catalog__code': 'EMPLOYMENT_STATUS'},
        related_name='employees_by_status',
        verbose_name="Estado Laboral"
    )

    is_boss = models.BooleanField(
        default=False,
        verbose_name="Es Jefe/Director de Área",
        help_text="Marcar si esta persona es la máxima autoridad de la unidad asignada."
    )

    # MODIFICADO: null=True para permitir creación automática desde Persona
    date_joined = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha de Ingreso"
    )
    date_left = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha de Salida"
    )

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        ordering = ['person__last_name']

    def __str__(self):
        boss_label = " (JEFE)" if self.is_boss else ""
        # Manejo de error si person no está cargada aún (edge cases)
        try:
            return f"{self.person.last_name} {self.person.first_name}{boss_label}"
        except:
            return f"Empleado ID: {self.id}"

    @property
    def full_name(self):
        return self.person.full_name

    @property
    def institution_path(self):
        if self.area:
            return self.area.get_full_path()
        return "Sin Asignar"

    def clean(self):
        """
        Valida integridad de jefaturas.
        """
        super().clean()

        # 1. Validación original: No puede haber dos jefes marcados con is_boss en la misma área
        if self.is_boss and self.area and self.is_active:
            existing_boss = Employee.objects.filter(
                area=self.area,
                is_boss=True,
                is_active=True
            ).exclude(pk=self.pk).first()

            if existing_boss:
                raise ValidationError({
                    'is_boss': f"El área '{self.area.name}' ya tiene un jefe marcado: {existing_boss.full_name}."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

        # LOGICA DE SINCRONIZACIÓN AUTOMÁTICA (Opcional pero recomendada)
        # Si este empleado se marca como jefe, actualizamos la Unidad Administrativa
        if self.area and self.is_boss:
            unit = self.area
            if unit.boss != self:
                unit.boss = self
                unit.save()
