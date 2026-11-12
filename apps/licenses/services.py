from datetime import datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
import uuid

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from contract.models import ManagementPeriod
from core.models import User
from employee.models import Employee
from institution.models import AdministrativeUnit
from payroll.models import PayrollRubric
from personnel_actions.models import ActionMovement, ActionType, PersonnelAction
from permitrequest.models import PermitRequest, PermitType
from schedule.models import get_employee_schedule_for_date

from .models import (
    LicensePayrollEffect,
    LicenseReception,
    LicenseReceptionCheck,
    LicenseSchedule,
    MedicalLicense,
    MedicalLicenseType,
)

MONTH_NAMES_ES = (
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
)


def get_human_resources_employees():
    """Return active employees belonging to the Human Resources administrative unit."""
    hr_unit = AdministrativeUnit.objects.filter(
        is_human_resources=True, is_active=True
    ).first()
    if not hr_unit:
        return Employee.objects.none()
    return Employee.objects.select_related('person').filter(
        area_id__in=hr_unit.get_descendant_ids(),
        is_active=True,
    ).order_by('person__last_name', 'person__first_name')


def get_human_resources_users():
    """Return active system users linked to Human Resources personnel."""
    hr_unit = AdministrativeUnit.objects.filter(
        is_human_resources=True, is_active=True
    ).first()
    if not hr_unit:
        return User.objects.none()

    unit_ids = hr_unit.get_descendant_ids()
    users = User.objects.filter(
        person__employee_profile__area_id__in=unit_ids,
        person__employee_profile__is_active=True,
        is_active=True,
    ).order_by('last_name', 'first_name', 'username')

    if users.exists():
        return users

    document_numbers = (
        get_human_resources_employees()
        .exclude(person__document_number__isnull=True)
        .exclude(person__document_number='')
        .values_list('person__document_number', flat=True)
    )
    return User.objects.filter(
        username__in=document_numbers,
        is_active=True,
    ).order_by('last_name', 'first_name', 'username')


def get_license_notification_counts(user):
    """Compute pending reception and management badge counts for the sidebar."""
    if not getattr(user, 'is_authenticated', False):
        return {
            'licenses_pending_reception_count': 0,
            'licenses_pending_management_count': 0,
            'licenses_sidebar_count': 0,
        }

    is_global_admin = user.is_superuser or user.has_perm('licenses.can_admin')
    reception_count = 0
    management_count = 0

    has_reception_perm = user.has_perm('licenses.view_licensereception') or is_global_admin
    if has_reception_perm:
        reception_qs = LicenseReception.objects.filter(status=LicenseReception.STATUS_APPROVED)
        if not is_global_admin:
            reception_qs = reception_qs.filter(Q(delivered_to=user) | Q(received_by=user))
        reception_count = reception_qs.distinct().count()

    has_management_perm = user.has_perm('licenses.view_medicallicense') or is_global_admin
    if has_management_perm:
        pending_qs = MedicalLicense.objects.filter(is_active=True).filter(
            Q(status__in=[MedicalLicense.STATUS_DRAFT, MedicalLicense.STATUS_SUBMITTED])
            | Q(personnel_action__isnull=False, personnel_action__is_registered=False)
        )
        if not is_global_admin:
            access_filter = (
                    Q(reception__delivered_to=user)
                    | Q(reception__received_by=user)
                    | Q(created_by=user)
                    | Q(employee__person__user=user)
                    | Q(employee__person__document_number=user.username)
            )
            pending_qs = pending_qs.filter(access_filter)
        management_count = pending_qs.distinct().count()

    sidebar_total = (reception_count if has_reception_perm else 0) + (
        management_count if has_management_perm else 0
    )

    return {
        'licenses_pending_reception_count': reception_count,
        'licenses_pending_management_count': management_count,
        'licenses_sidebar_count': sidebar_total,
    }


def render_license_action_text(template, start_date, end_date):
    """Replace supported placeholders in the legal description template."""
    if not template:
        return ''
    days = (end_date - start_date).days + 1 if start_date and end_date else 0
    replacements = {
        '[DIAS]': str(days),
        '[FECHA_INICIO]': start_date.strftime('%d/%m/%Y') if start_date else '',
        '[FECHA_FIN]': end_date.strftime('%d/%m/%Y') if end_date else '',
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def get_reception_statistics():
    """Return aggregated counts for reception status cards."""
    base_qs = LicenseReception.objects.exclude(status=LicenseReception.STATUS_CANCELLED)
    registered = base_qs.filter(status=LicenseReception.STATUS_REGISTERED).count()
    approved = base_qs.filter(status=LicenseReception.STATUS_APPROVED).count()
    delivered = base_qs.filter(status=LicenseReception.STATUS_DELIVERED).count()
    return {
        'total': registered + approved + delivered,
        'registered': registered,
        'approved': approved,
        'delivered': delivered,
    }


@transaction.atomic
def create_license_reception(data, user):
    employee = get_object_or_404(Employee, pk=data['employee_id'])
    license_type = get_object_or_404(MedicalLicenseType, pk=data['license_type_id'])
    license_days = data['license_days']
    start_date = data['license_start_date']
    observations = data.get('observations', '').strip()

    end_date = start_date + timedelta(days=license_days - 1) if license_days > 0 else None
    if license_days == 0:
        observations = f'{observations}\nLicencia indefinida desde {start_date:%d/%m/%Y}.'.strip()

    reception = LicenseReception.objects.create(
        employee=employee,
        license_type=license_type,
        received_by=user,
        license_start_date=start_date,
        license_end_date=end_date,
        license_days=license_days,
        supporting_document=data['supporting_document'],
        observations=observations,
        status=LicenseReception.STATUS_REGISTERED,
    )

    checked_ids = data.get('checked_req_ids', [])
    active_requirements = license_type.requirements.filter(is_active=True)
    checks = [
        LicenseReceptionCheck(
            reception=reception,
            requirement=req,
            is_checked=(req.id in checked_ids),
        )
        for req in active_requirements
    ]
    LicenseReceptionCheck.objects.bulk_create(checks)

    mandatory_missing = active_requirements.filter(is_mandatory=True).exclude(id__in=checked_ids).exists()
    if not mandatory_missing and active_requirements.exists():
        reception.status = LicenseReception.STATUS_APPROVED
        reception.save(update_fields=['status'])

    return reception


@transaction.atomic
def validate_reception_requirements(reception_id, newly_checked_ids):
    """Update pending checklist items and promote status to APPROVED if complete."""
    reception = get_object_or_404(LicenseReception.objects.select_for_update(), pk=reception_id)
    if newly_checked_ids:
        reception.checked_items.filter(id__in=newly_checked_ids).update(is_checked=True)

    if not reception.checked_items.filter(is_checked=False).exists():
        reception.status = LicenseReception.STATUS_APPROVED
        reception.save(update_fields=['status'])
    return reception


def ensure_medical_license_from_reception(reception, user):
    """Create the MedicalLicense management record when a reception is delivered."""
    if hasattr(reception, 'medical_license') and reception.medical_license:
        return reception.medical_license

    start_date = reception.license_start_date or reception.reception_date.date()
    return MedicalLicense.objects.create(
        reception=reception,
        employee=reception.employee,
        license_type=reception.license_type,
        start_date=start_date,
        end_date=reception.license_end_date,
        diagnosis=reception.observations or 'Licencia remitida desde recepción documental.',
        issuing_entity='Pendiente de registrar',
        status=MedicalLicense.STATUS_SUBMITTED,
        created_by=user,
    )


@transaction.atomic
def deliver_receptions_batch(reception_ids, delivered_to_id, observation, current_user):
    dest_user = get_object_or_404(get_human_resources_users(), pk=delivered_to_id)
    receptions = list(
        LicenseReception.objects.select_for_update().filter(
            pk__in=reception_ids,
            status=LicenseReception.STATUS_APPROVED,
        )
    )
    if len(receptions) != len(set(reception_ids)):
        raise ValueError('Solo se pueden remitir recepciones en estado aprobado.')

    batch_uuid = uuid.uuid4()
    timestamp = timezone.now().strftime('%d/%m/%Y %H:%M')
    obs_entry = f"\n[ENTREGA {timestamp}] Entregado a: {dest_user.get_full_name()}. Obs: {observation}"

    for reception in receptions:
        reception.status = LicenseReception.STATUS_DELIVERED
        reception.delivery_batch = batch_uuid
        reception.delivered_to = dest_user
        reception.observations = (reception.observations or '') + obs_entry
        reception.save(update_fields=['status', 'delivery_batch', 'delivered_to', 'observations'])
        ensure_medical_license_from_reception(reception, current_user)

    return batch_uuid, dest_user, len(receptions)


@transaction.atomic
def return_license_to_reception(license_id, reason, user):
    license_instance = get_object_or_404(
        MedicalLicense.objects.select_for_update(), pk=license_id, is_active=True
    )
    if not license_instance.reception:
        raise ValueError('La licencia no tiene una recepción documental asociada.')

    license_instance.status = MedicalLicense.STATUS_CANCELLED
    license_instance.is_active = False
    license_instance.updated_by = user
    license_instance.save(update_fields=['status', 'is_active', 'updated_by', 'updated_at'])

    reception = license_instance.reception
    reception.status = LicenseReception.STATUS_APPROVED
    reception.observations = (
        f"{reception.observations or ''}\n"
        f"[DEVUELTA A RECEPCIÓN {timezone.now():%d/%m/%Y %H:%M}] Motivo: {reason}"
    ).strip()
    reception.save(update_fields=['status', 'observations'])
    return license_instance


def _next_personnel_action_number():
    year = timezone.now().year
    last_action = (
        PersonnelAction.objects
        .filter(number__endswith=f'-{year}')
        .order_by('-created_at')
        .first()
    )
    next_number = 1
    if last_action:
        try:
            next_number = int(last_action.number.split('-')[0]) + 1
        except (TypeError, ValueError):
            pass
    return f'{next_number:04d}-{year}'


def ensure_license_action_movement(action):
    movement, created = ActionMovement.objects.get_or_create(personnel_action=action)
    if not created:
        return movement

    employee = action.employee
    current_budget = employee.current_budget_line.select_related('position_item').first()
    current_unit = employee.area
    movement.previous_unit = current_unit.name if current_unit else ''
    movement.previous_budget_line = current_budget
    movement.previous_position = (
        current_budget.position_item.name
        if current_budget and current_budget.position_item else ''
    )
    movement.previous_remuneration = current_budget.remuneration if current_budget else 0
    movement.save()
    return movement


def is_employee_labor_code(employee, reference_date):
    """Return True if the employee's active contract at reference_date is Código de Trabajo (CT)."""
    period = (
        ManagementPeriod.objects.select_related('contract_type__labor_regime')
        .filter(employee=employee, start_date__lte=reference_date)
        .order_by('-start_date')
        .first()
    )
    regime = period.contract_type.labor_regime if (period and period.contract_type) else None
    return bool(regime and regime.code == 'CT')


def create_draft_license_action(license_instance, actor_user=None):
    """Create a draft PersonnelAction linked to the medical."""
    if license_instance.personnel_action_id or license_instance.total_days < 1:
        return license_instance.personnel_action

    action_type = get_object_or_404(ActionType, code='LICENCIA', is_active=True)
    fallback_user = (
            actor_user
            or license_instance.convalidated_by
            or license_instance.created_by
            or User.objects.filter(is_active=True).order_by('id').first()
    )
    if not fallback_user:
        raise ValueError('No existe un usuario activo para asignar las firmas de la acción.')

    number = _next_personnel_action_number()
    is_ct = is_employee_labor_code(license_instance.employee, license_instance.start_date)
    legal_description = license_instance.license_type.get_legal_basis_for_regime(
        is_labor_code=is_ct
    ).strip()
    explanation = render_license_action_text(
        legal_description, license_instance.start_date, license_instance.end_date
    ) or f'Licencia médica #{license_instance.pk}: {license_instance.diagnosis}'

    reception_document = (
        license_instance.reception.supporting_document or ''
        if license_instance.reception_id else ''
    )
    action = PersonnelAction.objects.create(
        employee=license_instance.employee,
        action_type=action_type,
        number=number,
        explanation=explanation,
        motivation=reception_document,
        date_issue=timezone.now().date(),
        date_effective=license_instance.start_date,
        authority_1=license_instance.license_type.default_authority_1 or fallback_user,
        authority_2=license_instance.license_type.default_authority_2,
        reviewer=license_instance.license_type.default_reviewer,
        register=license_instance.license_type.default_register,
        elaboration=actor_user or license_instance.convalidated_by or fallback_user,
        created_by=actor_user or fallback_user,
    )
    ensure_license_action_movement(action)
    return action


@transaction.atomic
def prepare_license_action_modal(license_id, actor_user=None):
    """Ensure draft personnel action exists and synchronize default signatures."""
    license_instance = get_object_or_404(
        MedicalLicense.objects.select_for_update(of=('self',)).select_related(
            'employee__person', 'license_type', 'personnel_action'
        ),
        pk=license_id,
        is_active=True,
        status__in=[
            MedicalLicense.STATUS_DRAFT,
            MedicalLicense.STATUS_SUBMITTED,
            MedicalLicense.STATUS_VALIDATED,
            MedicalLicense.STATUS_ACTION_ISSUED,
        ],
    )
    if not license_instance.personnel_action_id:
        action = create_draft_license_action(license_instance, actor_user=actor_user)
        license_instance.personnel_action = action
        license_instance.status = MedicalLicense.STATUS_ACTION_ISSUED
        license_instance.save(update_fields=['personnel_action', 'status', 'updated_at'])
        license_instance.refresh_from_db()

    action = license_instance.personnel_action
    ensure_license_action_movement(action)
    action.authority_1 = license_instance.license_type.default_authority_1 or action.authority_1
    action.authority_2 = license_instance.license_type.default_authority_2
    action.reviewer = license_instance.license_type.default_reviewer
    action.register = license_instance.license_type.default_register
    update_fields = ['authority_1', 'authority_2', 'reviewer', 'register']
    if actor_user and not action.is_registered:
        action.elaboration = actor_user
        action.created_by = actor_user
        update_fields.extend(['elaboration', 'created_by'])
    action.save(update_fields=update_fields)
    return license_instance, action


@transaction.atomic
def save_license_personnel_action(license_instance, form, user):
    action = form.save(commit=False)
    action.authority_1 = license_instance.license_type.default_authority_1 or action.authority_1
    action.authority_2 = license_instance.license_type.default_authority_2
    action.reviewer = license_instance.license_type.default_reviewer
    action.register = license_instance.license_type.default_register
    action.elaboration = user
    action.created_by = user
    action.save()
    ensure_license_action_movement(action)

    license_instance.status = MedicalLicense.STATUS_ACTION_ISSUED
    license_instance.start_date = form.cleaned_data['date_from']
    license_instance.end_date = form.cleaned_data['date_to']
    license_instance.updated_by = user
    license_instance.save()

    mode = form.cleaned_data.get('schedule_mode')
    if mode and mode != 'FULL_DAY':
        modality_map = {
            'CUSTOM': LicenseSchedule.MODALITY_SHIFT_OVERRIDE,
            LicenseSchedule.MODALITY_ENTRY_DELAY: LicenseSchedule.MODALITY_ENTRY_DELAY,
            LicenseSchedule.MODALITY_EXIT_EARLY: LicenseSchedule.MODALITY_EXIT_EARLY,
            LicenseSchedule.MODALITY_LUNCH: LicenseSchedule.MODALITY_LUNCH,
        }
        LicenseSchedule.objects.update_or_create(
            license=license_instance,
            defaults={
                'modality': modality_map.get(mode, LicenseSchedule.MODALITY_REDUCTION_HOURS),
                'custom_entry_time': form.cleaned_data.get('custom_entry_time'),
                'custom_exit_time': form.cleaned_data.get('custom_exit_time'),
                'reduction_hours': Decimal('2.00'),
                'is_biometric_exempt': True,
            },
        )
    else:
        LicenseSchedule.objects.filter(license=license_instance).delete()


def _calculate_worker_subsidy_amount(license_instance, covered_days, discount_days):
    budget_line = license_instance.employee.current_budget_line.select_related('position_item').first()
    remuneration = getattr(budget_line, 'remuneration', None) or Decimal('0.00')
    daily_remuneration = remuneration / Decimal('30')
    return (
            daily_remuneration * min(covered_days, 3) * Decimal('0.50')
            + daily_remuneration * discount_days
    ).quantize(Decimal('0.01'))


def _subsidy_cutoff_dates(year, month):
    cutoff_end = datetime(year, month, 20).date()
    previous_month = cutoff_end.replace(day=1) - timedelta(days=1)
    return previous_month.replace(day=21), cutoff_end


@transaction.atomic
def generate_subsidy_excel_report(year, month, user):
    """Calculate pending Labor Code subsidies up to the 20th cutoff and build an XLSX buffer."""
    _cutoff_start, cutoff_end = _subsidy_cutoff_dates(year, month)

    pending_filter = Q(
        subsidy_reported=False,
        license__start_date__lte=cutoff_end,
        created_at__date__lte=cutoff_end,
        target_year__isnull=True,
        target_month__isnull=True,
        license_year__isnull=False,
        license_month__isnull=False,
    )
    reported_filter = Q(subsidy_reported=True, target_year=year, target_month=month)

    effects = list(
        LicensePayrollEffect.objects.select_for_update()
        .select_related('license__employee__person', 'license__personnel_action')
        .filter(
            license__is_active=True,
            license__personnel_action__is_registered=True,
            labor_regime='CT',
        )
        .filter(Q(employer_covered_days__gt=0) | Q(days_to_discount__gt=0))
        .filter(pending_filter | reported_filter)
    )

    if not effects:
        raise LookupError('No existen subsidios pendientes para este corte.')

    rows = []
    calculated_at = timezone.now()
    for effect in effects:
        license_instance = effect.license
        if not effect.subsidy_reported:
            effect.estimated_discount_amount = _calculate_worker_subsidy_amount(
                license_instance, effect.employer_covered_days, effect.days_to_discount
            )
            effect.save(update_fields=['estimated_discount_amount'])

        person = license_instance.employee.person
        lic_month = effect.license_month or license_instance.start_date.month
        lic_year = effect.license_year or license_instance.start_date.year
        rows.append({
            'document': person.document_number or '',
            'name': f'{person.last_name} {person.first_name}'.strip(),
            'month': f'{MONTH_NAMES_ES[lic_month]} {lic_year}',
            'days': effect.employer_covered_days + effect.days_to_discount,
            'amount': effect.estimated_discount_amount,
        })

        if not effect.subsidy_reported:
            LicensePayrollEffect.objects.filter(pk=effect.pk).update(
                subsidy_reported=True,
                subsidy_reported_at=calculated_at,
                target_year=year,
                target_month=month,
            )

    rows.sort(key=lambda r: (r['name'].lower(), r['month']))

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Subsidios'
    sheet.append([f'Reporte de Subsidios - Corte al {cutoff_end:%d/%m/%Y}'])
    sheet.append(['Cédula', 'Apellidos y nombres', 'Mes de licencia', 'Días subsidio', 'Valor calculado'])

    for row in rows:
        sheet.append([row['document'], row['name'], row['month'], row['days'], float(row['amount'])])

    sheet.append([])
    sheet.append([
        '', 'TOTAL', '',
        sum(r['days'] for r in rows),
        float(sum((r['amount'] for r in rows), Decimal('0.00'))),
    ])
    sheet.append([])
    sheet.append(['', f'Elaborado por: {user.get_full_name() or user.username}'])

    sheet.merge_cells('A1:E1')
    sheet['A1'].font = Font(bold=True, size=14)
    sheet['A1'].alignment = Alignment(horizontal='center')
    for cell in sheet[2]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1F4E78')
    for cell in sheet['E'][2:]:
        cell.number_format = '$#,##0.00'
    for col, width in {'A': 16, 'B': 42, 'C': 18, 'D': 16, 'E': 18}.items():
        sheet.column_dimensions[col].width = width

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()


def render_reception_delivery_document(receptions_qs, user, delivered_to_user, base_url):
    """Render delivery certificate HTML and convert to PDF bytes if WeasyPrint is available."""
    receptions = list(receptions_qs)
    for reception in receptions:
        reception.verified_attachments = ', '.join(
            check.requirement.name
            for check in reception.checked_items.all()
            if check.is_checked
        )

    html_string = render_to_string('licenses/reports/pdf_reception_delivery.html', {
        'receptions': receptions,
        'user': user,
        'delivered_to': delivered_to_user,
        'current_date': timezone.now(),
    })

    try:
        from weasyprint import HTML
        return HTML(string=html_string, base_url=base_url).write_pdf(), 'application/pdf'
    except ImportError:
        return html_string, 'text/html'
