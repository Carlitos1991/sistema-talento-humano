from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel, CatalogItem
from apps.employee.models import Employee


# ==========================================
# 1. ESTRUCTURA PROGRAMÁTICA
# ==========================================

class Program(BaseModel):
    code = models.CharField(verbose_name="Código", max_length=20, unique=True, db_index=True)
    name = models.CharField(verbose_name="Nombre", max_length=255)

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

    # --- CORRECCIÓN DE RELATED_NAMES AQUÍ ---
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
        if self.status_item and self.status_item.code == 'VACANT' and self.current_employee:
            raise ValidationError("Una partida con estado VACANTE no puede tener un empleado asignado.")

        if self.remuneration < 0:
            raise ValidationError("La remuneración no puede ser negativa.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)