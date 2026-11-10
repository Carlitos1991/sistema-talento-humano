from django.db.models import Q
from .models import LicenseReception, MedicalLicense


def license_notifications(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'licenses_pending_reception_count': 0,
            'licenses_pending_management_count': 0,
            'licenses_sidebar_count': 0,
        }

    user = request.user
    reception_count = 0
    management_count = 0

    is_global_admin = user.is_superuser or user.has_perm('licenses.can_admin')

    # 1. Conteo de Recepciones Pendientes
    has_reception_perm = user.has_perm('licenses.view_licensereception') or is_global_admin
    if has_reception_perm:
        reception_qs = LicenseReception.objects.filter(
            status=LicenseReception.STATUS_APPROVED
        )
        if not is_global_admin:
            reception_qs = reception_qs.filter(
                Q(delivered_to=user) | Q(received_by=user)
            )
        reception_count = reception_qs.distinct().count()

    # 2. Conteo de Gestión de Licencias Pendientes
    has_management_perm = user.has_perm('licenses.view_medicallicense') or is_global_admin
    if has_management_perm:
        pending_qs = MedicalLicense.objects.filter(is_active=True).filter(
            Q(status__in=[MedicalLicense.STATUS_DRAFT, MedicalLicense.STATUS_SUBMITTED])
            | Q(
                personnel_action__isnull=False,
                personnel_action__is_registered=False,
            )
        )

        if not is_global_admin:
            reception_filter = (
                    Q(reception__delivered_to=user) |
                    Q(reception__received_by=user)
            )
            creator_or_owner_filter = (
                    Q(created_by=user) |
                    Q(employee__person__user=user) |
                    Q(employee__person__document_number=user.username)
            )
            pending_qs = pending_qs.filter(reception_filter | creator_or_owner_filter)

        management_count = pending_qs.distinct().count()

    # 3. Total consolidado
    sidebar_total = 0
    if has_reception_perm:
        sidebar_total += reception_count
    if has_management_perm:
        sidebar_total += management_count

    return {
        'licenses_pending_reception_count': reception_count,
        'licenses_pending_management_count': management_count,
        'licenses_sidebar_count': sidebar_total,
    }
