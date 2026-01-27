from django.db import models

from core.models import User, Authorities, CatalogItem
from employee.models import Employee
from institution.models import AdministrativeUnit


class ActionType(models.Model):
    """
    Catálogo de Tipos de Acción (ej: Nombramiento, Ascenso, Vacaciones)
    """
    name = models.CharField(verbose_name='Nombre', max_length=100)
    code = models.CharField(verbose_name='Código', max_length=20, unique=True, help_text="Ej: ASC, NOM, REM")
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

    # Fechas
    date_issue = models.DateField(verbose_name='Fecha de Emisión')
    date_effective = models.DateField(verbose_name='Rige a partir de')

    # Estado del flujo
    is_registered = models.BooleanField(verbose_name='Registrada', default=False)
    date_registered = models.DateField(verbose_name='Fecha de Registro', blank=True, null=True)

    # Firmas (Relaciones optimizadas)
    authority_1 = models.ForeignKey(Authorities, verbose_name='Primera Autoridad', on_delete=models.PROTECT,
                                    related_name='actions_signed_auth1', limit_choices_to={'status': True})
    authority_2 = models.ForeignKey(Authorities, verbose_name='Segunda Autoridad', on_delete=models.PROTECT,
                                    related_name='actions_signed_auth2', limit_choices_to={'status': True}, null=True,
                                    blank=True)
    reviewer = models.ForeignKey(Authorities, verbose_name='Revisado por', on_delete=models.PROTECT,
                                 related_name='actions_reviewed', limit_choices_to={'status': True}, null=True,
                                 blank=True)
    elaboration = models.ForeignKey(Authorities, verbose_name='Elaborado por', on_delete=models.PROTECT,
                                 related_name='actions_elaboration', limit_choices_to={'status': True}, null=True,
                                 blank=True)
    register = models.ForeignKey(Authorities, verbose_name='Registrado   por', on_delete=models.PROTECT,
                                    related_name='actions_register', limit_choices_to={'status': True}, null=True,
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


class ActionMovement(models.Model):
    """
    Detalle del movimiento: Situación Actual vs Situación Propuesta.
    Se usa OneToOne porque una acción generalmente implica un solo movimiento lógico principal.
    """
    personnel_action = models.ForeignKey(PersonnelAction, on_delete=models.CASCADE, related_name='movement')

    # --- SITUACIÓN ACTUAL (Snapshots o FKs) ---
    previous_unit = models.ForeignKey(AdministrativeUnit, verbose_name='Unidad Anterior', on_delete=models.PROTECT,
                                      related_name='movements_from', null=True, blank=True)
    previous_position = models.ForeignKey(CatalogItem, verbose_name='Puesto Anterior', on_delete=models.PROTECT,
                                          related_name='movements_from_pos', null=True, blank=True)
    previous_remuneration = models.DecimalField(verbose_name='RMU Anterior', max_digits=10, decimal_places=2, default=0)

    # --- SITUACIÓN PROPUESTA ---
    new_unit = models.ForeignKey(AdministrativeUnit, verbose_name='Unidad Nueva', on_delete=models.PROTECT,
                                 related_name='movements_to', null=True, blank=True)
    new_position = models.ForeignKey(CatalogItem, verbose_name='Puesto Nuevo', on_delete=models.PROTECT,
                                     related_name='movements_to_pos', null=True, blank=True)
    new_remuneration = models.DecimalField(verbose_name='RMU Nuevo', max_digits=10, decimal_places=2, default=0)

    # Ubicación Física
    location_text = models.CharField(verbose_name='Lugar de Trabajo', max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = 'Detalle del Movimiento'
        verbose_name_plural = 'Detalles de Movimientos'

    def __str__(self):
        return f"Movimiento de {self.personnel_action.number}"