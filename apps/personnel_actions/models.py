from django.db import models

from core.models import User, CatalogItem
from employee.models import Employee
from institution.models import AdministrativeUnit
from budget.models import BudgetLine


class ActionType(models.Model):
    """
    Catálogo de Tipos de Acción (ej: Nombramiento, Ascenso, Vacaciones)
    """
    name = models.CharField(verbose_name='Nombre', max_length=100)
    code = models.CharField(verbose_name='Código', max_length=35, unique=True, help_text="Ej: ASC, NOM, REM")
    is_active = models.BooleanField(verbose_name='Activo', default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Tipo de Acción'
        verbose_name_plural = 'Tipos de Acciones'

    def __str__(self):
        return self.name


class PersonnelAction(models.Model):
    """
    Cabecera de la Acción de Personal. Contiene metadatos, fechas y firmas.
    """
    employee = models.ForeignKey(Employee, verbose_name='Empleado', on_delete=models.PROTECT,
                                 related_name='personnel_actions')
    action_type = models.ForeignKey(ActionType, verbose_name='Tipo de Acción', on_delete=models.PROTECT)

    # Identificación
    number = models.CharField(verbose_name='Número de Acción', max_length=50, unique=True)
    explanation = models.TextField(verbose_name='Explicación/Motivo', blank=True, null=True)
    motivation = models.CharField(verbose_name='Motivación', max_length=255, blank=True, null=True)

    # Fechas
    date_issue = models.DateField(verbose_name='Fecha de Emisión')
    date_effective = models.DateField(verbose_name='Rige a partir de')

    # Estado del flujo
    is_registered = models.BooleanField(verbose_name='Registrada', default=False)
    date_registered = models.DateField(verbose_name='Fecha de Registro', blank=True, null=True)

    # Firmas (Relaciones optimizadas)
    authority_1 = models.ForeignKey(User, verbose_name='Primera Autoridad', on_delete=models.PROTECT,
                                    related_name='actions_signed_auth1', limit_choices_to={'is_active': True})
    authority_2 = models.ForeignKey(User, verbose_name='Segunda Autoridad', on_delete=models.PROTECT,
                                    related_name='actions_signed_auth2', limit_choices_to={'is_active': True}, null=True,
                                    blank=True)
    reviewer = models.ForeignKey(User, verbose_name='Revisado por', on_delete=models.PROTECT,
                                 related_name='actions_reviewed', limit_choices_to={'is_active': True}, null=True,
                                 blank=True)
    elaboration = models.ForeignKey(User, verbose_name='Elaborado por', on_delete=models.PROTECT,
                                 related_name='actions_elaboration', limit_choices_to={'is_active': True}, null=True,
                                 blank=True)
    register = models.ForeignKey(User, verbose_name='Registrado   por', on_delete=models.PROTECT,
                                    related_name='actions_register', limit_choices_to={'is_active': True}, null=True,
                                    blank=True)

    # Auditoría
    created_by = models.ForeignKey(User, verbose_name='Creado por', on_delete=models.PROTECT,
                                   related_name='created_actions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_issue', '-number']
        verbose_name = 'Acción de Personal'
        verbose_name_plural = 'Acciones de Personal'

    def __str__(self):
        return f"{self.number} - {self.employee}"

    @property
    def elaboration_signature_name(self):
        user = self.elaboration or self.created_by
        return user.signature_name if user else ''

    @property
    def elaboration_signature_position(self):
        user = self.elaboration or self.created_by
        return user.signature_position if user else ''

    @property
    def authority_1_signature_name(self):
        return self.authority_1.signature_name if self.authority_1 else ''

    @property
    def authority_1_signature_position(self):
        return self.authority_1.signature_position if self.authority_1 else ''

    @property
    def authority_2_signature_name(self):
        return self.authority_2.signature_name if self.authority_2 else ''

    @property
    def authority_2_signature_position(self):
        return self.authority_2.signature_position if self.authority_2 else ''

    @property
    def reviewer_signature_name(self):
        return self.reviewer.signature_name if self.reviewer else ''

    @property
    def reviewer_signature_position(self):
        return self.reviewer.signature_position if self.reviewer else ''

    @property
    def register_signature_name(self):
        return self.register.signature_name if self.register else ''

    @property
    def register_signature_position(self):
        return self.register.signature_position if self.register else ''


class ActionMovement(models.Model):
    """
    Detalle del movimiento: Situación Actual vs Situación Propuesta.
    Se usa OneToOne porque una acción generalmente implica un solo movimiento lógico principal.
    """
    personnel_action = models.ForeignKey(PersonnelAction, on_delete=models.CASCADE, related_name='movement')

    # --- SITUACIÓN ACTUAL (Snapshots o FKs) ---
    previous_unit = models.CharField(verbose_name='Unidad Administrativa anterior', max_length=200, blank=True, null=True)
    previous_position = models.CharField(verbose_name='Puesto anterior', max_length=200, blank=True, null=True)
    previous_remuneration = models.DecimalField(verbose_name='RMU Anterior', max_digits=10, decimal_places=2, default=0)
    previous_budget_line = models.ForeignKey(BudgetLine, verbose_name='Partida Anterior', on_delete=models.SET_NULL,
                                             related_name='movements_from_budget', null=True, blank=True)

    # --- SITUACIÓN PROPUESTA ---
    new_unit = models.CharField(verbose_name='Unidad nueva', max_length=200, blank=True, null=True)
    new_position = models.CharField(verbose_name='Puesto nuevo', max_length=200, blank=True, null=True)
    new_remuneration = models.DecimalField(verbose_name='RMU Nuevo', max_digits=10, decimal_places=2, default=0)
    new_budget_line = models.ForeignKey(BudgetLine, verbose_name='Partida Presupuestaria Nueva', on_delete=models.SET_NULL,
                                        related_name='movements_to_budget', null=True, blank=True)

    # Ubicación Física
    location_text = models.CharField(verbose_name='Lugar de Trabajo', max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = 'Detalle del Movimiento'
        verbose_name_plural = 'Detalles de Movimientos'

    def __str__(self):
        return f"Movimiento de {self.personnel_action.number}"