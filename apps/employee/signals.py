from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.db import IntegrityError
from person.models import Person
from employee.models import Employee, InstitutionalData, Curriculum


@receiver(post_save, sender=Person)
def create_employee_profile(sender, instance, created, **kwargs):
    """
    Crea automáticamente un perfil de Empleado y datos institucionales básicos
    cuando se crea una Persona. Usamos get_or_create para evitar duplicados
    y una transacción para asegurar consistencia.
    """
    if created:
        try:
            with transaction.atomic():
                emp, emp_created = Employee.objects.get_or_create(person=instance)
                if emp_created:
                    print(f"Empleado creado automáticamente para Persona id={instance.id}")
                # Crear datos institucionales vacíos si no existen
                try:
                    inst, inst_created = InstitutionalData.objects.get_or_create(employee=emp)
                    if inst_created:
                        print(f"InstitutionalData creado para Employee id={emp.id}")
                except IntegrityError as ie:
                    print(f"IntegrityError creando InstitutionalData para Employee id={emp.id}: {ie}")
                    # Intentar recuperar si ya existe (condición de carrera o secuencia desincronizada)
                    inst = InstitutionalData.objects.filter(employee=emp).first()
                    inst_created = False
                    if not inst:
                        raise
                # Crear curriculum vacío si no existe
                cur, cur_created = Curriculum.objects.get_or_create(person=instance)
                if cur_created:
                    print(f"Curriculum creado para Persona id={instance.id}")
        except Exception as e:
            print(f"Error creando perfil de empleado automáticamente: {e}")


    @receiver(post_save, sender=Employee)
    def ensure_institutional_data_for_employee(sender, instance, created, **kwargs):
        """
        Asegura que exista un objeto InstitutionalData para cada Employee creado/actualizado.
        Esto cubre casos donde el Employee se crea fuera de la señal de Person.
        """
        try:
            try:
                inst, inst_created = InstitutionalData.objects.get_or_create(employee=instance)
                if inst_created:
                    print(f"InstitutionalData auto-creado por post_save Employee para Employee id={instance.id}")
            except IntegrityError as ie:
                print(f"IntegrityError creando InstitutionalData en post_save Employee id={instance.id}: {ie}")
                inst = InstitutionalData.objects.filter(employee=instance).first()
                if not inst:
                    raise
        except Exception as e:
            print(f"Error asegurando InstitutionalData para Employee id={getattr(instance,'id',None)}: {e}")