import calendar
import datetime as dt
import math
from decimal import Decimal
from io import BytesIO

import openpyxl
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import F, Q, Sum
from django.template.loader import get_template
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from xhtml2pdf import pisa

from contract.models import ManagementPeriod
from core.models import SystemConfiguration
from employee.models import Employee
from institution.models import AdministrativeUnit
from permitrequest.models import PermitRequest, PermitType
from personnel_actions.models import ActionType, PersonnelAction
from .models import (
    EmployeeVacationBalance,
    FACTOR_HOUR,
    FACTOR_MINUTE,
    ScheduleDiscrepancyRequest,
    VacationHistory,
    VacationRequest,
    VacationScheduleItem,
    VacationSchedulePlan,
)

MONTH_NAMES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}


def calculate_earned_days(employee, calculation_date=None):
    """Calculates annual earned vacation days based on labor regime (LOSEP vs Labor Code)."""
    if not employee or not employee.employment_status:
        return Decimal('30.0')

    regime = (employee.employment_status.code or '').upper()
    if any(k in regime for k in ('TRABAJADOR', 'CÓDIGO', 'CODIGO', 'OBRERO')):
        base_days = Decimal('15.0')
        extra_days = Decimal('0.0')
        previous_periods_count = EmployeeVacationBalance.objects.filter(employee=employee).count()
        entry_date = get_real_entry_date(employee)

        if entry_date:
            anniversary_date = calculation_date or dt.date.today()
            years_of_service = relativedelta(anniversary_date, entry_date).years
        else:
            years_of_service = previous_periods_count

        if years_of_service >= 5:
            bonus = min(years_of_service - 4, 15)
            extra_days = Decimal(str(bonus))

        return base_days + extra_days

    return Decimal('30.0')


def get_real_entry_date(employee):
    """Resolves official employee entry date from institutional data or active contract."""
    inst_data = getattr(employee, 'institutional_data', None)
    if inst_data and getattr(inst_data, 'entry_date', None):
        return inst_data.entry_date

    active_contract = ManagementPeriod.objects.filter(
        employee=employee
    ).exclude(
        status__code='FINALIZADO'
    ).exclude(
        contract_type__code='SERVICIOS_PROFESIONALES'
    ).order_by('-start_date').first()

    if active_contract and active_contract.start_date:
        return active_contract.start_date

    return getattr(employee, 'entry_date', None) or getattr(employee.person, 'entry_date', None)


def get_vacation_regime_info(employee):
    """Returns tuple (is_labor_code, base_annual_days, monthly_accrual_factor)."""
    terms = []
    if employee.employment_status:
        terms.append(str(employee.employment_status.code or ''))
        terms.append(str(employee.employment_status.name or ''))

    active_contract = ManagementPeriod.objects.filter(
        employee=employee
    ).exclude(
        status__code='FINALIZADO'
    ).exclude(
        contract_type__code='SERVICIOS_PROFESIONALES'
    ).select_related('contract_type__labor_regime').order_by('-start_date').first()

    if active_contract and active_contract.contract_type:
        c_type = active_contract.contract_type
        terms.extend([str(c_type.code or ''), str(c_type.name or '')])
        if c_type.labor_regime:
            terms.extend([str(c_type.labor_regime.code or ''), str(c_type.labor_regime.name or '')])

    full_text = ' '.join(terms).upper()
    ct_keywords = ('TRABAJADOR', 'OBRERO', 'CODIGO DE TRABAJO', 'CÓDIGO DE TRABAJO', 'CODIGO DEL TRABAJO',
                   'CODIGO_TRABAJO')
    if any(keyword in full_text for keyword in ct_keywords):
        return True, 15, 1.25

    return False, 30, 2.50


def calculate_available_days_for_month(employee, plan_year, target_month):
    """Calculates proportional or full available vacation days up to target_month."""
    entry_date = get_real_entry_date(employee)
    is_ct, base_annual, monthly_factor = get_vacation_regime_info(employee)
    plan_year = int(plan_year)
    target_month = int(target_month)

    if not entry_date:
        return base_annual, base_annual, False, f'{base_annual}'

    if is_ct:
        plan_end = dt.date(plan_year, 12, 31)
        years_completed = relativedelta(plan_end, entry_date).years
        bonus = max(0, years_completed - 5) if years_completed > 5 else 0
        ceiling_days = min(15 + bonus, 30)
    else:
        ceiling_days = 30

    plan_start = dt.date(plan_year, 1, 1)
    if relativedelta(plan_start, entry_date).years >= 1:
        return ceiling_days, ceiling_days, False, f'{ceiling_days}'

    if (entry_date.year > plan_year) or (entry_date.year == plan_year and entry_date.month > target_month):
        return 0, ceiling_days, True, '0'

    total_months_worked = (plan_year - entry_date.year) * 12 + (target_month - entry_date.month)
    if total_months_worked <= 0:
        return 0, ceiling_days, True, '0'

    accrued = min(total_months_worked * monthly_factor, float(ceiling_days))
    display_val = f'{int(accrued)}' if accrued % 1 == 0 else f'{accrued:.1f}'
    allowed_int = math.floor(accrued)
    is_proportional = allowed_int < ceiling_days

    return allowed_int, ceiling_days, is_proportional, display_val


def resolve_scheduling_hierarchy(user, requested_unit_id=None):
    """Resolves root scheduling administrative unit and all recursive descendant IDs."""
    base_unit = None
    if requested_unit_id and (user.is_staff or user.has_perm('vacation.change_vacationscheduleplan')):
        base_unit = AdministrativeUnit.objects.filter(pk=requested_unit_id, is_active=True).first()
    else:
        person = getattr(user, 'person', None)
        user_emp = getattr(person, 'employee_profile', None) if person else None
        if user_emp and user_emp.area:
            base_unit = user_emp.area.get_scheduling_root_unit()

    if not base_unit:
        base_unit = (
                AdministrativeUnit.objects.filter(is_active=True, is_main_unit=True).first()
                or AdministrativeUnit.objects.filter(is_active=True, parent__isnull=True).first()
        )

    unit_ids = []
    if base_unit:
        unit_ids = [base_unit.id]
        queue = [base_unit]
        while queue:
            curr = queue.pop(0)
            children = list(AdministrativeUnit.objects.filter(parent=curr, is_active=True))
            for child in children:
                unit_ids.append(child.id)
                queue.append(child)

    return base_unit, unit_ids


@transaction.atomic
def resolve_schedule_discrepancy(discrepancy, action, target_unit_id=None, admin_note=''):
    """Processes HR resolution or rejection for a schedule discrepancy request."""
    emp = discrepancy.employee
    if action == 'resolve':
        target_unit = None
        if target_unit_id:
            target_unit = AdministrativeUnit.objects.filter(pk=target_unit_id).first()
        elif discrepancy.request_type == ScheduleDiscrepancyRequest.RequestType.MISSING_EMPLOYEE:
            target_unit = discrepancy.unit

        if target_unit:
            emp.area = target_unit
            emp.save(update_fields=['area'])

        discrepancy.status = ScheduleDiscrepancyRequest.Status.RESOLVED
        discrepancy.is_viewed_by_unit = False
        hr_note = f'\n[TH Resuelto]: Reubicado a {emp.area.name}.'
        if admin_note:
            hr_note += f' Nota: {admin_note}'
        discrepancy.observation += hr_note
        discrepancy.save(update_fields=['status', 'is_viewed_by_unit', 'observation', 'updated_at'])
        return f'Novedad resuelta con éxito. {emp.person.full_name} reubicado a {emp.area.name}.'

    if action == 'reject':
        discrepancy.status = ScheduleDiscrepancyRequest.Status.REJECTED
        discrepancy.is_viewed_by_unit = False
        if admin_note:
            discrepancy.observation += f'\n[TH Desestimado]: {admin_note}'
        discrepancy.save(update_fields=['status', 'is_viewed_by_unit', 'observation', 'updated_at'])
        return 'La novedad ha sido desestimada y el funcionario liberado.'

    raise ValueError('Acción no válida.')

