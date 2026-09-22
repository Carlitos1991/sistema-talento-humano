"""
Módulo de Modelos para la Estructura Organizacional e Institucional (SIGETH).
Define los niveles jerárquicos, las unidades administrativas (árbol organizacional),
los entregables por dependencia y el organigrama oficial institucional.
"""

from django.apps import apps
from django.db import models, transaction
from core.models import BaseModel


# ==============================================================================
# 1. NIVELES JERÁRQUICOS ORGANIZACIONALES
# ==============================================================================
class OrganizationalLevel(BaseModel):
    """
    Define los estratos o rangos jerárquicos de la institución (ej. Nivel 1: Alcaldía,
    Nivel 2: Direcciones Generales, Nivel 3: Jefaturas de Departamento, etc.).
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre del Nivel",
        error_messages={'unique': 'Ya existe un nivel jerárquico con este nombre.'}
    )
    level_order = models.PositiveIntegerField(
        db_index=True,
        verbose_name="Orden Jerárquico",
        help_text="1 para el nivel superior (ej. Alcaldía), números mayores para dependencias subordinadas."
    )

    class Meta:
        verbose_name = "Nivel Organizacional"
        verbose_name_plural = "Niveles Organizacionales"
        ordering = ['level_order']
        indexes = [
            models.Index(fields=['level_order', 'is_active'], name='idx_orglevel_order_active'),
        ]

    def __str__(self):
        return f"{self.name} (Nivel {self.level_order})"


# ==============================================================================
# 2. UNIDADES ADMINISTRATIVAS (ÁRBOL JERÁRQUICO)
# ==============================================================================
class AdministrativeUnit(BaseModel):
    """
    Representa una dependencia, departamento o dirección dentro de la institución.
    Implementa una estructura de árbol (self-referencing ForeignKey) y garantiza
    la regla de negocio de jefatura única e inmediata por funcionario.
    """
    level = models.ForeignKey(
        OrganizationalLevel,
        on_delete=models.PROTECT,
        related_name="units",
        verbose_name="Nivel Jerárquico"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Pertenece a (Unidad Padre)"
    )
    boss = models.ForeignKey(
        'employee.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_units',
        verbose_name="Jefe Inmediato / Responsable"
    )

    name = models.CharField(
        max_length=150,
        db_index=True,
        verbose_name="Nombre de la Unidad"
    )
    ruc = models.CharField(
        max_length=13,
        blank=True,
        null=True,
        verbose_name="RUC (Opcional)"
    )
    code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Código Interno / Partida Presupuestaria"
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Ubicación Física"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Teléfono / Extensión"
    )

    class Meta:
        verbose_name = "Unidad Administrativa"
        verbose_name_plural = "Unidades Administrativas"
        ordering = ['code', 'name']
        indexes = [
            models.Index(fields=['parent', 'is_active'], name='idx_unit_parent_active'),
            models.Index(fields=['boss', 'is_active'], name='idx_unit_boss_active'),
            models.Index(fields=['code', 'is_active'], name='idx_unit_code_active'),
        ]

    def __str__(self):
        return f"{self.name} ({self.level.name})"

    def get_full_path(self):
        """
        Retorna la ruta jerárquica completa de la unidad (ej. Alcaldía > DTH > Nómina).
        Evita recursión infinita protegiendo contra posibles ciclos en el árbol.
        """
        path = [self.name]
        current = self.parent
        visited = {self.pk}

        while current and current.pk not in visited:
            visited.add(current.pk)
            path.append(current.name)
            current = current.parent

        return " > ".join(reversed(path))

    def save(self, *args, **kwargs):
        """
        Regla de negocio garantizada:
        1. Un funcionario solo puede ser jefe titular de UNA unidad a la vez.
        2. Si se asigna un jefe que ya lideraba otra unidad, se libera la asignación previa.
        3. El flag `Employee.is_boss` se actualiza atómicamente de forma consistente.
        """
        previous_boss_id = None
        if self.pk:
            previous_boss_id = AdministrativeUnit.objects.filter(pk=self.pk).values_list('boss_id', flat=True).first()

        with transaction.atomic():
            super().save(*args, **kwargs)

            Employee = apps.get_model('employee', 'Employee')

            # 1. Si se asignó un jefe a esta unidad:
            if self.boss_id:
                # Quitarlo de cualquier otra unidad donde figuraba como jefe
                AdministrativeUnit.objects.filter(boss_id=self.boss_id).exclude(pk=self.pk).update(boss=None)

                # Asegurar que el empleado esté marcado como jefe
                Employee.objects.filter(pk=self.boss_id).update(is_boss=True)

            # 2. Si se quitó o cambió el jefe anterior:
            if previous_boss_id and previous_boss_id != self.boss_id:
                # Verificar si aún tiene a cargo otra unidad activa
                still_manages = AdministrativeUnit.objects.filter(boss_id=previous_boss_id, is_active=True).exists()
                if not still_manages:
                    Employee.objects.filter(pk=previous_boss_id).update(is_boss=False)


# ==============================================================================
# 3. ENTREGABLES DE LA UNIDAD ADMINISTRATIVA
# ==============================================================================
class Deliverable(BaseModel):
    """
    Productos, informes o entregables normativos requeridos periódicamente
    a la unidad administrativa para auditoría o evaluación de desempeño.
    """
    unit = models.ForeignKey(
        AdministrativeUnit,
        on_delete=models.CASCADE,
        related_name='deliverables',
        verbose_name="Unidad Administrativa"
    )
    name = models.CharField(
        max_length=255,
        verbose_name="Nombre del Entregable"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción / Especificaciones Requeridas"
    )

    class Meta:
        verbose_name = "Entregable"
        verbose_name_plural = "Entregables"
        ordering = ['name']
        indexes = [
            models.Index(fields=['unit', 'is_active'], name='idx_deliverable_unit_active'),
        ]

    def __str__(self):
        return f"{self.name} - {self.unit.name}"


# ==============================================================================
# 4. ORGANIGRAMA INSTITUCIONAL GRÁFICO
# ==============================================================================
class InstitutionOrganigram(models.Model):
    """
    Conserva la versión gráfica oficial aprobada del organigrama institucional
    para visualización con visor zoom/pan y descarga en alta resolución.
    """
    image = models.ImageField(
        upload_to='institution/organigram/',
        verbose_name="Imagen del Organigrama"
    )
    uploaded_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Actualización"
    )
    updated_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Subido por"
    )

    class Meta:
        verbose_name = "Organigrama Posicional"
        verbose_name_plural = "Organigramas"
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Organigrama - {self.uploaded_at.strftime('%d/%m/%Y')}"
