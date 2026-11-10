from django.db.models import Q

from .models import LicenseReception, MedicalLicense


def license_notifications(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'licenses_pending_reception_count': 0,
            'licenses_pending_management_count': 0,
            'licenses_sidebar_count': 0,
        }

    reception_count = LicenseReception.objects.filter(
        status=LicenseReception.STATUS_APPROVED
    ).count()

    pending = MedicalLicense.objects.filter(
        is_active=True,
    ).filter(
        Q(status__in=[MedicalLicense.STATUS_DRAFT, MedicalLicense.STATUS_SUBMITTED])
        | Q(
            personnel_action__isnull=False,
            personnel_action__is_registered=False,
        )
    )
    if not (request.user.is_staff or request.user.is_superuser):
        pending = pending.filter(
            Q(employee__person__user=request.user)
            | Q(employee__person__document_number=request.user.username)
        )

    management_count = pending.count()
    is_admin = request.user.is_staff or request.user.is_superuser

    return {
        'licenses_pending_reception_count': reception_count,
        'licenses_pending_management_count': management_count,
        'licenses_sidebar_count': (
            reception_count + management_count
            if is_admin else management_count
        ),
    }
