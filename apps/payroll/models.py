from django.db import models
from employee.models import Employee
from django.utils.translation import gettext_lazy as _


class Income(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Nombre"))
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(verbose_name=_("Descripción"))
    is_active = models.BooleanField(default=True, verbose_name=_("Activo"))

    def __str__(self):
        return self.name


class Deduction(models.Model):
    TYPE_CHOICES = (('Mensual', 'Monthly'), ('Quincenal', 'Bi-weekly'))
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Nombre"))
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(verbose_name=_("Descripción"))
    is_active = models.BooleanField(default=True, verbose_name=_("Activo"))
    type = models.CharField(max_length=100, choices=TYPE_CHOICES)

    def __str__(self):
        return self.name


class PayrollConstant(models.Model):
    """
    Reemplaza a: Valor_Rol.
    Almacena SBU, Porcentajes del IESS, etc.
    """
    name = models.CharField(max_length=150, unique=True, verbose_name=_("Nombre"))
    code = models.CharField(max_length=30, unique=True, verbose_name=_("Código"))
    value = models.DecimalField(max_digits=10, decimal_places=4, verbose_name=_("Valor"))
    description = models.TextField(blank=True, verbose_name=_("Descripción"))

    def __str__(self):
        return f"{self.name} ({self.value})"

    class Meta:
        verbose_name = _("Constante de Nómina")
        verbose_name_plural = _("Constantes de Nómina")


class PayrollPeriod(models.Model):
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
    working_days = models.IntegerField(default=30)
    is_closed = models.BooleanField(default=False, verbose_name=_("Cerrado"))

    class Meta:
        unique_together = ('month', 'year')
        indexes = [
            models.Index(fields=['year', 'month']),
        ]
        ordering = ['-year', '-id']

    def __str__(self):
        return f"{self.month} {self.year}"


class Payslip(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='payslips')
    period = models.ForeignKey(PayrollPeriod, on_delete=models.PROTECT, related_name='payslips')

    worked_days = models.IntegerField(default=30)
    total_income = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Campos calculados (IESS Patronal, etc.)
    employer_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['period', 'employee']),
        ]
        ordering = ['employee__pk']


class PayslipItem(models.Model):
    """Modelo unificado para Ingresos y Descuentos por Rol para optimizar consultas"""
    ITEM_TYPE = (('INCOME', 'Ingreso'), ('DEDUCTION', 'Descuento'))

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name='items')
    income_ref = models.ForeignKey(Income, on_delete=models.PROTECT, null=True, blank=True)
    deduction_ref = models.ForeignKey(Deduction, on_delete=models.PROTECT, null=True, blank=True)

    item_type = models.CharField(max_length=10, choices=ITEM_TYPE)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        indexes = [models.Index(fields=['payslip', 'item_type'])]
