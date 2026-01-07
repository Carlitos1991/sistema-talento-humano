from django.db import models
from django.core.exceptions import ValidationError
from core.models import BaseModel, CatalogItem, User
from employee.models import Employee


# ==========================================
# 1. ESTRUCTURA PROGRAMÁTICA
# ==========================================

class Program(BaseModel):
    code = models.CharField(verbose_name="Código", max_length=20, unique=True, db_index=True)
    name = models.CharField(verbose_name="Nombre", max_length=255)
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        ordering = ['code']
        verbose_name = 'Área-Programa'
        verbose_name_plural = 'Áreas-Programas'

    def __str__(self):
        return f'{self.code} - {self.name}'


class Subprogram(BaseModel):
    program = models.ForeignKey(Program, verbose_name='Área/Programa', on_delete=models.PROTECT,
                                related_name='subprograms')
    code = models.CharField(verbose_name="Código", max_length=20, db_index=True)
    name = models.CharField(verbose_name="Nombre", max_length=255)
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        ordering = ['code']
        verbose_name = 'Subprograma'
        verbose_name_plural = 'Subprogramas'
        unique_together = [['program', 'code']]

    def __str__(self):
        return f'{self.code} - {self.name}'


class Project(BaseModel):
    subprogram = models.ForeignKey(Subprogram, verbose_name='Subprograma', on_delete=models.PROTECT,
                                   related_name='projects')
    code = models.CharField(verbose_name="Código", max_length=20, db_index=True)
    name = models.CharField(verbose_name="Nombre", max_length=255)
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        ordering = ['code']
        verbose_name = 'Proyecto'
        verbose_name_plural = 'Proyectos'
        unique_together = [['subprogram', 'code']]

    def __str__(self):
        return f'{self.code} - {self.name}'


class Activity(BaseModel):
    project = models.ForeignKey(Project, verbose_name='Proyecto', on_delete=models.PROTECT, related_name='activities')
    code = models.CharField(verbose_name="Código", max_length=20, db_index=True)
    name = models.CharField(verbose_name="Nombre", max_length=255)
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        ordering = ['code']
        verbose_name = 'Actividad'
        verbose_name_plural = 'Actividades'
        unique_together = [['project', 'code']]

    def __str__(self):
        return f'{self.code} - {self.name}'

    def get_full_hierarchy_name(self):
        return f"{self.project.subprogram.program.code}.{self.project.subprogram.code}.{self.project.code}.{self.code}"


# ==========================================
# 2. PARTIDA PRESUPUESTARIA
# ==========================================

class BudgetLine(BaseModel):
    activity = models.ForeignKey(Activity, on_delete=models.PROTECT, verbose_name='Actividad',
                                 related_name='budget_lines')

    code = models.CharField(verbose_name="Código Partida", max_length=50, db_index=True)
    number_individual = models.CharField(verbose_name="Partida Individual", max_length=20, unique=True, blank=True,
                                         null=True, db_index=True)

    remuneration = models.DecimalField(verbose_name='RMU', max_digits=12, decimal_places=2)
    observation = models.TextField(verbose_name="Observaciones", blank=True, null=True)

    current_employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, verbose_name='Custodio/Ocupante',
        blank=True, null=True, related_name='current_budget_line'
    )

    # Cada ForeignKey a CatalogItem debe tener un 'related_name' único

    status_item = models.ForeignKey(
        CatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'BUDGET_STATUS'},
        verbose_name='Estado',
        related_name='budget_lines_status'  # Único
    )

    group_item = models.ForeignKey(
        CatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'BUDGET_GROUP'},
        verbose_name='Grupo Ocupacional', blank=True, null=True,
        related_name='budget_lines_group'  # Único
    )

    category_item = models.ForeignKey(
        CatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'BUDGET_CATEGORY'},
        verbose_name='Categoría', blank=True, null=True,
        related_name='budget_lines_category'  # Único
    )

    position_item = models.ForeignKey(
        CatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'JOB_POSITIONS'},
        verbose_name='Cargo Estructural', blank=True, null=True,
        related_name='budget_lines_position'  # Único
    )

    grade_item = models.ForeignKey(
        CatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'BUDGET_GRADE'},
        verbose_name='Grado', blank=True, null=True,
        related_name='budget_lines_grade'  # Único
    )

    regime_item = models.ForeignKey(
        CatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'LABOR_REGIMES'},
        verbose_name='Régimen Laboral', blank=True, null=True,
        related_name='budget_lines_regime'  # Único
    )

    spending_type_item = models.ForeignKey(
        CatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'BUDGET_SPENDING_TYPE'},
        verbose_name='Tipo de Gasto', blank=True, null=True,
        related_name='budget_lines_spending'  # Único
    )

    class Meta:
        ordering = ['code', 'number_individual']
        verbose_name = 'Partida Presupuestaria'
        verbose_name_plural = 'Partidas Presupuestarias'
        permissions = [
            ("view_salary", "Puede ver remuneraciones"),
        ]

    def __str__(self):
        position = self.position_item.name if self.position_item else "VACANTE"
        return f'{self.number_individual or "S/N"} - {position}'

    def clean(self):
        if hasattr(self, 'status_item') and self.status_item:
            if self.status_item.code == 'LIBRE' and self.current_employee:
                raise ValidationError("Una partida con estado LIBRE no puede tener un empleado asignado.")

        if self.remuneration and self.remuneration < 0:
            raise ValidationError("La remuneración no puede ser negativa.")

    def save(self, *args, **kwargs):
        user = kwargs.pop('modified_by', None)

        if self.pk:
            # Obtenemos la versión anterior de la base de datos
            old_obj = BudgetLine.objects.get(pk=self.pk)

            # Lista de campos a auditar
            fields_to_watch = {
                'remuneration': 'Remuneración',
                'position_item': 'Cargo Estructural',
                'status_item': 'Estado',
            }

            for field, label in fields_to_watch.items():
                old_val = getattr(old_obj, field)
                new_val = getattr(self, field)

                if old_val != new_val:
                    BudgetModificationHistory.objects.create(
                        budget_line=self,
                        modified_by=user,
                        modification_type='UPDATE',
                        field_name=label,
                        old_value=str(old_val),
                        new_value=str(new_val),
                        reason="Cambio desde el formulario de edición"
                    )

        super().save(*args, **kwargs)


# ==========================================
# 3. HISTORIALES Y TRAZABILIDAD
# ==========================================

class BudgetModificationHistory(models.Model):
    """
    Rastrea cambios en la estructura de la partida.
    """
    budget_line = models.ForeignKey(BudgetLine, on_delete=models.PROTECT, verbose_name='Partida',
                                    related_name='modifications')
    modification_date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Modificación')
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, verbose_name='Modificado por',
                                    related_name='budget_modifications', null=True, blank=True)

    # Tipo de modificación
    modification_type = models.CharField(max_length=50, verbose_name='Tipo de Modificación',
                                         blank=True, null=True,
                                         choices=[
                                             ('CREATE', 'Creación'),
                                             ('UPDATE', 'Actualización'),
                                             ('STATUS_CHANGE', 'Cambio de Estado'),
                                             ('ASSIGNMENT', 'Asignación de Persona'),
                                             ('RELEASE', 'Liberación de Persona'),
                                         ])

    field_name = models.CharField(max_length=100, verbose_name='Campo modificado', blank=True, null=True)
    old_value = models.TextField(verbose_name='Valor anterior', blank=True, null=True)
    new_value = models.TextField(verbose_name='Valor nuevo', blank=True, null=True)
    reason = models.TextField(verbose_name="Motivo del Cambio", blank=True, null=True)

    class Meta:
        ordering = ['-modification_date']
        verbose_name = 'Historial de Modificación'
        verbose_name_plural = 'Historiales de Modificaciones'

    def __str__(self):
        return f"{self.modification_type} - {self.budget_line.code} ({self.modification_date.strftime('%d/%m/%Y')})"


class BudgetAssignmentHistory(models.Model):
    """
    Rastrea qué personas han ocupado esta partida y cuándo.
    """
    budget_line = models.ForeignKey(BudgetLine, on_delete=models.PROTECT, verbose_name='Partida',
                                    related_name='assignments')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, verbose_name='Empleado',
                                 related_name='budget_history')

    start_date = models.DateField(verbose_name='Fecha Inicio')
    end_date = models.DateField(verbose_name='Fecha Fin', blank=True, null=True)

    is_current = models.BooleanField(default=False, verbose_name="Es asignación actual")
    observation = models.TextField(verbose_name="Observación de salida", blank=True, null=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Historial de Asignación'
        verbose_name_plural = 'Historiales de Asignaciones'

    def __str__(self):
        return f"{self.employee} en {self.budget_line} ({self.start_date})"

    def clean(self):
        """
        Validación para asegurar que un empleado no tenga dos partidas activas simultáneamente.
        """
        from django.core.exceptions import ValidationError

        if self.is_current and not self.end_date:
            # Buscar si este empleado ya tiene otra asignación activa
            existing_assignment = BudgetAssignmentHistory.objects.filter(
                employee=self.employee,
                is_current=True,
                end_date__isnull=True
            ).exclude(pk=self.pk).first()

            if existing_assignment:
                partida_info = existing_assignment.budget_line.number_individual or existing_assignment.budget_line.code
                raise ValidationError({
                    'employee': f'Este empleado ya tiene asignada la partida {partida_info}. Debe liberar primero esa partida.'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
