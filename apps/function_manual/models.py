from django.db import models

from core.models import BaseModel, User
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
    Representa solo la escala salarial y grados.
    La definición de requisitos ahora reside en la estructura de Árbol (ValuationNode).
    """
    occupational_group = models.CharField(max_length=100, verbose_name="Grupo Ocupacional (Ej: SP1)")
    grade = models.PositiveIntegerField(verbose_name="Grado de la Escala")
    remuneration = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="R.M.U.")

    class Meta:
        verbose_name = "Matriz Ocupacional"
        verbose_name_plural = "Matrices Ocupacionales"
        unique_together = ('occupational_group', 'grade')
        ordering = ['grade']

    def __str__(self) -> str:
        return f"{self.occupational_group} - G{self.grade} - ${self.remuneration}"


# ==============================================================================
# PERFIL DE PUESTO (MODELO UNIFICADO)
# ==============================================================================

class JobProfile(BaseModel):
    objects = None
    position_code = models.CharField(max_length=50, blank=True, null=True, unique=True)
    specific_job_title = models.CharField(max_length=255, verbose_name="Cargo Específico", blank=True, null=True)
    administrative_unit = models.ForeignKey(AdministrativeUnit, on_delete=models.PROTECT, related_name='job_profiles')
    referential_employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)

    mission = models.TextField(verbose_name="Misión")
    interface_relations = models.TextField(verbose_name="Relaciones Internas/Externas")

    # Campos que se llenan desde los Nodos de Valoración seleccionados
    required_instruction = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'INSTRUCTION_LEVELS'},
        related_name='profiles_by_instruction', null=True, blank=True
    )
    decision_making = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'DECISION_LEVELS'},
        related_name='profiles_by_decision', null=True, blank=True
    )
    management_impact = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'IMPACT_LEVELS'},
        related_name='profiles_by_impact', null=True, blank=True
    )
    final_complexity_level = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'COMPLEXITY_LEVELS'},
        related_name='profiles_by_complexity', null=True, blank=True
    )
    job_role = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'JOB_ROLES'},
        related_name='profiles_by_role', null=True, blank=True
    )
    required_experience = models.CharField(max_length=255, verbose_name="Experiencia Requerida", default="No Requerida")

    knowledge_area = models.TextField(verbose_name="Área de Conocimiento")
    experience_details = models.TextField(verbose_name="Detalle de Experiencia")
    training_topic = models.TextField(verbose_name="Temática de Capacitación", blank=True, null=True)

    # Vinculación a la escala salarial (Resultado Final)
    occupational_classification = models.ForeignKey(
        OccupationalMatrix, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Clasificación Matriz"
    )

    # Total de puntos de las primeras 6 actividades
    total_activity_points = models.PositiveIntegerField(
        default=0, verbose_name="Total Puntos Actividades",
        help_text="Suma de puntos de las primeras 6 actividades"
    )

    # Nivel del cargo (obtenido del nodo RESULT seleccionado)
    level = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Nivel del Cargo",
        help_text="Nivel asociado al grupo ocupacional resultante"
    )

    # Control: si la denominación del cargo ya fue completada/editada
    denomination_completed = models.BooleanField(
        default=False, verbose_name="Denominación Completada",
        help_text="Indica si la denominación del cargo fue editada por el usuario"
    )

    competencies = models.ManyToManyField('Competency', through='ProfileCompetency')

    prepared_by = models.ForeignKey(User, related_name='prepared_profiles', on_delete=models.PROTECT, null=True)
    reviewed_by = models.ForeignKey(User, related_name='reviewed_profiles', on_delete=models.PROTECT, null=True)
    approved_by = models.ForeignKey(User, related_name='approved_profiles', on_delete=models.PROTECT, null=True)

    legalized_document = models.FileField(upload_to='profiles/legalized/', null=True, blank=True)

    is_legalized = models.BooleanField(
        default=False, verbose_name="Legalizado",
        help_text="Indica si el perfil de puesto fue legalizado"
    )

    def calculate_activity_points(self):
        """Calcula la suma de puntos de las primeras 6 actividades"""
        activities = self.activities.all()[:6]
        return sum(activity.points for activity in activities)

    def update_total_activity_points(self):
        """Actualiza el campo total_activity_points"""
        self.total_activity_points = self.calculate_activity_points()
        self.save(update_fields=['total_activity_points'])

    class Meta:
        verbose_name = "Perfil de Puesto"
        verbose_name_plural = "Perfiles de Puesto"

    def __str__(self) -> str:
        return f"{self.specific_job_title}"


# ==============================================================================
# DETALLES: ACTIVIDADES Y COMPETENCIAS
# ==============================================================================

class JobActivity(BaseModel):
    """
    Actividades esenciales del puesto enriquecidas con métricas de valoración.
    """
    profile = models.ForeignKey(JobProfile, on_delete=models.CASCADE, related_name='activities')

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
    points = models.PositiveIntegerField(default=0, verbose_name="Puntos de Actividad")
    description = models.TextField(verbose_name="Descripción")
    deliverable = models.ForeignKey(
        'institution.Deliverable',
        on_delete=models.PROTECT,
        related_name='activities',
        verbose_name="Entregable / Producto",
        null=True, blank=True
    )

    complexity = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'COMPLEXITY_LEVELS'},
        related_name='activities_complexity',
        verbose_name="Nivel de Complejidad",
        null=True, blank=True
    )

    contribution = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'COMPLEXITY_LEVELS'},
        related_name='activities_contribution',
        verbose_name="Aporte a la Gestión",
        null=True, blank=True
    )

    frequency = models.ForeignKey(
        ManualCatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'FREQUENCY'},
        related_name='activities_frequency',
        verbose_name="Frecuencia",
        null=True, blank=True
    )

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
            -> 5.Impacto -> 6.Complejidad -> 7.Resultado (Clasificación) -> 8.Denominación Genérica
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
        GENERIC_DENOMINATION = 'GENERIC_DENOMINATION', 'Denominación Genérica'

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

    # Campo para Denominación Genérica: valor mínimo (entero sin decimales)
    minimum_value = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Valor Mínimo",
        help_text="Valor mínimo para este nivel (sin decimales)"
    )

    # Nivel del nodo (solo para RESULT nodes - Resultado Final)
    level = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Nivel",
        help_text="Nivel asociado al grupo ocupacional (solo para Resultado Final)"
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
