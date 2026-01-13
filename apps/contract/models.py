from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models import BaseModel, CatalogItem
from employee.models import Employee
from budget.models import BudgetLine
from institution.models import AdministrativeUnit
from schedule.models import Schedule


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
        BudgetLine, on_delete=models.PROTECT,
        related_name='management_periods', verbose_name='Partida Presupuestaria'
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
        related_name='management_periods', verbose_name='Unidad Administrativa'
    )
    schedule = models.ForeignKey(
        Schedule, on_delete=models.PROTECT,
        related_name='management_periods', verbose_name='Horario'
    )

    # Detalles del Puesto
    job_functions = models.TextField(verbose_name='Funciones del Puesto')
    workplace = models.CharField(verbose_name='Lugar de Trabajo', max_length=255)

    # Referencias Legales/Presupuestarias
    institutional_need_memo = models.CharField(verbose_name='Memo Necesidad', max_length=100)
    budget_certification = models.CharField(verbose_name='Certificación Presup.', max_length=100)

    # Fechas
    start_date = models.DateField(verbose_name='Fecha de Inicio')
    end_date = models.DateField(verbose_name='Fecha de Fin', blank=True, null=True)

    # Archivos
    signed_document = models.FileField(
        verbose_name='Documento Firmado',
        upload_to='contracts/%Y/%m/', blank=True, null=True
    )

    class Meta:
        db_table = 'contract_management_period'
        verbose_name = 'Período de Gestión'
        verbose_name_plural = 'Períodos de Gestión'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.document_number} | {self.employee.person.full_name}'

    def clean(self):
        super().clean()
        if self.end_date and self.start_date > self.end_date:
            raise ValidationError({'end_date': 'La fecha de fin no puede ser anterior al inicio.'})

        if not self.pk:
            # VALIDACIÓN DINÁMICA:
            # Bloquear si la partida tiene cualquier contrato que NO esté FINALIZADO
            active_occupation = ManagementPeriod.objects.filter(
                budget_line=self.budget_line
            ).exclude(status__code='FINALIZADO').exists()

            if active_occupation:
                raise ValidationError({
                    'budget_line': 'Esta partida ya se encuentra ocupada o tiene un proceso de contrato en curso.'
                })

    @property
    def is_currently_active(self):
        today = timezone.now().date()
        date_active = self.start_date <= today
        if self.end_date:
            date_active = date_active and today <= self.end_date
        return date_active and self.status.code == 'ACTIVO'

    def save(self, *args, **kwargs):
        # 1. GENERACIÓN AUTOMÁTICA DEL CÓDIGO (Solo para registros nuevos)
        if not self.pk or not self.document_number:
            # Obtenemos el conteo histórico para la secuencia
            sequence = ManagementPeriod.objects.count() + 1
            regime_code = self.contract_type.labor_regime.code

            # Formato: ML-DTH-00n-CODE (con 3 ceros de padding)
            self.document_number = f"ML-DTH-{sequence:03d}-{regime_code}"

        # 2. TRANSACCIÓN ATÓMICA PARA SINCRONIZAR EMPLEADO
        # Usamos transaction.atomic por seguridad si se llama fuera de una vista transaccional
        with transaction.atomic():
            super().save(*args, **kwargs)

            # Actualizar el área del empleado automáticamente
            if self.employee and self.administrative_unit:
                # Solo actualizamos si es diferente para ahorrar recursos
                if self.employee.area != self.administrative_unit:
                    self.employee.area = self.administrative_unit
                    # Actualizamos también el estado laboral a activo si fuera necesario
                    self.employee.save()


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

    class Meta:
        db_table = 'contract_history'
        ordering = ['-date_register']
        verbose_name = 'Historial'
        verbose_name_plural = 'Historiales'

    def __str__(self):
        return f'Historial #{self.pk} - {self.type or "Sin tipo"}'
