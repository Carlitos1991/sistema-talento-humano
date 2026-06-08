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
from .models import Payslip, PayslipItem, PayrollConstant, Income, Deduction, InstitutionalContribution, PendingDebt, \
    PayrollPeriod, PayrollNovelty, RubroBudgetMapping


logger = logging.getLogger(__name__)


class PayrollCalculatorService:
    def __init__(self, period, employees, is_scope_run=False):
        self.period = period
        self.employees = employees
        self.is_scope_run = is_scope_run

        # Determine the cutoff date based on the run type
        if self.is_scope_run:
            self.cutoff_date = self.period.end_date
        else:
            # Cutoff is the 25th of the period's month
            try:
                self.cutoff_date = self.period.start_date.replace(day=25)
            except ValueError:  # Handles months with less than 25 days, though unlikely
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

        tipos_descontables = Q(permit_type__name__icontains='Personal') | Q(permit_type__name__icontains='Médico') | Q(
            permit_type__name__icontains='Medico') | \
                             Q(permit_type__parent__name__icontains='Personal') | Q(
            permit_type__parent__name__icontains='Médico') | Q(permit_type__parent__name__icontains='Medico')

        approved_permits = PermitRequest.objects.filter(
            employee_id__in=emp_ids, status='APPROVED', start_date__lte=self.period.end_date
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)).filter(
            tipos_descontables
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
        """Filtra empleados activos con asignaciones presupuestarias válidas en el período."""
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
        """Núcleo compartido de cálculo de nómina para bulk y seleccionados."""
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

            active_incomes = list(Income.objects.filter(is_active=True))
            active_income_codes = {inc.code.strip().upper() for inc in active_incomes if inc.code}
            has_ct_base_income = 'SALARIOS_BASICOS' in active_income_codes
            active_deductions = list(Deduction.objects.filter(is_active=True))
            ded_map = {d.code.strip().upper(): d for d in active_deductions if d.code}
            contrib_map = {c.code.strip().upper(): c for c in InstitutionalContribution.objects.filter(is_active=True)
                           if c.code}

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
            for mp in ManagementPeriod.objects.filter(employee_id__in=emp_ids).select_related('contract_type__labor_regime',
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

            novelties_map = {}
            for nov in PayrollNovelty.objects.filter(period=self.period, employee_id__in=emp_ids).select_related(
                    'income_ref', 'deduction_ref'):
                if nov.employee_id not in novelties_map:
                    novelties_map[nov.employee_id] = {'incomes': [], 'deductions': []}
                if nov.income_ref:
                    novelties_map[nov.employee_id]['incomes'].append(nov)
                if nov.deduction_ref:
                    novelties_map[nov.employee_id]['deductions'].append(nov)

            existing_pending_debts_map = {}
            old_debts_qs = PendingDebt.objects.filter(
                employee_id__in=emp_ids,
                pending_balance__gt=0
            ).exclude(period=self.period).select_related('deduction_ref').order_by('employee_id', 'id')
            for debt in old_debts_qs:
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

                            # Create a shallow copy to avoid modifying the cached object
                            assignment_copy = copy.copy(a)

                            if assignment_copy.end_date and assignment_copy.end_date > self.cutoff_date:
                                assignment_copy.end_date = None

                            emp_assignments.append(assignment_copy)

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
                                # Lógica mejorada para Mes Comercial (30 días)
                                if self.period.end_date.month == 2 and e_date == self.period.end_date:
                                    # Si es febrero y es el último día del mes, estiramos a 30
                                    # Ej: Ingreso 28 de Feb -> (30 - 28) + 1 = 3 días a pagar
                                    dias_reales = (30 - s_date.day) + 1
                                elif s_date.day == 31:
                                    # Caso especial: Ingreso un día 31
                                    dias_reales = 1
                                else:
                                    # Regla general: (Día Fin - Día Inicio) + 1
                                    # Limitamos el día de fin a 30 para meses de 31 días
                                    dia_fin_comercial = min(e_date.day, 30)
                                    dias_reales = (dia_fin_comercial - s_date.day) + 1

                                # Asegurar que no exceda los 30 días ni sea negativo
                                if total_dias_mes + dias_reales > 30:
                                    dias_reales = 30 - total_dias_mes

                                dias_reales = max(0, dias_reales)

                                if dias_reales > 0:
                                    tramos.append({
                                        'assignment': data['assignment'],
                                        'dias': dias_reales,
                                        'sueldo_base': Decimal(str(data['assignment'].budget_line.remuneration or 0)),
                                        'partida': data['assignment'].budget_line,
                                        'real_start': s_date,
                                        'real_end': e_date
                                    })
                                    total_dias_mes += dias_reales

                    if not tramos:
                        continue

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
                    mensualiza_decimos, mensualiza_fr, num_hijos_validos = False, True, 0

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

                    emp_novelties = novelties_map.get(slip.employee_id, {'incomes': [], 'deductions': []})
                    prepared_income_novelties = []
                    hours_income_total = Decimal('0.00')
                    for nov in emp_novelties['incomes']:
                        if nov.value <= 0:
                            continue
                        val_nov = Decimal(str(nov.value))
                        code_up = (nov.income_ref.code or '').strip().upper()

                        if 'HORAS_EXTRAS' in code_up or 'HORA_EXTRA' in code_up:
                            sueldo_dia = (salary / Decimal('30.0')).quantize(Decimal('0.01'),
                                                                              rounding=ROUND_HALF_UP)
                            sueldo_hora = (sueldo_dia / Decimal('8.0')).quantize(Decimal('0.01'),
                                                                                  rounding=ROUND_HALF_UP)
                            val_nov = (sueldo_hora * Decimal('1.50') * val_nov).quantize(Decimal('0.01'),
                                                                                           rounding=ROUND_HALF_UP)
                            hours_income_total += val_nov
                        elif 'SUPLEMENTARIAS' in code_up or 'SUPLEMENTARIA' in code_up:
                            sueldo_dia = (salary / Decimal('30.0')).quantize(Decimal('0.01'),
                                                                              rounding=ROUND_HALF_UP)
                            sueldo_hora = (sueldo_dia / Decimal('8.0')).quantize(Decimal('0.01'),
                                                                                  rounding=ROUND_HALF_UP)
                            val_nov = (sueldo_hora * Decimal('2.00') * val_nov).quantize(Decimal('0.01'),
                                                                                           rounding=ROUND_HALF_UP)
                            hours_income_total += val_nov

                        prepared_income_novelties.append((nov, val_nov))

                    for inc in active_incomes:
                        val, code_clean = Decimal('0.0'), inc.code.strip().upper() if inc.code else ''
                        is_ct_base_income = (code_clean == 'SALARIOS_BASICOS') if has_ct_base_income else (
                                code_clean == 'REMUNERACION')
                        is_base_income = (regime_code == 'CT' and is_ct_base_income) or (
                                regime_code != 'CT' and code_clean == 'REMUNERACION')

                        if is_base_income:
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
                            base_decimo_tercero = salary + hours_income_total
                            val = (base_decimo_tercero / Decimal('12.0')) * (
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
                            if is_base_income:
                                taxable_base += val

                    # ====================================================
                    # 1. IESS y Aportes Patronales (CORRECTAMENTE ALINEADO)
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
                                PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION', value=val))
                            total_desc += val

                    contrib_ref = contrib_map.get(target_patronal_code) or contrib_map.get('APORTE_PATRONAL')
                    if contrib_ref:
                        val_patronal = taxable_base * (Decimal(str(self.config.get(target_patronal_code,
                                                                                   self.config.get('APORTE_PATRONAL',
                                                                                                   '11.15')))) / Decimal(
                            '100.0'))
                        if val_patronal > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, contribution_ref=contrib_ref, item_type='CONTRIBUTION',
                                            value=val_patronal))

                    # ====================================================
                    # 2. NOVEDADES (Ingresos Extra y Horas del Excel)
                    # ====================================================
                    for nov, val_nov in prepared_income_novelties:
                        items_buffer.append(
                            PayslipItem(payslip=slip, income_ref=nov.income_ref, item_type='INCOME', value=val_nov))
                        total_ing += val_nov

                    # ====================================================
                    # 3. POCKET LOGIC (Descuentos y Deudas Viejas)
                    # ====================================================
                    available_balance = total_ing - total_desc
                    deduction_novelties = sorted(emp_novelties['deductions'],
                                                 key=lambda x: getattr(x.deduction_ref, 'priority', 100) or 100)
                    deudas_pendientes = existing_pending_debts_map.get(slip.employee_id, [])

                    for deuda in deudas_pendientes:
                        val_deuda = Decimal(str(deuda.pending_balance))
                        real_discount = Decimal('0.0') if available_balance <= Decimal('0.0') else min(val_deuda,
                                                                                                       available_balance)
                        items_buffer.append(
                            PayslipItem(payslip=slip, deduction_ref=deuda.deduction_ref, item_type='DEDUCTION',
                                        value=real_discount))
                        if real_discount > 0:
                            total_desc += real_discount
                            available_balance -= real_discount
                            deuda.collected_value += real_discount
                            deuda.pending_balance -= real_discount
                            debts_to_update.append(deuda)

                    for nov in deduction_novelties:
                        if nov.value > 0:
                            val_original = Decimal(str(nov.value))
                            real_discount = Decimal('0.0') if available_balance <= Decimal('0.0') else min(
                                val_original,
                                available_balance)
                            debt = val_original - real_discount
                            items_buffer.append(
                                PayslipItem(payslip=slip, deduction_ref=nov.deduction_ref, item_type='DEDUCTION',
                                            value=real_discount))
                            if real_discount > 0:
                                total_desc += real_discount
                                available_balance -= real_discount
                            if debt > 0:
                                pending_debts_buffer.append(PendingDebt(
                                    employee=slip.employee, period=self.period, deduction_ref=nov.deduction_ref,
                                    original_value=val_original, collected_value=real_discount, pending_balance=debt
                                ))

                    slip.total_income, slip.total_deduction, slip.net_pay = total_ing, total_desc, total_ing - total_desc
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

    def _resolve_budget_line_for_item(self, payslip_item, latest_budget_line_by_employee, income_mapping_map,
                                      deduction_mapping_map, contribution_mapping_map):
        """Resuelve la partida presupuestaria final para un ítem, basada en asignación y mapeo."""
        if getattr(payslip_item, 'budget_line_code', None):
            return None  # Ya procesado

        mapping = None
        if payslip_item.item_type == 'INCOME' and payslip_item.income_ref_id:
            mapping = income_mapping_map.get(payslip_item.income_ref_id)
        elif payslip_item.item_type == 'DEDUCTION' and payslip_item.deduction_ref_id:
            mapping = deduction_mapping_map.get(payslip_item.deduction_ref_id)
        elif payslip_item.item_type == 'CONTRIBUTION' and payslip_item.contribution_ref_id:
            mapping = contribution_mapping_map.get(payslip_item.contribution_ref_id)

        base_bl = (payslip_item._historical_bl if hasattr(payslip_item, '_historical_bl')
                   else latest_budget_line_by_employee.get(payslip_item.payslip.employee_id))

        if mapping and getattr(mapping, 'dynamic_suffix', None) and base_bl:
            if getattr(mapping, 'is_fixed', False):
                new_code = mapping.dynamic_suffix
            else:
                base_parts = base_bl.code.split('.')
                suffix_parts = mapping.dynamic_suffix.split('.')
                new_code = (f"{'.'.join(base_parts[:-len(suffix_parts)])}.{mapping.dynamic_suffix}"
                            if len(base_parts) > len(suffix_parts) else mapping.dynamic_suffix)
            payslip_item.budget_line, payslip_item.budget_line_code = base_bl, new_code
            return payslip_item

        if base_bl:
            payslip_item.budget_line, payslip_item.budget_line_code = base_bl, base_bl.code
            return payslip_item

        return None

    def _assign_budget_lines_to_items(self, created_payslips, assignment_map):
        """Asigna partidas presupuestarias a ítems de nómina post-creación."""
        created_item_rows = list(
            PayslipItem.objects.filter(payslip__in=created_payslips).values(
                'id',
                'item_type',
                'payslip__employee_id',
                'income_ref_id',
                'deduction_ref_id',
                'contribution_ref_id',
                'budget_line_code',
            )
        )

        latest_budget_line_by_employee = {}
        for employee_id, assignments in assignment_map.items():
            if not assignments:
                continue
            latest_assignment = max(assignments, key=lambda x: x.start_date)
            bl = latest_assignment.budget_line
            if bl:
                latest_budget_line_by_employee[employee_id] = (bl.id, bl.code)

        income_ids = set()
        deduction_ids = set()
        contribution_ids = set()
        for row in created_item_rows:
            if row['item_type'] == 'INCOME' and row['income_ref_id']:
                income_ids.add(row['income_ref_id'])
            elif row['item_type'] == 'DEDUCTION' and row['deduction_ref_id']:
                deduction_ids.add(row['deduction_ref_id'])
            elif row['item_type'] == 'CONTRIBUTION' and row['contribution_ref_id']:
                contribution_ids.add(row['contribution_ref_id'])

        income_mapping_map = {
            m.income_id: (m.dynamic_suffix, m.is_fixed)
            for m in RubroBudgetMapping.objects.filter(income_id__in=income_ids)
            .only('income_id', 'dynamic_suffix', 'is_fixed')
        }
        deduction_mapping_map = {
            m.deduction_id: (m.dynamic_suffix, m.is_fixed)
            for m in RubroBudgetMapping.objects.filter(deduction_id__in=deduction_ids)
            .only('deduction_id', 'dynamic_suffix', 'is_fixed')
        }
        contribution_mapping_map = {
            m.contribution_id: (m.dynamic_suffix, m.is_fixed)
            for m in RubroBudgetMapping.objects.filter(contribution_id__in=contribution_ids)
            .only('contribution_id', 'dynamic_suffix', 'is_fixed')
        }

        updates = []
        for row in created_item_rows:
            if row['budget_line_code']:
                continue

            employee_id = row['payslip__employee_id']
            base_bl = latest_budget_line_by_employee.get(employee_id)
            if not base_bl:
                continue
            base_bl_id, base_bl_code = base_bl

            mapping = None
            if row['item_type'] == 'INCOME' and row['income_ref_id']:
                mapping = income_mapping_map.get(row['income_ref_id'])
            elif row['item_type'] == 'DEDUCTION' and row['deduction_ref_id']:
                mapping = deduction_mapping_map.get(row['deduction_ref_id'])
            elif row['item_type'] == 'CONTRIBUTION' and row['contribution_ref_id']:
                mapping = contribution_mapping_map.get(row['contribution_ref_id'])

            new_code = base_bl_code
            if mapping and mapping[0]:
                dynamic_suffix, is_fixed = mapping
                if is_fixed:
                    new_code = dynamic_suffix
                else:
                    base_parts = base_bl_code.split('.')
                    suffix_parts = dynamic_suffix.split('.')
                    if len(base_parts) > len(suffix_parts):
                        new_code = f"{'.'.join(base_parts[:-len(suffix_parts)])}.{dynamic_suffix}"
                    else:
                        new_code = dynamic_suffix

            updates.append(PayslipItem(id=row['id'], budget_line_id=base_bl_id, budget_line_code=new_code))

        if updates:
            PayslipItem.objects.bulk_update(updates, ['budget_line', 'budget_line_code'], batch_size=1000)

    def _generate_accounting_journal(self, created_payslips):
        """Genera asiento contable de nómina con caché de cuentas para evitar N+1 queries."""
        aggregation, warnings = {}, []
        try:
            items_qs = PayslipItem.objects.filter(payslip__in=created_payslips).select_related('income_ref',
                                                                                               'deduction_ref',
                                                                                               'contribution_ref')
        except Exception:
            items_qs = PayslipItem.objects.filter(payslip__in=created_payslips).select_related('income_ref',
                                                                                               'deduction_ref')
        total_net_pay = sum(Decimal(str(slip.net_pay)) for slip in created_payslips)

        # Caché de cuentas para evitar consultas repetidas
        account_cache = {}
        special_accounts = {}

        def get_account_cached(acc_id):
            if acc_id not in account_cache:
                try:
                    account_cache[acc_id] = Account.objects.get(id=acc_id)
                except Account.DoesNotExist:
                    account_cache[acc_id] = None
            return account_cache[acc_id]

        def get_special_account(code):
            if code not in special_accounts:
                try:
                    special_accounts[code] = Account.objects.get(code=code)
                except Account.DoesNotExist:
                    special_accounts[code] = None
            return special_accounts[code]

        for it in items_qs:
            val, budget_code = Decimal(str(it.value)), getattr(it, 'budget_line_code', None)
            if it.item_type == 'INCOME' and it.income_ref:
                if it.income_ref.debit_account_id:
                    aggregation[(it.income_ref.debit_account_id, budget_code, 'debit')] = aggregation.get(
                        (it.income_ref.debit_account_id, budget_code, 'debit'), Decimal('0.0')) + val
                if it.income_ref.credit_account_id:
                    aggregation[(it.income_ref.credit_account_id, budget_code, 'credit')] = aggregation.get(
                        (it.income_ref.credit_account_id, budget_code, 'credit'), Decimal('0.0')) + val
            elif it.item_type == 'DEDUCTION' and it.deduction_ref:
                if it.deduction_ref.debit_account_id:
                    aggregation[(it.deduction_ref.debit_account_id, None, 'debit')] = aggregation.get(
                        (it.deduction_ref.debit_account_id, None, 'debit'), Decimal('0.0')) + val
                if it.deduction_ref.credit_account_id:
                    aggregation[(it.deduction_ref.credit_account_id, None, 'credit')] = aggregation.get(
                        (it.deduction_ref.credit_account_id, None, 'credit'), Decimal('0.0')) + val
            elif it.item_type == 'CONTRIBUTION' and getattr(it, 'contribution_ref', None):
                if it.contribution_ref.debit_account_id:
                    aggregation[(it.contribution_ref.debit_account_id, None, 'debit')] = aggregation.get(
                        (it.contribution_ref.debit_account_id, None, 'debit'), Decimal('0.0')) + val
                if it.contribution_ref.credit_account_id:
                    aggregation[(it.contribution_ref.credit_account_id, None, 'credit')] = aggregation.get(
                        (it.contribution_ref.credit_account_id, None, 'credit'), Decimal('0.0')) + val
                if 'PATRONAL' in getattr(it.contribution_ref, 'code', '').upper():
                    cta_gp = get_special_account('2.1.3.51')
                    if cta_gp:
                        aggregation[(cta_gp.id, None, 'debit')] = aggregation.get((cta_gp.id, None, 'debit'),
                                                                                   Decimal('0.0')) + val
                        aggregation[(cta_gp.id, None, 'credit')] = aggregation.get((cta_gp.id, None, 'credit'),
                                                                                    Decimal('0.0')) + val

        if aggregation or total_net_pay > 0:
            desc_asiento = f"Nómina {self.period.month} {self.period.year}"
            Journal.objects.filter(description=desc_asiento).delete()
            journal = Journal.objects.create(date=self.period.end_date, description=desc_asiento)
            total_debits, total_credits = Decimal('0.0'), Decimal('0.0')

            for (acc_id, b_code, mov_type), val in aggregation.items():
                if val <= 0:
                    continue
                acc = get_account_cached(acc_id)
                if acc:
                    if mov_type == 'debit':
                        JournalItem.objects.create(journal=journal, account=acc, debit=val, credit=Decimal('0.0'))
                        total_debits += val
                    else:
                        JournalItem.objects.create(journal=journal, account=acc, debit=Decimal('0.0'), credit=val)
                        total_credits += val

            if total_net_pay > 0:
                cta_gastos_personal = get_special_account('2.1.3.51')
                cta_banco = get_special_account('1.1.1.03.01')
                if cta_gastos_personal:
                    JournalItem.objects.create(journal=journal, account=cta_gastos_personal, debit=total_net_pay,
                                               credit=Decimal('0.0'))
                    total_debits += total_net_pay
                if cta_banco:
                    JournalItem.objects.create(journal=journal, account=cta_banco, debit=Decimal('0.0'),
                                               credit=total_net_pay)
                    total_credits += total_net_pay

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
    from decimal import Decimal
    from accounting.models import Journal, JournalItem, Account
    from .models import Payslip, PayslipItem, PayrollPeriod
    period = PayrollPeriod.objects.get(id=period_id)
    payslips = Payslip.objects.filter(period=period)
    if not payslips.exists(): return False

    with transaction.atomic():
        desc_asiento = f"Nómina {period.month} {period.year}"
        Journal.objects.filter(description=desc_asiento).delete()
        created_items = PayslipItem.objects.filter(payslip__period=period).select_related('payslip__employee',
                                                                                          'income_ref', 'deduction_ref',
                                                                                          'contribution_ref')
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
