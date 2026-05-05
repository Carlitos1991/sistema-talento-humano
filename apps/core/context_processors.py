from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q  # Importante para los filtros de permisos


def system_branding(request):
    """Expone la configuración institucional activa para usar branding en el layout."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'current_system_configuration': None,
            'sidebar_logo_url': None,
        }

    try:
        from core.models import SystemConfiguration

        current_config = SystemConfiguration.get_current()
        logo_url = None

        if current_config and getattr(current_config, 'logo', None):
            try:
                logo_url = current_config.logo.url
            except Exception:
                logo_url = None

        return {
            'current_system_configuration': current_config,
            'sidebar_logo_url': logo_url,
        }
    except Exception:
        return {
            'current_system_configuration': None,
            'sidebar_logo_url': None,
        }


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
                    AdministrativeUnit.objects.filter(parent_id__in=frontier, is_active=True).values_list('id',
                                                                                                          flat=True))
                if not children_ids: break
                collected.extend(children_ids)
                frontier = children_ids
            return collected

        if user.has_perm('permitrequest.change_permitrequest'):
            user_person = getattr(user, 'person', None)
            employee_profile = getattr(user_person, 'employee_profile', None) if user_person else None

            if not employee_profile:
                person_by_document = Person.objects.filter(document_number=user.username).select_related(
                    'employee_profile').first()
                if person_by_document: employee_profile = getattr(person_by_document, 'employee_profile', None)

            if not employee_profile and user.email:
                person_by_email = Person.objects.filter(email__iexact=user.email).select_related(
                    'employee_profile').first()
                if person_by_email: employee_profile = getattr(person_by_email, 'employee_profile', None)

            managed_unit = None
            if employee_profile:
                managed_unit = AdministrativeUnit.objects.filter(boss=employee_profile, is_active=True).select_related(
                    'level').order_by('level__level_order', 'name').first()
                if not managed_unit and getattr(employee_profile, 'person', None):
                    managed_unit = AdministrativeUnit.objects.filter(
                        boss__person__document_number=employee_profile.person.document_number,
                        is_active=True).select_related('level').order_by('level__level_order', 'name').first()
                if not managed_unit and employee_profile.is_boss and employee_profile.area_id:
                    managed_unit = employee_profile.area

            if managed_unit:
                scoped_unit_ids = collect_unit_tree_ids(managed_unit)
                # FILTRADO POR TIPO ID 1
                pending_count = PermitRequest.objects.filter(
                    Q(permit_type_id=1) | Q(permit_type__parent_id=1),
                    employee__area_id__in=scoped_unit_ids,
                    status='REQUESTED'
                ).count()
                notification_url = reverse('core:dashboard') + '?view=jefe'
            else:
                # FILTRADO POR TIPO ID 1 PARA ADMIN
                pending_count = PermitRequest.objects.filter(
                    Q(permit_type_id=1) | Q(permit_type__parent_id=1),
                    status='REQUESTED'
                ).count()
                notification_url = reverse('permissions:permit_admin')
        else:
            user_person = getattr(user, 'person', None)
            employee_profile = getattr(user_person, 'employee_profile', None) if user_person else None
            if employee_profile:
                # FILTRADO POR TIPO ID 1 PARA EMPLEADO
                pending_count = PermitRequest.objects.filter(
                    Q(permit_type_id=1) | Q(permit_type__parent_id=1),
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


def employee_archive_notifications(request):
    """Retorna el conteo de solicitudes de expediente físico para el sidebar."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'employee_archive_loan_requests_count': 0,
            'employee_archive_show_loan_counter': False,
            'employee_archive_pending_returns_count': 0,
            'employee_archive_show_return_counter': False,
        }

    request_count = 0
    pending_return_count = 0
    show_request_counter = False

    try:
        from employee.models import Employee
        from employee_archive.models import EmployeeArchiveLoan

        user = request.user

        show_request_counter = (
                user.has_perm('employee_archive.add_employeearchiveloan')
                or user.has_perm('employee_archive.change_employeearchiveloan')
                or user.has_perm('employee_archive.can_manage_archive_loans')
        )

        if show_request_counter:
            if user.has_perm('employee_archive.can_manage_archive_loans'):
                request_count = EmployeeArchiveLoan.objects.filter(
                    status__in=[
                        EmployeeArchiveLoan.Status.REQUESTED,
                        EmployeeArchiveLoan.Status.RETURN_REPORTED,
                    ],
                    is_active=True,
                ).count()
            else:
                user_employee = None
                user_person = getattr(user, 'person', None)
                if user_person:
                    user_employee = getattr(user_person, 'employee_profile', None)

                if not user_employee and user.email:
                    user_employee = Employee.objects.filter(
                        person__email__iexact=user.email,
                        is_active=True,
                    ).first()

                if not user_employee and user.username:
                    user_employee = Employee.objects.filter(
                        person__document_number=user.username,
                        is_active=True,
                    ).first()

                if user_employee:
                    request_count = EmployeeArchiveLoan.objects.filter(
                        employee=user_employee,
                        status__in=[
                            EmployeeArchiveLoan.Status.REQUESTED,
                            EmployeeArchiveLoan.Status.RETURN_REPORTED,
                        ],
                        is_active=True,
                    ).count()

        pending_return_count = EmployeeArchiveLoan.objects.filter(
            borrower_user=user,
            status=EmployeeArchiveLoan.Status.ON_LOAN,
            is_active=True,
        ).count()
    except Exception:
        request_count = 0
        pending_return_count = 0

    return {
        'employee_archive_loan_requests_count': request_count,
        'employee_archive_show_loan_counter': show_request_counter,
        'employee_archive_pending_returns_count': pending_return_count,
        'employee_archive_show_return_counter': pending_return_count > 0,
    }


def contract_notifications(request):
    """Retorna el conteo de contratos con fecha de fin dentro de los próximos 20 días."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'contract_expiring_count': 0,
            'contract_show_expiring_counter': False,
        }

    show_counter = request.user.has_perm('contract.view_managementperiod')
    if not show_counter:
        return {
            'contract_expiring_count': 0,
            'contract_show_expiring_counter': False,
        }

    count = 0
    try:
        from contract.models import ManagementPeriod

        today = timezone.now().date()
        deadline = today + timedelta(days=20)

        count = ManagementPeriod.objects.filter(
            is_active=True,
            end_date__isnull=False,
            end_date__gte=today,
            end_date__lte=deadline,
        ).count()
    except Exception:
        count = 0

    return {
        'contract_expiring_count': count,
        'contract_show_expiring_counter': count > 0,
    }
