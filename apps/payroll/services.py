import traceback
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from accounting.models import Journal, JournalItem, Account
from budget.models import BudgetAssignmentHistory
from contract.models import ManagementPeriod
from schedule.models import ScheduleObservation
from .models import Payslip, PayslipItem, PayrollConstant, Income, Deduction, InstitutionalContribution, PendingDebt, \
    PayrollPeriod


class PayrollCalculatorService:
    def __init__(self, period, employees):
        self.period = period
        self.employees = employees

        # CARGA OPTIMIZADA DE CONSTANTES (Solo 1 consulta a BD)
        constants = PayrollConstant.objects.all().values('code', 'value')
        self.config = {c['code']: c['value'] for c in constants}

        # Validar constantes críticas
        if 'SBU' not in self.config:
            raise ValueError("Falta configurar la constante 'SBU' (Salario Básico Unificado).")

    def generate_bulk(self):
        """
        Generación masiva optimizada con Logs y Casteo estricto a Decimal.
        """
        payslip_buffer = []
        eligible_employees = []

        candidate_ids = [emp.id for emp in self.employees if
                         emp.is_active and getattr(emp, 'person', None) and emp.person.is_active]
        valid_history_emp_ids = set(
            BudgetAssignmentHistory.objects.filter(
                employee_id__in=candidate_ids,
                start_date__lte=self.period.end_date
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)
            ).values_list('employee_id', flat=True)
        )
        holidays_qs = ScheduleObservation.objects.filter(
            is_holiday=True,
            is_active=True,
            start_date__lte=self.period.end_date,
            end_date__gte=self.period.start_date
        )
        holiday_dates = set()
        for h in holidays_qs:
            # Aseguramos que el feriado no se salga de los límites del mes actual
            curr = max(h.start_date, self.period.start_date)
            end_limit = min(h.end_date, self.period.end_date)
            while curr <= end_limit:
                holiday_dates.add(curr)
                curr += timedelta(days=1)

        for emp in self.employees:
            if emp.id not in valid_history_emp_ids:
                continue

            eligible_employees.append(emp)
            payslip_buffer.append(Payslip(
                employee=emp,
                period=self.period,
                worked_days=self.period.working_days
            ))

        with transaction.atomic():
            # 1. Limpieza previa del periodo (Roles y Deudas Pendientes)
            PendingDebt.objects.filter(period=self.period).delete()
            Payslip.objects.filter(period=self.period).delete()

            # BULK INSERT
            created_payslips = Payslip.objects.bulk_create(payslip_buffer)

            items_buffer = []
            payslips_to_update = []
            pending_debts_buffer = []

            active_incomes = list(Income.objects.filter(is_active=True))
            active_deductions = list(Deduction.objects.filter(is_active=True))
            ded_map = {d.code.strip().upper(): d for d in active_deductions if d.code}

            emp_ids = [p.employee.id for p in created_payslips]

            assignments_qs = BudgetAssignmentHistory.objects.filter(
                employee_id__in=emp_ids,
                start_date__lte=self.period.end_date
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)
            ).select_related('budget_line', 'budget_line__activity__project__subprogram__program')

            assignment_map = {}
            for a in assignments_qs:
                assignment_map.setdefault(a.employee_id, []).append(a)

            mp_qs = ManagementPeriod.objects.filter(employee_id__in=emp_ids).select_related(
                'contract_type__labor_regime').order_by('employee_id', '-start_date')
            mp_map = {}
            for mp in mp_qs:
                if mp.employee_id not in mp_map:
                    mp_map[mp.employee_id] = mp

            from .models import PayrollNovelty
            novelties_qs = PayrollNovelty.objects.filter(period=self.period, employee_id__in=emp_ids).select_related(
                'income_ref', 'deduction_ref')
            novelties_map = {}
            for nov in novelties_qs:
                if nov.employee_id not in novelties_map:
                    novelties_map[nov.employee_id] = {'incomes': [], 'deductions': []}
                if nov.income_ref:
                    novelties_map[nov.employee_id]['incomes'].append(nov)
                if nov.deduction_ref:
                    novelties_map[nov.employee_id]['deductions'].append(nov)
            # ====================================================
            # EXTRAER DÍAS EFECTIVOS DEL MES ANTERIOR (Optimizado)
            # ====================================================
            prev_period = PayrollPeriod.objects.filter(
                end_date__lt=self.period.start_date
            ).order_by('-end_date').first()

            prev_effective_days_map = {}
            if prev_period:
                # Traemos solo 2 columnas de los empleados que aplican
                prev_payslips = Payslip.objects.filter(
                    period=prev_period,
                    employee_id__in=emp_ids
                ).values_list('employee_id', 'effective_worked_days')

                for eid, eff_days in prev_payslips:
                    prev_effective_days_map[eid] = eff_days

            # ====================================================
            # 3. CÁLCULO INDIVIDUAL CON MANEJO DE ERRORES (LOGS)
            # ====================================================
            for slip in created_payslips:
                try:
                    emp_assignments = assignment_map.get(slip.employee_id, [])
                    tramos = []

                    # 1. Modifica la creación del tramo para guardar las fechas reales
                    if emp_assignments:
                        # 1. Ordenar por fecha de inicio para evaluar cronológicamente
                        emp_assignments.sort(key=lambda x: x.start_date)

                        # 2. Corregir solapamientos al vuelo (El candado a prueba de balas)
                        processed_assignments = []
                        for i in range(len(emp_assignments)):
                            current_asi = emp_assignments[i]
                            effective_end = current_asi.end_date

                            # Si hay una partida siguiente, la actual muere un día antes de que empiece la nueva
                            if i + 1 < len(emp_assignments):
                                next_start = emp_assignments[i + 1].start_date
                                # Si no tiene fin, o su fin invade la nueva, la cortamos
                                if not effective_end or effective_end >= next_start:
                                    effective_end = next_start - timedelta(days=1)

                            processed_assignments.append({
                                'assignment': current_asi,
                                'start': current_asi.start_date,
                                'end': effective_end
                            })

                        # 3. Crear los tramos asegurando que NUNCA pasen de 30 días
                        total_dias_mes = 0

                        for data in processed_assignments:
                            s_date = max(data['start'], self.period.start_date)
                            e_date = min(data['end'], self.period.end_date) if data['end'] else self.period.end_date

                            if s_date <= e_date:
                                dias_reales = (e_date - s_date).days + 1

                                # Ajuste comercial (mes de 30 días)
                                if dias_reales == 31: dias_reales = 30
                                if self.period.end_date.month == 2 and e_date == self.period.end_date:
                                    dias_reales += (30 - self.period.end_date.day)

                                # Limitador extra: Si la suma acumulada pasa de 30, truncamos el excedente
                                if total_dias_mes + dias_reales > 30:
                                    dias_reales = 30 - total_dias_mes

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
                    # =================================================================
                    # CALCULATE EFFECTIVE WORKED DAYS (Filtro de Feriados y Fin de Semana)
                    # =================================================================
                    effective_days = 0
                    for tramo in tramos:
                        curr_date = tramo['real_start']
                        while curr_date <= tramo['real_end']:
                            # Lunes=0, Martes=1 ... Viernes=4. Ignoramos 5(Sábado) y 6(Domingo)
                            if curr_date.weekday() < 5:
                                # Verificamos si ese día NO es un feriado institucional
                                if curr_date not in holiday_dates:
                                    # TODO: Aquí inyectaremos el módulo de Vacaciones en el futuro
                                    # if curr_date not in employee_vacations:

                                    effective_days += 1

                            curr_date += timedelta(days=1)

                    # Guardamos el valor matemáticamente perfecto en el rol temporal
                    slip.effective_worked_days = effective_days

                    tramos.sort(key=lambda x: x['assignment'].start_date)
                    partida_principal = tramos[-1]['partida']

                    salary = sum((t['sueldo_base'] / Decimal('30.0')) * Decimal(str(t['dias'])) for t in tramos)

                    total_ing = Decimal('0.0')
                    total_desc = Decimal('0.0')
                    taxable_base = Decimal('0.0')

                    mensualiza_decimos = False
                    mensualiza_fr = False

                    try:
                        person = getattr(slip.employee, 'person', None)
                        if person:
                            economic_data = getattr(person, 'economic_data', None)
                            if economic_data:
                                payroll_info = getattr(economic_data, 'payroll_info', None)
                                if payroll_info:
                                    mensualiza_decimos = bool(payroll_info.monthly_payment)
                                    mensualiza_fr = bool(payroll_info.reserve_funds)
                    except Exception:
                        pass
                    effective_days_prev = prev_effective_days_map.get(slip.employee_id, 0)
                    mp = mp_map.get(slip.employee_id)
                    anios_servicio = 0

                    if mp and mp.start_date:
                        dias_servicio = (self.period.end_date - mp.start_date).days
                        anios_servicio = dias_servicio / 365.25

                    regime_code = ''
                    if mp and mp.contract_type and mp.contract_type.labor_regime and mp.contract_type.labor_regime.code:
                        regime_code = mp.contract_type.labor_regime.code.strip().upper()

                    for inc in active_incomes:
                        val = Decimal('0.0')
                        code_clean = inc.code.strip().upper() if inc.code else ''

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

                        elif code_clean == 'DECIMO_TERCERO':
                            if mensualiza_decimos and self.period.working_days:
                                val = (salary / Decimal('12.0')) * (
                                        Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))

                        elif code_clean == 'DECIMO_CUARTO':
                            if mensualiza_decimos and self.period.working_days:
                                sbu = Decimal(str(self.config.get('SBU', '460.00')))
                                val = (sbu / Decimal('12.0')) * (
                                        Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))

                        elif code_clean == 'FONDOS_RESERVA':
                            if anios_servicio > 1 and mensualiza_fr:
                                pct_fr = Decimal(str(self.config.get('FONDOS_RESERVA', '8.33')))
                                val_total = salary * (pct_fr / Decimal('100.0'))
                                val = val_total * (
                                        Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))


                        elif code_clean == 'ALIMENTACION':
                            if regime_code == 'CT':
                                # Configuramos la constante ALIMENTACION_DIARIA a 4.00 en la Base de Datos
                                daily_food = Decimal(str(self.config.get('ALIMENTACION_DIARIA', '4.00')))
                                val = daily_food * Decimal(str(effective_days_prev))

                        elif code_clean == 'TRANSPORTE':
                            if regime_code == 'CT':
                                # Multiplica los $0.50 por los días reales del rol anterior
                                daily_transport = Decimal(str(self.config.get('TRANSPORTE_DIARIO', '0.50')))
                                val = daily_transport * Decimal(str(effective_days_prev))
                        elif code_clean == 'ANTIGUEDAD':
                            if regime_code == 'CT' and anios_servicio >= 1:
                                # Tomamos solo la parte entera de los años (años completos)
                                anios_completos = int(anios_servicio)

                                # 0.25% de su propio Sueldo Base
                                pct_antiguedad = Decimal('0.25') / Decimal('100.0')

                                # Nota: 'salary' ya contiene su remuneración mensual unificada en el código
                                val = salary * pct_antiguedad * Decimal(str(anios_completos))

                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val))
                            total_ing += val
                            if code_clean == 'REMUNERACION':
                                taxable_base += val

                    if regime_code == 'LOSEP':
                        target_iess_code = 'IESS_PER_EMP'
                        target_patronal_code = 'APORTE_PATRONAL_EMP'
                    elif regime_code == 'CT':
                        target_iess_code = 'IESS_PER_TRA'
                        target_patronal_code = 'APORTE_PATRONAL_TRA'
                    else:
                        target_iess_code = 'IESS_PER'
                        target_patronal_code = 'APORTE_PATRONAL'

                    iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')
                    if iess_ded:
                        iess_pct = Decimal(str(self.config.get(target_iess_code, self.config.get('IESS_PER', '9.45'))))
                        val = taxable_base * (iess_pct / Decimal('100.0'))
                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION', value=val))
                            total_desc += val

                            contrib_ref = InstitutionalContribution.objects.filter(code=target_patronal_code).first()
                            if not contrib_ref:
                                contrib_ref = InstitutionalContribution.objects.filter(code='APORTE_PATRONAL').first()

                            if contrib_ref:
                                patronal_pct = Decimal(str(self.config.get(target_patronal_code,
                                                                           self.config.get('APORTE_PATRONAL',
                                                                                           '11.15'))))
                                val_patronal = taxable_base * (patronal_pct / Decimal('100.0'))
                                if val_patronal > 0:
                                    items_buffer.append(PayslipItem(payslip=slip, contribution_ref=contrib_ref,
                                                                    item_type='CONTRIBUTION', value=val_patronal))

                                    emp_novelties = novelties_map.get(slip.employee_id,
                                                                      {'incomes': [], 'deductions': []})

                                    for nov in emp_novelties['incomes']:
                                        if nov.value > 0:
                                            val_nov = Decimal(str(nov.value))
                                            items_buffer.append(
                                                PayslipItem(payslip=slip, income_ref=nov.income_ref, item_type='INCOME',
                                                            value=val_nov))
                                            total_ing += val_nov

                                            # ====================================================
                                            # B. POCKET LOGIC (Prelación de Descuentos)
                                            # ====================================================
                                            # 1. Calculamos la plata real que le queda en el bolsillo después del IESS
                                            available_balance = total_ing - total_desc

                                            # 2. Ordenamos los descuentos por prioridad (1 primero, 100 después)
                                            deduction_novelties = emp_novelties['deductions']
                                            deduction_novelties.sort(
                                                key=lambda x: getattr(x.deduction_ref, 'priority', 100))

                                            for nov in deduction_novelties:
                                                if nov.value > 0:
                                                    val_original = Decimal(str(nov.value))

                                                    # Si el bolsillo ya está en $0.00, el descuento a cobrar es 0
                                                    if available_balance <= Decimal('0.0'):
                                                        real_discount = Decimal('0.0')
                                                    else:
                                                        # Se cobra máximo hasta vaciar el bolsillo
                                                        real_discount = min(val_original, available_balance)

                                                    # Lo que no se pudo cobrar es la deuda
                                                    debt = val_original - real_discount

                                                    if real_discount > 0:
                                                        items_buffer.append(PayslipItem(
                                                            payslip=slip,
                                                            deduction_ref=nov.deduction_ref,
                                                            item_type='DEDUCTION',
                                                            value=real_discount
                                                        ))
                                                        total_desc += real_discount
                                                        available_balance -= real_discount  # El bolsillo se vacía

                                                    # Si quedó debiendo, lo mandamos a la tabla de Cuentas por Cobrar
                                                    if debt > 0:
                                                        pending_debts_buffer.append(PendingDebt(
                                                            employee=slip.employee,
                                                            period=self.period,
                                                            deduction_ref=nov.deduction_ref,
                                                            original_value=val_original,
                                                            collected_value=real_discount,
                                                            pending_balance=debt
                                                        ))

                    slip.total_income = total_ing
                    slip.total_deduction = total_desc
                    slip.net_pay = total_ing - total_desc
                    payslips_to_update.append(slip)

                except Exception as e:
                    print(f"\n{'=' * 60}")
                    print(f"🔥 FATAL ERROR EN EMPLEADO ID: {slip.employee_id}")
                    print(f"Tipo de error: {type(e).__name__}")
                    print(f"Mensaje: {str(e)}")
                    traceback.print_exc()
                    print(f"{'=' * 60}\n")
                    raise e

            # 7. Guardado Masivo
            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update,
                                        ['total_income', 'total_deduction', 'net_pay', 'effective_worked_days'])
            PendingDebt.objects.bulk_create(pending_debts_buffer)

            try:
                created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                    'payslip__employee', 'income_ref', 'deduction_ref', 'contribution_ref'
                )
            except Exception:
                created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                    'payslip__employee', 'income_ref', 'deduction_ref'
                )

            items_to_update = []
            for it in created_items:
                if getattr(it, 'budget_line_code', None):
                    continue

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

                if hasattr(it, '_historical_bl'):
                    base_bl = it._historical_bl
                else:
                    emp_assignments = assignment_map.get(it.payslip.employee_id, [])
                    if emp_assignments:
                        emp_assignments.sort(key=lambda x: x.start_date)
                        base_bl = emp_assignments[-1].budget_line
                    else:
                        base_bl = None

                if mapping and getattr(mapping, 'dynamic_suffix', None) and base_bl:
                    if getattr(mapping, 'is_fixed', False):
                        new_code = mapping.dynamic_suffix
                    else:
                        base_parts = base_bl.code.split('.')
                        suffix_parts = mapping.dynamic_suffix.split('.')
                        num_parts_to_replace = len(suffix_parts)

                        if len(base_parts) > num_parts_to_replace:
                            prefix = ".".join(base_parts[:-num_parts_to_replace])
                            new_code = f"{prefix}.{mapping.dynamic_suffix}"
                        else:
                            new_code = mapping.dynamic_suffix

                    it.budget_line = base_bl
                    it.budget_line_code = new_code
                    items_to_update.append(it)
                    continue

                if base_bl:
                    it.budget_line = base_bl
                    it.budget_line_code = base_bl.code
                    items_to_update.append(it)

            if items_to_update:
                PayslipItem.objects.bulk_update(items_to_update, ['budget_line', 'budget_line_code'])

            # =====================================================================
            # 9. AGREGACIÓN CONTABLE Y PRESUPUESTARIA
            # =====================================================================
            aggregation = {}
            budget_aggregation = {}
            warnings = []

            total_net_pay = sum(Decimal(str(slip.net_pay)) for slip in created_payslips)

            for it in created_items:
                val = Decimal(str(it.value))
                budget_code = getattr(it, 'budget_line_code', None)

                if budget_code:
                    nombre_rubro = getattr(it.income_ref, 'name',
                                           getattr(it.deduction_ref, 'name', getattr(it.contribution_ref, 'name', '')))
                    key_budget = (budget_code, nombre_rubro)
                    budget_aggregation.setdefault(key_budget, Decimal('0.0'))
                    budget_aggregation[key_budget] += val

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

                    if 'PATRONAL' in it.contribution_ref.code.upper():
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
                desc_asiento = f"Nómina {self.period.month} {self.period.year}"
                Journal.objects.filter(description=desc_asiento).delete()

                journal = Journal.objects.create(
                    date=self.period.end_date,
                    description=desc_asiento
                )

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

                        JournalItem.objects.create(journal=journal, account=cta_gastos_personal,
                                                   debit=total_net_pay, credit=Decimal('0.0'))
                        total_debits += total_net_pay

                        JournalItem.objects.create(journal=journal, account=cta_banco, debit=Decimal('0.0'),
                                                   credit=total_net_pay)
                        total_credits += total_net_pay
                    except Account.DoesNotExist:
                        warnings.append(
                            "Crea las cuentas 2.1.3.51 y 1.1.1.03.01 en Contabilidad para registrar el Líquido a Pagar.")

                if total_debits != total_credits:
                    diff = (total_debits - total_credits)
                    balancing_account = Account.objects.filter(code__icontains='PAYROLL').first()
                    if balancing_account:
                        if diff > 0:
                            JournalItem.objects.create(journal=journal, account=balancing_account,
                                                       debit=Decimal('0.0'), credit=diff)
                        else:
                            JournalItem.objects.create(journal=journal, account=balancing_account,
                                                       debit=abs(diff), credit=Decimal('0.0'))

            return {"success": True, "warnings": warnings}

    def generate_for_selected(self, employees_with_days):
        payslip_buffer = []
        eligible_pairs = []

        candidate_ids = [emp.id for emp, _ in employees_with_days if
                         emp.is_active and getattr(emp, 'person', None) and emp.person.is_active]
        valid_history_emp_ids = set(
            BudgetAssignmentHistory.objects.filter(
                employee_id__in=candidate_ids,
                start_date__lte=self.period.end_date
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)
            ).values_list('employee_id', flat=True)
        )
        holidays_qs = ScheduleObservation.objects.filter(
            is_holiday=True,
            is_active=True,
            start_date__lte=self.period.end_date,
            end_date__gte=self.period.start_date
        )
        holiday_dates = set()
        for h in holidays_qs:
            # Aseguramos que el feriado no se salga de los límites del mes actual
            curr = max(h.start_date, self.period.start_date)
            end_limit = min(h.end_date, self.period.end_date)
            while curr <= end_limit:
                holiday_dates.add(curr)
                curr += timedelta(days=1)

        for emp, days in employees_with_days:
            # Si no tiene historial en este mes, se ignora
            if emp.id not in valid_history_emp_ids:
                continue

            eligible_pairs.append((emp, days))
            payslip_buffer.append(Payslip(employee=emp, period=self.period, worked_days=days))

        with transaction.atomic():
            selected_emp_ids = [emp.id for emp, _ in eligible_pairs]
            PendingDebt.objects.filter(period=self.period, employee_id__in=selected_emp_ids).delete()
            Payslip.objects.filter(period=self.period, employee_id__in=selected_emp_ids).delete()

            created_payslips = Payslip.objects.bulk_create(payslip_buffer)

            items_buffer = []
            payslips_to_update = []
            pending_debts_buffer = []

            active_incomes = list(Income.objects.filter(is_active=True))
            active_deductions = list(Deduction.objects.filter(is_active=True))
            ded_map = {d.code.strip().upper(): d for d in active_deductions if d.code}

            emp_ids = [p.employee.id for p in created_payslips]

            assignments_qs = BudgetAssignmentHistory.objects.filter(
                employee_id__in=emp_ids,
                start_date__lte=self.period.end_date
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=self.period.start_date)
            ).select_related('budget_line', 'budget_line__activity__project__subprogram__program')

            assignment_map = {}
            for a in assignments_qs:
                assignment_map.setdefault(a.employee_id, []).append(a)

            mp_qs = ManagementPeriod.objects.filter(employee_id__in=emp_ids).select_related(
                'contract_type__labor_regime').order_by('employee_id', '-start_date')
            mp_map = {}
            for mp in mp_qs:
                if mp.employee_id not in mp_map:
                    mp_map[mp.employee_id] = mp

            from .models import PayrollNovelty
            novelties_qs = PayrollNovelty.objects.filter(period=self.period,
                                                         employee_id__in=emp_ids).select_related('income_ref',
                                                                                                 'deduction_ref')
            novelties_map = {}
            for nov in novelties_qs:
                if nov.employee_id not in novelties_map:
                    novelties_map[nov.employee_id] = {'incomes': [], 'deductions': []}
                if nov.income_ref:
                    novelties_map[nov.employee_id]['incomes'].append(nov)
                if nov.deduction_ref:
                    novelties_map[nov.employee_id]['deductions'].append(nov)

            for slip in created_payslips:
                try:
                    emp_assignments = assignment_map.get(slip.employee_id, [])

                    tramos = []
                    if emp_assignments:
                        # 1. Ordenar por fecha de inicio para evaluar cronológicamente
                        emp_assignments.sort(key=lambda x: x.start_date)

                        # 2. Corregir solapamientos al vuelo (El candado a prueba de balas)
                        processed_assignments = []
                        for i in range(len(emp_assignments)):
                            current_asi = emp_assignments[i]
                            effective_end = current_asi.end_date

                            # Si hay una partida siguiente, la actual muere un día antes de que empiece la nueva
                            if i + 1 < len(emp_assignments):
                                next_start = emp_assignments[i + 1].start_date
                                # Si no tiene fin, o su fin invade la nueva, la cortamos
                                if not effective_end or effective_end >= next_start:
                                    effective_end = next_start - timedelta(days=1)

                            processed_assignments.append({
                                'assignment': current_asi,
                                'start': current_asi.start_date,
                                'end': effective_end
                            })

                        # 3. Crear los tramos asegurando que NUNCA pasen de 30 días
                        total_dias_mes = 0

                        for data in processed_assignments:
                            s_date = max(data['start'], self.period.start_date)
                            e_date = min(data['end'], self.period.end_date) if data['end'] else self.period.end_date

                            if s_date <= e_date:
                                dias_reales = (e_date - s_date).days + 1

                                # Ajuste comercial (mes de 30 días)
                                if dias_reales == 31: dias_reales = 30
                                if self.period.end_date.month == 2 and e_date == self.period.end_date:
                                    dias_reales += (30 - self.period.end_date.day)

                                # Limitador extra: Si la suma acumulada pasa de 30, truncamos el excedente
                                if total_dias_mes + dias_reales > 30:
                                    dias_reales = 30 - total_dias_mes

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
                    # =================================================================
                    # Filtro de Feriados y Fin de Semana
                    # =================================================================
                    effective_days = 0
                    for tramo in tramos:
                        curr_date = tramo['real_start']
                        while curr_date <= tramo['real_end']:
                            if curr_date.weekday() < 5:
                                if curr_date not in holiday_dates:
                                    effective_days += 1
                            curr_date += timedelta(days=1)

                    # Guardamos el valor matemáticamente perfecto en el rol temporal
                    slip.effective_worked_days = effective_days

                    tramos.sort(key=lambda x: x['assignment'].start_date)
                    partida_principal = tramos[-1]['partida']

                    salary = sum((t['sueldo_base'] / Decimal('30.0')) * Decimal(str(t['dias'])) for t in tramos)

                    total_ing = Decimal('0.0')
                    total_desc = Decimal('0.0')
                    taxable_base = Decimal('0.0')

                    mensualiza_decimos = False
                    mensualiza_fr = False

                    try:
                        person = getattr(slip.employee, 'person', None)
                        if person:
                            economic_data = getattr(person, 'economic_data', None)
                            if economic_data:
                                payroll_info = getattr(economic_data, 'payroll_info', None)
                                if payroll_info:
                                    mensualiza_decimos = bool(payroll_info.monthly_payment)
                                    mensualiza_fr = bool(payroll_info.reserve_funds)
                    except Exception:
                        pass

                    mp = mp_map.get(slip.employee_id)
                    anios_servicio = 0

                    if mp and mp.start_date:
                        dias_servicio = (self.period.end_date - mp.start_date).days
                        anios_servicio = dias_servicio / 365.25

                    regime_code = mp.contract_type.labor_regime.code if (
                            mp and mp.contract_type and mp.contract_type.labor_regime) else None

                    for inc in active_incomes:
                        val = Decimal('0.0')
                        code_clean = inc.code.strip().upper() if inc.code else ''

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

                        elif code_clean == 'DECIMO_TERCERO':
                            if mensualiza_decimos and self.period.working_days:
                                val = (salary / Decimal('12.0')) * (
                                        Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))

                        elif code_clean == 'DECIMO_CUARTO':
                            if mensualiza_decimos and self.period.working_days:
                                sbu = Decimal(str(self.config.get('SBU', '460.00')))
                                val = (sbu / Decimal('12.0')) * (
                                        Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))

                        elif code_clean == 'FONDOS_RESERVA':
                            if anios_servicio > 1 and mensualiza_fr:
                                pct_fr = Decimal(str(self.config.get('FONDOS_RESERVA', '8.33')))
                                val_total = salary * (pct_fr / Decimal('100.0'))
                                val = val_total * (
                                        Decimal(str(slip.worked_days)) / Decimal(str(self.period.working_days)))

                        elif code_clean == 'ALIMENTACION':
                            if regime_code == 'CT':
                                daily_food_allowance = Decimal(str(self.config.get('ALIMENTACION_DIARIA', '4.00')))
                                val = daily_food_allowance * Decimal(str(slip.effective_worked_days))

                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val))
                            total_ing += val
                            if code_clean == 'REMUNERACION':
                                taxable_base += val

                    if regime_code == 'LOSEP':
                        target_iess_code = 'IESS_PER_EMP'
                        target_patronal_code = 'APORTE_PATRONAL_EMP'
                    elif regime_code == 'CT':
                        target_iess_code = 'IESS_PER_TRA'
                        target_patronal_code = 'APORTE_PATRONAL_TRA'
                    else:
                        target_iess_code = 'IESS_PER'
                        target_patronal_code = 'APORTE_PATRONAL'

                    iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')
                    if iess_ded:
                        iess_pct = Decimal(str(self.config.get(target_iess_code, self.config.get('IESS_PER', '9.45'))))
                        val = taxable_base * (iess_pct / Decimal('100.0'))
                        if val > 0:
                            items_buffer.append(
                                PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION', value=val))
                            total_desc += val

                            contrib_ref = InstitutionalContribution.objects.filter(code=target_patronal_code).first()
                            if not contrib_ref:
                                contrib_ref = InstitutionalContribution.objects.filter(code='APORTE_PATRONAL').first()

                            if contrib_ref:
                                patronal_pct = Decimal(str(self.config.get(target_patronal_code,
                                                                           self.config.get('APORTE_PATRONAL',
                                                                                           '11.15'))))
                                val_patronal = taxable_base * (patronal_pct / Decimal('100.0'))
                                if val_patronal > 0:
                                    items_buffer.append(PayslipItem(payslip=slip, contribution_ref=contrib_ref,
                                                                    item_type='CONTRIBUTION', value=val_patronal))

                                    emp_novelties = novelties_map.get(slip.employee_id,
                                                                      {'incomes': [], 'deductions': []})

                                    for nov in emp_novelties['incomes']:
                                        if nov.value > 0:
                                            val_nov = Decimal(str(nov.value))
                                            items_buffer.append(
                                                PayslipItem(payslip=slip, income_ref=nov.income_ref, item_type='INCOME',
                                                            value=val_nov))
                                            total_ing += val_nov

                                            # ====================================================
                                            # B. POCKET LOGIC (Prelación de Descuentos)
                                            # ====================================================
                                            # 1. Calculamos la plata real que le queda en el bolsillo después del IESS
                                            available_balance = total_ing - total_desc

                                            # 2. Ordenamos los descuentos por prioridad (1 primero, 100 después)
                                            deduction_novelties = emp_novelties['deductions']
                                            deduction_novelties.sort(
                                                key=lambda x: getattr(x.deduction_ref, 'priority', 100))

                                            for nov in deduction_novelties:
                                                if nov.value > 0:
                                                    val_original = Decimal(str(nov.value))

                                                    # Si el bolsillo ya está en $0.00, el descuento a cobrar es 0
                                                    if available_balance <= Decimal('0.0'):
                                                        real_discount = Decimal('0.0')
                                                    else:
                                                        # Se cobra máximo hasta vaciar el bolsillo
                                                        real_discount = min(val_original, available_balance)

                                                    # Lo que no se pudo cobrar es la deuda
                                                    debt = val_original - real_discount

                                                    if real_discount > 0:
                                                        items_buffer.append(PayslipItem(
                                                            payslip=slip,
                                                            deduction_ref=nov.deduction_ref,
                                                            item_type='DEDUCTION',
                                                            value=real_discount
                                                        ))
                                                        total_desc += real_discount
                                                        available_balance -= real_discount  # El bolsillo se vacía

                                                    # Si quedó debiendo, lo mandamos a la tabla de Cuentas por Cobrar
                                                    if debt > 0:
                                                        pending_debts_buffer.append(PendingDebt(
                                                            employee=slip.employee,
                                                            period=self.period,
                                                            deduction_ref=nov.deduction_ref,
                                                            original_value=val_original,
                                                            collected_value=real_discount,
                                                            pending_balance=debt
                                                        ))

                    slip.total_income = total_ing
                    slip.total_deduction = total_desc
                    slip.net_pay = total_ing - total_desc
                    payslips_to_update.append(slip)

                except Exception as e:
                    print(f"\n{'=' * 60}")
                    print(f"🔥 FATAL ERROR EN EMPLEADO ID: {slip.employee_id}")
                    print(f"Tipo de error: {type(e).__name__}")
                    print(f"Mensaje: {str(e)}")
                    traceback.print_exc()
                    print(f"{'=' * 60}\n")
                    raise e

            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update,
                                        ['total_income', 'total_deduction', 'net_pay', 'effective_worked_days'])

            try:
                created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                    'payslip__employee', 'income_ref', 'deduction_ref', 'contribution_ref'
                )
            except Exception:
                created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                    'payslip__employee', 'income_ref', 'deduction_ref'
                )

            items_to_update = []
            for it in created_items:
                if getattr(it, 'budget_line_code', None):
                    continue

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

                if hasattr(it, '_historical_bl'):
                    base_bl = it._historical_bl
                else:
                    emp_assignments = assignment_map.get(it.payslip.employee_id, [])
                    if emp_assignments:
                        emp_assignments.sort(key=lambda x: x.start_date)
                        base_bl = emp_assignments[-1].budget_line
                    else:
                        base_bl = None

                if mapping and getattr(mapping, 'dynamic_suffix', None) and base_bl:
                    if getattr(mapping, 'is_fixed', False):
                        new_code = mapping.dynamic_suffix
                    else:
                        base_parts = base_bl.code.split('.')
                        suffix_parts = mapping.dynamic_suffix.split('.')
                        num_parts_to_replace = len(suffix_parts)

                        if len(base_parts) > num_parts_to_replace:
                            prefix = ".".join(base_parts[:-num_parts_to_replace])
                            new_code = f"{prefix}.{mapping.dynamic_suffix}"
                        else:
                            new_code = mapping.dynamic_suffix

                    it.budget_line = base_bl
                    it.budget_line_code = new_code
                    items_to_update.append(it)
                    continue

                if base_bl:
                    it.budget_line = base_bl
                    it.budget_line_code = base_bl.code
                    items_to_update.append(it)

            if items_to_update:
                PayslipItem.objects.bulk_update(items_to_update, ['budget_line', 'budget_line_code'])

            aggregation = {}
            budget_aggregation = {}
            warnings = []

            total_net_pay = sum(Decimal(str(slip.net_pay)) for slip in created_payslips)

            for it in created_items:
                val = Decimal(str(it.value))
                budget_code = getattr(it, 'budget_line_code', None)

                if budget_code:
                    nombre_rubro = getattr(it.income_ref, 'name',
                                           getattr(it.deduction_ref, 'name', getattr(it.contribution_ref, 'name', '')))
                    key_budget = (budget_code, nombre_rubro)
                    budget_aggregation.setdefault(key_budget, Decimal('0.0'))
                    budget_aggregation[key_budget] += val

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

                    if 'PATRONAL' in it.contribution_ref.code.upper():
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
                desc_asiento = f"Nómina {self.period.month} {self.period.year}"
                Journal.objects.filter(description=desc_asiento).delete()

                journal = Journal.objects.create(
                    date=self.period.end_date,
                    description=desc_asiento
                )

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

                        JournalItem.objects.create(journal=journal, account=cta_gastos_personal,
                                                   debit=total_net_pay, credit=Decimal('0.0'))
                        total_debits += total_net_pay

                        JournalItem.objects.create(journal=journal, account=cta_banco, debit=Decimal('0.0'),
                                                   credit=total_net_pay)
                        total_credits += total_net_pay
                    except Account.DoesNotExist:
                        warnings.append(
                            "Crea las cuentas 2.1.3.51 y 1.1.1.03.01 en Contabilidad para registrar el Líquido a Pagar.")

                if total_debits != total_credits:
                    diff = (total_debits - total_credits)
                    balancing_account = Account.objects.filter(code__icontains='PAYROLL').first()
                    if balancing_account:
                        if diff > 0:
                            JournalItem.objects.create(journal=journal, account=balancing_account,
                                                       debit=Decimal('0.0'), credit=diff)
                        else:
                            JournalItem.objects.create(journal=journal, account=balancing_account,
                                                       debit=abs(diff), credit=Decimal('0.0'))

            return {"success": True, "warnings": warnings}


from datetime import timedelta


def calculate_effective_days(employee, start_date, end_date):
    """
    Calcula los días reales trabajados excluyendo fines de semana,
    feriados, vacaciones y licencias sin sueldo/por enfermedad.
    """
    effective_days = 0
    current_date = start_date

    # Recorremos el mes día por día
    while current_date <= end_date:
        # 1. Excluir Sábados (5) y Domingos (6)
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue

        # 2. Excluir Feriados (Aquí consultas a tu modelo de Feriados/Horarios)
        # if Feriado.objects.filter(fecha=current_date).exists():
        #     current_date += timedelta(days=1)
        #     continue

        # 3. Excluir Vacaciones y Licencias (Aquí consultas tus Acciones de Personal)
        # ausente = AccionPersonal.objects.filter(
        #     employee=employee,
        #     start_date__lte=current_date,
        #     end_date__gte=current_date,
        #     tipo__descuenta_alimentacion=True # Ej: Enfermedad, Vacación
        # ).exists()

        # if ausente:
        #     current_date += timedelta(days=1)
        #     continue

        # Si superó todos los filtros, es un día que efectivamente fue a trabajar
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
        # 1. Borramos el asiento contable anterior
        desc_asiento = f"Nómina {period.month} {period.year}"
        Journal.objects.filter(description=desc_asiento).delete()

        created_items = PayslipItem.objects.filter(payslip__period=period).select_related(
            'payslip__employee', 'income_ref', 'deduction_ref', 'contribution_ref'
        )

        aggregation = {}
        total_net_pay = sum(Decimal(str(slip.net_pay)) for slip in payslips)

        # 2. Reagrupamos todos los rubros en cuentas contables
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

        # 3. Creamos el nuevo asiento cuadradito
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

            # Cuadre por centavos
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
