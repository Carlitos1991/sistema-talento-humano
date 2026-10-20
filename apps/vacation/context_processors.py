from .models import ScheduleDiscrepancyRequest


def schedule_discrepancy_notifications(request):
    """Expone el contador de novedades pendientes para el menú de Vacaciones."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'vacation_pending_discrepancies_count': 0,
            'vacation_show_discrepancy_counter': False,
        }

    can_manage = request.user.has_perm('vacation.change_vacationscheduleplan')
    pending_count = 0

    if can_manage:
        pending_count = ScheduleDiscrepancyRequest.objects.filter(
            status=ScheduleDiscrepancyRequest.Status.PENDING
        ).count()

    return {
        'vacation_pending_discrepancies_count': pending_count,
        'vacation_show_discrepancy_counter': can_manage and pending_count > 0,
    }
