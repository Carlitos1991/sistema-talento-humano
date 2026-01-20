from django.db import models

from core.models import BaseModel, Authorities
from employee.models import Employee
from institution.models import AdministrativeUnit


# ==============================================================================
# SISTEMA DE CATÁLOGOS DINÁMICOS PARA MANUAL DE FUNCIONES
# ==============================================================================

class ManualCatalog(BaseModel):
    """
    Catálogos genéricos para el módulo de manual de funciones.
    Ejemplos: 'Niveles de Complejidad', 'Roles del Puesto', 'Verbos de Acción'.
    """
    objects = None
    name = models.CharField(max_length=255, verbose_name="Nombre del Catálogo")
    code = models.CharField(max_length=100, unique=True, verbose_name="Código Interno")
    description = models.TextField(blank=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Catálogo de Manual"
        verbose_name_plural = "Catálogos de Manual"
        permissions = [
            ("can_admin", "Puede administrar Catálogos de Manual"),
        ]

    def __str__(self) -> str:
        return self.name


class ManualCatalogItem(BaseModel):
    """
    Items individuales de cada catálogo.
    Ejemplo: Bajo, Medio, Alto dentro del catálogo de 'Niveles de Complejidad'.
    """
    objects = None
    catalog = models.ForeignKey(
        ManualCatalog,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Catálogo"
    )
    name = models.CharField(max_length=255, verbose_name="Nombre del Item")
    code = models.CharField(max_length=100, verbose_name="Código Técnico")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción/Observación")
    target_role = models.ForeignKey(
        'ValuationNode',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='catalog_items',
        limit_choices_to={'node_type': 'ROLE'},
        verbose_name="Rol Permitido (Estructura de Valoración)"
    )

    class Meta:
        ordering = ['catalog', 'name']
        verbose_name = "Item de Catálogo"
        verbose_name_plural = "Items de Catálogo"
        unique_together = ('catalog', 'code')

    def __str__(self) -> str:
        return f"{self.catalog.name} - {self.name}"


# ==============================================================================
# MATRIZ OCUPACIONAL (NORMA MDT-2025-108)
# ==============================================================================

class OccupationalMatrix(BaseModel):
    """
    Representa la matriz de clasificación de los Art. 19 y 20 de la norma.
    """
    objects = None
    occupational_group = models.CharField(max_length=100, verbose_name="Grupo Ocupacional (Ej: SP1)")
    grade = models.PositiveIntegerField(verbose_name="Grado de la Escala")
    remuneration = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="R.M.U.")

    required_role = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'JOB_ROLES'},
        related_name='matrix_by_roles',
        verbose_name="Rol del Puesto"
    )
    required_decision = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'DECISION_LEVELS'},
        related_name='matrix_by_decisions',
        verbose_name="Nivel de Decisiones",
        null=True, blank=True  # Temporalmente opcionales para la migración
    )
    required_impact = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'IMPACT_LEVELS'},
        related_name='matrix_by_impact',
        verbose_name="Nivel de Impacto",
        null=True, blank=True
    )
    complexity_level = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'COMPLEXITY_LEVELS'},
        related_name='matrix_by_complexities',
        verbose_name="Nivel de Complejidad"
    )
    minimum_instruction = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'INSTRUCTION_LEVELS'},
        related_name='matrix_by_instructions',
        verbose_name="Instrucción Formal Mínima"
    )

    minimum_experience_months = models.PositiveIntegerField(verbose_name="Experiencia Mínima (Meses)")

    class Meta:
        verbose_name = "Matriz Ocupacional"
        verbose_name_plural = "Matrices Ocupacionales"
        unique_together = ('occupational_group', 'grade')
        permissions = [
            ("can_admin", "Puede administrar Matriz Ocupacional"),
        ]

    def __str__(self) -> str:
        return f"{self.occupational_group} - ${self.remuneration}"


# ==============================================================================
# PERFIL DE PUESTO (MODELO UNIFICADO)
# ==============================================================================

class JobProfile(BaseModel):
    """
    Modelo principal para el Perfil de Puesto normativa 2025.
    """
    objects = None
    position_code = models.CharField(max_length=50, blank=True, null=True, unique=True,
                                     verbose_name="Código Posicional")
    specific_job_title = models.CharField(max_length=255, verbose_name="Cargo Específico")
    administrative_unit = models.ForeignKey(
        AdministrativeUnit, on_delete=models.PROTECT, related_name='job_profiles', verbose_name="Unidad Administrativa"
    )
    referential_employee = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Empleado Referencial"
    )

    mission = models.TextField(verbose_name="Misión")
    interface_relations = models.TextField(verbose_name="Relaciones Internas/Externas")

    required_instruction = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'INSTRUCTION_LEVELS'},
        related_name='profiles_by_instruction',
        verbose_name="Nivel de Instrucción",
        null=True, blank=True
    )
    decision_making = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'DECISION_LEVELS'},
        related_name='profiles_by_decision',
        verbose_name="Toma de Decisiones",
        null=True, blank=True
    )
    management_impact = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'IMPACT_LEVELS'},
        related_name='profiles_by_impact',
        verbose_name="Impacto de Gestión",
        null=True, blank=True
    )
    final_complexity_level = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'COMPLEXITY_LEVELS'},
        related_name='profiles_by_complexity',
        verbose_name="Complejidad Resultante",
        null=True, blank=True
    )
    job_role = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'JOB_ROLES'},
        related_name='profiles_by_role',
        verbose_name="Rol Asignado",
        null=True, blank=True
    )

    knowledge_area = models.TextField(verbose_name="Área de Conocimiento")
    required_experience_months = models.PositiveIntegerField(default=0, verbose_name="Experiencia (Meses)")
    experience_details = models.TextField(verbose_name="Detalle de Experiencia")
    training_topic = models.TextField(verbose_name="Temática de Capacitación", blank=True, null=True)

    occupational_classification = models.ForeignKey(
        OccupationalMatrix, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Clasificación Matriz"
    )

    competencies = models.ManyToManyField('Competency', through='ProfileCompetency')

    prepared_by = models.ForeignKey(Authorities, related_name='prepared_profiles', on_delete=models.PROTECT, null=True)
    reviewed_by = models.ForeignKey(Authorities, related_name='reviewed_profiles', on_delete=models.PROTECT, null=True)
    approved_by = models.ForeignKey(Authorities, related_name='approved_profiles', on_delete=models.PROTECT, null=True)

    legalized_document = models.FileField(upload_to='profiles/legalized/', null=True, blank=True, verbose_name="Perfil Legalizado (Escaneado)")

    @property
    def is_legalized(self):
        """Retorna True si tiene las 3 firmas de legalización asignadas"""
        return bool(self.prepared_by and self.reviewed_by and self.approved_by)

    class Meta:
        verbose_name = "Perfil de Puesto"
        verbose_name_plural = "Perfiles de Puesto"
        permissions = [
            ("can_admin", "Puede administrar Perfiles de Puesto"),
        ]

    def __str__(self) -> str:
        return f"{self.specific_job_title}"


# ==============================================================================
# DETALLES: ACTIVIDADES Y COMPETENCIAS
# ==============================================================================

class JobActivity(BaseModel):
    """
    Actividades esenciales del puesto.
    """
    profile = models.ForeignKey(JobProfile, on_delete=models.CASCADE, related_name='activities')

    # SOLUCIÓN AL ERROR: related_name explícitos
    action_verb = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'ACTION_VERBS'},
        related_name='activity_action_verbs',
        verbose_name="Verbo de Acción"
    )
    additional_knowledge = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Conocimientos Adicionales"
    )

    description = models.TextField(verbose_name="Descripción")

    class Meta:
        verbose_name = "Actividad Esencial"
        verbose_name_plural = "Actividades Esenciales"


class Competency(BaseModel):
    """
    Diccionario maestro de competencias técnicas y conductuales.
    """
    objects = None
    COMPETENCY_TYPES = (
        ('TECHNICAL', 'Técnica'),
        ('BEHAVIORAL', 'Conductual'),
        ('TRANSVERSAL', 'Transversales'),
    )
    name = models.CharField(max_length=150, verbose_name="Nombre de la Competencia")
    type = models.CharField(max_length=20, choices=COMPETENCY_TYPES, verbose_name="Tipo")
    definition = models.TextField(verbose_name="Definición de la Competencia")

    # Nivel sugerido vinculado a catálogo
    suggested_level = models.ForeignKey(
        ManualCatalogItem, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'catalog__code': 'COMPLEXITY_LEVELS'},
        verbose_name="Nivel Sugerido"
    )

    class Meta:
        verbose_name = "Competencia"
        verbose_name_plural = "Diccionario de Competencias"
        permissions = [
            ("can_admin", "Puede administrar Competencias"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_type_display()})"


class ProfileCompetency(models.Model):
    """
    Tabla intermedia para asignar competencias a perfiles con comportamientos específicos.
    """
    profile = models.ForeignKey(JobProfile, on_delete=models.CASCADE)
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE)
    observable_behavior = models.TextField(verbose_name="Comportamiento Observable", blank=True, null=True)

    class Meta:
        verbose_name = "Competencia del Perfil"
        verbose_name_plural = "Competencias del Perfil"


class ValuationNode(BaseModel):
    """
    Representa un nodo en la estructura jerárquica de valoración.
    Niveles: 1.Rol -> 2.Instrucción -> 3.Experiencia -> 4.Decisiones
            -> 5.Impacto -> 6.Complejidad -> 7.Resultado (Clasificación)
    """

    objects = None

    class NodeType(models.TextChoices):
        ROLE = 'ROLE', 'Rol de Puesto'
        INSTRUCTION = 'INSTRUCTION', 'Instrucción Formal'
        EXPERIENCE = 'EXPERIENCE', 'Experiencia'
        DECISION = 'DECISION', 'Nivel de Decisiones'
        IMPACT = 'IMPACT', 'Nivel de Impacto'
        COMPLEXITY = 'COMPLEXITY', 'Nivel de Complejidad'
        RESULT = 'RESULT', 'Grupo Ocupacional (Resultado)'

    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='children',
        verbose_name="Nodo Padre"
    )
    node_type = models.CharField(
        max_length=20, choices=NodeType.choices,
        verbose_name="Tipo de Nivel"
    )

    # El valor real (vinculado a tus catálogos)
    catalog_item = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        null=True, blank=True, verbose_name="Valor del Catálogo"
    )
    name_extra = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Descripción personalizada"
    )

    # Solo se llena en el último nivel (RESULT) para dar el grado y sueldo
    occupational_classification = models.ForeignKey(
        OccupationalMatrix, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Clasificación Salarial"
    )

    class Meta:
        verbose_name = "Nodo de Valoración"
        verbose_name_plural = "Estructura de Valoración"
        ordering = ['node_type']
        permissions = [
            ("can_admin", "Puede administrar Estructura de Valoración"),
        ]

    def __str__(self):
        return f"{self.get_node_type_display()}: {self.catalog_item.name if self.catalog_item else 'Resultado'}"
