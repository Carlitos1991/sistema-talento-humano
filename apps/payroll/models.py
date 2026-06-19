from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify

from accounting.models import Account
from core.models import BaseModel
from employee.models import Employee


class PayrollConstant(models.Model):
    """Reemplaza a: Valor_Rol (SBU, IESS, etc.)"""
    name = models.CharField(max_length=150, unique=True, verbose_name=_("Nombre"))
    code = models.CharField(max_length=30, unique=True, verbose_name=_("Código"))
    value = models.DecimalField(max_digits=10, decimal_places=4, verbose_name=_("Valor"))
    description = models.TextField(blank=True, verbose_name=_("Descripción"))
    is_active = models.BooleanField(default=True, verbose_name=_("Activo"))

    def __str__(self):
        return f"{self.name} ({self.value})"

    class Meta:
        verbose_name = _("Constante de Nómina")
        verbose_name_plural = _("Constantes de Nómina")


class PayrollRubric(models.Model):
    RUBRIC_TYPES = (
        ('INCOME', 'Ingreso'),
        ('DEDUCTION', 'Descuento/Egreso'),
        ('CONTRIBUTION', 'Aportes Institucionales'),
    )
    CONTEXT_CHOICES = (
        ('TODOS', '1. Todos (Universal)'),
        ('5.1', '2. Corriente (5.1)'),
        ('7.1', '3. Inversión (7.1)'),
        ('6.1', '4. Producción (6.1)'),
    )

    rubric_type = models.CharField(max_length=15, choices=RUBRIC_TYPES, verbose_name="Tipo de Rubro")
    name = models.CharField(max_length=255, verbose_name="Nombre")
    code = models.CharField(max_length=50, unique=True)
    is_salary = models.BooleanField(default=False, verbose_name="¿Es Sueldo / Remuneración Base?",
                                    help_text="Marque esta casilla solo para el rubro que represente el Sueldo Mensual Base.")
    description = models.TextField(null=True, blank=True)
    spending_context = models.CharField(max_length=10, choices=CONTEXT_CHOICES, default='TODOS',
                                        verbose_name="Contexto de Gasto")
    abbreviation = models.CharField(max_length=30, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=100)
    priority = models.IntegerField(default=100, null=True, blank=True)

    # --- MATRIZ CONTABLE (Corriente, Producción, Inversión) ---
    debit_account = models.ForeignKey('accounting.Account', related_name='rubric_debits_corr',
                                      on_delete=models.SET_NULL, null=True, blank=True)
    credit_account = models.ForeignKey('accounting.Account', related_name='rubric_credits_corr',
                                       on_delete=models.SET_NULL, null=True, blank=True)

    debit_account_prod = models.ForeignKey('accounting.Account', related_name='rubric_debits_prod',
                                           on_delete=models.SET_NULL, null=True, blank=True)
    credit_account_prod = models.ForeignKey('accounting.Account', related_name='rubric_credits_prod',
                                            on_delete=models.SET_NULL, null=True, blank=True)

    debit_account_inv = models.ForeignKey('accounting.Account', related_name='rubric_debits_inv',
                                          on_delete=models.SET_NULL, null=True, blank=True)
    credit_account_inv = models.ForeignKey('accounting.Account', related_name='rubric_credits_inv',
                                           on_delete=models.SET_NULL, null=True, blank=True)

    income_account = models.ForeignKey('accounting.Account', related_name='rubric_incomes', on_delete=models.SET_NULL,
                                       null=True, blank=True)

    # --- MAPEO PRESUPUESTARIO INTEGRADO ---
    has_mapping = models.BooleanField(default=False, verbose_name="¿Afecta al Presupuesto?")
    dynamic_suffix = models.CharField(max_length=50, null=True, blank=True, verbose_name="Sufijo Presupuestario")
    is_fixed = models.BooleanField(default=False, verbose_name="¿Es Partida Fija?")

    def __str__(self):
        return f"[{self.get_rubric_type_display()}] {self.name}"


class PayrollPeriod(models.Model):
    """Periodo de Nómina (Mes y Año)"""
    MONTH_CHOICES = (
        ('ENERO', 'ENERO'), ('FEBRERO', 'FEBRERO'), ('MARZO', 'MARZO'),
        ('ABRIL', 'ABRIL'), ('MAYO', 'MAYO'), ('JUNIO', 'JUNIO'),
        ('JULIO', 'JULIO'), ('AGOSTO', 'AGOSTO'), ('SEPTIEMBRE', 'SEPTIEMBRE'),
        ('OCTUBRE', 'OCTUBRE'), ('NOVIEMBRE', 'NOVIEMBRE'), ('DICIEMBRE', 'DICIEMBRE')
    )

    month = models.CharField(max_length=15, choices=MONTH_CHOICES, verbose_name=_("Mes"))
    year = models.CharField(max_length=4, verbose_name=_("Año"))
    start_date = models.DateField(verbose_name=_("Fecha Inicio"))
    end_date = models.DateField(verbose_name=_("Fecha Fin"))
    working_days = models.IntegerField(default=30, verbose_name=_("Días Laborables"))
    is_closed = models.BooleanField(default=False, verbose_name=_("Cerrado"))

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('month', 'year')
        ordering = ['-year', '-id']
        verbose_name = _("Periodo de Nómina")

    def __str__(self):
        return f"{self.month} {self.year}"

    def get_working_days(self):
        """
        Calcula dinámicamente los días laborables del período,
        considerando feriados registrados en ScheduleObservation.
        Se usa en lugar de confiar solo en el campo guardado.
        """
        from datetime import timedelta
        from schedule.models import ScheduleObservation

        first_day = self.start_date
        last_day = self.end_date

        # Obtener feriados activos en el rango
        holidays = ScheduleObservation.objects.filter(
            is_holiday=True,
            is_active=True,
            start_date__lte=last_day,
            end_date__gte=first_day
        )

        # Compilar conjunto de fechas de feriados
        holiday_dates = set()
        for holiday in holidays:
            curr = max(holiday.start_date, first_day)
            end_limit = min(holiday.end_date, last_day)
            while curr <= end_limit:
                holiday_dates.add(curr)
                curr += timedelta(days=1)

        # Contar lunes-viernes sin feriados
        working_days = 0
        current = first_day
        while current <= last_day:
            if current.weekday() < 5 and current not in holiday_dates:
                working_days += 1
            current += timedelta(days=1)

        return working_days

    @property
    def month_number(self):
        mapping = {
            'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
            'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
            'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
        }
        return mapping.get(self.month.upper(), 0)


class Payslip(models.Model):
    """Cabecera del Rol de Pagos (Empleado + Periodo + Totales)"""
    period = models.ForeignKey(PayrollPeriod, on_delete=models.PROTECT, related_name='payslips')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='payslips')

    # Datos Base
    worked_days = models.IntegerField(default=30, verbose_name=_("Días Trabajados"))
    effective_worked_days = models.IntegerField(default=0, verbose_name='Días Efectivos Laborados')
    is_paid = models.BooleanField(
        default=False,
        verbose_name='Pagado / Enviado al Banco',
        help_text='Si es True, este rol ya se envió en un archivo SPI-SP y no debe volver a salir en los alcances.'
    )
    is_withheld = models.BooleanField(
        default=False,
        verbose_name='Pago Retenido',
        help_text='Si es True, este rol no saldrá en los reportes de transferencia bancaria'
    )
    # --- CAMPOS LEGADOS (Horas Extras y Recargos) ---
    extra_hours = models.DecimalField(
        default=0.00, max_digits=5, decimal_places=2,
        verbose_name=_("Horas Extras (Fines de semana)")
    )
    supplementary_hours = models.DecimalField(
        default=0.00, max_digits=5, decimal_places=2,
        verbose_name=_("Horas Suplementarias (Lun-Vie)")
    )
    night_hours = models.DecimalField(
        default=0.00, max_digits=5, decimal_places=2,
        verbose_name=_("Horas Nocturnas")
    )

    # Totales Monetarios
    total_income = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    employer_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        indexes = [
            models.Index(fields=['period', 'employee']),
        ]
        # ordering = ['employee__person__lastname']
        verbose_name = _("Rol de Pago")

    @property
    def historical_position(self):
        """
        Busca en el historial de asignaciones qué cargo (puesto) tenía el empleado
        durante el periodo específico de este rol de pagos.
        """
        from budget.models import BudgetAssignmentHistory
        from django.db.models import Q

        # Buscamos la asignación presupuestaria que estuvo vigente en este periodo
        assignment = BudgetAssignmentHistory.objects.filter(
            employee=self.employee,
            start_date__lte=self.period.end_date
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)
        ).select_related('budget_line', 'budget_line__position').first()

        if assignment and assignment.budget_line:
            pos = getattr(assignment.budget_line, 'position', None)
            if pos:
                return getattr(pos, 'name', str(pos))
            # Fallbacks por si acaso la estructura difiere
            return getattr(assignment.budget_line, 'name', getattr(assignment.budget_line, 'description', ''))

        # Fallback si no hay historial: usamos el cargo actual que tiene registrado
        inst_data = getattr(self.employee, 'institutional_data', None)
        if inst_data and getattr(inst_data, 'position', None):
            pos = inst_data.position
            return getattr(pos, 'name', str(pos))

        return "No asignado"

    def __str__(self):
        return f"Rol: {self.employee} - {self.period}"


class PayrollNovelty(models.Model):
    """
    Almacena las variaciones mensuales (novedades) de cada empleado,
    como préstamos, multas, horas extras, anticipos, etc.
    """
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='novelties',
                               verbose_name='Periodo')
    employee = models.ForeignKey('employee.Employee', on_delete=models.CASCADE, related_name='novelties',
                                 verbose_name='Empleado')

    rubric = models.ForeignKey(PayrollRubric, on_delete=models.CASCADE, verbose_name='Rubro', null=True, blank=True)

    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Valor ($)')

    class Meta:
        verbose_name = 'Novedad de Nómina'
        verbose_name_plural = 'Novedades de Nómina'
        unique_together = ('period', 'employee', 'rubric')

    def __str__(self):
        return f"{self.employee} - {self.rubric.name}: ${self.value}"


class PayslipItem(models.Model):
    """Detalle del Rol (Ingresos y Egresos individuales)"""
    ITEM_TYPE = (('INCOME', 'Ingreso'), ('DEDUCTION', 'Descuento'), ('CONTRIBUTION', 'Contribución'))

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name='items')

    rubric = models.ForeignKey(PayrollRubric, on_delete=models.PROTECT, null=True, blank=True)
    item_type = models.CharField(max_length=15)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # Partida presupuestaria asociada a este ítem (si aplica)
    budget_line = models.ForeignKey('budget.BudgetLine', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='payslip_items', verbose_name=_('Partida Presupuestaria'))
    budget_line_code = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="Código de Partida Aplicada (Histórico)")
    # Orden de presentación en el rol (menor número = aparece primero)
    order = models.IntegerField(default=100, verbose_name=_("Orden de Presentación"))

    class Meta:
        indexes = [models.Index(fields=['payslip', 'item_type'])]
        ordering = ['order', 'id']


class PendingDebt(BaseModel):
    """
    Tabla de Cuentas por Cobrar: Registra los saldos negativos cuando el sueldo no alcanza.
    """
    employee = models.ForeignKey('employee.Employee', on_delete=models.CASCADE, related_name='pending_debts',
                                 verbose_name='Empleado')
    period = models.ForeignKey('PayrollPeriod', on_delete=models.CASCADE, related_name='pending_debts',
                               verbose_name='Periodo')
    rubric = models.ForeignKey(PayrollRubric, on_delete=models.CASCADE, verbose_name='Descuento', null=True, blank=True)
    original_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor Original')
    collected_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor Cobrado')
    pending_balance = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Saldo Pendiente')

    class Meta:
        db_table = 'payroll_pending_debt'
        verbose_name = 'Cuenta por Cobrar'
        verbose_name_plural = 'Cuentas por Cobrar'

    def __str__(self):
        return f"{self.employee} - Deuda: ${self.pending_balance}"
