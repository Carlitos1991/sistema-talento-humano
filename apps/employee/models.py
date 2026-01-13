from django.db import models
from django.core.exceptions import ValidationError
from core.models import BaseModel, CatalogItem
from person.models import Person
from institution.models import AdministrativeUnit
from datetime import date


# ==============================================================================
# 1. PERFIL DE EMPLEADO (ESTRUCTURA PRINCIPAL)
# ==============================================================================

class Employee(BaseModel):
    """
    Vincula una Persona con la estructura organizacional.
    """
    person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        related_name='employee_profile',
        verbose_name="Persona"
    )
    area = models.ForeignKey(
        AdministrativeUnit,
        on_delete=models.PROTECT,
        related_name='employees',
        verbose_name="Área / Departamento",
        null=True, blank=True
    )
    employment_status = models.ForeignKey(
        CatalogItem,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'catalog__code': 'EMPLOYMENT_STATUS'},
        related_name='employees_by_status',
        verbose_name="Estado Laboral"
    )
    is_boss = models.BooleanField(
        default=False,
        verbose_name="Es Jefe/Director de Área"
    )
    date_joined = models.DateField(null=True, blank=True, verbose_name="Fecha de Ingreso")
    date_left = models.DateField(null=True, blank=True, verbose_name="Fecha de Salida")

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        ordering = ['person__last_name']

    def __str__(self):
        return f"{self.person.full_name}"


# ==============================================================================
# 2. DATOS INSTITUCIONALES (EXPEDIENTE)
# ==============================================================================

class InstitutionalData(BaseModel):
    """
    Datos de control interno y biométrico.
    """
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name='institutional_data',
        verbose_name='Empleado'
    )
    file_number = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='Número de Expediente'
    )
    biometric_id = models.CharField(
        max_length=50, blank=True, null=True, unique=True,
        verbose_name='ID Biométrico'
    )
    institutional_email = models.EmailField(
        max_length=100, blank=True, null=True, unique=True,
        verbose_name='Correo Institucional'
    )
    observations = models.TextField(blank=True, null=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Datos Institucionales'
        verbose_name_plural = 'Datos Institucionales'


# ==============================================================================
# 3. CURRICULUM VITAE (HOJA DE VIDA)
# ==============================================================================

class Curriculum(BaseModel):
    person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        related_name='curriculum',
        verbose_name='Persona'
    )
    pdf_file = models.FileField(
        upload_to='curriculum/pdfs/',
        blank=True, null=True,
        verbose_name='Curriculum PDF'
    )

    class Meta:
        verbose_name = 'Curriculum'
        verbose_name_plural = 'Curriculums'

    def get_total_work_years(self):
        total_days = 0
        for exp in self.work_experiences.all():
            end_date = exp.end_date or date.today()
            if exp.start_date:
                total_days += (end_date - exp.start_date).days
        return round(total_days / 365.25, 1)


class AcademicTitle(BaseModel):
    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name='academic_titles'
    )
    education_level = models.ForeignKey(
        CatalogItem,
        on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'EDUCATION_LEVELS'},
        related_name='academic_titles_by_level',
        verbose_name='Nivel de Instrucción'
    )
    title_obtained = models.CharField(max_length=200, verbose_name='Título Obtenido')
    educational_institution = models.CharField(max_length=200, verbose_name='Institución')
    senescyt_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='N° SENESCYT')
    graduation_year = models.IntegerField(null=True, blank=True, verbose_name='Año de Graduación')
    is_current = models.BooleanField(default=False, verbose_name='En Curso')


class WorkExperience(BaseModel):
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, related_name='work_experiences')
    company_name = models.CharField(max_length=200, verbose_name='Empresa')
    position = models.CharField(max_length=200, verbose_name='Cargo')
    start_date = models.DateField(verbose_name='Fecha Inicio')
    end_date = models.DateField(null=True, blank=True, verbose_name='Fecha Fin')
    is_current = models.BooleanField(default=False, verbose_name='Trabajo Actual')
    responsibilities = models.TextField(blank=True, null=True)


class Training(BaseModel):
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, related_name='trainings')
    training_name = models.CharField(max_length=200, verbose_name='Nombre del Curso')
    institution = models.CharField(max_length=200, verbose_name='Institución')
    hours = models.IntegerField(verbose_name='Horas')
    completion_date = models.DateField(null=True, blank=True)


# ==============================================================================
# 4. DATOS ECONÓMICOS Y NÓMINA
# ==============================================================================

class EconomicData(BaseModel):
    person = models.OneToOneField(
        Person, on_delete=models.CASCADE,
        related_name='economic_data',
        verbose_name='Persona'
    )

    class Meta:
        verbose_name = 'Datos Económicos'
        verbose_name_plural = 'Datos Económicos'


class BankAccount(BaseModel):
    economic_data = models.OneToOneField(
        EconomicData,
        on_delete=models.CASCADE,
        related_name='bank_account'
    )

    # Agregamos related_name únicos para evitar el choque
    bank = models.ForeignKey(
        CatalogItem,
        on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'BANCO'},
        related_name='bank_accounts_as_bank',  # <--- Único
        verbose_name='Banco'
    )

    account_type = models.ForeignKey(
        CatalogItem,
        on_delete=models.PROTECT,
        limit_choices_to={'catalog__code': 'ACCOUNT_TYPES'},
        related_name='bank_accounts_as_type',  # <--- Único
        verbose_name='Tipo de Cuenta'
    )

    account_number = models.CharField(max_length=50, verbose_name='Número de Cuenta')
    holder_name = models.CharField(max_length=200, verbose_name='Titular')

    class Meta:
        verbose_name = 'Cuenta Bancaria'
        verbose_name_plural = 'Cuentas Bancarias'


class PayrollInfo(BaseModel):
    """Corresponde al modelo Mensualizacion"""
    economic_data = models.OneToOneField(EconomicData, on_delete=models.CASCADE, related_name='payroll_info')
    monthly_payment = models.BooleanField(default=False, verbose_name='Mensualiza Décimos')
    reserve_funds = models.BooleanField(default=False, verbose_name='Mensualiza Fondos Reserva')
    family_dependents = models.IntegerField(default=0, verbose_name='Cargas Familiares')
    education_dependents = models.IntegerField(default=0, verbose_name='Cargas Educación')
    roles_entry_date = models.DateField(null=True, blank=True, verbose_name='Ingreso a Roles')

    def clean(self):
        if self.family_dependents < 0 or self.family_dependents > 20:
            raise ValidationError({'family_dependents': 'Debe estar entre 0 y 20'})
