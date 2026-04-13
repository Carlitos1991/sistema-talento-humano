from django.db import IntegrityError, models, transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone
import re
from core.models import BaseModel, CatalogItem, Authority
from employee.models import Employee
from budget.models import BudgetLine
from institution.models import AdministrativeUnit
from schedule.models import Schedule
from personnel_actions.models import ActionMovement, ActionType, PersonnelAction


class LaborRegime(BaseModel):
    """
    Régimen Laboral (LOSEP, Código de Trabajo, LOES, etc.)
    """
    code = models.CharField(verbose_name="Código", max_length=50, unique=True)
    name = models.CharField(verbose_name="Nombre del Régimen", max_length=255)
    description = models.TextField(verbose_name="Descripción", blank=True, null=True)

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        self.name = self.name.upper().strip()
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'contract_labor_regime'
        verbose_name = 'Régimen Laboral'
        verbose_name_plural = 'Regímenes Laborales'
        ordering = ['-code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class ContractType(BaseModel):
    """
    Tipo de Contrato o Modalidad Laboral
    """
    TYPE_CONTRATO = 'CONTRATO'
    TYPE_ACCION_PERSONAL = 'ACCION_PERSONAL'

    CONTRACT_TYPE_CHOICES = [
        (TYPE_CONTRATO, 'Contrato'),
        (TYPE_ACCION_PERSONAL, 'Acción de Personal'),
    ]

    labor_regime = models.ForeignKey(
        LaborRegime, on_delete=models.PROTECT,
        related_name='contract_types', verbose_name='Régimen Laboral'
    )
    code = models.CharField(verbose_name="Código", max_length=50)
    name = models.CharField(verbose_name="Nombre del Tipo de Contrato", max_length=255)
    contract_type_category = models.CharField(
        verbose_name="Categoría de Documento",
        max_length=20,
        choices=CONTRACT_TYPE_CHOICES,
        default=TYPE_CONTRATO
    )

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        self.name = self.name.upper().strip()
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'contract_contract_type'
        verbose_name = 'Tipo de Contrato'
        verbose_name_plural = 'Tipos de Contrato'
        unique_together = [['labor_regime', 'code']]
        ordering = ['name']

    def __str__(self):
        return f'{self.labor_regime.code} - {self.name}'


class ContractTemplate(BaseModel):
    """
    Plantilla dinámica por modalidad de contratación.
    Una plantilla por cada ContractType.
    """
    contract_type = models.OneToOneField(
        ContractType,
        on_delete=models.CASCADE,
        related_name='dynamic_template',
        verbose_name='Modalidad de contratación',
    )

    class Meta:
        ordering = ['contract_type__labor_regime__code', 'contract_type__name']
        verbose_name = 'Plantilla de contrato'
        verbose_name_plural = 'Plantillas de contrato'

    def __str__(self):
        return f'Plantilla - {self.contract_type.name}'


class ContractTemplateSection(BaseModel):
    """
    Sección editable de una plantilla de contrato/acción de personal.
    """
    SECTION_TYPE_CHOICES = [
        ('PARAGRAPH', 'Párrafo (justificado)'),
        ('TITLE', 'Título (izquierda)'),
    ]

    template = models.ForeignKey(
        ContractTemplate,
        on_delete=models.CASCADE,
        related_name='sections',
        verbose_name='Plantilla',
    )
    section_type = models.CharField(
        verbose_name='Tipo de sección',
        max_length=20,
        choices=SECTION_TYPE_CHOICES,
        default='PARAGRAPH',
    )
    content = models.TextField(
        verbose_name='Contenido',
        help_text='Puede incluir variables: [FULL_NAME], [DOCUMENT_NUMBER], [START_DATE], etc.',
    )
    order = models.PositiveSmallIntegerField(verbose_name='Orden', default=0)

    class Meta:
        ordering = ['template', 'order']
        verbose_name = 'Sección de plantilla contractual'
        verbose_name_plural = 'Secciones de plantillas contractuales'

    def __str__(self):
        return f'{self.template.contract_type.name} - [{self.get_section_type_display()}] Orden {self.order}'


class ManagementPeriod(BaseModel):
    """
    Período de Gestión / Contrato Activo
    Representa el vínculo formal entre el Empleado, la Partida y la Institución.
    """
    # Identificador único del contrato (Ej: MUN-TTHH-2024-001-CT)
    document_number = models.CharField(
        verbose_name='Número de Documento',
        max_length=100, unique=True, db_index=True,blank=True
    )

    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT,
        related_name='management_periods', verbose_name='Empleado'
    )
    budget_line = models.ForeignKey(
        'budget.BudgetLine',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    manual_position = models.CharField(
        verbose_name='Cargo Manual',
        max_length=255,
        blank=True,
        null=True
    )
    manual_remuneration = models.DecimalField(
        verbose_name='Remuneración Manual',
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )
    contract_type = models.ForeignKey(
        ContractType, on_delete=models.PROTECT,
        related_name='management_periods', verbose_name='Tipo de Contrato'
    )
    status = models.ForeignKey(
        CatalogItem, on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'STATUS_CONTRACT'},
        related_name='periods_by_status', verbose_name='Estado'
    )
    administrative_unit = models.ForeignKey(
        AdministrativeUnit, on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='management_periods', verbose_name='Unidad Administrativa'
    )
    schedule = models.ForeignKey(
        Schedule, on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='management_periods', verbose_name='Horario'
    )

    # Detalles del Puesto
    job_functions = models.TextField(verbose_name='Funciones del Puesto', blank=True, null=True)
    workplace = models.CharField(verbose_name='Lugar de Trabajo', max_length=255, blank=True, null=True)

    # Referencias Legales/Presupuestarias
    institutional_need_memo = models.CharField(verbose_name='Memo Necesidad', max_length=100, blank=True, null=True)
    budget_certification = models.CharField(verbose_name='Certificación Presup.', max_length=100, blank=True, null=True)

    # Fechas
    elaboration_date = models.DateField(verbose_name='Fecha de Elaboración', blank=True, null=True)
    start_date = models.DateField(verbose_name='Fecha de Inicio')
    end_date = models.DateField(verbose_name='Fecha de Fin', blank=True, null=True)

    # Campos específicos para acciones de personal
    action_motivation = models.CharField(verbose_name='Motivación de Acción', max_length=255, blank=True, null=True)
    action_explanation = models.TextField(verbose_name='Explicación de Acción', blank=True, null=True)

    # Archivos
    signed_document = models.FileField(
        verbose_name='Documento Firmado',
        upload_to='contracts/%Y/%m/', blank=True, null=True
    )
    personnel_action = models.OneToOneField(
        'personnel_actions.PersonnelAction',
        on_delete=models.PROTECT,
        related_name='management_period',
        verbose_name='Acción de personal vinculada',
        blank=True,
        null=True,
    )

    class Meta:
        db_table = 'contract_management_period'
        verbose_name = 'Período de Gestión'
        verbose_name_plural = 'Períodos de Gestión'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.document_number} | {self.employee.person.full_name}'

    def clean(self):
        super().clean()
        if self.end_date and self.start_date > self.end_date:
            raise ValidationError({'end_date': 'La fecha de fin no puede ser anterior al inicio.'})
        contract_code = (getattr(self.contract_type, 'code', '') or '').upper()
        contract_category = (getattr(self.contract_type, 'contract_type_category', '') or '').upper()
        is_professional_service = contract_code == 'SERVICIOS_PROFESIONALES'
        is_action_document = contract_category == ContractType.TYPE_ACCION_PERSONAL

        if is_action_document:
            errors = {}
            if not self.elaboration_date:
                errors['elaboration_date'] = 'La fecha de elaboración es obligatoria para acciones de personal.'
            if not self.start_date:
                errors['start_date'] = 'La fecha rige desde es obligatoria para acciones de personal.'
            if not self.action_motivation:
                errors['action_motivation'] = 'La motivación es obligatoria para acciones de personal.'
            if not self.action_explanation:
                errors['action_explanation'] = 'La explicación es obligatoria para acciones de personal.'
            if not self.administrative_unit_id:
                errors['administrative_unit'] = 'La unidad administrativa de destino es obligatoria para acciones de personal.'
            if errors:
                raise ValidationError(errors)
        elif is_professional_service:
            errors = {}
            if not self.manual_position:
                errors['manual_position'] = 'El cargo es obligatorio para Servicios Profesionales.'
            if self.manual_remuneration in (None, ''):
                errors['manual_remuneration'] = 'La remuneración es obligatoria para Servicios Profesionales.'
            if errors:
                raise ValidationError(errors)
        else:
            errors = {}
            if not self.administrative_unit_id:
                errors['administrative_unit'] = 'La unidad administrativa es obligatoria para este tipo de contrato.'
            if not self.schedule_id:
                errors['schedule'] = 'El horario es obligatorio para este tipo de contrato.'
            if not self.job_functions:
                errors['job_functions'] = 'Las funciones del puesto son obligatorias para este tipo de contrato.'
            if not self.workplace:
                errors['workplace'] = 'El lugar de trabajo es obligatorio para este tipo de contrato.'
            if not self.institutional_need_memo:
                errors['institutional_need_memo'] = 'El memo de necesidad es obligatorio para este tipo de contrato.'
            if not self.budget_certification:
                errors['budget_certification'] = 'La certificación presupuestaria es obligatoria para este tipo de contrato.'
            if not self.budget_line_id:
                errors['budget_line'] = 'La partida presupuestaria es obligatoria para este tipo de contrato.'
            if errors:
                raise ValidationError(errors)
        # Nota: validación de ocupación de partida removida.
        # La validación de integridad sobre asignaciones se gestiona desde el módulo de presupuesto.

    @property
    def display_position(self):
        if self.budget_line and self.budget_line.position_item:
            return self.budget_line.position_item.name
        return self.manual_position or 'SIN CARGO'

    @property
    def display_remuneration(self):
        if self.budget_line and self.budget_line.remuneration is not None:
            return self.budget_line.remuneration
        return self.manual_remuneration

    @property
    def is_currently_active(self):
        today = timezone.now().date()
        date_active = self.start_date <= today
        if self.end_date:
            date_active = date_active and today <= self.end_date
        return date_active and self.status.code == 'ACTIVO'

    def _normalized_contract_type_code(self):
        raw_code = (getattr(self.contract_type, 'code', '') or '').upper().strip()
        normalized = re.sub(r'[^A-Z0-9]+', '_', raw_code).strip('_')
        return (normalized or 'SIN_TIPO')[:20]

    def _resolve_personnel_action_type(self):
        contract_code = (getattr(self.contract_type, 'code', '') or '').upper().strip()
        contract_name = (getattr(self.contract_type, 'name', '') or '').upper().strip()
        return (
            ActionType.objects.filter(is_active=True).filter(
                Q(code__iexact=contract_code) |
                Q(name__iexact=contract_name) |
                Q(code__iexact=self._normalized_contract_type_code())
            ).first()
        )

    def _generate_personnel_action_number(self):
        year = (self.elaboration_date.year if self.elaboration_date else (self.start_date.year if self.start_date else timezone.now().year))
        max_sequence = 0
        existing_numbers = PersonnelAction.objects.filter(number__endswith=f'-{year}').values_list('number', flat=True)

        for number in existing_numbers:
            sequence_str = (number or '').split('-')[0]
            if sequence_str.isdigit():
                max_sequence = max(max_sequence, int(sequence_str))

        return f'{max_sequence + 1:04d}-{year}'

    def _get_personnel_action_authorities(self):
        authorities = list(Authority.objects.filter(is_active=True).order_by('id')[:2])
        if not authorities:
            raise ValidationError({'personnel_action': 'Debe existir al menos una autoridad activa para generar la acción de personal.'})
        primary = authorities[0]
        secondary = authorities[1] if len(authorities) > 1 else None
        return primary, secondary

    def _get_action_template_sections(self):
        template = ContractTemplate.objects.filter(contract_type=self.contract_type, is_active=True).first()
        if not template:
            return []
        return list(template.sections.filter(is_active=True).order_by('order')[:6])

    def _resolve_authority_from_template(self, sections, index, fallback):
        if len(sections) <= index:
            return fallback
        raw_value = (sections[index].content or '').strip()
        if not raw_value:
            return fallback
        authority = Authority.objects.filter(pk=raw_value, is_active=True).first()
        return authority or fallback

    def _create_linked_personnel_action(self):
        if self.personnel_action_id:
            return

        if (getattr(self.contract_type, 'contract_type_category', '') or '').upper() != ContractType.TYPE_ACCION_PERSONAL:
            return

        action_type = self._resolve_personnel_action_type()
        template_sections = self._get_action_template_sections()

        if template_sections:
            template_action_type = ActionType.objects.filter(
                pk=(template_sections[0].content or '').strip(),
                is_active=True,
            ).first()
            action_type = template_action_type or action_type

        if not action_type:
            raise ValidationError({'contract_type': 'No existe un tipo de acción activo que coincida con esta modalidad.'})

        authority_1, authority_2 = self._get_personnel_action_authorities()
        authority_1 = self._resolve_authority_from_template(template_sections, 1, authority_1)
        authority_2 = self._resolve_authority_from_template(template_sections, 2, authority_2)
        reviewer = self._resolve_authority_from_template(template_sections, 3, authority_2 or authority_1)
        elaboration = self._resolve_authority_from_template(template_sections, 4, authority_1)
        register = self._resolve_authority_from_template(template_sections, 5, authority_1)
        action = PersonnelAction.objects.create(
            employee=self.employee,
            action_type=action_type,
            number=self._generate_personnel_action_number(),
            motivation=self.action_motivation or self.contract_type.name,
            date_issue=self.elaboration_date or self.start_date,
            date_effective=self.start_date,
            explanation=self.action_explanation or self.job_functions or '',
            authority_1=authority_1,
            authority_2=authority_2,
            reviewer=reviewer,
            elaboration=elaboration,
            register=register,
            created_by=self.created_by,
        )

        ActionMovement.objects.create(
            personnel_action=action,
            previous_unit=None,
            previous_position=None,
            previous_remuneration=0,
            previous_budget_line=None,
            new_unit=self.administrative_unit,
            new_position=self.budget_line.position_item if self.budget_line and self.budget_line.position_item else None,
            new_remuneration=self.display_remuneration or 0,
            new_budget_line=self.budget_line if self.budget_line else None,
            location_text=self.workplace or '',
        )

        self.personnel_action = action

    def _generate_document_number(self):
        year = self.start_date.year if self.start_date else timezone.now().year
        prefix = "ML-DTH-"

        max_sequence = 0
        existing_numbers = ManagementPeriod.objects.filter(
            document_number__startswith=prefix
        ).values_list('document_number', flat=True)

        for number in existing_numbers:
            match = re.fullmatch(r'ML-DTH-(\d{4})(\d{4})', (number or '').strip())
            if not match:
                continue

            sequence_str, year_str = match.groups()
            if int(year_str) != int(year):
                continue

            max_sequence = max(max_sequence, int(sequence_str))

        return f"{prefix}{max_sequence + 1:04d}{year}"

    def save(self, *args, **kwargs):
        is_new = not self.pk
        auto_generate_document_number = is_new and not self.document_number

        for attempt in range(5):
            if auto_generate_document_number:
                self.document_number = self._generate_document_number()

            try:
                # Usamos transaction.atomic por seguridad si se llama fuera de una vista transaccional
                with transaction.atomic():
                    super().save(*args, **kwargs)

                    # Actualizar el área del empleado automáticamente
                    if self.employee and self.administrative_unit:
                        if self.employee.area != self.administrative_unit:
                            self.employee.area = self.administrative_unit
                            self.employee.save()

                    if self.personnel_action_id is None and (getattr(self.contract_type, 'contract_type_category', '') or '').upper() == ContractType.TYPE_ACCION_PERSONAL:
                        self._create_linked_personnel_action()
                        super().save(update_fields=['personnel_action'])
                return
            except IntegrityError as error:
                # Reintento solo cuando el número fue autogenerado y colisiona por concurrencia.
                if auto_generate_document_number and attempt < 4 and 'document_number' in str(error):
                    continue
                raise


class History(models.Model):
    """Historial de cambios en contratos"""
    employee = models.ForeignKey(
        Employee,
        verbose_name='Employee',
        blank=True,
        null=True,
        on_delete=models.PROTECT
    )
    contract = models.ForeignKey(
        'ManagementPeriod',
        verbose_name='Contrato',
        blank=True,
        null=True,
        on_delete=models.PROTECT
    )
    user_register = models.CharField(
        verbose_name='Registro por:',
        max_length=100,
        blank=True,
        null=True
    )
    type = models.CharField(
        verbose_name='Tipo Historial',
        max_length=100,
        blank=True,
        null=True
    )
    date_register = models.DateTimeField(
        verbose_name='Fecha Registro',
        auto_now_add=True
    )
    reason = models.TextField(
        verbose_name='Motivo',
        blank=True,
        null=True
    )
    historical_position = models.CharField(
        verbose_name='Cargo en ese momento',
        max_length=255,
        blank=True,
        null=True
    )
    historical_salary = models.DecimalField(
        verbose_name='Sueldo en ese momento',
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'contract_history'
        ordering = ['-date_register']
        verbose_name = 'Historial'
        verbose_name_plural = 'Historiales'

    def __str__(self):
        return f'Historial #{self.pk} - {self.type or "Sin tipo"}'
