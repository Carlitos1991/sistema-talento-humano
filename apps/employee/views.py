# apps/employee/views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Employee
from budget.models import BudgetLine


@login_required
def search_employee_by_cedula(request):
    cedula = request.GET.get('q', '').strip()

    if not cedula:
        return JsonResponse({'success': False, 'message': 'Cédula no proporcionada.'})

    try:
        # Buscamos el Empleado a través de su relación con Persona
        # Nota: El campo en tu modelo Person es 'document_number'
        emp = Employee.objects.select_related('person').get(
            person__document_number=cedula,
            is_active=True
        )

        # VALIDACIÓN: ¿Este empleado ya ocupa OTRA partida?
        # Buscamos si el ID de este empleado ya está en algún BudgetLine
        existing_assignment = BudgetLine.objects.filter(current_employee=emp).first()

        if existing_assignment:
            return JsonResponse({
                'success': False,
                'message': f'La persona {emp.person.full_name} ya tiene asignada la partida {existing_assignment.code}.'
            })

        # Si está libre, devolvemos data para el modal
        return JsonResponse({
            'success': True,
            'id': emp.id,
            'full_name': emp.person.full_name,
            'email': emp.person.email or 'Sin correo registrado',
            'photo_url': emp.person.photo.url if emp.person.photo else None
        })

    except Employee.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'No se encontró un registro de Empleado con esa cédula. Asegúrese de que la Persona esté registrada y tenga un perfil de Empleado activo.'
        })