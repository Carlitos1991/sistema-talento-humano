from django.db import models
from core.models import BaseModel


class OrganizationalLevel(BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Nivel")
    level_order = models.PositiveIntegerField(
        verbose_name="Orden Jerárquico",
        help_text="1 para la cabeza (Institución), números mayores para dependencias."
    )

    class Meta:
        verbose_name = "Nivel Organizacional"
        verbose_name_plural = "Niveles Organizacionales"
        ordering = ['level_order']

    def __str__(self):
        return self.name


class AdministrativeUnit(BaseModel):
    objects = None
    level = models.ForeignKey(
        OrganizationalLevel,
        on_delete=models.PROTECT,
        verbose_name="Nivel Jerárquico",
        related_name="units"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Pertenece a (Padre)"
    )

    # --- NUEVO CAMPO SOLICITADO: JEFE INMEDIATO ---
    boss = models.ForeignKey(
        'employee.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_units',
        verbose_name="Jefe Inmediato / Responsable"
    )

    name = models.CharField(max_length=150, verbose_name="Nombre de la Unidad")
    ruc = models.CharField(max_length=13, blank=True, null=True, verbose_name="RUC (Opcional)")
    code = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código Interno/Partida")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Ubicación Física")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono Extensión")

    class Meta:
        verbose_name = "Unidad Administrativa"
        verbose_name_plural = "Unidades Administrativas"
        ordering = ['level__level_order', 'name']

    def __str__(self):
        return f"{self.name} ({self.level.name})"

    def get_full_path(self):
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name