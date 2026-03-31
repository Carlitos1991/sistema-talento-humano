from django.urls import reverse


def navbar_notifications(request):
    """Retorna el conteo de solicitudes de permiso pendientes para la campanita del navbar."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'navbar_show_permit_notifications': False,
            'navbar_permit_notifications_count': 0,
            'navbar_permit_notifications_url': ''
        }

    pending_count = 0
    notification_url = ''

    try:
        from permitrequest.models import PermitRequest
        from institution.models import AdministrativeUnit
        from person.models import Person

        user = request.user

        def collect_unit_tree_ids(root_unit):
            collected = [root_unit.id]
            frontier = [root_unit.id]

            while frontier:
                children_ids = list(
                    AdministrativeUnit.objects.filter(
                        parent_id__in=frontier,
                        is_active=True
                    ).values_list('id', flat=True)
                )
                if not children_ids:
                    break
                collected.extend(children_ids)
                frontier = children_ids

            return collected

        if user.has_perm('permitrequest.change_permitrequest'):
            user_person = getattr(user, 'person', None)
            employee_profile = getattr(user_person, 'employee_profile', None) if user_person else None

            if not employee_profile:
                person_by_document = Person.objects.filter(
                    document_number=user.username
                ).select_related('employee_profile').first()
                if person_by_document:
                    employee_profile = getattr(person_by_document, 'employee_profile', None)

            if not employee_profile and user.email:
                person_by_email = Person.objects.filter(
                    email__iexact=user.email
                ).select_related('employee_profile').first()
                if person_by_email:
                    employee_profile = getattr(person_by_email, 'employee_profile', None)

            managed_unit = None
            if employee_profile:
                managed_unit = AdministrativeUnit.objects.filter(
                    boss=employee_profile,
                    is_active=True
                ).select_related('level').order_by('level__level_order', 'name').first()

                if not managed_unit and getattr(employee_profile, 'person', None):
                    managed_unit = AdministrativeUnit.objects.filter(
                        boss__person__document_number=employee_profile.person.document_number,
                        is_active=True
                    ).select_related('level').order_by('level__level_order', 'name').first()

                if not managed_unit and employee_profile.is_boss and employee_profile.area_id:
                    managed_unit = employee_profile.area

            if managed_unit:
                scoped_unit_ids = collect_unit_tree_ids(managed_unit)
                pending_count = PermitRequest.objects.filter(
                    employee__area_id__in=scoped_unit_ids,
                    status='REQUESTED'
                ).count()
                notification_url = reverse('core:dashboard') + '?view=jefe'
            else:
                pending_count = PermitRequest.objects.filter(status='REQUESTED').count()
                notification_url = reverse('permissions:permit_admin')
        else:
            user_person = getattr(user, 'person', None)
            employee_profile = getattr(user_person, 'employee_profile', None) if user_person else None

            if employee_profile:
                pending_count = PermitRequest.objects.filter(
                    employee=employee_profile,
                    status='REQUESTED'
                ).count()
                notification_url = reverse('employee:self_dashboard')

    except Exception:
        pending_count = 0
        notification_url = ''

    return {
        'navbar_show_permit_notifications': pending_count > 0,
        'navbar_permit_notifications_count': pending_count,
        'navbar_permit_notifications_url': notification_url
    }
