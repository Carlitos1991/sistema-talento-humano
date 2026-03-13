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

    def __str__(self):
        return f"{self.name} ({self.value})"

    class Meta:
        verbose_name = _("Constante de Nómina")
        verbose_name_plural = _("Constantes de Nómina")


class Income(models.Model):
    """Rubros de Ingresos (Sueldo, Bonos, etc.)"""
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Nombre"))
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(verbose_name=_("Descripción"))
    is_active = models.BooleanField(default=True, verbose_name=_("Activo"))

    # --- AJUSTE CONTABLE ---
    debit_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='income_debits', verbose_name=_('Cuenta DEBE (Gasto)'))
    credit_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='income_credits', verbose_name=_('Cuenta HABER (Pasivo/Pago)'))

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Generar código automáticamente a partir del nombre: mayúsculas y guiones bajos
        if self.name:
            generated = slugify(self.name).replace('-', '_').upper()
            self.code = generated
        super().save(*args, **kwargs)


class Deduction(models.Model):
    """Rubros de Egresos (IESS, Préstamos, etc.)"""
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Nombre"))
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(verbose_name=_("Descripción"))
    is_active = models.BooleanField(default=True, verbose_name=_("Activo"))
    priority = models.IntegerField(
        default=100,
        verbose_name='Prioridad de Cobro',
        help_text='Menor número = Se cobra primero. Ej: 1=IESS, 2=Retención Judicial, 10=Cooperativa'
    )

    # --- AJUSTE CONTABLE ---
    debit_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='deduction_debits', verbose_name=_('Cuenta DEBE (Reducción Pasivo)'))
    credit_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='deduction_credits',
                                       verbose_name=_('Cuenta HABER (Retención a Pagar)'))

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.name:
            generated = slugify(self.name).replace('-', '_').upper()
            self.code = generated
        super().save(*args, **kwargs)


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


class Payslip(models.Model):
    """Cabecera del Rol de Pagos (Empleado + Periodo + Totales)"""
    period = models.ForeignKey(PayrollPeriod, on_delete=models.PROTECT, related_name='payslips')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='payslips')

    # Datos Base
    worked_days = models.IntegerField(default=30, verbose_name=_("Días Trabajados"))
    effective_worked_days = models.IntegerField(default=0, verbose_name='Días Efectivos Laborados')
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

    def __str__(self):
        return f"Rol: {self.employee} - {self.period}"


class InstitutionalContribution(models.Model):
    """
    Obligaciones patronales e institucionales (Ej: Aporte Patronal, Secap, IECE).
    No afectan el líquido a pagar del empleado, pero generan asientos contables y presupuestarios.
    """
    name = models.CharField(max_length=100, verbose_name="Nombre del Aporte")
    code = models.CharField(max_length=50, unique=True, verbose_name="Código del Algoritmo")
    description = models.TextField(blank=True, verbose_name=_("Descripción"))

    # Enlaces contables directos
    debit_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='contrib_debits', verbose_name="Cuenta DEBE (Gasto)")
    credit_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='contrib_credits', verbose_name="Cuenta HABER (Pasivo)")

    is_active = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Aporte Institucional"
        verbose_name_plural = "Aportes Institucionales"

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if self.name:
            generated = slugify(self.name).replace('-', '_').upper()
            self.code = generated
        super().save(*args, **kwargs)


class RubroBudgetMapping(models.Model):
    """
    Mapeo presupuestario usando Claves Foráneas para Integridad Referencial absoluta.
    Solo UNA de las tres FK debe tener datos por cada registro.
    """
    income = models.OneToOneField('Income', on_delete=models.CASCADE, null=True, blank=True,
                                  related_name='budget_mapping', verbose_name="Ingreso")
    deduction = models.OneToOneField('Deduction', on_delete=models.CASCADE, null=True, blank=True,
                                     related_name='budget_mapping', verbose_name="Descuento")
    contribution = models.OneToOneField(InstitutionalContribution, on_delete=models.CASCADE, null=True, blank=True,
                                        related_name='budget_mapping', verbose_name="Aporte Institucional")

    dynamic_suffix = models.CharField(max_length=50, help_text="Ej: 5.1.01.05", verbose_name="Sufijo Presupuestario")
    is_fixed = models.BooleanField(default=False, verbose_name="¿Es partida fija?")

    class Meta:
        verbose_name = "Mapeo Presupuestario"
        verbose_name_plural = "Mapeos Presupuestarios"

    def __str__(self):
        if self.income:
            return f"Ingreso: {self.income.name} -> {self.dynamic_suffix}"
        if self.deduction:
            return f"Descuento: {self.deduction.name} -> {self.dynamic_suffix}"
        if self.contribution:
            return f"Aporte: {self.contribution.name} -> {self.dynamic_suffix}"
        return f"Mapeo sin asignar -> {self.dynamic_suffix}"


class PayrollNovelty(models.Model):
    """
    Almacena las variaciones mensuales (novedades) de cada empleado,
    como préstamos, multas, horas extras, anticipos, etc.
    """
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='novelties',
                               verbose_name='Periodo')
    employee = models.ForeignKey('employee.Employee', on_delete=models.CASCADE, related_name='novelties',
                                 verbose_name='Empleado')

    # Puede ser un Ingreso (Ej: Horas extras) o un Egreso (Ej: Multa/Anticipo)
    income_ref = models.ForeignKey(Income, on_delete=models.CASCADE, null=True, blank=True,
                                   verbose_name='Rubro de Ingreso')
    deduction_ref = models.ForeignKey(Deduction, on_delete=models.CASCADE, null=True, blank=True,
                                      verbose_name='Rubro de Egreso')

    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Valor ($)')

    class Meta:
        verbose_name = 'Novedad de Nómina'
        verbose_name_plural = 'Novedades de Nómina'
        # Evita que se cargue dos veces el mismo rubro al mismo empleado en el mismo mes
        unique_together = [
            ('period', 'employee', 'income_ref'),
            ('period', 'employee', 'deduction_ref'),
        ]

    def __str__(self):
        rubro = self.income_ref.name if self.income_ref else (
            self.deduction_ref.name if self.deduction_ref else 'Sin rubro')
        return f"{self.employee} - {rubro}: ${self.value}"


class PayslipItem(models.Model):
    """Detalle del Rol (Ingresos y Egresos individuales)"""
    ITEM_TYPE = (('INCOME', 'Ingreso'), ('DEDUCTION', 'Descuento'), ('CONTRIBUTION', 'Contribución'))

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name='items')

    income_ref = models.ForeignKey(Income, on_delete=models.PROTECT, null=True, blank=True)
    deduction_ref = models.ForeignKey(Deduction, on_delete=models.PROTECT, null=True, blank=True)
    contribution_ref = models.ForeignKey(InstitutionalContribution, on_delete=models.CASCADE, null=True, blank=True)
    item_type = models.CharField(max_length=12, choices=ITEM_TYPE)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # Partida presupuestaria asociada a este ítem (si aplica)
    budget_line = models.ForeignKey('budget.BudgetLine', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='payslip_items', verbose_name=_('Partida Presupuestaria'))
    budget_line_code = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="Código de Partida Aplicada (Histórico)")

    class Meta:
        indexes = [models.Index(fields=['payslip', 'item_type'])]


class PendingDebt(BaseModel):
    """
    Tabla de Cuentas por Cobrar: Registra los saldos negativos cuando el sueldo no alcanza.
    """
    employee = models.ForeignKey('employee.Employee', on_delete=models.CASCADE, related_name='pending_debts',
                                 verbose_name='Empleado')
    period = models.ForeignKey('PayrollPeriod', on_delete=models.CASCADE, related_name='pending_debts',
                               verbose_name='Periodo')
    deduction_ref = models.ForeignKey('Deduction', on_delete=models.CASCADE, verbose_name='Descuento')

    original_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor Original')
    collected_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor Cobrado')
    pending_balance = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Saldo Pendiente')

    class Meta:
        db_table = 'payroll_pending_debt'
        verbose_name = 'Cuenta por Cobrar'
        verbose_name_plural = 'Cuentas por Cobrar'

    def __str__(self):
        return f"{self.employee} - Deuda: ${self.pending_balance}"
