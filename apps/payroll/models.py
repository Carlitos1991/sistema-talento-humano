from django.db import models
from django.utils.translation import gettext_lazy as _
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


class Deduction(models.Model):
    """Rubros de Egresos (IESS, Préstamos, etc.)"""
    TYPE_CHOICES = (('Mensual', 'Monthly'), ('Quincenal', 'Bi-weekly'))
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Nombre"))
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(verbose_name=_("Descripción"))
    is_active = models.BooleanField(default=True, verbose_name=_("Activo"))
    type = models.CharField(max_length=100, choices=TYPE_CHOICES)

    # --- AJUSTE CONTABLE ---
    debit_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='deduction_debits', verbose_name=_('Cuenta DEBE (Reducción Pasivo)'))
    credit_account = models.ForeignKey('accounting.Account', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='deduction_credits',
                                       verbose_name=_('Cuenta HABER (Retención a Pagar)'))

    def __str__(self):
        return self.name


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


class PayslipItem(models.Model):
    """Detalle del Rol (Ingresos y Egresos individuales)"""
    ITEM_TYPE = (('INCOME', 'Ingreso'), ('DEDUCTION', 'Descuento'))

    # Aquí usamos 'Payslip' como string para evitar errores de referencia circular,
    # aunque estando abajo de la clase Payslip ya no debería fallar.
    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name='items')

    income_ref = models.ForeignKey(Income, on_delete=models.PROTECT, null=True, blank=True)
    deduction_ref = models.ForeignKey(Deduction, on_delete=models.PROTECT, null=True, blank=True)

    item_type = models.CharField(max_length=10, choices=ITEM_TYPE)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # Partida presupuestaria asociada a este ítem (si aplica)
    budget_line = models.ForeignKey('budget.BudgetLine', on_delete=models.SET_NULL, null=True, blank=True, related_name='payslip_items', verbose_name=_('Partida Presupuestaria'))

    class Meta:
        indexes = [models.Index(fields=['payslip', 'item_type'])]


class RubroBudgetMapping(models.Model):
    """Mapa explícito entre un rubro (ingreso/desc.) y una partida presupuestaria.

    Permite mapeos generales o específicos por unidad administrativa.
    """
    RUBRO_TYPE = (('INCOME', 'Ingreso'), ('DEDUCTION', 'Descuento'))

    rubro_type = models.CharField(max_length=10, choices=RUBRO_TYPE)
    rubro_code = models.CharField(max_length=50, verbose_name=_('Código Rubro'))
    budget_line = models.ForeignKey('budget.BudgetLine', on_delete=models.PROTECT, related_name='rubro_mappings')
    administrative_unit = models.ForeignKey(
        'institution.AdministrativeUnit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rubro_mappings',
        verbose_name=_('Unidad Administrativa (opcional)')
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('rubro_type', 'rubro_code', 'administrative_unit')
        verbose_name = _('Mapa Rubro-Partida')
        verbose_name_plural = _('Mapas Rubro-Partida')

    def __str__(self):
        unit = f" / {self.administrative_unit}" if self.administrative_unit else ''
        return f"{self.get_rubro_type_display()} {self.rubro_code} -> {self.budget_line}{unit}"
