from django.db import models
from django.db.models import Q
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
    order = models.IntegerField(null=True, blank=True, verbose_name="Orden de Reporte")

    class Meta:
        verbose_name = 'Cuenta Contable'
        verbose_name_plural = 'Plan de Cuentas'

        constraints = [
            models.UniqueConstraint(
                fields=['order'],
                condition=Q(is_active=True),
                name='unique_active_account_order'
            )
        ]

    def save(self, *args, **kwargs):
        if getattr(self, 'is_active', True) and self.order is None:
            # Buscamos el último orden registrado
            ultimo_orden = Account.objects.filter(
                is_active=True, order__isnull=False
            ).order_by('-order').first()

            # Le sumamos 1 al último, o le ponemos 1 si es la primera cuenta
            self.order = (ultimo_orden.order + 1) if ultimo_orden else 1

        # Si la cuenta se inactiva, liberamos su número de orden para que pueda ser reusado
        elif not getattr(self, 'is_active', True):
            self.order = None

        super().save(*args, **kwargs)

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
    # Asociar a una partida presupuestaria
    budget_line = models.ForeignKey('budget.BudgetLine', on_delete=models.SET_NULL, null=True, blank=True, related_name='journal_items')
    reference = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Línea Asiento'
        verbose_name_plural = 'Líneas Asiento'

    def __str__(self):
        return f"{self.account.code} D:{self.debit} C:{self.credit} ({self.budget_line.code if self.budget_line else 'No Partida'})"
