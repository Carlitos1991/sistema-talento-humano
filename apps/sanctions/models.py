from django.db import models
from django.conf import settings

from core.models import BaseModel
from contract.models import LaborRegime
from core.models import User
from employee.models import Employee
from personnel_actions.models import PersonnelAction


class SanctionType(models.Model):
    """
    Define the configuration of sanction types (Amonestación, Suspensión, etc.)
    """
    name = models.CharField(verbose_name='Tipo de sanción', max_length=100)
    description = models.TextField(verbose_name='Descripción', blank=True, null=True)
    is_active = models.BooleanField(verbose_name='Estado', default=True)
    requires_attachment = models.BooleanField(verbose_name='¿Requiere adjunto?', default=False)
    authority_1 = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sanction_types_auth1', verbose_name='Primera Autoridad'
    )
    authority_2 = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sanction_types_auth2', verbose_name='Segunda Autoridad'
    )
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sanction_types_reviewer', verbose_name='Revisado por'
    )
    register = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sanction_types_register', verbose_name='Registrado por'
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Tipo de Sanción'
        verbose_name_plural = 'Tipos de Sanciones'

    def __str__(self):
        return self.name


class SanctionNotificationType(BaseModel):
    """
    Define un tipo de notificación de sanción con plantillas por régimen laboral.
    """
    name = models.CharField(verbose_name='Tipo de notificación', max_length=120)
    description = models.TextField(verbose_name='Descripción', blank=True, null=True)
    labor_regimes = models.ManyToManyField(
        LaborRegime,
        through='SanctionNotificationTypeRegime',
        related_name='sanction_notification_types',
        blank=True,
        verbose_name='Regímenes laborales',
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Tipo de Notificación'
        verbose_name_plural = 'Tipos de Notificaciones'

    def __str__(self):
        return self.name


class SanctionNotificationTypeMapping(models.Model):
    """
    Define un mapeo reutilizable entre un marcador y una fuente de datos.
    """
    SOURCE_CHOICES = [
        ('employee_full_name', 'Nombre completo del empleado'),
        ('employee_first_name', 'Nombres del empleado'),
        ('employee_last_name', 'Apellidos del empleado'),
        ('employee_document_number', 'Documento del empleado'),
        ('employee_position', 'Cargo del empleado'),
        ('employee_unit', 'Unidad / área del empleado'),
        ('regime_code', 'Código del régimen'),
        ('regime_name', 'Nombre del régimen'),
        ('notification_name', 'Nombre del tipo de notificación'),
        ('month_name', 'Nombre del mes'),
        ('month_number', 'Número del mes'),
        ('year', 'Año'),
        ('registration_date', 'Fecha de registro'),
        ('authority_1_name', 'Nombre de la autoridad 1'),
        ('authority_1_position', 'Cargo de la autoridad 1'),
        ('authority_2_name', 'Nombre de la autoridad 2'),
        ('authority_2_position', 'Cargo de la autoridad 2'),
        ('minutes_late', 'Minutos de atraso'),
        ('regs_without_mark', 'Registros sin marcar'),
        ('observations', 'Observaciones'),
    ]

    notification_type = models.ForeignKey(
        SanctionNotificationType,
        on_delete=models.CASCADE,
        related_name='template_mappings',
        verbose_name='Tipo de notificación',
    )
    placeholder = models.CharField(verbose_name='Marcador', max_length=80)
    label = models.CharField(verbose_name='Nombre visible', max_length=120)
    source_key = models.CharField(verbose_name='Fuente de datos', max_length=60, choices=SOURCE_CHOICES)
    description = models.TextField(verbose_name='Descripción', blank=True, null=True)
    is_active = models.BooleanField(verbose_name='Activo', default=True)
    order = models.PositiveSmallIntegerField(verbose_name='Orden', default=0)

    class Meta:
        ordering = ['order', 'label']
        verbose_name = 'Mapeo de marcador'
        verbose_name_plural = 'Mapeos de marcadores'
        unique_together = [['notification_type', 'placeholder']]

    def __str__(self):
        return f'{self.notification_type.name} - {self.placeholder}'


class SanctionNotificationMapping(BaseModel):
    """
    Mapeo global reutilizable para todas las plantillas de notificación.
    """
    placeholder = models.CharField(verbose_name='Marcador', max_length=80, unique=True)
    label = models.CharField(verbose_name='Nombre visible', max_length=120)
    expression = models.CharField(
        verbose_name='Expresión',
        max_length=255,
        help_text='Ej.: person.first_name + " " + person.last_name o today',
    )
    description = models.TextField(verbose_name='Descripción', blank=True, null=True)
    is_active = models.BooleanField(verbose_name='Activo', default=True)
    order = models.PositiveSmallIntegerField(verbose_name='Orden', default=0)

    class Meta:
        ordering = ['order', 'label']
        verbose_name = 'Mapeo global'
        verbose_name_plural = 'Mapeos globales'

    def __str__(self):
        return f'{self.placeholder} -> {self.expression}'


class SanctionNotificationTypeRegime(models.Model):
    """
    Plantilla específica de un tipo de notificación para un régimen laboral.
    """
    notification_type = models.ForeignKey(
        SanctionNotificationType,
        on_delete=models.CASCADE,
        related_name='regime_templates',
        verbose_name='Tipo de notificación',
    )
    labor_regime = models.ForeignKey(
        LaborRegime,
        on_delete=models.PROTECT,
        related_name='notification_templates',
        verbose_name='Régimen laboral',
    )

    class Meta:
        ordering = ['labor_regime__name']
        verbose_name = 'Formato de notificación por régimen'
        verbose_name_plural = 'Formatos de notificación por régimen'
        unique_together = [['notification_type', 'labor_regime']]

    def __str__(self):
        return f'{self.notification_type.name} - {self.labor_regime.name}'


class NotificationTemplate(BaseModel):
    """
    Template dinámico de notificación: encabezado fijo por régimen + secciones editables.
    Una plantilla por combinación de SanctionNotificationType + LaborRegime.
    """
    notification_type = models.ForeignKey(
        SanctionNotificationType,
        on_delete=models.CASCADE,
        related_name='dynamic_templates',
        verbose_name='Tipo de notificación',
    )
    labor_regime = models.ForeignKey(
        LaborRegime,
        on_delete=models.PROTECT,
        related_name='dynamic_notification_templates',
        verbose_name='Régimen laboral',
    )
    is_active = models.BooleanField(verbose_name='Activo', default=True)

    class Meta:
        ordering = ['labor_regime__code', 'notification_type__name']
        verbose_name = 'Template dinámico'
        verbose_name_plural = 'Templates dinámicos'
        unique_together = [['notification_type', 'labor_regime']]

    def __str__(self):
        return f'{self.notification_type.name} - {self.labor_regime.name}'


class TemplateSection(BaseModel):
    """
    Sección dentro de un template dinámico: párrafo o título.
    """
    SECTION_TYPE_CHOICES = [
        ('PARAGRAPH', 'Párrafo (justificado)'),
        ('TITLE', 'Título (izquierda)'),
    ]

    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        related_name='sections',
        verbose_name='Template',
    )
    section_type = models.CharField(
        verbose_name='Tipo de sección',
        max_length=20,
        choices=SECTION_TYPE_CHOICES,
        default='PARAGRAPH',
    )
    content = models.TextField(
        verbose_name='Contenido',
        help_text='Puede incluir variables: [FULL_NAME], [POSITION], [today], etc.',
    )
    order = models.PositiveSmallIntegerField(verbose_name='Orden', default=0)
    is_active = models.BooleanField(verbose_name='Activo', default=True)

    class Meta:
        ordering = ['template', 'order']
        verbose_name = 'Sección de template'
        verbose_name_plural = 'Secciones de template'

    def __str__(self):
        return f'{self.template.notification_type.name} - [{self.get_section_type_display()}] Orden {self.order}'


class SanctionNotification(BaseModel):
    """
    Registro de una notificación generada desde una plantilla interna.
    """
    MONTH_LABELS = {
        1: 'ENERO',
        2: 'FEBRERO',
        3: 'MARZO',
        4: 'ABRIL',
        5: 'MAYO',
        6: 'JUNIO',
        7: 'JULIO',
        8: 'AGOSTO',
        9: 'SEPTIEMBRE',
        10: 'OCTUBRE',
        11: 'NOVIEMBRE',
        12: 'DICIEMBRE',
    }

    STATUS_CHOICES = [
        ('GENERADO', 'Generado'),
        ('EN_PROCESO', 'En proceso'),
        ('ARCHIVADO', 'Archivado'),
        ('SANCIONADO', 'Sancionado'),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='sanction_notifications',
        verbose_name='Empleado',
    )
    notification_type = models.ForeignKey(
        SanctionNotificationType,
        on_delete=models.PROTECT,
        related_name='notifications',
        verbose_name='Tipo de notificación',
    )
    regime_template = models.ForeignKey(
        SanctionNotificationTypeRegime,
        on_delete=models.PROTECT,
        related_name='notifications',
        verbose_name='Formato por régimen',
    )
    labor_regime = models.ForeignKey(
        LaborRegime,
        on_delete=models.PROTECT,
        related_name='sanction_notifications',
        verbose_name='Régimen laboral',
    )
    month = models.PositiveSmallIntegerField(verbose_name='Mes')
    year = models.PositiveSmallIntegerField(verbose_name='Año')
    registration_date = models.DateField(verbose_name='Fecha de registro')
    authority_1 = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='sanction_notifications_authority_1',
        verbose_name='Firma 1',
        blank=True,
        null=True,
    )
    authority_2 = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='sanction_notifications_authority_2',
        verbose_name='Firma 2',
        blank=True,
        null=True,
    )
    minutes_late = models.PositiveIntegerField(
        verbose_name='Minutos de atraso',
        default=0,
        blank=True,
        null=True,
    )
    regs_without_mark = models.PositiveIntegerField(
        verbose_name='Regs. sin marcar',
        default=0,
        blank=True,
        null=True,
    )
    observations = models.TextField(verbose_name='Observaciones', blank=True, null=True)
    sequence_number = models.PositiveIntegerField(
        verbose_name='Secuencia',
        default=0,
        editable=False,
    )
    user_code = models.CharField(
        verbose_name='Código de usuario',
        max_length=12,
        blank=True,
        default='',
        editable=False,
    )
    generated_pdf = models.FileField(
        upload_to='documents/sanction_notifications/generated/%Y/%m/',
        verbose_name='Documento PDF generado',
        blank=True,
        null=True,
    )
    status = models.CharField(
        verbose_name='Estado',
        max_length=20,
        choices=STATUS_CHOICES,
        default='GENERADO',
    )
    has_responded = models.BooleanField(
        verbose_name='¿Ha respondido?',
        default=False,
    )

    def save(self, *args, **kwargs):
        if not self.sequence_number:
            last_sequence = self.__class__.objects.order_by('-sequence_number').values_list('sequence_number',
                                                                                            flat=True).first() or 0
            self.sequence_number = last_sequence + 1

        if self.created_by and not self.user_code:
            first_name = ''
            last_name = ''
            person = getattr(self.created_by, 'person', None)
            if person:
                first_name = person.first_name or ''
                last_name = person.last_name or ''
            else:
                full_name = self.created_by.get_full_name() or self.created_by.username or ''
                name_parts = full_name.split()
                if name_parts:
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else name_parts[0]

            self.user_code = f'{first_name[:2].upper()}{last_name[:2].upper()}'.strip()

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-registration_date', '-created_at']
        verbose_name = 'Notificación de Sanción'
        verbose_name_plural = 'Notificaciones de Sanción'

    @property
    def sequential_code(self):
        return f'{self.sequence_number:04d}' if self.sequence_number else '0000'

    @property
    def month_label(self):
        return self.MONTH_LABELS.get(self.month, str(self.month or ''))

    def __str__(self):
        return f'{self.notification_type.name} - {self.employee}'

    @property
    def current_assignment(self):
        """Retorna la asignación activa actual"""
        return self.assignment_history.filter(is_current=True).first()
    @property
    def get_related_sanction(self):
        """
        Busca la sanción asociada en cualquier registro del historial
        de asignaciones de esta notificación.
        """
        assignment = self.assignment_history.filter(sanction__isnull=False).select_related(
            'sanction__personnel_action').first()
        if assignment:
            return assignment.sanction
        return None

    @property
    def linked_action(self):
        """Retorna la Acción de Personal asociada a través de la sanción en el historial"""
        assignment = self.assignment_history.filter(sanction__isnull=False).select_related(
            'sanction__personnel_action').first()
        if assignment and assignment.sanction:
            return assignment.sanction.personnel_action
        return None


class Sanction(models.Model):
    """
    Records a sanction applied to an employee.
    """
    STATUS_CHOICES = [
        ('REGISTERED', 'Registrada'),
        ('ACTIVE', 'Activa'),
        ('COMPLETED', 'Cumplida'),
        ('CANCELED', 'Anulada'),
    ]

    SEVERITY_CHOICES = [
        ('VERBAL_WARNING', 'Amonestación Verbal'),
        ('WRITTEN_WARNING', 'Amonestación Escrita'),
        ('PECUNIARY_WARNING', 'Amonestación Pecuniaria'),
        ('ADMINISTRATIVE_SUMMARY', 'Sumario Administrativo'),
    ]

    employee = models.ForeignKey(
        Employee,
        verbose_name='Empleado',
        on_delete=models.PROTECT,
        related_name='sanctions'
    )
    sanction_type = models.ForeignKey(
        SanctionType,
        verbose_name='Tipo de Sanción',
        on_delete=models.PROTECT
    )

    # Sanction details
    severity = models.CharField(
        verbose_name='Gravedad',
        max_length=30,
        choices=SEVERITY_CHOICES,
        default='VERBAL_WARNING'
    )
    description = models.TextField(verbose_name='Descripción de la falta', blank=True, null=True)
    legal_basis = models.TextField(verbose_name='Base legal', blank=True, null=True)

    # Dates
    incident_date = models.DateField(verbose_name='Fecha del incidente', blank=True, null=True)
    sanction_date = models.DateField(verbose_name='Fecha de la sanción', blank=True, null=True)
    start_date = models.DateField(verbose_name='Fecha de inicio', blank=True, null=True)
    end_date = models.DateField(verbose_name='Fecha de fin', blank=True, null=True)

    # Duration (for suspensions)
    days = models.IntegerField(verbose_name='Días de suspensión', default=0, blank=True, null=True)

    # Status
    status = models.CharField(
        verbose_name='Estado',
        max_length=20,
        choices=STATUS_CHOICES,
        default='REGISTERED'
    )

    # Attachment
    attachment_file = models.FileField(
        upload_to='documents/sanctions/%Y/%m/',
        verbose_name='Documento adjunto',
        blank=True,
        null=True
    )

    # Related Personnel Action
    personnel_action = models.ForeignKey(
        PersonnelAction,
        verbose_name='Acción de Personal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_sanctions'
    )

    # Observations
    observations = models.TextField(verbose_name='Observaciones', blank=True, null=True)

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de registro')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última modificación')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Registrado por',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sanctions_created'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Modificado por',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sanctions_updated'
    )

    class Meta:
        ordering = ['-sanction_date', '-created_at']
        verbose_name = 'Sanción'
        verbose_name_plural = 'Sanciones'
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['sanction_date']),
        ]

    def __str__(self):
        if self.personnel_action:
            return f"{self.personnel_action.number} - {self.employee}"
        return f"Sanción - {self.employee}"


class SanctionAssignment(BaseModel):
    """
    Historial de asignaciones y tiempos de respuesta para notificaciones/sanciones.
    """
    notification = models.ForeignKey(
        'SanctionNotification',
        on_delete=models.CASCADE,
        related_name='assignment_history',
        verbose_name="Notificación Relacionada"
    )
    # Si se llega a sancionar, este campo se llena al final del flujo
    sanction = models.ForeignKey(
        'Sanction',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assignments',
        verbose_name="Sanción Resultante"
    )
    assigned_to = models.ForeignKey(
        'core.User',
        on_delete=models.PROTECT,
        related_name='received_sanction_tasks',
        verbose_name="Responsable Actual"
    )
    assigned_by = models.ForeignKey(
        'core.User',
        on_delete=models.PROTECT,
        related_name='given_sanction_tasks',
        verbose_name="Asignado por"
    )
    start_date = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Recepción")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Despacho")
    is_current = models.BooleanField(default=True, verbose_name="¿Es la asignación activa?")
    observation = models.TextField(blank=True, null=True, verbose_name="Instrucciones/Observaciones")

    class Meta:
        verbose_name = "Asignación de Sanción"
        verbose_name_plural = "Asignaciones de Sanciones"
        ordering = ['created_at']

    @property
    def duration_days(self):
        from django.utils import timezone
        end = self.end_date or timezone.now()
        diff = end - self.start_date
        return diff.days

    def get_status_color(self):
        from core.models import SystemConfiguration
        config = SystemConfiguration.get_current()
        if not config:
            return '#10b981'  # Verde por defecto

        days = self.duration_days
        if days <= config.sanction_green_days:
            return '#10b981'  # Verde
        elif days <= config.sanction_yellow_days:
            return '#f59e0b'  # Amarillo
        else:
            return '#ef4444'  # Rojo

    def complete_assignment(self, sanction_obj=None):
        """Marca la asignación como terminada"""
        from django.utils import timezone
        self.end_date = timezone.now()
        self.is_current = False
        if sanction_obj:
            self.sanction = sanction_obj
        self.save()

    def get_status_info(self):
        """Retorna el color y los días transcurridos para el semáforo."""
        from core.models import SystemConfiguration
        from django.utils import timezone

        config = SystemConfiguration.get_current()
        # Valores por defecto si no hay configuración
        green = config.sanction_green_days if config else 2
        yellow = config.sanction_yellow_days if config else 5

        end = self.end_date or timezone.now()
        diff = end - self.start_date
        days = diff.days

        if days <= green:
            return {'color': '#10b981', 'label': 'A tiempo', 'days': days}  # Verde
        elif days <= yellow:
            return {'color': '#f59e0b', 'label': 'En alerta', 'days': days}  # Amarillo
        else:
            return {'color': '#ef4444', 'label': 'Atrasado', 'days': days}  # Rojo
