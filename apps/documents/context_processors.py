from django.db.models import Q
from .models import Procedure, ProcedureTask
from institution.models import AdministrativeUnit


def procedure_counters(request):
    if not request.user.is_authenticated:
        return {'sidebar_pending_tramites_count': 0}

    user = request.user
    employee = getattr(getattr(user, 'person', None), 'employee_profile', None)
    user_unit = employee.area if employee else None

    main_unit = user_unit.get_scheduling_root_unit() if user_unit else None

    units_to_check = []
    if main_unit:
        units_to_check = main_unit.get_descendant_ids()
    elif user_unit:
        units_to_check = [user_unit.id]

    if user.is_superuser or user.has_perm('auth.dashboard_talento_humano') or (main_unit and user_unit):
        pending_count = Procedure.objects.filter(
            Q(current_unit_id__in=units_to_check) |
            Q(tasks__unit_id__in=units_to_check) |
            Q(tasks__assigned_to=user),
            status__in=[Procedure.Status.IN_DESPATCH, Procedure.Status.IN_PROCESS],
        is_active = True
        ).distinct().count()
    else:
        pending_count = ProcedureTask.objects.filter(
            assigned_to=user,
            status__in=[ProcedureTask.TaskStatus.PENDING, ProcedureTask.TaskStatus.IN_PROCESS],
            is_active=True
        ).count()

    return {
        'sidebar_pending_tramites_count': pending_count
    }
