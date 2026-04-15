from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from employee.models import Employee
from .models import BudgetLine


def _sync_user_position_from_employee(employee):
    if not employee:
        return

    person = getattr(employee, 'person', None)
    user = getattr(person, 'user', None) if person else None
    if not user:
        return

    default_position = user.get_default_signature_position()
    if default_position:
        user.custom_position = default_position
        user.save(update_fields=['custom_position'])


@receiver(pre_save, sender=BudgetLine)
def budgetline_store_previous_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_current_employee_id = None
        instance._previous_position_item_id = None
        return

    previous = sender.objects.filter(pk=instance.pk).only('current_employee_id', 'position_item_id').first()
    instance._previous_current_employee_id = previous.current_employee_id if previous else None
    instance._previous_position_item_id = previous.position_item_id if previous else None


@receiver(post_save, sender=BudgetLine)
def budgetline_sync_user_custom_position(sender, instance, **kwargs):
    previous_employee_id = getattr(instance, '_previous_current_employee_id', None)
    previous_position_id = getattr(instance, '_previous_position_item_id', None)

    current_employee_id = instance.current_employee_id
    current_position_id = instance.position_item_id

    if previous_employee_id == current_employee_id and previous_position_id == current_position_id:
        return

    affected_ids = {emp_id for emp_id in [previous_employee_id, current_employee_id] if emp_id}
    if not affected_ids:
        return

    for employee in Employee.objects.filter(pk__in=affected_ids).select_related('person__user'):
        _sync_user_position_from_employee(employee)
