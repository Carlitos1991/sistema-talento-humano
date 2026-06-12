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
from .models import (
    Payslip, PayslipItem, PayrollConstant, PendingDebt,
    PayrollPeriod, PayrollNovelty, PayrollRubric,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de selección de cuentas contables (sin estado, reutilizables)
# ---------------------------------------------------------------------------

def _resolve_accounts_for_rubric(rubric: PayrollRubric, spending_type: str) -> dict:
    """
    Devuelve las IDs de cuenta (debit / credit) correctas para un rubro dado el
    tipo de gasto del empleado, aplicando el fallback a la cuenta base (corriente)
    cuando la cuenta específica está vacía.

    Retorna:
        {'debit': <int|None>, 'credit': <int|None>}
    """
    if spending_type.startswith('7'):  # INVERSIÓN
        debit = rubric.debit_account_inv_id or rubric.debit_account_id
        credit = rubric.credit_account_inv_id or rubric.credit_account_id
    elif spending_type.startswith('6'):  # PRODUCCIÓN
        debit = rubric.debit_account_prod_id or rubric.debit_account_id
        credit = rubric.credit_account_prod_id or rubric.credit_account_id
    else:  # CORRIENTE (5.1) — es el fallback universal
        debit = rubric.debit_account_id
        credit = rubric.credit_account_id

    return {'debit': debit, 'credit': credit}


def _resolve_bridge_account_id(salary_rubric: PayrollRubric, spending_type: str) -> int | None:
    """
    Devuelve el ID de la CUENTA PUENTE (credit_account) del rubro de sueldo
    según el tipo de gasto, con fallback a la cuenta base.

    La cuenta puente es la "bisagra" del asiento: es el HABER en los ingresos
    y el DEBE en los descuentos y en la liquidación de bancos.
    """
    if spending_type.startswith('7'):
        return salary_rubric.credit_account_inv_id or salary_rubric.credit_account_id
    elif spending_type.startswith('6'):
        return salary_rubric.credit_account_prod_id or salary_rubric.credit_account_id
    else:
        return salary_rubric.credit_account_id


def _get_employee_spending_type(segments: list) -> str:
    """
    Extrae el código de tipo de gasto (ej. '5.1', '7.1', '6.1') del primer
    segmento presupuestario del empleado.  Fallback = '5.1'.
    """
    if not segments:
        return '5.1'
    bl = segments[0].get('budget_line')
    if bl and getattr(bl, 'spending_type_item', None):
        return bl.spending_type_item.code or '5.1'
    return '5.1'


def _filter_rubrics_by_context(rubrics: list, spending_type: str) -> list:
    """
    Devuelve solo los rubros cuyo spending_context es 'TODOS' o coincide
    exactamente con el tipo de gasto del empleado.

    Esto evita, por ejemplo, que el rubro RMU marcado como '5.1' se aplique
    a un empleado de inversión (7.1), lo que generaría un doble cómputo
    del sueldo base.
    """
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

    # ------------------------------------------------------------------
    # Métodos de soporte (sin cambios respecto al original)
    # ------------------------------------------------------------------

    def _prepare_mass_data(self, emp_ids):
        holidays_qs = ScheduleObservation.objects.filter(
            is_holiday=True, is_active=True,
            start_date__lte=self.period.end_date,
            end_date__gte=self.period.start_date,
        ).values_list('start_date', 'end_date')

        holiday_dates = set()
        for start_date, end_date in holidays_qs:
            curr = max(start_date, self.period.start_date)
            end_limit = min(end_date, self.period.end_date)
            while curr <= end_limit:
                holiday_dates.add(curr)
                curr += timedelta(days=1)

        prev_period = (
            PayrollPeriod.objects
            .filter(end_date__lt=self.period.start_date)
            .order_by('-end_date')
            .first()
        )
        prev_effective_days_map = {}
        if prev_period:
            prev_effective_days_map = dict(
                Payslip.objects
                .filter(period=prev_period, employee_id__in=emp_ids)
                .values_list('employee_id', 'effective_worked_days')
            )

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

        absent_dates_map = {}
        for permit in approved_permits:
            eid = permit['employee_id']
            absent_dates_map.setdefault(eid, set())
            p_start = max(permit['start_date'], self.period.start_date)
            p_end = min(
                permit['end_date'] or permit['start_date'],
                self.period.end_date,
            )
            if (
                    (permit.get('days') or 0) >= 1
                    or (permit.get('hours') or 0) >= 8
                    or p_start != p_end
            ):
                curr = p_start
                while curr <= p_end:
                    absent_dates_map[eid].add(curr)
                    curr += timedelta(days=1)

        return holiday_dates, prev_effective_days_map, absent_dates_map

    def _filter_eligible_employees(self, employees):
        candidate_ids = [
            emp.id for emp in employees
            if emp.is_active and getattr(emp, 'person', None) and emp.person.is_active
        ]

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

    # ------------------------------------------------------------------
    # Puntos de entrada públicos
    # ------------------------------------------------------------------

    def generate_bulk(self):
        eligible_employees = self._filter_eligible_employees(self.employees)
        payslip_buffer = [
            Payslip(employee=emp, period=self.period, worked_days=self.period.working_days)
            for emp in eligible_employees
        ]
        return self._execute_payroll_calculation(payslip_buffer, delete_entire_period=True)

    def generate_for_selected(self, employees_with_days):
        employees = [emp for emp, _ in employees_with_days]
        eligible_employees = self._filter_eligible_employees(employees)
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

    # ------------------------------------------------------------------
    # Motor de cálculo principal
    # ------------------------------------------------------------------

    def _execute_payroll_calculation(
            self,
            payslip_buffer,
            delete_entire_period=False,
            employee_ids_to_delete=None,
    ):
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
            # ── 1. Limpieza de datos previos ──────────────────────────────
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

            # ── 2. Crear roles vacíos ─────────────────────────────────────
            created_payslips = Payslip.objects.bulk_create(payslip_buffer)
            emp_ids = [p.employee.id for p in created_payslips]
            _lap("bulk_create payslips")

            # ── 3. Datos masivos (feriados, permisos, etc.) ───────────────
            holiday_dates, prev_effective_days_map, absent_dates_map = self._prepare_mass_data(emp_ids)
            _lap("prepare mass data")

            # ── 4. Cargar catálogo de rubros ACTIVOS (una sola vez) ───────
            #
            # Se cargan TODOS los rubros activos sin pre-filtrar por contexto.
            # El filtrado se realiza POR EMPLEADO dentro del bucle usando
            # _filter_rubrics_by_context(), porque cada empleado puede tener
            # un tipo de gasto distinto (5.1, 7.1, 6.1).
            #
            all_rubrics = list(PayrollRubric.objects.filter(is_active=True).order_by('order'))
            all_incomes = [r for r in all_rubrics if r.rubric_type == 'INCOME']
            all_deductions = [r for r in all_rubrics if r.rubric_type == 'DEDUCTION']
            all_contributions = [r for r in all_rubrics if r.rubric_type == 'CONTRIBUTION']

            # Índices de acceso rápido por código (sobre la lista completa)
            ded_map = {d.code.strip().upper(): d for d in all_deductions if d.code}
            contrib_map = {c.code.strip().upper(): c for c in all_contributions if c.code}

            # ── 5. Datos relacionales masivos ─────────────────────────────
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
                # Conservamos el último contrato para el régimen y estado activo
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

                # Acumulamos los días de servicio de todos los contratos históricos
                if mp.start_date <= self.period.end_date:
                    contract_start = mp.start_date
                    contract_end = min(mp.end_date, self.period.end_date) if mp.end_date else self.period.end_date
                    if contract_start <= contract_end:
                        days_count = (contract_end - contract_start).days + 1
                        service_days_map[mp.employee_id] = service_days_map.get(mp.employee_id, 0) + days_count

            # ── 6. Novedades del periodo ──────────────────────────────────
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

            # ── 7. Deudas pendientes de periodos anteriores ───────────────
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

            _lap("load mappings and novelties")

            # ── 8. Buffers de escritura diferida ──────────────────────────
            items_buffer = []
            payslips_to_update = []
            pending_debts_buffer = []
            debts_to_update = []
            warnings = []

            # ── 9. BUCLE PRINCIPAL POR EMPLEADO ───────────────────────────
            for slip in created_payslips:
                try:
                    # -- 9.1 Asignaciones presupuestarias del empleado ------
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

                    # -- 9.2 Segmentos de tiempo (por partida) --------------
                    segments = self._build_segments(emp_assignments)
                    if not segments:
                        continue

                    # -- 9.3 Tipo de gasto del empleado (UNA sola lectura) --
                    #
                    # FIX: La variable emp_spending_type se definía DOS veces
                    # (líneas 345 y 351 del original) y la primera asignación
                    # se descartaba silenciosamente.  Ahora se calcula una vez
                    # con el helper dedicado.
                    emp_spending_type = _get_employee_spending_type(segments)

                    # -- 9.4 Filtrar rubros aplicables a ESTE empleado ------
                    #
                    # FIX: El filtro solo se aplicaba a active_incomes en el
                    # original; active_deductions y active_contributions se
                    # usaban sin filtrar, lo que podía duplicar el sueldo base
                    # cuando coexistían rubros RMU para distintos contextos.
                    emp_incomes = _filter_rubrics_by_context(all_incomes, emp_spending_type)
                    emp_deductions = _filter_rubrics_by_context(all_deductions, emp_spending_type)
                    emp_contributions = _filter_rubrics_by_context(all_contributions, emp_spending_type)

                    # Reconstruir índices locales ya filtrados
                    emp_ded_map = {d.code.strip().upper(): d for d in emp_deductions if d.code}
                    emp_contrib_map = {c.code.strip().upper(): c for c in emp_contributions if c.code}

                    # -- 9.5 Días efectivos laborados -----------------------
                    effective_days = 0
                    emp_absences = absent_dates_map.get(slip.employee_id, set())
                    for segment in segments:
                        curr_date = segment['real_start']
                        while curr_date <= segment['real_end']:
                            if (
                                    curr_date.weekday() < 5
                                    and curr_date not in holiday_dates
                                    and curr_date not in emp_absences
                            ):
                                effective_days += 1
                            curr_date += timedelta(days=1)
                    slip.effective_worked_days = effective_days

                    # -- 9.6 Sueldo proporcional total (base para cálculos) -
                    salary = sum(
                        (seg['base_salary'] / Decimal('30.0')) * Decimal(str(seg['actual_days']))
                        for seg in segments
                    )

                    # -- 9.7 Datos laborales del empleado -------------------
                    total_income = Decimal('0.0')
                    total_deduction = Decimal('0.0')
                    taxable_base = Decimal('0.0')
                    monthly_bonuses = False
                    monthly_reserve_funds = True
                    valid_dependents_count = 0

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
                    except Exception:
                        pass

                    effective_days_prev = prev_effective_days_map.get(slip.employee_id, 0)
                    mp = mp_map.get(slip.employee_id)
                    total_days_service = service_days_map.get(slip.employee_id, 0)
                    years_of_service = total_days_service / 365.25
                    regime_code = (
                        mp.contract_type.labor_regime.code.strip().upper()
                        if mp and mp.contract_type and mp.contract_type.labor_regime
                        else ''
                    )

                    # -- 9.8 Preparar novedades de ingreso ------------------
                    emp_novelties = novelties_map.get(
                        slip.employee_id, {'incomes': [], 'deductions': []}
                    )
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

                    # ── 9.9 INGRESOS ────────────────────────────────────────
                    for inc in emp_incomes:
                        val = Decimal('0.0')
                        code_clean = inc.code.strip().upper() if inc.code else ''

                        if getattr(inc, 'is_salary', False):
                            # Sueldo base: un ítem por segmento presupuestario
                            for segment in segments:
                                segment_val = (
                                                      segment['base_salary'] / Decimal('30.0')
                                              ) * Decimal(str(segment['actual_days']))
                                if segment_val > 0:
                                    it = PayslipItem(
                                        payslip=slip,
                                        rubric=inc,
                                        item_type='INCOME',
                                        value=segment_val,
                                    )
                                    it._historical_bl = segment['budget_line']
                                    items_buffer.append(it)
                                    total_income += segment_val
                                    taxable_base += segment_val
                            continue  # No sigue al bloque "if val > 0" de abajo

                        elif code_clean == 'DECIMO_TERCERO' and monthly_bonuses and self.period.working_days:
                            thirteenth_base = salary + hours_income_total
                            val = (thirteenth_base / Decimal('12.0')) * (
                                    Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days))
                            )
                        elif code_clean == 'DECIMO_CUARTO' and monthly_bonuses and self.period.working_days:
                            val = (
                                          Decimal(str(self.config.get('SBU', '460.00'))) / Decimal('12.0')
                                  ) * (
                                          Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days))
                                  )
                        elif code_clean == 'FONDOS_RESERVA':
                            if not monthly_reserve_funds and years_of_service > 1:
                                val = (
                                              salary
                                              * (Decimal(str(self.config.get('FONDOS_RESERVA', '8.33'))) / Decimal(
                                          '100.0'))
                                      ) * (
                                              Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days))
                                      )

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

                    # ── 9.11 NOVEDADES DE INGRESO (horas extras, etc.) ──────
                    for nov, nov_val in prepared_income_novelties:
                        items_buffer.append(
                            PayslipItem(payslip=slip, rubric=nov.rubric, item_type='INCOME', value=nov_val)
                        )
                        total_income += nov_val

                    # ── 9.12 POCKET LOGIC (descuentos y deudas) ─────────────
                    available_balance = total_income - total_deduction
                    deduction_novelties = sorted(
                        emp_novelties['deductions'],
                        key=lambda x: getattr(x.rubric, 'priority', 100) or 100,
                    )
                    pending_debts_list = existing_pending_debts_map.get(slip.employee_id, [])

                    # Primero: cobrar deudas pendientes de periodos anteriores
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

                    # Luego: descuentos del periodo actual (con posible nueva deuda)
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

                    # ── 9.13 Totales del rol ─────────────────────────────────
                    slip.total_income = total_income
                    slip.total_deduction = total_deduction
                    slip.net_pay = total_income - total_deduction
                    payslips_to_update.append(slip)

                except Exception as e:
                    print(
                        f"\n{'=' * 60}\n"
                        f"🔥 ERROR EMPLEADO: {slip.employee_id}\n"
                        f"Mensaje: {str(e)}\n"
                        f"{'=' * 60}\n"
                    )
                    traceback.print_exc()
                    raise e

            _lap("calculate items loop")

            # ── 10. Persistencia masiva ────────────────────────────────────
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
            _lap("bulk persist items and debts")

            self._assign_budget_lines_to_items(created_payslips, assignment_map)
            _lap("assign budget lines")

            warnings = self._generate_accounting_journal(created_payslips)
            _lap("generate accounting journal")

            total_msg = (
                f"[PAYROLL][PERF] total payroll execution: "
                f"{(time.perf_counter() - t0):.3f}s"
            )
            logger.info(total_msg)
            print(total_msg)

            return {"success": True, "warnings": warnings}

    # ------------------------------------------------------------------
    # Helper interno: construcción de segmentos de tiempo
    # ------------------------------------------------------------------

    def _build_segments(self, emp_assignments: list) -> list:
        """
        A partir de las asignaciones presupuestarias del empleado construye los
        segmentos de tiempo dentro del periodo, calculando los días comerciales
        (base 30) de cada segmento.
        """
        if not emp_assignments:
            return []

        emp_assignments.sort(key=lambda x: x.start_date)
        processed = []
        for i, asi in enumerate(emp_assignments):
            effective_end = asi.end_date
            if i + 1 < len(emp_assignments):
                next_start = emp_assignments[i + 1].start_date
                if not effective_end or effective_end >= next_start:
                    effective_end = next_start - timedelta(days=1)
            processed.append({'assignment': asi, 'start': asi.start_date, 'end': effective_end})

        segments = []
        total_month_days = 0

        for data in processed:
            s_date = max(data['start'], self.period.start_date)
            e_date = (
                min(data['end'], self.period.end_date)
                if data['end'] else self.period.end_date
            )
            if s_date > e_date:
                continue

            # Cálculo en base comercial (30 días)
            if self.period.end_date.month == 2 and e_date == self.period.end_date:
                actual_days = (30 - s_date.day) + 1
            elif s_date.day == 31:
                actual_days = 1
            else:
                commercial_end_day = min(e_date.day, 30)
                actual_days = (commercial_end_day - s_date.day) + 1

            # Nunca superar 30 días en total
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
                    'real_end': e_date,
                })
                total_month_days += actual_days

        return segments

    # ------------------------------------------------------------------
    # Asignación de partidas presupuestarias (sin cambios)
    # ------------------------------------------------------------------

    def _assign_budget_lines_to_items(self, created_payslips, assignment_map):
        created_items = PayslipItem.objects.filter(
            payslip__in=created_payslips
        ).select_related('rubric')

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

    # ------------------------------------------------------------------
    # Generación del asiento contable
    # ------------------------------------------------------------------

    def _generate_accounting_journal(self, created_payslips) -> list:
        """
        Genera el asiento contable de la nómina.

        Estructura:
          INGRESOS   -> Debe: cta_gasto(rubro)   / Haber: cta_puente(sueldo)
          DESCUENTOS -> Debe: cta_puente(sueldo) / Haber: cta_pasivo(rubro)
          APORTES    -> Debe: cta_gasto(rubro)   / Haber: cta_pasivo(rubro)
          BANCOS     -> Debe: cta_puente(sueldo) / Haber: income_account(sueldo)

        Orden: respeta rubric.order; descuentos order+800, banco order 900.
        """
        # aggregation: {(acc_id, mov): [order_min, importe]}
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
            """Acumula importe conservando el order minimo para ordenar el asiento."""
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

        # -- PASO 1: Items individuales (ingresos, descuentos, aportes) ------
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
            sal_rubric = _find_salary_rubric(spending_type)
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

        # -- PASO 2: Liquidacion de bancos -----------------
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

            # Banco siempre al final del asiento (order 900)
            _add(c_puente_banco, 'debit', slip.net_pay, 900)
            _add(c_banco, 'credit', slip.net_pay, 900)

            # -- PASO 3: Persistir asiento ordenado por order_min ----------------
            desc_asiento = f"Nomina {self.period.month} {self.period.year}"
            Journal.objects.filter(description=desc_asiento).delete()
            journal = Journal.objects.create(
                date=self.period.end_date, description=desc_asiento
            )

            total_debits = Decimal('0.0')
            total_credits = Decimal('0.0')

            # Al ordenar por x[1][0], el asiento se guarda con una estética impecable:
            for (acc_id, mov_type), (_, val) in sorted(aggregation.items(), key=lambda x: x[1][0]):
                acc = _get_account(acc_id)
                if acc and val > 0:
                    # Blindaje: Forzamos redondeo a dos decimales por registro
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

            # --- SALVACAÍDAS DE CUADRE (Por diferencias infinitesimales de redondeo) ---
            if total_debits != total_credits:
                diff = total_debits - total_credits
                balancing_account = Account.objects.filter(
                    Q(code__icontains='PAYROLL') | Q(name__icontains='DIFERENCIAS')
                ).first()

                if balancing_account:
                    if diff > 0:
                        JournalItem.objects.create(journal=journal, account=balancing_account, debit=Decimal('0.0'),
                                                   credit=diff, reference=str(self.period))
                    else:
                        JournalItem.objects.create(journal=journal, account=balancing_account, debit=abs(diff),
                                                   credit=Decimal('0.0'), reference=str(self.period))
                else:
                    warnings.append(
                        f"AVISO: El asiento tuvo un descuadre por redondeo de ${abs(diff)}. Configure una cuenta de ajuste.")

            return warnings


# ---------------------------------------------------------------------------
# Utilidades independientes
# ---------------------------------------------------------------------------

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
