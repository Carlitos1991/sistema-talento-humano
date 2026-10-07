import copy
import calendar
import traceback
import logging
import time
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta, date
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import TruncDate
from payroll.models import PayslipItem
from accounting.models import Journal, JournalItem, Account
from budget.models import BudgetAssignmentHistory
from contract.models import ManagementPeriod
from biometric.models import AttendanceRegistry
from permitrequest.models import PermitRequest
from schedule.models import ScheduleObservation
from vacation.models import VacationRequest
from .models import (
    Payslip, PayrollConstant, PendingDebt,
    PayrollPeriod, PayrollNovelty, PayrollRubric,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de selección de cuentas contables (sin estado, reutilizables)
# ---------------------------------------------------------------------------

def _resolve_accounts_for_rubric(rubric: PayrollRubric, spending_type: str) -> dict:
    if spending_type.startswith('7'):  # INVERSIÓN
        debit = rubric.debit_account_inv_id or rubric.debit_account_id
        credit = rubric.credit_account_inv_id or rubric.credit_account_id
    elif spending_type.startswith('6'):  # PRODUCCIÓN
        debit = rubric.debit_account_prod_id or rubric.debit_account_id
        credit = rubric.credit_account_prod_id or rubric.credit_account_id
    else:  # CORRIENTE (5.1)
        debit = rubric.debit_account_id
        credit = rubric.credit_account_id

    return {'debit': debit, 'credit': credit}


def _resolve_bridge_account_id(salary_rubric: PayrollRubric, spending_type: str) -> int | None:
    if spending_type.startswith('7'):
        return salary_rubric.credit_account_inv_id or salary_rubric.credit_account_id
    elif spending_type.startswith('6'):
        return salary_rubric.credit_account_prod_id or salary_rubric.credit_account_id
    else:
        return salary_rubric.credit_account_id


def _get_employee_spending_type(segments: list) -> str:
    if not segments:
        return '5.1'
    bl = segments[0].get('budget_line')
    if bl and getattr(bl, 'spending_type_item', None):
        return bl.spending_type_item.code or '5.1'
    return '5.1'


def _filter_rubrics_by_context(rubrics: list, spending_type: str) -> list:
    return [
        r for r in rubrics
        if r.spending_context == 'TODOS' or r.spending_context == spending_type
    ]


# ---------------------------------------------------------------------------
# Servicio principal
# ---------------------------------------------------------------------------

class PayrollCalculatorService:

    def __init__(self, period, employees, is_scope_run=False):
        self.period = period
        self.employees = employees
        self.is_scope_run = is_scope_run

        if self.is_scope_run:
            self.cutoff_date = self.period.end_date
        else:
            try:
                self.cutoff_date = self.period.start_date.replace(day=25)
            except ValueError:
                self.cutoff_date = self.period.end_date

        constants = PayrollConstant.objects.filter(is_active=True).values('code', 'value')
        self.config = {c['code']: c['value'] for c in constants}

        if 'SBU' not in self.config:
            raise ValueError("Falta configurar la constante 'SBU' (Salario Básico Unificado).")

    def _prepare_mass_data(self, emp_ids):
        holidays_qs = ScheduleObservation.objects.filter(
            is_holiday=True, is_active=True,
            start_date__lte=self.period.end_date,
            end_date__gte=self.period.start_date,
        ).values_list('start_date', 'end_date')
        vacation_dates_map = {}
        approved_vacations = VacationRequest.objects.filter(
            employee_id__in=emp_ids,
            status='APPROVED',
            start_date__lte=self.period.end_date,
            end_date__gte=self.period.start_date
        ).values('employee_id', 'start_date', 'end_date')

        for v in approved_vacations:
            eid = v['employee_id']
            vacation_dates_map.setdefault(eid, set())
            v_curr = max(v['start_date'], self.period.start_date)
            v_limit = min(v['end_date'], self.period.end_date)
            while v_curr <= v_limit:
                vacation_dates_map[eid].add(v_curr)
                v_curr += timedelta(days=1)

        holiday_dates = set()
        for start_date, end_date in holidays_qs:
            curr = max(start_date, self.period.start_date)
            end_limit = min(end_date, self.period.end_date)
            while curr <= end_limit:
                holiday_dates.add(curr)
                curr += timedelta(days=1)

        prev_effective_days_map = {}
        prev_year = self.period.start_date.year
        prev_month = self.period.start_date.month - 1
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1
        prev_start = date(prev_year, prev_month, 1)
        prev_end = date(prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1])

        if emp_ids:
            prev_holiday_dates = set()
            prev_holidays_qs = ScheduleObservation.objects.filter(
                is_holiday=True, is_active=True,
                start_date__lte=prev_end,
                end_date__gte=prev_start,
            ).values_list('start_date', 'end_date')
            for start_date, end_date in prev_holidays_qs:
                curr = max(start_date, prev_start)
                end_limit = min(end_date, prev_end)
                while curr <= end_limit:
                    prev_holiday_dates.add(curr)
                    curr += timedelta(days=1)

            prev_discountable_types = (
                    Q(permit_type__name__icontains='Personal')
                    | Q(permit_type__name__icontains='Médico')
                    | Q(permit_type__name__icontains='Medico')
                    | Q(permit_type__parent__name__icontains='Personal')
                    | Q(permit_type__parent__name__icontains='Médico')
                    | Q(permit_type__parent__name__icontains='Medico')
            )
            prev_approved_permits = (
                PermitRequest.objects
                .filter(
                    employee_id__in=emp_ids,
                    status='APPROVED',
                    start_date__lte=prev_end,
                )
                .filter(Q(end_date__isnull=True) | Q(end_date__gte=prev_start))
                .filter(prev_discountable_types)
                .values('employee_id', 'start_date', 'end_date', 'days', 'hours')
            )
            prev_absent_dates_map = {}
            full_day_hours = Decimal(str(self.config.get('JORNADA_DIARIA_HORAS', '8')))
            for permit in prev_approved_permits:
                eid = permit['employee_id']
                prev_absent_dates_map.setdefault(eid, set())
                p_start = max(permit['start_date'], prev_start)
                p_end = min(permit['end_date'] or permit['start_date'], prev_end)
                is_multi_day = p_start != p_end
                hours = Decimal(str(permit.get('hours') or 0))
                days = Decimal(str(permit.get('days') or 0))
                is_full_day_absence = (
                        is_multi_day
                        or hours >= full_day_hours
                        or (hours == 0 and days >= 1)
                )
                if is_full_day_absence:
                    curr = p_start
                    while curr <= p_end:
                        prev_absent_dates_map[eid].add(curr)
                        curr += timedelta(days=1)

            prev_worked_holidays_map = self._get_worked_holidays_map(emp_ids, prev_holiday_dates)
            prev_business_days_set = self._build_business_days_set(prev_start, prev_end, prev_holiday_dates)
            prev_effective_days_map = {
                eid: self._count_valid_benefit_days(
                    eid,
                    prev_holiday_dates,
                    prev_absent_dates_map,
                    prev_worked_holidays_map,
                    start_date=prev_start,
                    end_date=prev_end,
                    business_days_set=prev_business_days_set,
                )
                for eid in emp_ids
            }

        discountable_types = (
                Q(permit_type__name__icontains='Personal')
                | Q(permit_type__name__icontains='Médico')
                | Q(permit_type__name__icontains='Medico')
                | Q(permit_type__parent__name__icontains='Personal')
                | Q(permit_type__parent__name__icontains='Médico')
                | Q(permit_type__parent__name__icontains='Medico')
        )

        approved_permits = (
            PermitRequest.objects
            .filter(
                employee_id__in=emp_ids,
                status='APPROVED',
                start_date__lte=self.period.end_date,
            )
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date))
            .filter(discountable_types)
            .values('employee_id', 'start_date', 'end_date', 'days', 'hours')
        )

        full_day_hours = Decimal(str(self.config.get('JORNADA_DIARIA_HORAS', '8')))
        absent_dates_map = {}
        for permit in approved_permits:
            eid = permit['employee_id']
            absent_dates_map.setdefault(eid, set())
            p_start = max(permit['start_date'], self.period.start_date)
            p_end = min(
                permit['end_date'] or permit['start_date'],
                self.period.end_date,
            )
            is_multi_day = p_start != p_end
            hours = Decimal(str(permit.get('hours') or 0))
            days = Decimal(str(permit.get('days') or 0))
            is_full_day_absence = (
                    is_multi_day
                    or hours >= full_day_hours
                    or (hours == 0 and days >= 1)
            )
            if is_full_day_absence:
                curr = p_start
                while curr <= p_end:
                    absent_dates_map[eid].add(curr)
                    curr += timedelta(days=1)

        worked_holidays_map = self._get_worked_holidays_map(emp_ids, holiday_dates)
        return holiday_dates, prev_effective_days_map, absent_dates_map, worked_holidays_map, vacation_dates_map

    def _get_worked_holidays_map(self, emp_ids, holiday_dates):
        if not emp_ids or not holiday_dates:
            return {}

        worked_holidays = (
            AttendanceRegistry.objects
            .filter(
                employee_id__in=emp_ids,
                registry_date__date__in=holiday_dates,
            )
            .annotate(date=TruncDate('registry_date'))
            .values('employee_id', 'date')
            .distinct()
        )

        worked_map = {}
        for item in worked_holidays:
            worked_map.setdefault(item['employee_id'], set()).add(item['date'])
        return worked_map

    def _build_business_days_set(self, start_date, end_date, holiday_dates):
        business_days = set()
        curr = start_date
        while curr <= end_date:
            if curr.weekday() < 5 and curr not in holiday_dates:
                business_days.add(curr)
            curr += timedelta(days=1)
        return business_days

    def _count_valid_benefit_days(
            self,
            employee_id,
            holiday_dates,
            absent_dates_map,
            worked_holidays_map,
            start_date=None,
            end_date=None,
            business_days_set=None,
    ):
        start_date = start_date or self.period.start_date
        end_date = end_date or self.period.end_date

        if business_days_set is None:
            business_days_set = self._build_business_days_set(start_date, end_date, holiday_dates)

        employee_absences = absent_dates_map.get(employee_id, set())
        employee_worked_holidays = worked_holidays_map.get(employee_id, set())

        normal_valid = len(business_days_set - employee_absences)
        holiday_valid = len(employee_worked_holidays - employee_absences)
        return normal_valid + holiday_valid

    def _filter_employees(self, employees):
        candidate_ids = [emp.id for emp in employees if getattr(emp, 'person', None)]
        all_assignments_qs = BudgetAssignmentHistory.objects.filter(
            employee_id__in=candidate_ids,
            start_date__lte=self.period.end_date,
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date))

        if self.is_scope_run:
            valid_history_emp_ids = set(all_assignments_qs.values_list('employee_id', flat=True))
        else:
            valid_history_emp_ids = set()
            for a in all_assignments_qs:
                if a.start_date <= self.cutoff_date:
                    valid_history_emp_ids.add(a.employee_id)

        return [emp for emp in employees if emp.id in valid_history_emp_ids]

    def generate_bulk(self):
        eligible_employees = self._filter_employees(self.employees)
        payslip_buffer = [
            Payslip(employee=emp, period=self.period, worked_days=self.period.working_days)
            for emp in eligible_employees
        ]
        return self._execute_payroll_calculation(payslip_buffer, delete_entire_period=True)

    def generate_for_selected(self, employees_with_days):
        employees = [emp for emp, _ in employees_with_days]
        eligible_employees = self._filter_employees(employees)
        eligible_ids = {emp.id for emp in eligible_employees}

        eligible_pairs = [(emp, days) for emp, days in employees_with_days if emp.id in eligible_ids]
        payslip_buffer = [
            Payslip(employee=emp, period=self.period, worked_days=days)
            for emp, days in eligible_pairs
        ]
        selected_emp_ids = [emp.id for emp, _ in eligible_pairs]
        return self._execute_payroll_calculation(
            payslip_buffer,
            employee_ids_to_delete=selected_emp_ids,
            delete_entire_period=False,
        )

    def _execute_payroll_calculation(self, payslip_buffer, delete_entire_period=False, employee_ids_to_delete=None):
        t0 = time.perf_counter()
        t_mark = t0

        def _lap(label):
            nonlocal t_mark
            now = time.perf_counter()
            t_mark = now

        with transaction.atomic():
            if delete_entire_period:
                PendingDebt.objects.filter(period=self.period).delete()
                Payslip.objects.filter(period=self.period).delete()
            elif employee_ids_to_delete:
                PendingDebt.objects.filter(
                    period=self.period, employee_id__in=employee_ids_to_delete
                ).delete()
                Payslip.objects.filter(
                    period=self.period, employee_id__in=employee_ids_to_delete
                ).delete()
            _lap("delete previous payroll data")

            created_payslips = Payslip.objects.bulk_create(payslip_buffer)
            emp_ids = [p.employee.id for p in created_payslips]
            _lap("bulk_create payslips")

            holiday_dates, prev_effective_days_map, absent_dates_map, worked_holidays_map, vacation_dates_map = self._prepare_mass_data(
                emp_ids)

            current_business_days_set = self._build_business_days_set(
                self.period.start_date, self.period.end_date, holiday_dates
            )
            _lap("prepare mass data")

            all_rubrics = list(PayrollRubric.objects.filter(is_active=True).order_by('order'))
            all_incomes = [r for r in all_rubrics if r.rubric_type == 'INCOME']
            all_deductions = [r for r in all_rubrics if r.rubric_type == 'DEDUCTION']
            all_contributions = [r for r in all_rubrics if r.rubric_type == 'CONTRIBUTION']

            all_assignments_qs = (
                BudgetAssignmentHistory.objects
                .filter(
                    employee_id__in=emp_ids,
                    start_date__lte=self.period.end_date,
                )
                .filter(Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date))
                .select_related('budget_line', 'budget_line__activity__project__subprogram__program')
            )

            assignment_map = {}
            for a in all_assignments_qs:
                assignment_map.setdefault(a.employee_id, []).append(a)

            mp_map = {}
            service_days_map = {}

            management_periods = ManagementPeriod.objects.filter(employee_id__in=emp_ids).select_related(
                'contract_type__labor_regime', 'status'
            ).order_by('employee_id', 'start_date')

            for mp in management_periods:
                curr = mp_map.get(mp.employee_id)
                if not curr:
                    mp_map[mp.employee_id] = mp
                else:
                    if mp.start_date > curr.start_date:
                        mp_map[mp.employee_id] = mp
                    elif mp.start_date == curr.start_date:
                        code_curr = str(curr.status.code if curr.status else '').upper()
                        if 'FINA' in code_curr:
                            mp_map[mp.employee_id] = mp
                        elif curr.end_date is not None and mp.end_date is None:
                            mp_map[mp.employee_id] = mp

                if mp.start_date <= self.period.end_date:
                    contract_start = mp.start_date
                    contract_end = min(mp.end_date, self.period.end_date) if mp.end_date else self.period.end_date
                    if contract_start <= contract_end:
                        days_count = (contract_end - contract_start).days + 1
                        service_days_map[mp.employee_id] = service_days_map.get(mp.employee_id, 0) + days_count

            novelties_map = {}
            for nov in (
                    PayrollNovelty.objects
                            .filter(period=self.period, employee_id__in=emp_ids)
                            .select_related('rubric')
            ):
                if not nov.rubric:
                    continue
                bucket = novelties_map.setdefault(
                    nov.employee_id, {'incomes': [], 'deductions': []}
                )
                if nov.rubric.rubric_type == 'INCOME':
                    bucket['incomes'].append(nov)
                elif nov.rubric.rubric_type == 'DEDUCTION':
                    bucket['deductions'].append(nov)

            existing_pending_debts_map = {}
            for debt in (
                    PendingDebt.objects
                            .filter(employee_id__in=emp_ids, pending_balance__gt=0)
                            .exclude(period=self.period)
                            .select_related('rubric')
                            .order_by('employee_id', 'id')
            ):
                if not debt.rubric:
                    continue
                existing_pending_debts_map.setdefault(debt.employee_id, []).append(debt)

            items_buffer = []
            payslips_to_update = []
            pending_debts_buffer = []
            debts_to_update = []
            payslips_to_delete = []
            warnings = []

            # ── 9. BUCLE PRINCIPAL POR EMPLEADO ───────────────────────────
            for slip in created_payslips:
                try:
                    all_emp_assignments = assignment_map.get(slip.employee_id, [])

                    if self.is_scope_run:
                        emp_assignments = all_emp_assignments
                    else:
                        emp_assignments = []
                        for a in all_emp_assignments:
                            if a.start_date > self.cutoff_date:
                                continue
                            assignment_copy = copy.copy(a)
                            if assignment_copy.end_date and assignment_copy.end_date > self.cutoff_date:
                                assignment_copy.end_date = None
                            emp_assignments.append(assignment_copy)
                    emp_vacation_dates = vacation_dates_map.get(slip.employee_id, set())
                    segments = self._build_segments(emp_assignments, slip.employee, emp_vacation_dates)

                    if not segments:
                        payslips_to_delete.append(slip.id)
                        continue

                    emp_spending_type = _get_employee_spending_type(segments)

                    emp_incomes = _filter_rubrics_by_context(all_incomes, emp_spending_type)
                    emp_deductions = _filter_rubrics_by_context(all_deductions, emp_spending_type)
                    emp_contributions = _filter_rubrics_by_context(all_contributions, emp_spending_type)

                    emp_ded_map = {d.code.strip().upper(): d for d in emp_deductions if d.code}
                    emp_contrib_map = {c.code.strip().upper(): c for c in emp_contributions if c.code}

                    effective_days = self._count_valid_benefit_days(
                        slip.employee_id,
                        holiday_dates,
                        absent_dates_map,
                        worked_holidays_map,
                        business_days_set=current_business_days_set,
                    )
                    slip.effective_worked_days = effective_days

                    salary = sum(
                        (seg['base_salary'] / Decimal('30.0')) * Decimal(str(seg['actual_days']))
                        for seg in segments
                    )

                    total_income = Decimal('0.0')
                    total_deduction = Decimal('0.0')
                    taxable_base = salary
                    thirteenth_base = salary

                    monthly_bonuses = False
                    monthly_reserve_funds = True
                    valid_dependents_count = 0
                    has_prior_funds_right = False

                    try:
                        payroll_info = getattr(
                            getattr(getattr(slip.employee, 'person', None), 'economic_data', None),
                            'payroll_info', None,
                        )
                        if payroll_info:
                            monthly_bonuses = bool(payroll_info.monthly_payment)
                            monthly_reserve_funds = bool(payroll_info.reserve_funds)
                            valid_dependents_count = (
                                    payroll_info.family_dependents + payroll_info.education_dependents
                            )
                            has_prior_funds_right = getattr(payroll_info, 'immediate_reserve_funds', False)
                    except Exception:
                        pass

                    mp = mp_map.get(slip.employee_id)
                    total_days_service = service_days_map.get(slip.employee_id, 0)
                    years_of_service = total_days_service / 365.25
                    regime_code = (
                        mp.contract_type.labor_regime.code.strip().upper()
                        if mp and mp.contract_type and mp.contract_type.labor_regime
                        else ''
                    )
                    years_of_last_contract = 0.0
                    if mp and mp.start_date <= self.period.end_date:
                        c_start = mp.start_date
                        c_end = min(mp.end_date, self.period.end_date) if mp.end_date else self.period.end_date
                        if c_start <= c_end:
                            last_contract_days = (c_end - c_start).days + 1
                            years_of_last_contract = last_contract_days / 365.25

                    emp_novelties = novelties_map.get(
                        slip.employee_id, {'incomes': [], 'deductions': []}
                    )
                    prepared_income_novelties = []

                    for nov in emp_novelties['incomes']:
                        if nov.value <= 0:
                            continue

                        nov_val = Decimal(str(nov.value))
                        code_up = (nov.rubric.code or '').strip().upper()

                        if 'FONDOS_RESERVA' in code_up:
                            if not monthly_reserve_funds: continue
                            if years_of_service <= 1 and not has_prior_funds_right: continue

                        if getattr(nov.rubric, 'is_taxable', False):
                            taxable_base += nov_val

                        if getattr(nov.rubric, 'is_overtime', False):
                            thirteenth_base += nov_val

                        prepared_income_novelties.append((nov, nov_val))

                    # ── 9.9 INGRESOS (RESTAURADO IDÉNTICO AL ORIGINAL) ────
                    for inc in emp_incomes:
                        val = Decimal('0.0')
                        code_clean = inc.code.strip().upper() if inc.code else ''

                        if getattr(inc, 'is_salary', False):
                            # Sueldo base proporcional por segmentos: toma el rubro con is_salary
                            # asignado al contexto del empleado sin bloquear por código rígido
                            for segment in segments:
                                segment_val = (segment['base_salary'] / Decimal('30.0')) * Decimal(
                                    str(segment['actual_days']))
                                if segment_val > 0:
                                    it = PayslipItem(payslip=slip, rubric=inc, item_type='INCOME', value=segment_val)
                                    it._historical_bl = segment['budget_line']
                                    items_buffer.append(it)
                                    total_income += segment_val
                            continue

                        elif code_clean == 'DECIMO_TERCERO' and monthly_bonuses:
                            val = (thirteenth_base / Decimal('12.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                        elif code_clean == 'DECIMO_CUARTO' and monthly_bonuses and self.period.working_days:
                            val = (Decimal(str(self.config.get('SBU', '460.00'))) / Decimal('12.0')) * (
                                    Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days))
                            )
                            val = val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                        elif code_clean == 'FONDOS_RESERVA':
                            if monthly_reserve_funds and (years_of_service > 1 or has_prior_funds_right):
                                tasa = Decimal(str(self.config.get('FONDOS_RESERVA', '8.33'))) / Decimal('100.0')
                                val = (taxable_base * tasa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                        elif code_clean == 'ALIMENTACION' and regime_code == 'CT' and years_of_service >= 1:
                            benefit_days = prev_effective_days_map.get(slip.employee_id, 0)
                            val = Decimal(str(self.config.get('ALIMENTACION_DIARIA', '4.00'))) * Decimal(
                                str(benefit_days))

                        elif code_clean == 'TRANSPORTE' and regime_code == 'CT' and years_of_service >= 1:
                            benefit_days = prev_effective_days_map.get(slip.employee_id, 0)
                            val = Decimal(str(self.config.get('TRANSPORTE_DIARIO', '0.50'))) * Decimal(
                                str(benefit_days))

                        elif (
                                code_clean == 'SUBSIDIO_FAMILIAR'
                                and regime_code == 'CT'
                                and years_of_service >= 1
                                and valid_dependents_count > 0
                        ):
                            val = Decimal(str(self.config.get('SBU', '460.00'))) * (
                                    Decimal('1.00') / Decimal('100.0')
                            ) * Decimal(str(valid_dependents_count))

                        elif code_clean == 'ANTIGUEDAD':
                            if regime_code == 'CT' and years_of_last_contract >= 1:
                                if years_of_service >= 1:
                                    val = salary * (Decimal('0.25') / Decimal('100.0')) * Decimal(
                                        str(int(years_of_last_contract)))

                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, rubric=inc, item_type='INCOME', value=val)
                            )
                            total_income += val

                    # ── 9.10 IESS Y APORTE PATRONAL ─────────────────────────
                    if regime_code == 'LOSEP':
                        target_iess_code = 'IESS_PER_EMP'
                        target_patronal_code = 'APORTE_PATRONAL_EMP'
                    elif regime_code == 'CT':
                        target_iess_code = 'IESS_PER_TRA'
                        target_patronal_code = 'APORTE_PATRONAL_TRA'
                    else:
                        target_iess_code = 'IESS_PER'
                        target_patronal_code = 'APORTE_PATRONAL'

                    iess_ded = emp_ded_map.get(target_iess_code) or emp_ded_map.get('IESS_PER')
                    if iess_ded:
                        iess_rate = Decimal(str(
                            self.config.get(target_iess_code, self.config.get('IESS_PER', '9.45'))
                        )) / Decimal('100.0')
                        val = taxable_base * iess_rate
                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, rubric=iess_ded, item_type='DEDUCTION', value=val)
                            )
                            total_deduction += val

                    contrib_ref = emp_contrib_map.get(target_patronal_code) or emp_contrib_map.get('APORTE_PATRONAL')
                    if contrib_ref:
                        patronal_rate = Decimal(str(
                            self.config.get(target_patronal_code, self.config.get('APORTE_PATRONAL', '11.15'))
                        )) / Decimal('100.0')
                        employer_val = taxable_base * patronal_rate
                        if employer_val > 0:
                            items_buffer.append(
                                PayslipItem(
                                    payslip=slip, rubric=contrib_ref,
                                    item_type='CONTRIBUTION', value=employer_val,
                                )
                            )

                    # ── 9.11 NOVEDADES DE INGRESO ───────────────────────────
                    for nov, nov_val in prepared_income_novelties:
                        items_buffer.append(
                            PayslipItem(payslip=slip, rubric=nov.rubric, item_type='INCOME', value=nov_val)
                        )
                        total_income += nov_val

                    # ── 9.12 POCKET LOGIC (descuentos y deudas protegidas) ─────────────────

                    # Códigos de beneficios de ley mensualizados protegidos contra saldos negativos
                    PROTECTED_BENEFIT_CODES = {'DECIMO_TERCERO', 'DECIMO_CUARTO', 'FONDOS_RESERVA'}

                    # Calculamos los ingresos protegidos generados para este rol
                    protected_income = sum(
                        item.value for item in items_buffer
                        if item.payslip == slip
                        and item.item_type == 'INCOME'
                        and item.rubric
                        and (item.rubric.code or '').strip().upper() in PROTECTED_BENEFIT_CODES
                    )

                    # Saldo disponible solo sobre la remuneración descontable (sueldo base, horas extras, etc.)
                    # total_deduction hasta este punto contiene aportes obligatorios de ley (ej. IESS individual)
                    discountable_income = total_income - protected_income
                    available_balance = max(Decimal('0.0'), discountable_income - total_deduction)

                    deduction_novelties = sorted(
                        emp_novelties['deductions'],
                        key=lambda x: getattr(x.rubric, 'priority', 100) or 100,
                    )
                    pending_debts_list = existing_pending_debts_map.get(slip.employee_id, [])

                    # Descuento de deudas previas
                    for debt in pending_debts_list:
                        debt_val = Decimal(str(debt.pending_balance))
                        real_discount = (
                            Decimal('0.0')
                            if available_balance <= Decimal('0.0')
                            else min(debt_val, available_balance)
                        )
                        items_buffer.append(
                            PayslipItem(payslip=slip, rubric=debt.rubric, item_type='DEDUCTION', value=real_discount)
                        )
                        if real_discount > 0:
                            total_deduction += real_discount
                            available_balance -= real_discount
                            debt.collected_value += real_discount
                            debt.pending_balance -= real_discount
                            debts_to_update.append(debt)

                    # Descuento de novedades del periodo
                    for nov in deduction_novelties:
                        if nov.value <= 0:
                            continue
                        original_val = Decimal(str(nov.value))
                        real_discount = (
                            Decimal('0.0')
                            if available_balance <= Decimal('0.0')
                            else min(original_val, available_balance)
                        )
                        new_debt = original_val - real_discount
                        items_buffer.append(
                            PayslipItem(payslip=slip, rubric=nov.rubric, item_type='DEDUCTION', value=real_discount)
                        )
                        if real_discount > 0:
                            total_deduction += real_discount
                            available_balance -= real_discount
                        if new_debt > 0:
                            pending_debts_buffer.append(
                                PendingDebt(
                                    employee=slip.employee,
                                    period=self.period,
                                    rubric=nov.rubric,
                                    original_value=original_val,
                                    collected_value=real_discount,
                                    pending_balance=new_debt,
                                )
                            )

                    # El líquido a pagar siempre incluirá intactos los beneficios protegidos
                    slip.total_income = total_income
                    slip.total_deduction = total_deduction
                    slip.net_pay = total_income - total_deduction
                    payslips_to_update.append(slip)

                except Exception as e:
                    traceback.print_exc()
                    raise e

            if payslips_to_delete:
                Payslip.objects.filter(id__in=payslips_to_delete).delete()
            PayslipItem.objects.bulk_create(items_buffer, batch_size=1000)
            Payslip.objects.bulk_update(
                payslips_to_update,
                ['total_income', 'total_deduction', 'net_pay', 'effective_worked_days'],
            )
            PendingDebt.objects.bulk_create(pending_debts_buffer, batch_size=1000)
            if debts_to_update:
                PendingDebt.objects.bulk_update(
                    debts_to_update, ['collected_value', 'pending_balance']
                )

            # Optimización de carga por relación (evita N+1 queries)
            self._assign_budget_lines_to_items(created_payslips, assignment_map)
            warnings = self._generate_accounting_journal(created_payslips)

            return {"success": True, "warnings": warnings}

    def _build_segments(self, emp_assignments: list, employee=None, vacation_dates=None) -> list:
        if not emp_assignments:
            return []

        vacation_dates = vacation_dates or set()

        original_bl = None
        orig_salary = Decimal('0.0')
        if employee:
            try:
                inst_data = getattr(employee, 'institutional_data', None)
                if inst_data and inst_data.original_budget_line:
                    original_bl = inst_data.original_budget_line
                    orig_salary = Decimal(str(original_bl.remuneration or 0))
            except Exception:
                inst_data = None

        emp_assignments.sort(key=lambda x: (x.start_date, not getattr(x, 'is_acting', False)))

        processed = []
        for i, asi in enumerate(emp_assignments):
            effective_end = asi.end_date
            if i + 1 < len(emp_assignments):
                next_start = emp_assignments[i + 1].start_date
                if not getattr(asi, 'is_acting', False) and getattr(emp_assignments[i + 1], 'is_acting', False):
                    pass
                elif not effective_end or effective_end >= next_start:
                    effective_end = next_start - timedelta(days=1)
            processed.append({'assignment': asi, 'start': asi.start_date, 'end': effective_end})

        acting_ranges = [
            (p['start'], p['end'] or self.period.end_date, p['assignment'])
            for p in processed if getattr(p['assignment'], 'is_acting', False)
        ]

        segments = []
        total_month_days = 0

        for data in processed:
            asi = data['assignment']
            is_acting = getattr(asi, 'is_acting', False)

            s_date = max(data['start'], self.period.start_date)
            e_date = min(data['end'], self.period.end_date) if data['end'] else self.period.end_date
            if s_date > e_date:
                continue

            base_remun = Decimal(str(asi.budget_line.remuneration or 0))

            curr = s_date
            segment_acting_worked_days = 0
            segment_acting_vacation_days = 0
            segment_normal_days = 0

            while curr <= e_date:
                if curr.day > 30:
                    curr += timedelta(days=1)
                    continue

                if is_acting:
                    if curr in vacation_dates:
                        segment_acting_vacation_days += 1
                    else:
                        segment_acting_worked_days += 1
                else:
                    in_acting = any(act_s <= curr <= act_e for act_s, act_e, _ in acting_ranges)
                    if not in_acting:
                        segment_normal_days += 1

                curr += timedelta(days=1)

            # Ajuste de febrero (al mismo nivel del while)
            if self.period.end_date.month == 2 and e_date == self.period.end_date:
                feb_missing_days = 30 - e_date.day
                if feb_missing_days > 0:
                    if is_acting:
                        if e_date in vacation_dates:
                            segment_acting_vacation_days += feb_missing_days
                        else:
                            segment_acting_worked_days += feb_missing_days
                    else:
                        segment_normal_days += feb_missing_days

            # Creación de segmentos respetando el tope de 30 días
            if is_acting:
                if segment_acting_worked_days > 0:
                    actual = min(segment_acting_worked_days, max(0, 30 - total_month_days))
                    if actual > 0:
                        segments.append({
                            'assignment': asi,
                            'actual_days': actual,
                            'base_salary': base_remun,
                            'budget_line': asi.budget_line,
                            'real_start': s_date,
                            'real_end': e_date,
                        })
                        total_month_days += actual

                if segment_acting_vacation_days > 0:
                    actual = min(segment_acting_vacation_days, max(0, 30 - total_month_days))
                    if actual > 0:
                        fallback_salary = orig_salary if orig_salary > 0 else base_remun
                        fallback_bl = original_bl if original_bl else asi.budget_line
                        segments.append({
                            'assignment': asi,
                            'actual_days': actual,
                            'base_salary': fallback_salary,
                            'budget_line': fallback_bl,
                            'real_start': s_date,
                            'real_end': e_date,
                        })
                        total_month_days += actual
            else:
                if segment_normal_days > 0:
                    actual = min(segment_normal_days, max(0, 30 - total_month_days))
                    if actual > 0:
                        segments.append({
                            'assignment': asi,
                            'actual_days': actual,
                            'base_salary': base_remun,
                            'budget_line': asi.budget_line,
                            'real_start': s_date,
                            'real_end': e_date,
                        })
                        total_month_days += actual

            if total_month_days >= 30:
                break

        return segments

    def _assign_budget_lines_to_items(self, created_payslips, assignment_map):
        created_items = PayslipItem.objects.filter(
            payslip__in=created_payslips
        ).select_related('rubric', 'payslip')

        latest_budget_line_by_employee = {}
        for employee_id, assignments in assignment_map.items():
            if not assignments:
                continue
            latest_assignment = max(assignments, key=lambda x: x.start_date)
            if latest_assignment.budget_line:
                latest_budget_line_by_employee[employee_id] = latest_assignment.budget_line

        updates = []
        for item in created_items:
            if item.budget_line_code:
                continue
            base_bl = latest_budget_line_by_employee.get(item.payslip.employee_id)
            if not base_bl:
                continue

            rubric = item.rubric
            new_code = base_bl.code

            if rubric.has_mapping and rubric.dynamic_suffix:
                if rubric.is_fixed:
                    new_code = rubric.dynamic_suffix
                else:
                    base_parts = base_bl.code.split('.')
                    suffix_parts = rubric.dynamic_suffix.split('.')
                    if len(base_parts) > len(suffix_parts):
                        new_code = (
                            f"{'.'.join(base_parts[:-len(suffix_parts)])}"
                            f".{rubric.dynamic_suffix}"
                        )
                    else:
                        new_code = rubric.dynamic_suffix

            item.budget_line = base_bl
            item.budget_line_code = new_code
            updates.append(item)

        if updates:
            PayslipItem.objects.bulk_update(
                updates, ['budget_line', 'budget_line_code'], batch_size=1000
            )

    def _generate_accounting_journal(self, created_payslips) -> list:
        aggregation: dict[tuple, list] = {}
        warnings: list[str] = []

        salary_rubrics = list(PayrollRubric.objects.filter(is_salary=True, is_active=True))
        if not salary_rubrics:
            warnings.append(
                "ERROR: No hay ningun rubro marcado como 'Es Sueldo / Remuneracion Base'."
            )

        def _find_salary_rubric(spending_type: str):
            sc = str(spending_type or '5')
            if sc.startswith('7'):
                target = '7.1'
            elif sc.startswith('6'):
                target = '6.1'
            else:
                target = '5.1'
            return (
                    next((r for r in salary_rubrics if r.spending_context == target), None)
                    or next((r for r in salary_rubrics if r.spending_context == 'TODOS'), None)
            )

        def _add(acc_id, mov, amt, order=100):
            if not acc_id or amt <= 0:
                return
            key = (acc_id, mov)
            if key in aggregation:
                aggregation[key][0] = min(aggregation[key][0], order)
                aggregation[key][1] += amt
            else:
                aggregation[key] = [order, amt]

        account_cache: dict[int, Account] = {}

        def _get_account(acc_id):
            if not acc_id:
                return None
            if acc_id not in account_cache:
                account_cache[acc_id] = Account.objects.filter(id=acc_id).first()
            return account_cache[acc_id]

        items_qs = (
            PayslipItem.objects
            .filter(payslip__in=created_payslips)
            .select_related('rubric', 'budget_line__spending_type_item')
            .order_by('rubric__order')
        )

        for it in items_qs:
            rubric = it.rubric
            if not rubric:
                continue
            val = Decimal(str(it.value))
            if val <= 0:
                continue

            spending_type = (
                it.budget_line.spending_type_item.code
                if it.budget_line and it.budget_line.spending_type_item
                else '5.1'
            )
            rub_order = getattr(rubric, 'order', 100) or 100

            accounts = _resolve_accounts_for_rubric(rubric, spending_type)
            sal_rubric = rubric if getattr(rubric, 'is_salary', False) else _find_salary_rubric(spending_type)
            c_puente = _resolve_bridge_account_id(sal_rubric, spending_type) if sal_rubric else None

            if rubric.rubric_type == 'INCOME':
                _add(accounts['debit'], 'debit', val, rub_order)
                _add(c_puente, 'credit', val, rub_order)

            elif rubric.rubric_type == 'DEDUCTION':
                _add(c_puente, 'debit', val, 800 + rub_order)
                _add(accounts['credit'], 'credit', val, 800 + rub_order)
                if rubric.income_account_id:
                    _add(accounts['credit'], 'debit', val, 800 + rub_order)
                    _add(rubric.income_account_id, 'credit', val, 800 + rub_order)

            elif rubric.rubric_type == 'CONTRIBUTION':
                _add(accounts['debit'], 'debit', val, rub_order)
                if c_puente:
                    _add(c_puente, 'credit', val, rub_order)
                    _add(c_puente, 'debit', val, 800 + rub_order)
                _add(accounts['credit'], 'credit', val, 800 + rub_order)

        for slip in created_payslips:
            if slip.net_pay <= 0:
                continue

            first_item = (
                slip.items
                .select_related('budget_line__spending_type_item')
                .first()
            )
            spending_type_slip = (
                first_item.budget_line.spending_type_item.code
                if first_item and first_item.budget_line and first_item.budget_line.spending_type_item
                else '5.1'
            )

            salary_rubric_slip = _find_salary_rubric(spending_type_slip)
            if not salary_rubric_slip:
                warnings.append(
                    f"AVISO: Rol {slip.id} ({slip.employee}) sin rubro sueldo para tipo {spending_type_slip}."
                )
                continue

            c_puente_banco = _resolve_bridge_account_id(salary_rubric_slip, spending_type_slip)
            c_banco = salary_rubric_slip.income_account_id

            if not c_banco:
                warnings.append(
                    f"AVISO: Rubro sueldo '{salary_rubric_slip.name}' sin cuenta de banco (income_account)."
                )

            _add(c_puente_banco, 'debit', slip.net_pay, 900)
            _add(c_banco, 'credit', slip.net_pay, 900)

            # 2. FUERA DEL BUCLE: Crear la cabecera del asiento contable consolidado
        desc_asiento = f"Nomina {self.period.month} {self.period.year}"
        Journal.objects.filter(description=desc_asiento).delete()
        journal = Journal.objects.create(
            date=self.period.end_date, description=desc_asiento
        )

        total_debits = Decimal('0.0')
        total_credits = Decimal('0.0')

        # 3. Crear los detalles del asiento (JournalItems)
        for (acc_id, mov_type), (_, val) in sorted(aggregation.items(), key=lambda x: x[1][0]):
            acc = _get_account(acc_id)
            if acc and val > 0:
                val_rounded = val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                is_debit = (mov_type == 'debit')
                debit_amt = val_rounded if is_debit else Decimal('0.0')
                credit_amt = Decimal('0.0') if is_debit else val_rounded

                JournalItem.objects.create(
                    journal=journal,
                    account=acc,
                    debit=debit_amt,
                    credit=credit_amt,
                    reference=str(self.period),
                )
                total_debits += debit_amt
                total_credits += credit_amt

        # 4. Ajuste por redondeo si existe descuadre de centavos
        if total_debits != total_credits:
            diff = total_debits - total_credits
            balancing_account = Account.objects.filter(
                Q(code__icontains='PAYROLL') | Q(name__icontains='DIFERENCIAS')
            ).first()

            if balancing_account:
                if diff > 0:
                    JournalItem.objects.create(
                        journal=journal, account=balancing_account,
                        debit=Decimal('0.0'), credit=diff, reference=str(self.period)
                    )
                else:
                    JournalItem.objects.create(
                        journal=journal, account=balancing_account,
                        debit=abs(diff), credit=Decimal('0.0'), reference=str(self.period)
                    )
            else:
                warnings.append(
                    f"AVISO: El asiento tuvo un descuadre por redondeo de ${abs(diff)}. Configure una cuenta de ajuste."
                )

        return warnings


def calculate_effective_days(employee, start_date, end_date) -> int:
    effective_days = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:
            effective_days += 1
        current_date += timedelta(days=1)
    return effective_days


def rebuild_accounting_for_period(period_id: int) -> bool:
    period = PayrollPeriod.objects.get(pk=period_id)
    slips = Payslip.objects.filter(period=period)
    if slips.exists():
        employees = [s.employee for s in slips]
        calc = PayrollCalculatorService(period, employees)
        calc._generate_accounting_journal(slips)
    return True
