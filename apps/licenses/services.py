from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from contract.models import ManagementPeriod
from core.models import User
from payroll.models import PayrollRubric
from personnel_actions.models import ActionType, PersonnelAction
from permitrequest.models import PermitRequest, PermitType
from schedule.models import get_employee_schedule_for_date

from .models import LicensePayrollEffect, LicenseSchedule, MedicalLicense


def _active_regime(license_instance):
    period = (
        ManagementPeriod.objects.select_related('contract_type__labor_regime')
        .filter(employee=license_instance.employee, start_date__lte=license_instance.start_date)
        .order_by('-start_date')
        .first()
    )
    return period.contract_type.labor_regime if period and period.contract_type else None


def _create_payroll_effects(license_instance):
    regime = _active_regime(license_instance)
    regime_code = (regime.code if regime else 'LOSEP').upper()
    employer_days = license_instance.license_type.employer_coverage_days
    subsidy_percentage = license_instance.license_type.iess_subsidy_percentage
    payroll_rubric = PayrollRubric.objects.filter(
        is_active=True,
    ).filter(
        code__icontains='SUBSIDIO'
    ).first()
    covered_remaining = employer_days
    current = license_instance.start_date.replace(day=1)
    while current <= license_instance.end_date:
        month_end = (current.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        overlap_start = max(current, license_instance.start_date)
        overlap_end = min(month_end, license_instance.end_date)
        days = (overlap_end - overlap_start).days + 1
        covered_days = min(covered_remaining, days)
        covered_remaining -= covered_days
        LicensePayrollEffect.objects.update_or_create(
            license=license_instance,
            target_year=current.year,
            target_month=current.month,
            defaults={
                'labor_regime': regime_code,
                'employer_covered_days': covered_days,
                'subsidy_percentage': subsidy_percentage,
                'days_to_discount': max(days - covered_days, 0),
                'estimated_discount_amount': Decimal('0.00'),
                'observation': f'Descuento Subsidio Mes {current.month:02d}/{current.year}',
                'status': LicensePayrollEffect.STATUS_PENDING,
                'payroll_rubric': payroll_rubric,
            },
        )
        current = month_end + timedelta(days=1)


def _create_attendance_permits(license_instance):
    permit_type, _ = PermitType.objects.get_or_create(
        name='Licencia Médica',
        defaults={'needs_justification': False, 'is_active': True},
    )
    adjustment = getattr(license_instance, 'schedule_adjustment', None)
    PermitRequest.objects.filter(
        employee=license_instance.employee,
        response_note__icontains=f'licencia médica #{license_instance.pk}',
    ).delete()
    day = license_instance.start_date
    while day <= license_instance.end_date:
        schedule = get_employee_schedule_for_date(license_instance.employee, day)
        permit_start, permit_end = time.min, time(23, 59)
        if adjustment and adjustment.modality == LicenseSchedule.MODALITY_ENTRY_DELAY:
            if not schedule:
                raise ValueError(f'No existe horario asignado para {day:%d/%m/%Y}.')
            permit_start = schedule.morning_start
            permit_end = (datetime.combine(day, permit_start) + timedelta(hours=2)).time()
        elif adjustment and adjustment.modality == LicenseSchedule.MODALITY_EXIT_EARLY:
            if not schedule:
                raise ValueError(f'No existe horario asignado para {day:%d/%m/%Y}.')
            permit_end = schedule.morning_end
            permit_start = (datetime.combine(day, permit_end) - timedelta(hours=2)).time()
        elif adjustment and adjustment.modality == LicenseSchedule.MODALITY_LUNCH:
            if not schedule or not schedule.afternoon_start:
                raise ValueError(f'El horario no tiene almuerzo definido para {day:%d/%m/%Y}.')
            permit_start, permit_end = schedule.morning_end, schedule.afternoon_start
        elif adjustment and adjustment.modality == LicenseSchedule.MODALITY_REDUCTION_HOURS:
            if not schedule:
                raise ValueError(f'No existe horario asignado para {day:%d/%m/%Y}.')
            reduction = float(adjustment.reduction_hours or Decimal('2.00'))
            permit_start = schedule.morning_start
            permit_end = (datetime.combine(day, permit_start) + timedelta(hours=reduction)).time()
        elif adjustment and adjustment.custom_entry_time and adjustment.custom_exit_time:
            permit_start = adjustment.custom_entry_time
            permit_end = adjustment.custom_exit_time
        marker = f'licencia médica #{license_instance.pk}'
        if not PermitRequest.objects.filter(
            employee=license_instance.employee, permit_type=permit_type,
            start_date=day, response_note__icontains=marker,
        ).exists():
            duration = datetime.combine(day, permit_end) - datetime.combine(day, permit_start)
            PermitRequest.objects.create(
                employee=license_instance.employee, permit_type=permit_type,
                start_date=day, end_date=day, start_time=permit_start, end_time=permit_end,
                days=1 if permit_start == time.min else 0,
                hours=max(0, int(duration.total_seconds() // 3600)),
                minutes=max(0, int(duration.total_seconds() // 60) % 60),
                status='APPROVED', response_note=f'Permiso generado por {marker}.',
                response_date=timezone.now(), response_by=license_instance.convalidated_by,
                created_by=license_instance.created_by, updated_by=license_instance.updated_by,
            )
        day += timedelta(days=1)


def _create_draft_action(license_instance):
    if license_instance.personnel_action_id or license_instance.total_days < 1:
        return license_instance.personnel_action
    action_type = get_object_or_404(ActionType, code='LICENCIA', is_active=True)
    fallback_user = (
        license_instance.convalidated_by
        or license_instance.created_by
        or User.objects.filter(is_active=True).order_by('id').first()
    )
    if not fallback_user:
        raise ValueError('No existe un usuario activo para asignar las firmas de la acción.')
    last_action = PersonnelAction.objects.order_by('-created_at').first()
    number = f'{(last_action.pk + 1 if last_action else 1):04d}-{timezone.now().year}'
    return PersonnelAction.objects.create(
        employee=license_instance.employee, action_type=action_type, number=number,
        explanation=f'Licencia médica #{license_instance.pk}: {license_instance.diagnosis}',
        motivation='Borrador generado automáticamente al convalidar la licencia.',
        date_issue=datetime.now().date(), date_effective=license_instance.start_date,
        authority_1=action_type.default_authority_1 or fallback_user,
        authority_2=action_type.default_authority_2, reviewer=action_type.default_reviewer,
        register=action_type.default_register,         elaboration=license_instance.convalidated_by or fallback_user,
        created_by=fallback_user,
    )


@transaction.atomic
def apply_validation_effects(license_instance):
    """Create payroll, attendance and personnel-action effects after validation."""
    _create_payroll_effects(license_instance)
    _create_attendance_permits(license_instance)
    action = _create_draft_action(license_instance)
    if action and license_instance.personnel_action_id != action.pk:
        license_instance.personnel_action = action
        license_instance.save(update_fields=['personnel_action', 'status', 'updated_at'])
    return action