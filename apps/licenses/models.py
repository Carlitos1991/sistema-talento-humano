from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from core.models import User
from employee.models import Employee


class LicenseTypeRequirement(models.Model):
    """Anexos / Requisitos preconfigurados por tipo de licencia."""
    name = models.CharField(max_length=255, verbose_name="Nombre del Anexo / Requisito")
    is_mandatory = models.BooleanField(default=True, verbose_name="¿Es Obligatorio por Defecto?")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        ordering = ['name']
        verbose_name = 'Requisito de Licencia'
        verbose_name_plural = 'Requisitos de Licencias'

    def __str__(self):
        return self.name


class MedicalLicenseType(models.Model):
    """
    Catálogo de Tipos de Licencias (ej: Médica por Enfermedad, Sustituto, Reducción de Jornada)
    Funciona como plantilla base para la emisión de Acciones de Personal y recepción de anexos.
    """
    code = models.CharField(max_length=35, unique=True, verbose_name="Código", help_text="Ej: LIC_MED, LIC_SUST")
    name = models.CharField(max_length=150, verbose_name="Nombre del Tipo de Licencia")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción / Base Legal")
    description_ct = models.TextField(blank=True, null=True,
                                      verbose_name='Descripción / Base Legal (Código de Trabajo - CT)')

    # Requisitos / Anexos preconfigurados
    requirements = models.ManyToManyField(LicenseTypeRequirement, blank=True, related_name="license_types",
                                          verbose_name="Requisitos / Anexos Requeridos")

    # Firmas Preconfiguradas (Por Defecto) para la Acción de Personal
    default_authority_1 = models.ForeignKey(User, verbose_name='Autoridad Nominadora (1)', on_delete=models.SET_NULL,
                                            related_name='default_auth1_license_types',
                                            limit_choices_to={'is_active': True}, null=True, blank=True)
    default_authority_2 = models.ForeignKey(
        User,
        verbose_name='Director de Talento Humano (2)',
        on_delete=models.SET_NULL,
        related_name='default_auth2_license_types',
        limit_choices_to={'is_active': True},
        null=True, blank=True
    )
    default_reviewer = models.ForeignKey(
        User,
        verbose_name='Revisado Por',
        on_delete=models.SET_NULL,
        related_name='default_reviewer_license_types',
        limit_choices_to={'is_active': True},
        null=True, blank=True
    )
    default_register = models.ForeignKey(
        User,
        verbose_name='Registrado Por',
        on_delete=models.SET_NULL,
        related_name='default_register_license_types',
        limit_choices_to={'is_active': True},
        null=True, blank=True
    )

    # Estado de operación
    is_active = models.BooleanField(default=True, verbose_name="Tipo de Licencia Activo para Operación")
    employer_coverage_days = models.PositiveIntegerField(
        default=3, verbose_name='Días cubiertos por empleador'
    )
    iess_subsidy_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('75.00'),
        verbose_name='% Subsidio IESS'
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Tipo de Licencia Médica'
        verbose_name_plural = 'Tipos de Licencias Médicas'

    def get_legal_basis_for_regime(self, is_labor_code=False):
        if is_labor_code and self.description_ct:
            return self.description_ct
        return self.description or ''

    def __str__(self):
        return f"{self.code} - {self.name}"


class LicenseReception(models.Model):
    STATUS_REGISTERED = 'REGISTERED'  # Documentos físicos recibidos / Pendientes
    STATUS_APPROVED = 'APPROVED'  # Checklist 100% verificado y conforme
    STATUS_DELIVERED = 'DELIVERED'  # Remitido para elaboración de Acción de Personal
    STATUS_CANCELLED = 'CANCELLED'  # Dado de baja

    STATUS_CHOICES = [
        (STATUS_REGISTERED, 'Registrado'),
        (STATUS_APPROVED, 'Aprobado'),
        (STATUS_DELIVERED, 'Entregado'),
        (STATUS_CANCELLED, 'Dado de Baja'),
    ]

    employee = models.ForeignKey('employee.Employee', on_delete=models.CASCADE, related_name='license_receptions')
    license_type = models.ForeignKey('MedicalLicenseType', on_delete=models.PROTECT)
    reception_date = models.DateTimeField(auto_now_add=True)
    license_start_date = models.DateField(
        verbose_name='Fecha de inicio de la licencia',
        null=True,
        blank=True
    )
    license_end_date = models.DateField(
        verbose_name='Fecha de fin de la licencia',
        null=True,
        blank=True
    )
    license_days = models.PositiveIntegerField(
        verbose_name='Número de días de licencia',
        null=True,
        blank=True
    )
    received_by = models.ForeignKey('core.User', on_delete=models.PROTECT)
    supporting_document = models.CharField(
        max_length=255,
        verbose_name='Documento habilitante',
        default='',
    )
    observations = models.TextField(blank=True, null=True)
    delivery_batch = models.UUIDField(null=True, blank=True, db_index=True, editable=False)
    delivered_to = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='delivered_license_receptions'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REGISTERED)

    class Meta:
        verbose_name = 'Recepción de Licencia'
        verbose_name_plural = 'Recepciones de Licencias'

    def __str__(self):
        return f"#LIC-{self.id} - {self.employee.person.full_name()}"


class LicenseReceptionCheck(models.Model):
    """Checklist verificado durante el proceso de recepción."""
    reception = models.ForeignKey(LicenseReception, on_delete=models.CASCADE, related_name="checked_items")
    requirement = models.ForeignKey(LicenseTypeRequirement, on_delete=models.PROTECT)
    is_checked = models.BooleanField(default=False)


class MedicalLicense(models.Model):
    """Modelo Principal de Licencia Médica."""
    STATUS_DRAFT = 'DRAFT'
    STATUS_SUBMITTED = 'SUBMITTED'
    STATUS_VALIDATED = 'VALIDATED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_ACTION_ISSUED = 'ACTION_ISSUED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_DRAFT, _('Borrador')),
        (STATUS_SUBMITTED, _('Pendiente Convalidación TH')),
        (STATUS_VALIDATED, _('Convalidada / Aprobada')),
        (STATUS_REJECTED, _('Rechazada')),
        (STATUS_ACTION_ISSUED, _('Acción de Personal Emitida')),
        (STATUS_CANCELLED, _('Anulada')),
    ]

    employee = models.ForeignKey(
        'employee.Employee',
        on_delete=models.PROTECT,
        related_name='medical_licenses',
        verbose_name=_("Servidor / Trabajador")
    )
    license_type = models.ForeignKey(
        MedicalLicenseType,
        on_delete=models.PROTECT,
        related_name='licenses',
        verbose_name=_("Tipo de Licencia")
    )

    start_date = models.DateField(_("Fecha Inicio"))
    end_date = models.DateField(_("Fecha Fin"), null=True, blank=True)
    total_days = models.PositiveIntegerField(_("Total Días"), editable=False, default=0)

    cie10_code = models.CharField(_("Código CIE-10"), max_length=10, blank=True, null=True)
    diagnosis = models.TextField(_("Diagnóstico / Observación"))
    issuing_entity = models.CharField(_("Entidad Emisora"), max_length=150)
    doctor_name = models.CharField(_("Nombre del Médico"), max_length=150, blank=True, null=True)
    medical_certificate_number = models.CharField(_("Nº Certificado"), max_length=50, blank=True, null=True)

    status = models.CharField(_("Estado"), max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    # Auditoría de Validación
    convalidated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='convalidated_licenses'
    )
    convalidation_date = models.DateTimeField(_("Fecha de Convalidación"), null=True, blank=True)
    convalidation_notes = models.TextField(_("Notas de Convalidación / Rechazo"), blank=True, null=True)

    # Vinculación con Acción de Personal
    personnel_action = models.OneToOneField(
        'personnel_actions.PersonnelAction',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='medical_license'
    )
    reception = models.OneToOneField(
        'LicenseReception',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medical_license',
        verbose_name='Recepción de origen'
    )

    # Campos de Auditoría y Control
    is_active = models.BooleanField(_("Activo"), default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_licenses'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_licenses'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'licenses_medical_license'
        verbose_name = _("Licencia Médica")
        verbose_name_plural = _("Licencias Médicas")
        ordering = ['-start_date']

    @property
    def is_legalized(self):
        """Propiedad virtual para compatibilidad con legalización (Convalidada o Emitida)."""
        return self.status in [self.STATUS_VALIDATED, self.STATUS_ACTION_ISSUED]

    @property
    def has_substitute(self):
        """Indica si tiene un funcionario sustituto asignado."""
        return hasattr(self, 'substitute_assignment') and self.substitute_assignment is not None

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            self.total_days = (self.end_date - self.start_date).days + 1
        elif self.start_date:
            self.total_days = 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Licencia #{self.id} - {self.employee} ({self.start_date})"


class LicenseSchedule(models.Model):
    """Gestión de Horarios Especiales / Reducción de Jornada."""
    MODALITY_SHIFT_OVERRIDE = 'OVERRIDE'
    MODALITY_REDUCTION_HOURS = 'REDUCTION'
    MODALITY_ENTRY_DELAY = 'ENTRY_DELAY'
    MODALITY_EXIT_EARLY = 'EXIT_EARLY'
    MODALITY_LUNCH = 'LUNCH'

    MODALITY_CHOICES = [
        (MODALITY_SHIFT_OVERRIDE, _('Horario Fijo Especial (Ej. 08:00 a 14:00 sin almuerzo)')),
        (MODALITY_REDUCTION_HOURS, _('Reducción de Horas Diarias (Entrada tardía o Salida anticipada)')),
        (MODALITY_ENTRY_DELAY, _('Entrada 2 horas después')),
        (MODALITY_EXIT_EARLY, _('Salida 2 horas antes')),
        (MODALITY_LUNCH, _('Permiso en horario de almuerzo')),
    ]

    license = models.OneToOneField(
        MedicalLicense,
        on_delete=models.CASCADE,
        related_name='schedule_adjustment'
    )
    modality = models.CharField(_("Modalidad de Jornada"), max_length=20, choices=MODALITY_CHOICES,
                                default=MODALITY_SHIFT_OVERRIDE)

    custom_entry_time = models.TimeField(_("Hora Entrada Especial"), null=True, blank=True)
    custom_exit_time = models.TimeField(_("Hora Salida Especial"), null=True, blank=True)
    includes_lunch_break = models.BooleanField(_("Incluye Hora de Almuerzo"), default=False)

    reduction_hours = models.DecimalField(
        _("Horas a Reducir"), max_digits=4, decimal_places=2,
        default=Decimal("2.00"), null=True, blank=True
    )

    is_biometric_exempt = models.BooleanField(_("Exención de Marcación Biométrica"), default=False)

    class Meta:
        db_table = 'licenses_schedule'
        verbose_name = _("Ajuste de Jornada por Licencia")


class LicenseSubstitute(models.Model):
    """Asignación de Funcionario Sustituto."""
    license = models.OneToOneField(
        MedicalLicense,
        on_delete=models.CASCADE,
        related_name='substitute_assignment'
    )
    substitute_employee = models.ForeignKey(
        'employee.Employee',
        on_delete=models.PROTECT,
        related_name='substitutions_performed'
    )
    start_date = models.DateField(_("Inicio Sustitución"))
    end_date = models.DateField(_("Fin Sustitución"))
    observation = models.TextField(_("Funciones Asignadas"), blank=True, null=True)

    class Meta:
        db_table = 'licenses_substitute'
        verbose_name = _("Sustituto de Licencia")


class LicensePayrollEffect(models.Model):
    """Novedades registradas para impactar el Rol de Pagos (Descuento de Subsidio)."""
    STATUS_PENDING = 'PENDING'
    STATUS_APPLIED = 'APPLIED'
    STATUS_EXEMPT = 'EXEMPT'

    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pendiente de Aplicar en Rol')),
        (STATUS_APPLIED, _('Aplicado en Rol de Pagos')),
        (STATUS_EXEMPT, _('Exento / Sin Descuento')),
    ]

    license = models.ForeignKey(
        MedicalLicense,
        on_delete=models.CASCADE,
        related_name='payroll_effects'
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    target_year = models.PositiveIntegerField(_("Año de Aplicación"), null=True, blank=True)
    target_month = models.PositiveIntegerField(_("Mes de Aplicación (1-12)"), null=True, blank=True)
    license_year = models.PositiveIntegerField(_("Año de Licencia"), null=True, blank=True)
    license_month = models.PositiveIntegerField(_("Mes de Licencia (1-12)"), null=True, blank=True)

    days_to_discount = models.PositiveIntegerField(_("Días Sujetos a Subsidio IESS"))
    labor_regime = models.CharField(_("Régimen Laboral"), max_length=50, default='LOSEP')
    employer_covered_days = models.PositiveIntegerField(_("Días cubiertos por empleador"), default=0)
    subsidy_percentage = models.DecimalField(
        _("% Subsidio aplicable"), max_digits=5, decimal_places=2, default=Decimal('100.00')
    )
    payroll_rubric = models.ForeignKey(
        'payroll.PayrollRubric', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='license_subsidy_effects'
    )
    estimated_discount_amount = models.DecimalField(
        _("Monto Estimado Descuento Subsidio"),
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    observation = models.CharField(
        _("Observación para Rol"),
        max_length=255,
        help_text=_("Ej. Descuento Subsidio IESS Mes de Octubre")
    )
    status = models.CharField(_("Estado"), max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    applied_in_payroll = models.ForeignKey(
        'payroll.PayrollPeriod',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='applied_license_subsidies'
    )
    subsidy_reported = models.BooleanField(
        _("Subsidio incluido en reporte"), default=False, db_index=True
    )
    subsidy_reported_at = models.DateTimeField(
        _("Fecha de cálculo del subsidio"), null=True, blank=True
    )

    class Meta:
        db_table = 'licenses_payroll_effect'
        verbose_name = _("Efecto en Rol de Pagos")
