import copy
import traceback
import logging
import time
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta, date
from django.db import transaction
from django.db.models import Q

from accounting.models import Journal, JournalItem, Account
from budget.models import BudgetAssignmentHistory
from contract.models import ManagementPeriod
from permitrequest.models import PermitRequest
from schedule.models import ScheduleObservation
# Eliminamos Income, Deduction e InstitutionalContribution. Agregamos PayrollRubric
from .models import Payslip, PayslipItem, PayrollConstant, PendingDebt, PayrollPeriod, PayrollNovelty, PayrollRubric

logger = logging.getLogger(__name__)


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
            start_date__lte=self.period.end_date, end_date__gte=self.period.start_date
        ).values_list('start_date', 'end_date')

        holiday_dates = set()
        for start_date, end_date in holidays_qs:
            curr = max(start_date, self.period.start_date)
            end_limit = min(end_date, self.period.end_date)
            while curr <= end_limit:
                holiday_dates.add(curr)
                curr += timedelta(days=1)

        prev_period = PayrollPeriod.objects.filter(end_date__lt=self.period.start_date).order_by('-end_date').first()
        prev_effective_days_map = {}
        if prev_period:
            prev_effective_days_map = dict(
                Payslip.objects.filter(period=prev_period, employee_id__in=emp_ids).values_list(
                    'employee_id', 'effective_worked_days'
                )
            )

        discountable_types = Q(permit_type__name__icontains='Personal') | Q(permit_type__name__icontains='Médico') | Q(
            permit_type__name__icontains='Medico') | \
                             Q(permit_type__parent__name__icontains='Personal') | Q(
            permit_type__parent__name__icontains='Médico') | Q(permit_type__parent__name__icontains='Medico')

        approved_permits = PermitRequest.objects.filter(
            employee_id__in=emp_ids, status='APPROVED', start_date__lte=self.period.end_date
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)).filter(
            discountable_types
        ).values('employee_id', 'start_date', 'end_date', 'days', 'hours')

        absent_dates_map = {}
        for permit in approved_permits:
            eid = permit['employee_id']
            if eid not in absent_dates_map:
                absent_dates_map[eid] = set()

            p_start = max(permit['start_date'], self.period.start_date)
            p_end = min(permit['end_date'] or permit['start_date'], self.period.end_date)

            if (permit.get('days') or 0) >= 1 or (permit.get('hours') or 0) >= 8 or p_start != p_end:
                curr = p_start
                while curr <= p_end:
                    absent_dates_map[eid].add(curr)
                    curr += timedelta(days=1)

        return holiday_dates, prev_effective_days_map, absent_dates_map

    def _filter_eligible_employees(self, employees):
        candidate_ids = [emp.id for emp in employees if
                         emp.is_active and getattr(emp, 'person', None) and emp.person.is_active]

        all_assignments_qs = BudgetAssignmentHistory.objects.filter(
            employee_id__in=candidate_ids,
            start_date__lte=self.period.end_date
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)
        )

        if self.is_scope_run:
            valid_history_emp_ids = set(all_assignments_qs.values_list('employee_id', flat=True))
        else:
            valid_history_emp_ids = set()
            for a in all_assignments_qs:
                if a.start_date <= self.cutoff_date:
                    valid_history_emp_ids.add(a.employee_id)

        return [emp for emp in employees if emp.id in valid_history_emp_ids]

    def generate_bulk(self):
        eligible_employees = self._filter_eligible_employees(self.employees)
        payslip_buffer = [Payslip(employee=emp, period=self.period, worked_days=self.period.working_days)
                          for emp in eligible_employees]

        return self._execute_payroll_calculation(payslip_buffer, delete_entire_period=True)

    def generate_for_selected(self, employees_with_days):
        eligible_pairs = []
        employees = [emp for emp, _ in employees_with_days]
        eligible_employees = self._filter_eligible_employees(employees)
        eligible_ids = {emp.id for emp in eligible_employees}

        for emp, days in employees_with_days:
            if emp.id in eligible_ids:
                eligible_pairs.append((emp, days))

        payslip_buffer = [Payslip(employee=emp, period=self.period, worked_days=days)
                          for emp, days in eligible_pairs]

        selected_emp_ids = [emp.id for emp, _ in eligible_pairs]
        return self._execute_payroll_calculation(payslip_buffer, employee_ids_to_delete=selected_emp_ids,
                                                 delete_entire_period=False)

    def _execute_payroll_calculation(self, payslip_buffer, delete_entire_period=False, employee_ids_to_delete=None):
        t0 = time.perf_counter()
        t_mark = t0

        def _lap(label):
            nonlocal t_mark
            now = time.perf_counter()
            msg = f"[PAYROLL][PERF] {label} -> +{(now - t_mark):.3f}s (acum: {(now - t0):.3f}s)"
            logger.info(msg)
            print(msg)
            t_mark = now

        with transaction.atomic():
            if delete_entire_period:
                PendingDebt.objects.filter(period=self.period).delete()
                Payslip.objects.filter(period=self.period).delete()
            elif employee_ids_to_delete:
                PendingDebt.objects.filter(period=self.period, employee_id__in=employee_ids_to_delete).delete()
                Payslip.objects.filter(period=self.period, employee_id__in=employee_ids_to_delete).delete()
            _lap("delete previous payroll data")

            created_payslips = Payslip.objects.bulk_create(payslip_buffer)
            emp_ids = [p.employee.id for p in created_payslips]
            _lap("bulk_create payslips")

            holiday_dates, prev_effective_days_map, absent_dates_map = self._prepare_mass_data(emp_ids)
            _lap("prepare mass data")

            items_buffer, payslips_to_update, pending_debts_buffer = [], [], []
            debts_to_update = []

            # ====================================================
            # USO EXCLUSIVO DEL MODELO UNIFICADO (PayrollRubric)
            # ====================================================
            all_rubrics = list(PayrollRubric.objects.filter(is_active=True))
            active_incomes = [r for r in all_rubrics if r.rubric_type == 'INCOME']
            active_deductions = [r for r in all_rubrics if r.rubric_type == 'DEDUCTION']
            active_contributions = [r for r in all_rubrics if r.rubric_type == 'CONTRIBUTION']

            active_income_codes = {inc.code.strip().upper() for inc in active_incomes if inc.code}
            has_ct_base_income = 'SALARIOS_BASICOS' in active_income_codes
            ded_map = {d.code.strip().upper(): d for d in active_deductions if d.code}
            contrib_map = {c.code.strip().upper(): c for c in active_contributions if c.code}

            all_assignments_qs = BudgetAssignmentHistory.objects.filter(
                employee_id__in=emp_ids,
                start_date__lte=self.period.end_date
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)
            ).select_related('budget_line', 'budget_line__activity__project__subprogram__program')

            assignment_map = {}
            for a in all_assignments_qs:
                assignment_map.setdefault(a.employee_id, []).append(a)

            mp_map = {}
            for mp in ManagementPeriod.objects.filter(employee_id__in=emp_ids).select_related(
                    'contract_type__labor_regime',
                    'status').order_by(
                'employee_id', 'start_date'):
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

                        # ==============================
                        # CARGA DE NOVEDADES
                        # ==============================
                        novelties_map = {}
                        for nov in PayrollNovelty.objects.filter(period=self.period,
                                                                 employee_id__in=emp_ids).select_related('rubric'):
                            if not nov.rubric:
                                continue

                            if nov.employee_id not in novelties_map:
                                novelties_map[nov.employee_id] = {'incomes': [], 'deductions': []}

                            if nov.rubric.rubric_type == 'INCOME':
                                novelties_map[nov.employee_id]['incomes'].append(nov)
                            elif nov.rubric.rubric_type == 'DEDUCTION':
                                novelties_map[nov.employee_id]['deductions'].append(nov)

                        # ==============================
                        # CARGA DE DEUDAS PENDIENTES
                        # ==============================
                        existing_pending_debts_map = {}
                        old_debts_qs = PendingDebt.objects.filter(
                            employee_id__in=emp_ids,
                            pending_balance__gt=0
                        ).exclude(period=self.period).select_related('rubric').order_by('employee_id', 'id')

                        for debt in old_debts_qs:
                            if not debt.rubric:
                                continue
                            existing_pending_debts_map.setdefault(debt.employee_id, []).append(debt)

                        _lap("load mappings and novelties")

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

                    segments = []

                    if emp_assignments:
                        emp_assignments.sort(key=lambda x: x.start_date)
                        processed_assignments = []
                        for i in range(len(emp_assignments)):
                            current_asi = emp_assignments[i]
                            effective_end = current_asi.end_date
                            if i + 1 < len(emp_assignments):
                                next_start = emp_assignments[i + 1].start_date
                                if not effective_end or effective_end >= next_start:
                                    effective_end = next_start - timedelta(days=1)
                            processed_assignments.append(
                                {'assignment': current_asi, 'start': current_asi.start_date, 'end': effective_end})

                        total_month_days = 0
                        for data in processed_assignments:
                            s_date = max(data['start'], self.period.start_date)
                            e_date = min(data['end'], self.period.end_date) if data['end'] else self.period.end_date
                            if s_date <= e_date:
                                if self.period.end_date.month == 2 and e_date == self.period.end_date:
                                    actual_days = (30 - s_date.day) + 1
                                elif s_date.day == 31:
                                    actual_days = 1
                                else:
                                    commercial_end_day = min(e_date.day, 30)
                                    actual_days = (commercial_end_day - s_date.day) + 1

                                if total_month_days + actual_days > 30:
                                    actual_days = 30 - total_month_days

                                actual_days = max(0, actual_days)

                                if actual_days > 0:
                                    segments.append({
                                        'assignment': data['assignment'],
                                        'actual_days': actual_days,
                                        'base_salary': Decimal(str(data['assignment'].budget_line.remuneration or 0)),
                                        'budget_line': data['assignment'].budget_line,
                                        'real_start': s_date,
                                        'real_end': e_date
                                    })
                                    total_month_days += actual_days

                    if not segments:
                        continue

                    effective_days = 0
                    emp_absences = absent_dates_map.get(slip.employee_id, set())
                    for segment in segments:
                        curr_date = segment['real_start']
                        while curr_date <= segment['real_end']:
                            if curr_date.weekday() < 5 and curr_date not in holiday_dates and curr_date not in emp_absences:
                                effective_days += 1
                            curr_date += timedelta(days=1)

                    slip.effective_worked_days = effective_days
                    segments.sort(key=lambda x: x['assignment'].start_date)
                    salary = sum(
                        (t['base_salary'] / Decimal('30.0')) * Decimal(str(t['actual_days'])) for t in segments)

                    total_income, total_deduction, taxable_base = Decimal('0.0'), Decimal('0.0'), Decimal('0.0')
                    monthly_bonuses, monthly_reserve_funds, valid_dependents_count = False, True, 0

                    try:
                        payroll_info = getattr(getattr(getattr(slip.employee, 'person', None), 'economic_data', None),
                                               'payroll_info', None)
                        if payroll_info:
                            monthly_bonuses, monthly_reserve_funds = bool(payroll_info.monthly_payment), bool(
                                payroll_info.reserve_funds)
                            valid_dependents_count = payroll_info.family_dependents + payroll_info.education_dependents
                    except Exception:
                        pass

                    effective_days_prev = prev_effective_days_map.get(slip.employee_id, 0)
                    mp = mp_map.get(slip.employee_id)
                    years_of_service = (
                            (self.period.end_date - mp.start_date).days / 365.25) if mp and mp.start_date else 0
                    regime_code = mp.contract_type.labor_regime.code.strip().upper() if mp and mp.contract_type and mp.contract_type.labor_regime else ''

                    emp_novelties = novelties_map.get(slip.employee_id, {'incomes': [], 'deductions': []})
                    prepared_income_novelties = []
                    hours_income_total = Decimal('0.00')

                    for nov in emp_novelties['incomes']:
                        if nov.value <= 0:
                            continue
                        nov_val = Decimal(str(nov.value))
                        code_up = (nov.rubric.code or '').strip().upper()

                        if 'HORAS_EXTRAS' in code_up or 'HORA_EXTRA' in code_up:
                            daily_salary = (salary / Decimal('30.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                            hourly_salary = (daily_salary / Decimal('8.0')).quantize(Decimal('0.01'),
                                                                                     rounding=ROUND_HALF_UP)
                            nov_val = (hourly_salary * Decimal('1.50') * nov_val).quantize(Decimal('0.01'),
                                                                                           rounding=ROUND_HALF_UP)
                            hours_income_total += nov_val
                        elif 'SUPLEMENTARIAS' in code_up or 'SUPLEMENTARIA' in code_up:
                            daily_salary = (salary / Decimal('30.0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                            hourly_salary = (daily_salary / Decimal('8.0')).quantize(Decimal('0.01'),
                                                                                     rounding=ROUND_HALF_UP)
                            nov_val = (hourly_salary * Decimal('2.00') * nov_val).quantize(Decimal('0.01'),
                                                                                           rounding=ROUND_HALF_UP)
                            hours_income_total += nov_val

                        prepared_income_novelties.append((nov, nov_val))

                    for inc in active_incomes:
                        val, code_clean = Decimal('0.0'), inc.code.strip().upper() if inc.code else ''

                        # LOGICA DINÁMICA DE SUELDO (SIN CÓDIGO QUEMADO)
                        is_base_income = getattr(inc, 'is_salary', False)
                        if not is_base_income:
                            is_ct_base_income = (code_clean == 'SALARIOS_BASICOS') if has_ct_base_income else (
                                    code_clean == 'REMUNERACION')
                            is_base_income = (regime_code == 'CT' and is_ct_base_income) or (
                                    regime_code != 'CT' and code_clean == 'REMUNERACION')

                        if is_base_income:
                            for segment in segments:
                                segment_val = (segment['base_salary'] / Decimal('30.0')) * Decimal(
                                    str(segment['actual_days']))
                                if segment_val > 0:
                                    it = PayslipItem(payslip=slip, rubric=inc, item_type='INCOME', value=segment_val)
                                    it._historical_bl = segment['budget_line']
                                    items_buffer.append(it)
                                    total_income += segment_val
                                    taxable_base += segment_val
                            continue
                        elif code_clean == 'DECIMO_TERCERO' and monthly_bonuses and self.period.working_days:
                            thirteenth_base = salary + hours_income_total
                            val = (thirteenth_base / Decimal('12.0')) * (
                                    Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))
                        elif code_clean == 'DECIMO_CUARTO' and monthly_bonuses and self.period.working_days:
                            val = (Decimal(str(self.config.get('SBU', '460.00'))) / Decimal('12.0')) * (
                                    Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))
                        elif code_clean == 'FONDOS_RESERVA':
                            if not monthly_reserve_funds or (years_of_service > 1):
                                if not monthly_reserve_funds:
                                    val = (salary * (Decimal(str(self.config.get('FONDOS_RESERVA', '8.33'))) / Decimal(
                                        '100.0'))) * (Decimal(str(slip.worked_days)) / Decimal(
                                        str(self.period.working_days)))
                        elif code_clean == 'ALIMENTACION' and regime_code == 'CT' and years_of_service >= 1:
                            val = Decimal(str(self.config.get('ALIMENTACION_DIARIA', '4.00'))) * Decimal(
                                str(effective_days_prev))
                        elif code_clean == 'TRANSPORTE' and regime_code == 'CT' and years_of_service >= 1:
                            val = Decimal(str(self.config.get('TRANSPORTE_DIARIO', '0.50'))) * Decimal(
                                str(effective_days_prev))
                        elif code_clean == 'SUBSIDIO_FAMILIAR' and regime_code == 'CT' and years_of_service >= 1 and valid_dependents_count > 0:
                            val = Decimal(str(self.config.get('SBU', '460.00'))) * (
                                    Decimal('1.00') / Decimal('100.0')) * Decimal(str(valid_dependents_count))
                        elif code_clean == 'ANTIGUEDAD' and regime_code == 'CT' and years_of_service >= 1:
                            val = salary * (Decimal('0.25') / Decimal('100.0')) * Decimal(str(int(years_of_service)))

                        if val > 0:
                            items_buffer.append(PayslipItem(payslip=slip, rubric=inc, item_type='INCOME', value=val))
                            total_income += val
                            if is_base_income:
                                taxable_base += val

                    # ====================================================
                    # 1. IESS y Aportes Patronales
                    # ====================================================
                    target_iess_code = 'IESS_PER_EMP' if regime_code == 'LOSEP' else 'IESS_PER_TRA' if regime_code == 'CT' else 'IESS_PER'
                    target_patronal_code = 'APORTE_PATRONAL_EMP' if regime_code == 'LOSEP' else 'APORTE_PATRONAL_TRA' if regime_code == 'CT' else 'APORTE_PATRONAL'

                    iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')
                    if iess_ded:
                        val = taxable_base * (Decimal(
                            str(self.config.get(target_iess_code, self.config.get('IESS_PER', '9.45')))) / Decimal(
                            '100.0'))
                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, rubric=iess_ded, item_type='DEDUCTION', value=val))
                            total_deduction += val

                    contrib_ref = contrib_map.get(target_patronal_code) or contrib_map.get('APORTE_PATRONAL')
                    if contrib_ref:
                        employer_val = taxable_base * (Decimal(str(self.config.get(target_patronal_code,
                                                                                   self.config.get('APORTE_PATRONAL',
                                                                                                   '11.15')))) / Decimal(
                            '100.0'))
                        if employer_val > 0:
                            items_buffer.append(PayslipItem(payslip=slip, rubric=contrib_ref, item_type='CONTRIBUTION',
                                                            value=employer_val))

                    # ====================================================
                    # 2. NOVEDADES (Ingresos Extra y Horas)
                    # ====================================================
                    for nov, nov_val in prepared_income_novelties:
                        items_buffer.append(
                            PayslipItem(payslip=slip, rubric=nov.rubric, item_type='INCOME', value=nov_val))
                        total_income += nov_val

                    # ====================================================
                    # 3. POCKET LOGIC (Descuentos y Deudas Viejas)
                    # ====================================================
                    available_balance = total_income - total_deduction
                    deduction_novelties = sorted(emp_novelties['deductions'],
                                                 key=lambda x: getattr(x.rubric, 'priority', 100) or 100)
                    pending_debts_list = existing_pending_debts_map.get(slip.employee_id, [])

                    for debt in pending_debts_list:
                        debt_val = Decimal(str(debt.pending_balance))
                        real_discount = Decimal('0.0') if available_balance <= Decimal('0.0') else min(debt_val,
                                                                                                       available_balance)
                        items_buffer.append(
                            PayslipItem(payslip=slip, rubric=debt.rubric, item_type='DEDUCTION', value=real_discount))
                        if real_discount > 0:
                            total_deduction += real_discount
                            available_balance -= real_discount
                            debt.collected_value += real_discount
                            debt.pending_balance -= real_discount
                            debts_to_update.append(debt)

                    for nov in deduction_novelties:
                        if nov.value > 0:
                            original_val = Decimal(str(nov.value))
                            real_discount = Decimal('0.0') if available_balance <= Decimal('0.0') else min(original_val,
                                                                                                           available_balance)
                            new_debt = original_val - real_discount
                            items_buffer.append(PayslipItem(payslip=slip, rubric=nov.rubric, item_type='DEDUCTION',
                                                            value=real_discount))
                            if real_discount > 0:
                                total_deduction += real_discount
                                available_balance -= real_discount
                            if new_debt > 0:
                                pending_debts_buffer.append(PendingDebt(
                                    employee=slip.employee, period=self.period, rubric=nov.rubric,
                                    original_value=original_val, collected_value=real_discount, pending_balance=new_debt
                                ))

                    slip.total_income, slip.total_deduction, slip.net_pay = total_income, total_deduction, total_income - total_deduction
                    payslips_to_update.append(slip)

                except Exception as e:
                    print(f"\n{'=' * 60}\n🔥 ERROR EMPLEADO: {slip.employee_id}\nMensaje: {str(e)}\n{'=' * 60}\n")
                    traceback.print_exc()
                    raise e
            _lap("calculate items loop")

            PayslipItem.objects.bulk_create(items_buffer, batch_size=1000)
            Payslip.objects.bulk_update(payslips_to_update,
                                        ['total_income', 'total_deduction', 'net_pay', 'effective_worked_days'])
            PendingDebt.objects.bulk_create(pending_debts_buffer, batch_size=1000)
            if debts_to_update:
                PendingDebt.objects.bulk_update(debts_to_update, ['collected_value', 'pending_balance'])
            _lap("bulk persist items and debts")

            self._assign_budget_lines_to_items(created_payslips, assignment_map)
            _lap("assign budget lines")
            warnings = self._generate_accounting_journal(created_payslips)
            _lap("generate accounting journal")

            total_msg = f"[PAYROLL][PERF] total payroll execution: {(time.perf_counter() - t0):.3f}s"
            logger.info(total_msg)
            print(total_msg)

            return {"success": True, "warnings": warnings}

    def _assign_budget_lines_to_items(self, created_payslips, assignment_map):
        created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related('rubric')
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
                        new_code = f"{'.'.join(base_parts[:-len(suffix_parts)])}.{rubric.dynamic_suffix}"
                    else:
                        new_code = rubric.dynamic_suffix

            item.budget_line = base_bl
            item.budget_line_code = new_code
            updates.append(item)

        if updates:
            PayslipItem.objects.bulk_update(updates, ['budget_line', 'budget_line_code'], batch_size=1000)

    def _generate_accounting_journal(self, created_payslips):
        aggregation, warnings = {}, []
        items_qs = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
            'rubric', 'budget_line', 'budget_line__budget_group', 'budget_line__activity__project'
        )
        total_net_pay = sum(Decimal(str(slip.net_pay)) for slip in created_payslips)

        account_cache = {}

        def get_account_cached(acc_id):
            if not acc_id: return None
            if acc_id not in account_cache:
                try:
                    account_cache[acc_id] = Account.objects.get(id=acc_id)
                except Account.DoesNotExist:
                    account_cache[acc_id] = None
            return account_cache[acc_id]

        for it in items_qs:
            val = Decimal(str(it.value))
            budget_code = getattr(it, 'budget_line_code', None)
            rubric = it.rubric

            tipo_gasto = ''
            if it.budget_line and hasattr(it.budget_line, 'budget_group') and hasattr(it.budget_line.budget_group,
                                                                                      'spending_type') and it.budget_line.budget_group.spending_type:
                tipo_gasto = it.budget_line.budget_group.spending_type.code

            if tipo_gasto.startswith('7'):
                cta_debe = rubric.debit_account_inv_id
                cta_haber = rubric.credit_account_inv_id
            elif tipo_gasto.startswith('6'):
                cta_debe = rubric.debit_account_prod_id
                cta_haber = rubric.credit_account_prod_id
            else:
                cta_debe = rubric.debit_account_id
                cta_haber = rubric.credit_account_id

            if rubric.rubric_type == 'INCOME':
                if cta_debe: aggregation[(cta_debe, budget_code, 'debit')] = aggregation.get(
                    (cta_debe, budget_code, 'debit'), Decimal('0.0')) + val
                if cta_haber: aggregation[(cta_haber, budget_code, 'credit')] = aggregation.get(
                    (cta_haber, budget_code, 'credit'), Decimal('0.0')) + val

                if tipo_gasto.startswith('7') or tipo_gasto.startswith('6'):
                    if cta_debe: aggregation[(cta_debe, budget_code, 'credit')] = aggregation.get(
                        (cta_debe, budget_code, 'credit'), Decimal('0.0')) + val
                    if it.budget_line and hasattr(it.budget_line,
                                                  'activity') and it.budget_line.activity and it.budget_line.activity.project and hasattr(
                        it.budget_line.activity.project, 'capitalization_account_id'):
                        cta_proyecto = it.budget_line.activity.project.capitalization_account_id
                        if cta_proyecto:
                            aggregation[(cta_proyecto, None, 'debit')] = aggregation.get((cta_proyecto, None, 'debit'),
                                                                                         Decimal('0.0')) + val

            elif rubric.rubric_type == 'DEDUCTION':
                if cta_debe: aggregation[(cta_debe, None, 'debit')] = aggregation.get((cta_debe, None, 'debit'),
                                                                                      Decimal('0.0')) + val
                if cta_haber: aggregation[(cta_haber, None, 'credit')] = aggregation.get((cta_haber, None, 'credit'),
                                                                                         Decimal('0.0')) + val

                if rubric.income_account_id:
                    if cta_haber: aggregation[(cta_haber, None, 'debit')] = aggregation.get((cta_haber, None, 'debit'),
                                                                                            Decimal('0.0')) + val
                    aggregation[(rubric.income_account_id, None, 'credit')] = aggregation.get(
                        (rubric.income_account_id, None, 'credit'), Decimal('0.0')) + val

            elif rubric.rubric_type == 'CONTRIBUTION':
                if cta_debe: aggregation[(cta_debe, None, 'debit')] = aggregation.get((cta_debe, None, 'debit'),
                                                                                      Decimal('0.0')) + val
                if cta_haber: aggregation[(cta_haber, None, 'credit')] = aggregation.get((cta_haber, None, 'credit'),
                                                                                         Decimal('0.0')) + val

        if aggregation or total_net_pay > 0:
            desc_asiento = f"Nómina {self.period.month} {self.period.year}"
            Journal.objects.filter(description=desc_asiento).delete()
            journal = Journal.objects.create(date=self.period.end_date, description=desc_asiento)
            total_debits, total_credits = Decimal('0.0'), Decimal('0.0')

            for (acc_id, b_code, mov_type), val in aggregation.items():
                if val <= 0: continue
                acc = get_account_cached(acc_id)
                if acc:
                    if mov_type == 'debit':
                        JournalItem.objects.create(journal=journal, account=acc, debit=val, credit=Decimal('0.0'),
                                                   reference=str(self.period))
                        total_debits += val
                    else:
                        JournalItem.objects.create(journal=journal, account=acc, debit=Decimal('0.0'), credit=val,
                                                   reference=str(self.period))

            if total_net_pay > 0:
                cta_gp = Account.objects.filter(code='2.1.3.51').first()
                cta_bco = Account.objects.filter(code='1.1.1.03.01').first()
                if cta_gp:
                    JournalItem.objects.create(journal=journal, account=cta_gp, debit=total_net_pay,
                                               credit=Decimal('0.0'), reference=str(self.period))
                    total_debits += total_net_pay
                if cta_bco:
                    JournalItem.objects.create(journal=journal, account=cta_bco, debit=Decimal('0.0'),
                                               credit=total_net_pay, reference=str(self.period))

            if total_debits != total_credits:
                diff = total_debits - total_credits
                balancing_account = Account.objects.filter(code__icontains='PAYROLL').first()
                if balancing_account:
                    if diff > 0:
                        JournalItem.objects.create(journal=journal, account=balancing_account, debit=Decimal('0.0'),
                                                   credit=diff, reference=str(self.period))
                    else:
                        JournalItem.objects.create(journal=journal, account=balancing_account, debit=abs(diff),
                                                   credit=Decimal('0.0'), reference=str(self.period))

        return warnings


def calculate_effective_days(employee, start_date, end_date):
    effective_days = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
        effective_days += 1
        current_date += timedelta(days=1)
    return effective_days


def rebuild_accounting_for_period(period_id):
    period = PayrollPeriod.objects.get(pk=period_id)
    slips = Payslip.objects.filter(period=period)
    if slips.exists():
        employees = [s.employee for s in slips]
        calc = PayrollCalculatorService(period, employees)
        calc._generate_accounting_journal(slips)
    return True
