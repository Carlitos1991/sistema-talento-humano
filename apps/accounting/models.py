from django.db import models

from core.models import BaseModel


class Account(BaseModel):
    ACCOUNT_TYPES = (
        ('ASSET', 'Activo'),
        ('LIABILITY', 'Pasivo'),
        ('EQUITY', 'Patrimonio'),
        ('INCOME', 'Ingreso'),
        ('EXPENSE', 'Gasto'),
    )

    code = models.CharField(max_length=50, unique=True, verbose_name='Código Cuenta')
    name = models.CharField(max_length=255, verbose_name='Nombre Cuenta')
    type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, verbose_name='Tipo de Cuenta')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Cuenta Contable'
        verbose_name_plural = 'Plan de Cuentas'

    def __str__(self):
        return f"{self.code} - {self.name}"


class Journal(BaseModel):
    date = models.DateField(verbose_name='Fecha')
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Asiento'
        verbose_name_plural = 'Asientos'

    def __str__(self):
        return f"Asiento {self.id} - {self.date} - {self.description or ''}"


class JournalItem(models.Model):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='items')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_items')
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Asociar a una partida presupuestaria opcionalmente
    budget_line = models.ForeignKey('budget.BudgetLine', on_delete=models.SET_NULL, null=True, blank=True, related_name='journal_items')
    reference = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Línea Asiento'
        verbose_name_plural = 'Líneas Asiento'

    def __str__(self):
        return f"{self.account.code} D:{self.debit} C:{self.credit} ({self.budget_line.code if self.budget_line else 'No Partida'})"
