import traceback
from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.db.models import Q

from accounting.models import Journal, JournalItem, Account
from budget.models import BudgetAssignmentHistory
from contract.models import ManagementPeriod
from permitrequest.models import PermitRequest
from schedule.models import ScheduleObservation
from .models import Payslip, PayslipItem, PayrollConstant, Income, Deduction, InstitutionalContribution, PendingDebt, \
    PayrollPeriod, PayrollNovelty


class PayrollCalculatorService:
    def __init__(self, period, employees):
        self.period = period
        self.employees = employees

        constants = PayrollConstant.objects.all().values('code', 'value')
        self.config = {c['code']: c['value'] for c in constants}

        if 'SBU' not in self.config:
            raise ValueError("Falta configurar la constante 'SBU' (Salario Básico Unificado).")

    def _prepare_mass_data(self, emp_ids):
        # 1. Feriados
        holidays_qs = ScheduleObservation.objects.filter(
            is_holiday=True, is_active=True,
            start_date__lte=self.period.end_date, end_date__gte=self.period.start_date
        )
        holiday_dates = set()
        for h in holidays_qs:
            curr = max(h.start_date, self.period.start_date)
            end_limit = min(h.end_date, self.period.end_date)
            while curr <= end_limit:
                holiday_dates.add(curr)
                curr += timedelta(days=1)

        # 2. Días efectivos del mes anterior
        prev_period = PayrollPeriod.objects.filter(end_date__lt=self.period.start_date).order_by('-end_date').first()
        prev_effective_days_map = {}
        if prev_period:
            prev_payslips = Payslip.objects.filter(period=prev_period, employee_id__in=emp_ids).values_list(
                'employee_id', 'effective_worked_days')
            for eid, eff_days in prev_payslips:
                prev_effective_days_map[eid] = eff_days

        # 3. Permisos Descontables
        tipos_descontables = Q(permit_type__name__icontains='Personal') | Q(permit_type__name__icontains='Médico') | Q(
            permit_type__name__icontains='Medico') | \
                             Q(permit_type__parent__name__icontains='Personal') | Q(
            permit_type__parent__name__icontains='Médico') | Q(permit_type__parent__name__icontains='Medico')

        approved_permits = PermitRequest.objects.filter(
            employee_id__in=emp_ids, status='APPROVED', start_date__lte=self.period.end_date
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)).filter(tipos_descontables)

        absent_dates_map = {}
        for permit in approved_permits:
            eid = permit.employee_id
            if eid not in absent_dates_map:
                absent_dates_map[eid] = set()

            p_start = max(permit.start_date, self.period.start_date)
            p_end = min(permit.end_date or permit.start_date, self.period.end_date)

            if permit.days >= 1 or permit.hours >= 8 or p_start != p_end:
                curr = p_start
                while curr <= p_end:
                    absent_dates_map[eid].add(curr)
                    curr += timedelta(days=1)

        return holiday_dates, prev_effective_days_map, absent_dates_map

    def generate_bulk(self):
        payslip_buffer = []
        eligible_employees = []

        candidate_ids = [emp.id for emp in self.employees if
                         emp.is_active and getattr(emp, 'person', None) and emp.person.is_active]
        valid_history_emp_ids = set(
            BudgetAssignmentHistory.objects.filter(employee_id__in=candidate_ids, start_date__lte=self.period.end_date)
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)).values_list('employee_id',
                                                                                                    flat=True))

        for emp in self.employees:
            if emp.id not in valid_history_emp_ids: continue
            eligible_employees.append(emp)
            payslip_buffer.append(Payslip(employee=emp, period=self.period, worked_days=self.period.working_days))

        with transaction.atomic():
            PendingDebt.objects.filter(period=self.period).delete()
            Payslip.objects.filter(period=self.period).delete()

            created_payslips = Payslip.objects.bulk_create(payslip_buffer)
            emp_ids = [p.employee.id for p in created_payslips]

            holiday_dates, prev_effective_days_map, absent_dates_map = self._prepare_mass_data(emp_ids)

            items_buffer, payslips_to_update, pending_debts_buffer = [], [], []

            active_incomes = list(Income.objects.filter(is_active=True))
            active_deductions = list(Deduction.objects.filter(is_active=True))
            ded_map = {d.code.strip().upper(): d for d in active_deductions if d.code}
            contrib_map = {c.code.strip().upper(): c for c in InstitutionalContribution.objects.filter(is_active=True)
                           if c.code}

            assignments_qs = BudgetAssignmentHistory.objects.filter(employee_id__in=emp_ids,
                                                                    start_date__lte=self.period.end_date) \
                .filter(Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)).select_related(
                'budget_line', 'budget_line__activity__project__subprogram__program')

            assignment_map = {}
            for a in assignments_qs: assignment_map.setdefault(a.employee_id, []).append(a)

            mp_map = {mp.employee_id: mp for mp in
                      ManagementPeriod.objects.filter(employee_id__in=emp_ids).select_related(
                          'contract_type__labor_regime').order_by('employee_id', '-start_date')}

            novelties_map = {}
            for nov in PayrollNovelty.objects.filter(period=self.period, employee_id__in=emp_ids).select_related(
                    'income_ref', 'deduction_ref'):
                if nov.employee_id not in novelties_map: novelties_map[nov.employee_id] = {'incomes': [],
                                                                                           'deductions': []}
                if nov.income_ref: novelties_map[nov.employee_id]['incomes'].append(nov)
                if nov.deduction_ref: novelties_map[nov.employee_id]['deductions'].append(nov)

            for slip in created_payslips:
                try:
                    emp_assignments = assignment_map.get(slip.employee_id, [])
                    tramos = []

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

                        total_dias_mes = 0
                        for data in processed_assignments:
                            s_date = max(data['start'], self.period.start_date)
                            e_date = min(data['end'], self.period.end_date) if data['end'] else self.period.end_date
                            if s_date <= e_date:
                                dias_reales = (e_date - s_date).days + 1
                                if dias_reales == 31: dias_reales = 30
                                if self.period.end_date.month == 2 and e_date == self.period.end_date: dias_reales += (
                                        30 - self.period.end_date.day)
                                if total_dias_mes + dias_reales > 30: dias_reales = 30 - total_dias_mes
                                if dias_reales > 0:
                                    tramos.append({
                                        'assignment': data['assignment'], 'dias': dias_reales,
                                        'sueldo_base': Decimal(str(data['assignment'].budget_line.remuneration or 0)),
                                        'partida': data['assignment'].budget_line, 'real_start': s_date,
                                        'real_end': e_date
                                    })
                                    total_dias_mes += dias_reales

                    if not tramos: continue

                    effective_days = 0
                    emp_absences = absent_dates_map.get(slip.employee_id, set())
                    for tramo in tramos:
                        curr_date = tramo['real_start']
                        while curr_date <= tramo['real_end']:
                            if curr_date.weekday() < 5 and curr_date not in holiday_dates and curr_date not in emp_absences:
                                effective_days += 1
                            curr_date += timedelta(days=1)

                    slip.effective_worked_days = effective_days
                    tramos.sort(key=lambda x: x['assignment'].start_date)
                    salary = sum((t['sueldo_base'] / Decimal('30.0')) * Decimal(str(t['dias'])) for t in tramos)

                    total_ing, total_desc, taxable_base = Decimal('0.0'), Decimal('0.0'), Decimal('0.0')
                    mensualiza_decimos, mensualiza_fr, num_hijos_validos = False, False, 0

                    try:
                        payroll_info = getattr(getattr(getattr(slip.employee, 'person', None), 'economic_data', None),
                                               'payroll_info', None)
                        if payroll_info:
                            mensualiza_decimos, mensualiza_fr = bool(payroll_info.monthly_payment), bool(
                                payroll_info.reserve_funds)
                            num_hijos_validos = payroll_info.family_dependents + payroll_info.education_dependents
                    except Exception:
                        pass

                    effective_days_prev = prev_effective_days_map.get(slip.employee_id, 0)
                    mp = mp_map.get(slip.employee_id)
                    anios_servicio = (
                            (self.period.end_date - mp.start_date).days / 365.25) if mp and mp.start_date else 0
                    regime_code = mp.contract_type.labor_regime.code.strip().upper() if mp and mp.contract_type and mp.contract_type.labor_regime else ''

                    for inc in active_incomes:
                        val, code_clean = Decimal('0.0'), inc.code.strip().upper() if inc.code else ''
                        if code_clean == 'REMUNERACION':
                            for tramo in tramos:
                                val_tramo = (tramo['sueldo_base'] / Decimal('30.0')) * Decimal(str(tramo['dias']))
                                if val_tramo > 0:
                                    it = PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val_tramo)
                                    it._historical_bl = tramo['partida']
                                    items_buffer.append(it)
                                    total_ing += val_tramo
                                    taxable_base += val_tramo
                            continue
                        elif code_clean == 'DECIMO_TERCERO' and mensualiza_decimos and self.period.working_days:
                            val = (salary / Decimal('12.0')) * (
                                    Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))
                        elif code_clean == 'DECIMO_CUARTO' and mensualiza_decimos and self.period.working_days:
                            val = (Decimal(str(self.config.get('SBU', '460.00'))) / Decimal('12.0')) * (
                                    Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))
                        elif code_clean == 'FONDOS_RESERVA' and anios_servicio > 1 and mensualiza_fr:
                            val = (salary * (
                                    Decimal(str(self.config.get('FONDOS_RESERVA', '8.33'))) / Decimal('100.0'))) * (
                                          Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))
                        elif code_clean == 'ALIMENTACION' and regime_code == 'CT' and anios_servicio >= 1:
                            val = Decimal(str(self.config.get('ALIMENTACION_DIARIA', '4.00'))) * Decimal(
                                str(effective_days_prev))
                        elif code_clean == 'TRANSPORTE' and regime_code == 'CT' and anios_servicio >= 1:
                            val = Decimal(str(self.config.get('TRANSPORTE_DIARIO', '0.50'))) * Decimal(
                                str(effective_days_prev))
                        elif code_clean == 'SUBSIDIO_FAMILIAR' and regime_code == 'CT' and anios_servicio >= 1 and num_hijos_validos > 0:
                            val = Decimal(str(self.config.get('SBU', '460.00'))) * (
                                    Decimal('1.00') / Decimal('100.0')) * Decimal(str(num_hijos_validos))
                        elif code_clean == 'ANTIGUEDAD' and regime_code == 'CT' and anios_servicio >= 1:
                            val = salary * (Decimal('0.25') / Decimal('100.0')) * Decimal(str(int(anios_servicio)))

                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val))
                            total_ing += val
                            if code_clean == 'REMUNERACION': taxable_base += val

                    # IESS y Aportes Patronales
                    target_iess_code = 'IESS_PER_EMP' if regime_code == 'LOSEP' else 'IESS_PER_TRA' if regime_code == 'CT' else 'IESS_PER'
                    target_patronal_code = 'APORTE_PATRONAL_EMP' if regime_code == 'LOSEP' else 'APORTE_PATRONAL_TRA' if regime_code == 'CT' else 'APORTE_PATRONAL'

                    iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')
                    if iess_ded:
                        val = taxable_base * (Decimal(
                            str(self.config.get(target_iess_code, self.config.get('IESS_PER', '9.45')))) / Decimal(
                            '100.0'))
                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION', value=val))
                            total_desc += val

                            contrib_ref = contrib_map.get(target_patronal_code) or contrib_map.get('APORTE_PATRONAL')
                            if contrib_ref:
                                val_patronal = taxable_base * (Decimal(str(self.config.get(target_patronal_code,
                                                                                           self.config.get(
                                                                                               'APORTE_PATRONAL',
                                                                                               '11.15')))) / Decimal(
                                    '100.0'))
                                if val_patronal > 0:
                                    items_buffer.append(PayslipItem(payslip=slip, contribution_ref=contrib_ref,
                                                                    item_type='CONTRIBUTION', value=val_patronal))

                                    emp_novelties = novelties_map.get(slip.employee_id,
                                                                      {'incomes': [], 'deductions': []})
                                    for nov in emp_novelties['incomes']:
                                        if nov.value > 0:
                                            val_nov = Decimal(str(nov.value))

                                            # ==================================================
                                            # MAGIA: CÁLCULO DE HORAS EXTRAS (De Horas a Dinero)
                                            # ==================================================
                                            code_up = (nov.income_ref.code or '').strip().upper()

                                            if 'HORAS_EXTRAS' in code_up or 'HORA_EXTRA' in code_up:
                                                # El valor del Excel son Horas. Multiplicamos por 2 (100% recargo)
                                                sueldo_hora = salary / Decimal('240.0')
                                                val_nov = sueldo_hora * Decimal('2.0') * val_nov

                                            elif 'SUPLEMENTARIAS' in code_up or 'SUPLEMENTARIA' in code_up:
                                                # El valor del Excel son Horas. Multiplicamos por 1.5 (50% recargo)
                                                sueldo_hora = salary / Decimal('240.0')
                                                val_nov = sueldo_hora * Decimal('1.5') * val_nov

                                            items_buffer.append(
                                                PayslipItem(payslip=slip, income_ref=nov.income_ref, item_type='INCOME',
                                                            value=val_nov))
                                            total_ing += val_nov

                                    # Pocket Logic (Descuentos)
                                    available_balance = total_ing - total_desc
                                    deduction_novelties = sorted(emp_novelties['deductions'],
                                                                 key=lambda x: getattr(x.deduction_ref, 'priority',
                                                                                       100))
                                    for nov in deduction_novelties:
                                        if nov.value > 0:
                                            val_original = Decimal(str(nov.value))
                                            real_discount = Decimal('0.0') if available_balance <= Decimal(
                                                '0.0') else min(val_original, available_balance)
                                            debt = val_original - real_discount

                                            if real_discount > 0:
                                                items_buffer.append(
                                                    PayslipItem(payslip=slip, deduction_ref=nov.deduction_ref,
                                                                item_type='DEDUCTION', value=real_discount))
                                                total_desc += real_discount
                                                available_balance -= real_discount

                                            if debt > 0:
                                                pending_debts_buffer.append(PendingDebt(
                                                    employee=slip.employee, period=self.period,
                                                    deduction_ref=nov.deduction_ref,
                                                    original_value=val_original, collected_value=real_discount,
                                                    pending_balance=debt
                                                ))

                    slip.total_income, slip.total_deduction, slip.net_pay = total_ing, total_desc, total_ing - total_desc
                    payslips_to_update.append(slip)

                except Exception as e:
                    print(f"\n{'=' * 60}\n🔥 ERROR EMPLEADO: {slip.employee_id}\nMensaje: {str(e)}\n{'=' * 60}\n")
                    traceback.print_exc()
                    raise e

            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update,
                                        ['total_income', 'total_deduction', 'net_pay', 'effective_worked_days'])
            PendingDebt.objects.bulk_create(pending_debts_buffer)

            # Usamos los métodos auxiliares modulares
            self._assign_budget_lines_to_items(created_payslips, assignment_map)
            warnings = self._generate_accounting_journal(created_payslips)

            return {"success": True, "warnings": warnings}

    def generate_for_selected(self, employees_with_days):
        payslip_buffer = []
        eligible_pairs = []

        candidate_ids = [emp.id for emp, _ in employees_with_days if
                         emp.is_active and getattr(emp, 'person', None) and emp.person.is_active]
        valid_history_emp_ids = set(
            BudgetAssignmentHistory.objects.filter(employee_id__in=candidate_ids, start_date__lte=self.period.end_date)
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)).values_list('employee_id',
                                                                                                    flat=True))

        for emp, days in employees_with_days:
            if emp.id not in valid_history_emp_ids: continue
            eligible_pairs.append((emp, days))
            payslip_buffer.append(Payslip(employee=emp, period=self.period, worked_days=days))

        with transaction.atomic():
            selected_emp_ids = [emp.id for emp, _ in eligible_pairs]
            PendingDebt.objects.filter(period=self.period, employee_id__in=selected_emp_ids).delete()
            Payslip.objects.filter(period=self.period, employee_id__in=selected_emp_ids).delete()

            created_payslips = Payslip.objects.bulk_create(payslip_buffer)
            emp_ids = [p.employee.id for p in created_payslips]

            holiday_dates, prev_effective_days_map, absent_dates_map = self._prepare_mass_data(emp_ids)

            items_buffer, payslips_to_update, pending_debts_buffer = [], [], []

            active_incomes = list(Income.objects.filter(is_active=True))
            active_deductions = list(Deduction.objects.filter(is_active=True))
            ded_map = {d.code.strip().upper(): d for d in active_deductions if d.code}
            contrib_map = {c.code.strip().upper(): c for c in InstitutionalContribution.objects.filter(is_active=True)
                           if c.code}

            assignments_qs = BudgetAssignmentHistory.objects.filter(employee_id__in=emp_ids,
                                                                    start_date__lte=self.period.end_date) \
                .filter(Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)).select_related(
                'budget_line', 'budget_line__activity__project__subprogram__program')

            assignment_map = {}
            for a in assignments_qs: assignment_map.setdefault(a.employee_id, []).append(a)

            mp_map = {mp.employee_id: mp for mp in
                      ManagementPeriod.objects.filter(employee_id__in=emp_ids).select_related(
                          'contract_type__labor_regime').order_by('employee_id', '-start_date')}

            novelties_map = {}
            for nov in PayrollNovelty.objects.filter(period=self.period, employee_id__in=emp_ids).select_related(
                    'income_ref', 'deduction_ref'):
                if nov.employee_id not in novelties_map: novelties_map[nov.employee_id] = {'incomes': [],
                                                                                           'deductions': []}
                if nov.income_ref: novelties_map[nov.employee_id]['incomes'].append(nov)
                if nov.deduction_ref: novelties_map[nov.employee_id]['deductions'].append(nov)

            for slip in created_payslips:
                try:
                    emp_assignments = assignment_map.get(slip.employee_id, [])
                    tramos = []

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

                        total_dias_mes = 0
                        for data in processed_assignments:
                            s_date = max(data['start'], self.period.start_date)
                            e_date = min(data['end'], self.period.end_date) if data['end'] else self.period.end_date
                            if s_date <= e_date:
                                dias_reales = (e_date - s_date).days + 1
                                if dias_reales == 31: dias_reales = 30
                                if self.period.end_date.month == 2 and e_date == self.period.end_date: dias_reales += (
                                        30 - self.period.end_date.day)
                                if total_dias_mes + dias_reales > 30: dias_reales = 30 - total_dias_mes
                                if dias_reales > 0:
                                    tramos.append({
                                        'assignment': data['assignment'], 'dias': dias_reales,
                                        'sueldo_base': Decimal(str(data['assignment'].budget_line.remuneration or 0)),
                                        'partida': data['assignment'].budget_line, 'real_start': s_date,
                                        'real_end': e_date
                                    })
                                    total_dias_mes += dias_reales

                    if not tramos: continue

                    effective_days = 0
                    emp_absences = absent_dates_map.get(slip.employee_id, set())
                    for tramo in tramos:
                        curr_date = tramo['real_start']
                        while curr_date <= tramo['real_end']:
                            if curr_date.weekday() < 5 and curr_date not in holiday_dates and curr_date not in emp_absences:
                                effective_days += 1
                            curr_date += timedelta(days=1)

                    slip.effective_worked_days = effective_days
                    tramos.sort(key=lambda x: x['assignment'].start_date)
                    salary = sum((t['sueldo_base'] / Decimal('30.0')) * Decimal(str(t['dias'])) for t in tramos)

                    total_ing, total_desc, taxable_base = Decimal('0.0'), Decimal('0.0'), Decimal('0.0')
                    mensualiza_decimos, mensualiza_fr, num_hijos_validos = False, False, 0

                    try:
                        payroll_info = getattr(getattr(getattr(slip.employee, 'person', None), 'economic_data', None),
                                               'payroll_info', None)
                        if payroll_info:
                            mensualiza_decimos, mensualiza_fr = bool(payroll_info.monthly_payment), bool(
                                payroll_info.reserve_funds)
                            num_hijos_validos = payroll_info.family_dependents + payroll_info.education_dependents
                    except Exception:
                        pass

                    effective_days_prev = prev_effective_days_map.get(slip.employee_id, 0)
                    mp = mp_map.get(slip.employee_id)
                    anios_servicio = (
                            (self.period.end_date - mp.start_date).days / 365.25) if mp and mp.start_date else 0
                    regime_code = mp.contract_type.labor_regime.code.strip().upper() if mp and mp.contract_type and mp.contract_type.labor_regime else ''

                    for inc in active_incomes:
                        val, code_clean = Decimal('0.0'), inc.code.strip().upper() if inc.code else ''
                        if code_clean == 'REMUNERACION':
                            for tramo in tramos:
                                val_tramo = (tramo['sueldo_base'] / Decimal('30.0')) * Decimal(str(tramo['dias']))
                                if val_tramo > 0:
                                    it = PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val_tramo)
                                    it._historical_bl = tramo['partida']
                                    items_buffer.append(it)
                                    total_ing += val_tramo
                                    taxable_base += val_tramo
                            continue
                        elif code_clean == 'DECIMO_TERCERO' and mensualiza_decimos and self.period.working_days:
                            val = (salary / Decimal('12.0')) * (
                                    Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))
                        elif code_clean == 'DECIMO_CUARTO' and mensualiza_decimos and self.period.working_days:
                            val = (Decimal(str(self.config.get('SBU', '460.00'))) / Decimal('12.0')) * (
                                    Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))
                        elif code_clean == 'FONDOS_RESERVA' and anios_servicio > 1 and mensualiza_fr:
                            val = (salary * (
                                    Decimal(str(self.config.get('FONDOS_RESERVA', '8.33'))) / Decimal('100.0'))) * (
                                          Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))
                        elif code_clean == 'ALIMENTACION' and regime_code == 'CT' and anios_servicio >= 1:
                            val = Decimal(str(self.config.get('ALIMENTACION_DIARIA', '4.00'))) * Decimal(
                                str(effective_days_prev))
                        elif code_clean == 'TRANSPORTE' and regime_code == 'CT' and anios_servicio >= 1:
                            val = Decimal(str(self.config.get('TRANSPORTE_DIARIO', '0.50'))) * Decimal(
                                str(effective_days_prev))
                        elif code_clean == 'SUBSIDIO_FAMILIAR' and regime_code == 'CT' and anios_servicio >= 1 and num_hijos_validos > 0:
                            val = Decimal(str(self.config.get('SBU', '460.00'))) * (
                                    Decimal('1.00') / Decimal('100.0')) * Decimal(str(num_hijos_validos))
                        elif code_clean == 'ANTIGUEDAD' and regime_code == 'CT' and anios_servicio >= 1:
                            val = salary * (Decimal('0.25') / Decimal('100.0')) * Decimal(str(int(anios_servicio)))

                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val))
                            total_ing += val
                            if code_clean == 'REMUNERACION': taxable_base += val

                    # IESS y Aportes Patronales
                    target_iess_code = 'IESS_PER_EMP' if regime_code == 'LOSEP' else 'IESS_PER_TRA' if regime_code == 'CT' else 'IESS_PER'
                    target_patronal_code = 'APORTE_PATRONAL_EMP' if regime_code == 'LOSEP' else 'APORTE_PATRONAL_TRA' if regime_code == 'CT' else 'APORTE_PATRONAL'

                    iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')
                    if iess_ded:
                        val = taxable_base * (Decimal(
                            str(self.config.get(target_iess_code, self.config.get('IESS_PER', '9.45')))) / Decimal(
                            '100.0'))
                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION', value=val))
                            total_desc += val

                            contrib_ref = contrib_map.get(target_patronal_code) or contrib_map.get('APORTE_PATRONAL')
                            if contrib_ref:
                                val_patronal = taxable_base * (Decimal(str(self.config.get(target_patronal_code,
                                                                                           self.config.get(
                                                                                               'APORTE_PATRONAL',
                                                                                               '11.15')))) / Decimal(
                                    '100.0'))
                                if val_patronal > 0:
                                    items_buffer.append(PayslipItem(payslip=slip, contribution_ref=contrib_ref,
                                                                    item_type='CONTRIBUTION', value=val_patronal))

                                    emp_novelties = novelties_map.get(slip.employee_id,
                                                                      {'incomes': [], 'deductions': []})
                                    for nov in emp_novelties['incomes']:
                                        if nov.value > 0:
                                            val_nov = Decimal(str(nov.value))

                                            # ==================================================
                                            # MAGIA: CÁLCULO DE HORAS EXTRAS (De Horas a Dinero)
                                            # ==================================================
                                            code_up = (nov.income_ref.code or '').strip().upper()

                                            if 'HORAS_EXTRAS' in code_up or 'HORA_EXTRA' in code_up:
                                                # El valor del Excel son Horas. Multiplicamos por 2 (100% recargo)
                                                sueldo_hora = salary / Decimal('240.0')
                                                val_nov = sueldo_hora * Decimal('2.0') * val_nov

                                            elif 'SUPLEMENTARIAS' in code_up or 'SUPLEMENTARIA' in code_up:
                                                # El valor del Excel son Horas. Multiplicamos por 1.5 (50% recargo)
                                                sueldo_hora = salary / Decimal('240.0')
                                                val_nov = sueldo_hora * Decimal('1.5') * val_nov

                                            items_buffer.append(
                                                PayslipItem(payslip=slip, income_ref=nov.income_ref, item_type='INCOME',
                                                            value=val_nov))
                                            total_ing += val_nov

                                    # Pocket Logic (Descuentos)
                                    available_balance = total_ing - total_desc
                                    deduction_novelties = sorted(emp_novelties['deductions'],
                                                                 key=lambda x: getattr(x.deduction_ref, 'priority',
                                                                                       100))
                                    for nov in deduction_novelties:
                                        if nov.value > 0:
                                            val_original = Decimal(str(nov.value))
                                            real_discount = Decimal('0.0') if available_balance <= Decimal(
                                                '0.0') else min(val_original, available_balance)
                                            debt = val_original - real_discount

                                            if real_discount > 0:
                                                items_buffer.append(
                                                    PayslipItem(payslip=slip, deduction_ref=nov.deduction_ref,
                                                                item_type='DEDUCTION', value=real_discount))
                                                total_desc += real_discount
                                                available_balance -= real_discount

                                            if debt > 0:
                                                pending_debts_buffer.append(PendingDebt(
                                                    employee=slip.employee, period=self.period,
                                                    deduction_ref=nov.deduction_ref,
                                                    original_value=val_original, collected_value=real_discount,
                                                    pending_balance=debt
                                                ))

                    slip.total_income, slip.total_deduction, slip.net_pay = total_ing, total_desc, total_ing - total_desc
                    payslips_to_update.append(slip)

                except Exception as e:
                    print(f"\n{'=' * 60}\n🔥 ERROR EMPLEADO: {slip.employee_id}\nMensaje: {str(e)}\n{'=' * 60}\n")
                    traceback.print_exc()
                    raise e

            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update,
                                        ['total_income', 'total_deduction', 'net_pay', 'effective_worked_days'])
            PendingDebt.objects.bulk_create(pending_debts_buffer)

            # Usamos los métodos auxiliares modulares
            self._assign_budget_lines_to_items(created_payslips, assignment_map)
            warnings = self._generate_accounting_journal(created_payslips)

            return {"success": True, "warnings": warnings}

    def _assign_budget_lines_to_items(self, created_payslips, assignment_map):
        try:
            created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related('payslip__employee',
                                                                                                    'income_ref',
                                                                                                    'deduction_ref',
                                                                                                    'contribution_ref')
        except Exception:
            created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related('payslip__employee',
                                                                                                    'income_ref',
                                                                                                    'deduction_ref')

        items_to_update = []
        for it in created_items:
            if getattr(it, 'budget_line_code', None): continue
            mapping = None
            try:
                if it.item_type == 'INCOME' and getattr(it.income_ref, 'budget_mapping', None):
                    mapping = it.income_ref.budget_mapping
                elif it.item_type == 'DEDUCTION' and getattr(it.deduction_ref, 'budget_mapping', None):
                    mapping = it.deduction_ref.budget_mapping
                elif it.item_type == 'CONTRIBUTION' and getattr(it, 'contribution_ref', None) and getattr(
                        it.contribution_ref, 'budget_mapping', None):
                    mapping = it.contribution_ref.budget_mapping
            except Exception:
                pass

            base_bl = it._historical_bl if hasattr(it, '_historical_bl') else (
                assignment_map.get(it.payslip.employee_id,
                                   sorted(assignment_map.get(it.payslip.employee_id, []), key=lambda x: x.start_date))[
                    -1].budget_line if assignment_map.get(it.payslip.employee_id) else None)

            if mapping and getattr(mapping, 'dynamic_suffix', None) and base_bl:
                if getattr(mapping, 'is_fixed', False):
                    new_code = mapping.dynamic_suffix
                else:
                    base_parts, suffix_parts = base_bl.code.split('.'), mapping.dynamic_suffix.split('.')
                    new_code = f"{'.'.join(base_parts[:-len(suffix_parts)])}.{mapping.dynamic_suffix}" if len(
                        base_parts) > len(suffix_parts) else mapping.dynamic_suffix
                it.budget_line, it.budget_line_code = base_bl, new_code
                items_to_update.append(it)
                continue

            if base_bl:
                it.budget_line, it.budget_line_code = base_bl, base_bl.code
                items_to_update.append(it)

        if items_to_update: PayslipItem.objects.bulk_update(items_to_update, ['budget_line', 'budget_line_code'])

    def _generate_accounting_journal(self, created_payslips):
        aggregation, warnings = {}, []
        try:
            items_qs = PayslipItem.objects.filter(payslip__in=created_payslips).select_related('income_ref',
                                                                                               'deduction_ref',
                                                                                               'contribution_ref')
        except Exception:
            items_qs = PayslipItem.objects.filter(payslip__in=created_payslips).select_related('income_ref',
                                                                                               'deduction_ref')
        total_net_pay = sum(Decimal(str(slip.net_pay)) for slip in created_payslips)

        for it in items_qs:
            val, budget_code = Decimal(str(it.value)), getattr(it, 'budget_line_code', None)
            if it.item_type == 'INCOME' and it.income_ref:
                if it.income_ref.debit_account: aggregation[
                    (it.income_ref.debit_account.id, budget_code, 'debit')] = aggregation.get(
                    (it.income_ref.debit_account.id, budget_code, 'debit'), Decimal('0.0')) + val
                if it.income_ref.credit_account: aggregation[
                    (it.income_ref.credit_account.id, budget_code, 'credit')] = aggregation.get(
                    (it.income_ref.credit_account.id, budget_code, 'credit'), Decimal('0.0')) + val
            elif it.item_type == 'DEDUCTION' and it.deduction_ref:
                if it.deduction_ref.debit_account: aggregation[
                    (it.deduction_ref.debit_account.id, None, 'debit')] = aggregation.get(
                    (it.deduction_ref.debit_account.id, None, 'debit'), Decimal('0.0')) + val
                if it.deduction_ref.credit_account: aggregation[
                    (it.deduction_ref.credit_account.id, None, 'credit')] = aggregation.get(
                    (it.deduction_ref.credit_account.id, None, 'credit'), Decimal('0.0')) + val
            elif it.item_type == 'CONTRIBUTION' and getattr(it, 'contribution_ref', None):
                if it.contribution_ref.debit_account: aggregation[
                    (it.contribution_ref.debit_account.id, None, 'debit')] = aggregation.get(
                    (it.contribution_ref.debit_account.id, None, 'debit'), Decimal('0.0')) + val
                if it.contribution_ref.credit_account: aggregation[
                    (it.contribution_ref.credit_account.id, None, 'credit')] = aggregation.get(
                    (it.contribution_ref.credit_account.id, None, 'credit'), Decimal('0.0')) + val
                if 'PATRONAL' in getattr(it.contribution_ref, 'code', '').upper():
                    try:
                        cta_gp_id = Account.objects.get(code='2.1.3.51').id
                        aggregation[(cta_gp_id, None, 'debit')] = aggregation.get((cta_gp_id, None, 'debit'),
                                                                                  Decimal('0.0')) + val
                        aggregation[(cta_gp_id, None, 'credit')] = aggregation.get((cta_gp_id, None, 'credit'),
                                                                                   Decimal('0.0')) + val
                    except Exception:
                        pass

        if aggregation or total_net_pay > 0:
            desc_asiento = f"Nómina {self.period.month} {self.period.year}"
            Journal.objects.filter(description=desc_asiento).delete()
            journal = Journal.objects.create(date=self.period.end_date, description=desc_asiento)
            total_debits, total_credits = Decimal('0.0'), Decimal('0.0')

            for (acc_id, b_code, mov_type), val in aggregation.items():
                if val <= 0: continue
                try:
                    acc = Account.objects.get(id=acc_id)
                    if mov_type == 'debit':
                        JournalItem.objects.create(journal=journal, account=acc, debit=val, credit=Decimal('0.0'))
                        total_debits += val
                    else:
                        JournalItem.objects.create(journal=journal, account=acc, debit=Decimal('0.0'), credit=val)
                        total_credits += val
                except Account.DoesNotExist:
                    pass

            if total_net_pay > 0:
                try:
                    cta_gastos_personal, cta_banco = Account.objects.get(code='2.1.3.51'), Account.objects.get(
                        code='1.1.1.03.01')
                    JournalItem.objects.create(journal=journal, account=cta_gastos_personal, debit=total_net_pay,
                                               credit=Decimal('0.0'))
                    JournalItem.objects.create(journal=journal, account=cta_banco, debit=Decimal('0.0'),
                                               credit=total_net_pay)
                    total_debits += total_net_pay
                    total_credits += total_net_pay
                except Account.DoesNotExist:
                    warnings.append("Faltan cuentas 2.1.3.51 y 1.1.1.03.01 para el Líquido a Pagar.")

            if total_debits != total_credits:
                diff = total_debits - total_credits
                balancing_account = Account.objects.filter(code__icontains='PAYROLL').first()
                if balancing_account:
                    if diff > 0:
                        JournalItem.objects.create(journal=journal, account=balancing_account, debit=Decimal('0.0'),
                                                   credit=diff)
                    else:
                        JournalItem.objects.create(journal=journal, account=balancing_account, debit=abs(diff),
                                                   credit=Decimal('0.0'))

        return warnings

def calculate_effective_days(employee, start_date, end_date):
    """
    Calcula los días reales trabajados excluyendo fines de semana,
    feriados, vacaciones y licencias sin sueldo/por enfermedad.
    """
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
    """
    Reconstruye el Asiento Contable de un periodo sumando todos sus roles actuales.
    Se llama automáticamente cuando se edita un rol manualmente.
    """
    from decimal import Decimal
    from accounting.models import Journal, JournalItem, Account
    from .models import Payslip, PayslipItem, PayrollPeriod

    period = PayrollPeriod.objects.get(id=period_id)
    payslips = Payslip.objects.filter(period=period)

    if not payslips.exists():
        return False

    with transaction.atomic():
        desc_asiento = f"Nómina {period.month} {period.year}"
        Journal.objects.filter(description=desc_asiento).delete()

        created_items = PayslipItem.objects.filter(payslip__period=period).select_related(
            'payslip__employee', 'income_ref', 'deduction_ref', 'contribution_ref'
        )

        aggregation = {}
        total_net_pay = sum(Decimal(str(slip.net_pay)) for slip in payslips)

        for it in created_items:
            val = Decimal(str(it.value))
            budget_code = getattr(it, 'budget_line_code', None)

            if it.item_type == 'INCOME' and it.income_ref:
                if it.income_ref.debit_account:
                    key_debit = (it.income_ref.debit_account.id, budget_code, 'debit')
                    aggregation.setdefault(key_debit, Decimal('0.0'))
                    aggregation[key_debit] += val
                if it.income_ref.credit_account:
                    key_credit = (it.income_ref.credit_account.id, budget_code, 'credit')
                    aggregation.setdefault(key_credit, Decimal('0.0'))
                    aggregation[key_credit] += val

            elif it.item_type == 'DEDUCTION' and it.deduction_ref:
                if it.deduction_ref.debit_account:
                    key_debit = (it.deduction_ref.debit_account.id, None, 'debit')
                    aggregation.setdefault(key_debit, Decimal('0.0'))
                    aggregation[key_debit] += val
                if it.deduction_ref.credit_account:
                    key_credit = (it.deduction_ref.credit_account.id, None, 'credit')
                    aggregation.setdefault(key_credit, Decimal('0.0'))
                    aggregation[key_credit] += val

            elif it.item_type == 'CONTRIBUTION' and getattr(it, 'contribution_ref', None):
                if it.contribution_ref.debit_account:
                    key_debit = (it.contribution_ref.debit_account.id, None, 'debit')
                    aggregation.setdefault(key_debit, Decimal('0.0'))
                    aggregation[key_debit] += val
                if it.contribution_ref.credit_account:
                    key_credit = (it.contribution_ref.credit_account.id, None, 'credit')
                    aggregation.setdefault(key_credit, Decimal('0.0'))
                    aggregation[key_credit] += val

                if 'PATRONAL' in getattr(it.contribution_ref.code, '').upper():
                    try:
                        cta_gastos_personal = Account.objects.get(code='2.1.3.51')
                        key_debit_puente = (cta_gastos_personal.id, None, 'debit')
                        aggregation.setdefault(key_debit_puente, Decimal('0.0'))
                        aggregation[key_debit_puente] += val
                        key_credit_puente = (cta_gastos_personal.id, None, 'credit')
                        aggregation.setdefault(key_credit_puente, Decimal('0.0'))
                        aggregation[key_credit_puente] += val
                    except Exception:
                        pass

        if aggregation or total_net_pay > 0:
            journal = Journal.objects.create(date=period.end_date, description=desc_asiento)
            total_debits = Decimal('0.0')
            total_credits = Decimal('0.0')

            for key, val in aggregation.items():
                if val <= 0: continue
                acc_id, b_code, mov_type = key
                try:
                    acc = Account.objects.get(id=acc_id)
                    if mov_type == 'debit':
                        JournalItem.objects.create(journal=journal, account=acc, debit=val, credit=Decimal('0.0'))
                        total_debits += val
                    else:
                        JournalItem.objects.create(journal=journal, account=acc, debit=Decimal('0.0'), credit=val)
                        total_credits += val
                except Account.DoesNotExist:
                    pass

            if total_net_pay > 0:
                try:
                    cta_gastos_personal = Account.objects.get(code='2.1.3.51')
                    cta_banco = Account.objects.get(code='1.1.1.03.01')
                    JournalItem.objects.create(journal=journal, account=cta_gastos_personal, debit=total_net_pay,
                                               credit=Decimal('0.0'))
                    total_debits += total_net_pay
                    JournalItem.objects.create(journal=journal, account=cta_banco, debit=Decimal('0.0'),
                                               credit=total_net_pay)
                    total_credits += total_net_pay
                except Account.DoesNotExist:
                    pass

            if total_debits != total_credits:
                diff = (total_debits - total_credits)
                balancing_account = Account.objects.filter(code__icontains='PAYROLL').first()
                if balancing_account:
                    if diff > 0:
                        JournalItem.objects.create(journal=journal, account=balancing_account, debit=Decimal('0.0'),
                                                   credit=diff)
                    else:
                        JournalItem.objects.create(journal=journal, account=balancing_account, debit=abs(diff),
                                                   credit=Decimal('0.0'))

    return True
