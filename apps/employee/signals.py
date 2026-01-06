from django.db.models.signals import post_save
from django.dispatch import receiver
from person.models import Person
from employee.models import Employee

@receiver(post_save, sender=Person)
def create_employee_profile(sender, instance, created, **kwargs):
    """
    Crea automáticamente un perfil de Empleado cuando se crea una Persona.
    """
    if created:
        Employee.objects.create(person=instance)