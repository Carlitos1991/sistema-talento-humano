from decimal import Decimal
from django.db import transaction
from .models import Payslip, PayslipItem, PayrollConstant, Income, Deduction, RubroBudgetMapping
from accounting.models import Journal, JournalItem, Account
from budget.models import BudgetLine
from contract.models import ManagementPeriod


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
        Generación masiva optimizada.
        Tiempo estimado para 4000 roles: < 2 segundos.
        """
        payslip_buffer = []
        eligible_employees = []

        candidate_ids = [emp.id for emp in self.employees]
        assigned_emp_ids = set(
            BudgetLine.objects.filter(current_employee_id__in=candidate_ids).values_list('current_employee_id',
                                                                                         flat=True)
        )

        for emp in self.employees:
            person = getattr(emp, 'person', None)
            if not emp.is_active or not (person and getattr(person, 'is_active', False)):
                continue
            if emp.id not in assigned_emp_ids:
                continue
            eligible_employees.append(emp)
            payslip_buffer.append(Payslip(
                employee=emp,
                period=self.period,
                worked_days=self.period.working_days
            ))

        with transaction.atomic():
            # Limpieza previa del periodo
            Payslip.objects.filter(period=self.period).delete()

            # BULK INSERT
            created_payslips = Payslip.objects.bulk_create(payslip_buffer)

            items_buffer = []
            payslips_to_update = []

            active_incomes = list(Income.objects.filter(is_active=True))
            active_deductions = list(Deduction.objects.filter(is_active=True))
            ded_map = {d.code: d for d in active_deductions}

            # 1. Pre-cargar Sueldos
            emp_ids = [emp.id for emp in eligible_employees]
            salary_map = {}
            bl_qs = BudgetLine.objects.filter(current_employee_id__in=emp_ids).values('current_employee_id',
                                                                                      'remuneration')
            for b in bl_qs:
                try:
                    salary_map[b['current_employee_id']] = Decimal(b['remuneration'])
                except (ValueError, TypeError, KeyError):
                    salary_map[b['current_employee_id']] = Decimal(0)

            # 2. Pre-cargar el último ManagementPeriod (Contrato) para calcular antigüedad y régimen
            mp_qs = ManagementPeriod.objects.filter(employee_id__in=emp_ids).select_related(
                'contract_type__labor_regime').order_by('employee_id', '-start_date')
            mp_map = {}
            for mp in mp_qs:
                if mp.employee_id not in mp_map:
                    mp_map[mp.employee_id] = mp

            # 3. Calcular valores
            for slip in created_payslips:
                salary = salary_map.get(slip.employee_id, Decimal(0))
                total_ing = Decimal(0)
                total_desc = Decimal(0)
                taxable_base = Decimal(0)

                # --- 3. Leer las preferencias del modelo PayrollInfo ---
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

                # --- 4. Calcular Antigüedad basada en el ManagementPeriod ---
                mp = mp_map.get(slip.employee_id)
                anios_servicio = 0

                if mp and mp.start_date:
                    dias_servicio = (self.period.end_date - mp.start_date).days
                    anios_servicio = dias_servicio / 365.25

                # --- 5. Lógica de Ingresos ---
                for inc in active_incomes:
                    val = Decimal(0)

                    if inc.code == 'REMUNERACION':
                        val = (salary / 30) * slip.worked_days

                    elif inc.code == 'DECIMO_TERCERO':
                        if mensualiza_decimos and self.period.working_days:
                            val = (salary / Decimal(12)) * (
                                    Decimal(slip.worked_days) / Decimal(self.period.working_days))

                    elif inc.code == 'DECIMO_CUARTO':
                        if mensualiza_decimos and self.period.working_days:
                            try:
                                sbu = Decimal(self.config.get('SBU', 460.00))
                            except Exception:
                                sbu = Decimal(0)
                            val = (sbu / Decimal(12)) * (Decimal(slip.worked_days) / Decimal(self.period.working_days))

                    elif inc.code == 'FONDOS_RESERVA':
                        if anios_servicio > 1 and mensualiza_fr:
                            try:
                                pct_fr = Decimal(self.config.get('FONDOS_RESERVA', '8.33'))
                            except Exception:
                                pct_fr = Decimal('8.33')

                            val_total = salary * (pct_fr / Decimal(100))
                            val = val_total * (Decimal(slip.worked_days) / Decimal(self.period.working_days))

                    if val > 0:
                        items_buffer.append(PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val))
                        total_ing += val
                        if inc.code == 'REMUNERACION':
                            taxable_base += val

                            # --- Lógica de Descuentos ---
                            regime_code = mp.contract_type.labor_regime.code if (
                                    mp and mp.contract_type and mp.contract_type.labor_regime) else None

                            # 1. Determinar códigos exactos según el régimen
                            if regime_code == 'LOSEP':
                                target_iess_code = 'IESS_PER_EMP'
                                target_patronal_code = 'APORTE_PATRONAL_EMP'
                            elif regime_code == 'CT':
                                target_iess_code = 'IESS_PER_TRA'
                                target_patronal_code = 'APORTE_PATRONAL_TRA'
                            else:
                                target_iess_code = 'IESS_PER'
                                target_patronal_code = 'APORTE_PATRONAL'

                            # 2. Aporte Personal IESS
                            iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')
                            if iess_ded:
                                iess_pct = self.config.get(target_iess_code,
                                                           self.config.get('IESS_PER', Decimal('9.45')))
                                val = taxable_base * (Decimal(iess_pct) / Decimal(100))
                                if val > 0:
                                    items_buffer.append(
                                        PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION',
                                                    value=val))
                                    total_desc += val

                            # 3. Aporte Patronal
                            patronal_ded = ded_map.get(target_patronal_code) or ded_map.get('APORTE_PATRONAL')
                            if patronal_ded:
                                try:
                                    patronal_pct = Decimal(self.config.get(target_patronal_code,
                                                                           self.config.get('APORTE_PATRONAL', '11.15')))
                                except Exception:
                                    patronal_pct = Decimal('11.15')

                                val_patronal = taxable_base * (patronal_pct / Decimal(100))
                                if val_patronal > 0:
                                    items_buffer.append(
                                        PayslipItem(payslip=slip, deduction_ref=patronal_ded, item_type='DEDUCTION',
                                                    value=val_patronal))

                            slip.total_income = total_ing
                            slip.total_deduction = total_desc
                            slip.net_pay = total_ing - total_desc
                            payslips_to_update.append(slip)

            # 7. Guardado Masivo
            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update, ['total_income', 'total_deduction', 'net_pay'])

            # 8. Asignación de partidas optimizada (con is_fixed)
            created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                'payslip__employee', 'income_ref', 'deduction_ref'
            )

            items_to_update = []
            for it in created_items:
                if getattr(it, 'budget_line_code', None):
                    continue

                rubro_code = None
                rubro_type = None
                if it.item_type == 'INCOME' and it.income_ref:
                    rubro_code = it.income_ref.code
                    rubro_type = 'INCOME'
                elif it.item_type == 'DEDUCTION' and it.deduction_ref:
                    rubro_code = it.deduction_ref.code
                    rubro_type = 'DEDUCTION'

                mapping = None
                if rubro_code:
                    mapping = RubroBudgetMapping.objects.filter(
                        is_active=True, rubro_type=rubro_type, rubro_code=rubro_code
                    ).first()

                base_bl = BudgetLine.objects.filter(current_employee_id=it.payslip.employee_id).first()

                if mapping and getattr(mapping, 'dynamic_suffix', None) and base_bl:

                    # LÓGICA SEGÚN CHECKBOX:
                    if getattr(mapping, 'is_fixed', False):
                        # CASO A: Partida Fija (toma todo el texto literal)
                        new_code = mapping.dynamic_suffix
                    else:
                        # CASO B: Es solo un sufijo (corta el final de la partida base)
                        base_parts = base_bl.code.split('.')
                        suffix_parts = mapping.dynamic_suffix.split('.')
                        num_parts_to_replace = len(suffix_parts)

                        if len(base_parts) > num_parts_to_replace:
                            prefix = ".".join(base_parts[:-num_parts_to_replace])
                            new_code = f"{prefix}.{mapping.dynamic_suffix}"
                        else:
                            new_code = mapping.dynamic_suffix  # Fallback seguridad

                    it.budget_line = base_bl
                    it.budget_line_code = new_code
                    items_to_update.append(it)
                    continue

                # Fallback: Si no hay mapeo o sufijo (Ej: Sueldo Base)
                if base_bl:
                    it.budget_line = base_bl
                    it.budget_line_code = base_bl.code
                    items_to_update.append(it)

            if items_to_update:
                PayslipItem.objects.bulk_update(items_to_update, ['budget_line', 'budget_line_code'])

            # =====================================================================
            # 9. Agregación contable (Partida Doble) - RECALCULO TOTAL DEL PERIODO
            # =====================================================================
            # A. Limpiamos los asientos contables viejos de este periodo para evitar duplicados
            journal_ids = list(
                JournalItem.objects.filter(reference=str(self.period)).values_list('journal_id', flat=True))
            if journal_ids:
                Journal.objects.filter(id__in=journal_ids).delete()

            # B. Volvemos a leer TODOS los items del periodo (no solo los recién creados)
            items_with_account = PayslipItem.objects.filter(payslip__period=self.period).select_related(
                'income_ref__debit_account', 'income_ref__credit_account',
                'deduction_ref__debit_account', 'deduction_ref__credit_account', 'budget_line'
            )

            aggregation = {}
            warnings = []

            for it in items_with_account:
                if it.item_type == 'INCOME' and it.income_ref:
                    if it.income_ref.debit_account:
                        key_debit = (it.income_ref.debit_account.id, it.budget_line_id, 'debit')
                        aggregation.setdefault(key_debit, Decimal(0))
                        aggregation[key_debit] += Decimal(it.value)
                    if it.income_ref.credit_account:
                        key_credit = (it.income_ref.credit_account.id, None, 'credit')
                        aggregation.setdefault(key_credit, Decimal(0))
                        aggregation[key_credit] += Decimal(it.value)

                elif it.item_type == 'DEDUCTION' and it.deduction_ref:
                    if it.deduction_ref.debit_account:
                        key_debit = (it.deduction_ref.debit_account.id, None, 'debit')
                        aggregation.setdefault(key_debit, Decimal(0))
                        aggregation[key_debit] += Decimal(it.value)
                    if it.deduction_ref.credit_account:
                        key_credit = (it.deduction_ref.credit_account.id, None, 'credit')
                        aggregation.setdefault(key_credit, Decimal(0))
                        aggregation[key_credit] += Decimal(it.value)

            if aggregation:
                journal = Journal.objects.create(date=self.period.end_date, description=f"Asiento Nómina {self.period}")
                total_debits = Decimal(0)
                total_credits = Decimal(0)

                for (account_id, budget_line_id, side), amount in aggregation.items():
                    if amount == 0:
                        continue
                    account = Account.objects.get(pk=account_id)
                    budget_line = BudgetLine.objects.filter(pk=budget_line_id).first() if budget_line_id else None
                    debit = amount if side == 'debit' else Decimal(0)
                    credit = amount if side == 'credit' else Decimal(0)

                    JournalItem.objects.create(
                        journal=journal, account=account, debit=debit, credit=credit,
                        budget_line=budget_line, reference=str(self.period)
                    )
                    total_debits += debit
                    total_credits += credit

                # --- MAGIA CONTABLE: LÍQUIDO A PAGAR (BANCO VS GASTOS PERSONAL) ---
                total_net_pay = sum(slip.net_pay for slip in created_payslips)
                if total_net_pay > 0:
                    try:
                        # Buscamos las cuentas maestras
                        cta_gastos_personal = Account.objects.get(code='2.1.3.51')
                        cta_banco = Account.objects.get(code='1.1.1.03.01')

                        # 1. Débito a Gastos en Personal (Cancelando deuda con el empleado)
                        JournalItem.objects.create(journal=journal, account=cta_gastos_personal, debit=total_net_pay,
                                                   credit=Decimal(0), reference=str(self.period))
                        total_debits += total_net_pay

                        # 2. Crédito a Banco Central (La salida de dinero real)
                        JournalItem.objects.create(journal=journal, account=cta_banco, debit=Decimal(0),
                                                   credit=total_net_pay, reference=str(self.period))
                        total_credits += total_net_pay
                    except Account.DoesNotExist:
                        warnings.append(
                            "Crea las cuentas 2.1.3.51 y 1.1.1.03.01 en Contabilidad para asentar el Líquido a Pagar automático.")
                # ------------------------------------------------------------------

                # Fallback de cuadre final de Django
                if total_debits != total_credits:
                    diff = (total_debits - total_credits)
                    balancing_account = Account.objects.filter(code__icontains='PAYROLL').first()
                    if balancing_account:
                        if diff > 0:
                            JournalItem.objects.create(journal=journal, account=balancing_account, debit=Decimal(0),
                                                       credit=diff)
                        else:
                            JournalItem.objects.create(journal=journal, account=balancing_account, debit=abs(diff),
                                                       credit=Decimal(0))

            return {"success": True, "warnings": warnings}

    def generate_for_selected(self, employees_with_days):
        payslip_buffer = []
        eligible_pairs = []

        candidate_ids = [emp.id for emp, _ in employees_with_days]
        assigned_emp_ids = set(
            BudgetLine.objects.filter(current_employee_id__in=candidate_ids).values_list('current_employee_id',
                                                                                         flat=True)
        )

        for emp, days in employees_with_days:
            person = getattr(emp, 'person', None)
            if not emp.is_active or not (person and getattr(person, 'is_active', False)):
                continue
            if emp.id not in assigned_emp_ids:
                continue
            eligible_pairs.append((emp, days))
            payslip_buffer.append(Payslip(employee=emp, period=self.period, worked_days=days))

        with transaction.atomic():
            selected_emp_ids = [emp.id for emp, _ in eligible_pairs]
            Payslip.objects.filter(period=self.period, employee_id__in=selected_emp_ids).delete()

            created_payslips = Payslip.objects.bulk_create(payslip_buffer)

            items_buffer = []
            payslips_to_update = []

            active_incomes = list(Income.objects.filter(is_active=True))
            active_deductions = list(Deduction.objects.filter(is_active=True))

            # BLINDAJE: Limpiamos los espacios en blanco y forzamos mayúsculas
            ded_map = {d.code.strip().upper(): d for d in active_deductions if d.code}

            emp_ids = [p.employee.id for p in created_payslips]

            salary_map = {}
            bl_qs = BudgetLine.objects.filter(current_employee_id__in=emp_ids).values('current_employee_id',
                                                                                      'remuneration')
            for b in bl_qs:
                try:
                    salary_map[b['current_employee_id']] = Decimal(b['remuneration'])
                except (ValueError, TypeError, KeyError):
                    salary_map[b['current_employee_id']] = Decimal(0)

            mp_qs = ManagementPeriod.objects.filter(employee_id__in=emp_ids).select_related(
                'contract_type__labor_regime').order_by('employee_id', '-start_date')
            mp_map = {}
            for mp in mp_qs:
                if mp.employee_id not in mp_map:
                    mp_map[mp.employee_id] = mp

            for slip in created_payslips:
                salary = salary_map.get(slip.employee_id, Decimal(0))
                total_ing = Decimal(0)
                total_desc = Decimal(0)
                taxable_base = Decimal(0)

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

                # --- Lógica de Ingresos ---
                for inc in active_incomes:
                    val = Decimal(0)
                    # BLINDAJE: Limpiar espacios del código del rubro
                    code_clean = inc.code.strip().upper() if inc.code else ''

                    if code_clean == 'REMUNERACION':
                        val = (salary / 30) * slip.worked_days

                    elif code_clean == 'DECIMO_TERCERO':
                        if mensualiza_decimos and self.period.working_days:
                            val = (salary / Decimal(12)) * (
                                    Decimal(slip.worked_days) / Decimal(self.period.working_days))

                    elif code_clean == 'DECIMO_CUARTO':
                        if mensualiza_decimos and self.period.working_days:
                            try:
                                sbu = Decimal(self.config.get('SBU', 460.00))
                            except Exception:
                                sbu = Decimal(0)
                            val = (sbu / Decimal(12)) * (Decimal(slip.worked_days) / Decimal(self.period.working_days))

                    elif code_clean == 'FONDOS_RESERVA':
                        if anios_servicio > 1 and mensualiza_fr:
                            try:
                                pct_fr = Decimal(self.config.get('FONDOS_RESERVA', '8.33'))
                            except Exception:
                                pct_fr = Decimal('8.33')

                            val_total = salary * (pct_fr / Decimal(100))
                            val = val_total * (Decimal(slip.worked_days) / Decimal(self.period.working_days))

                    if val > 0:
                        items_buffer.append(PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val))
                        total_ing += val
                        if code_clean == 'REMUNERACION':
                            taxable_base += val

                            # --- Lógica de Descuentos ---
                            regime_code = mp.contract_type.labor_regime.code if (
                                    mp and mp.contract_type and mp.contract_type.labor_regime) else None

                            # 1. Determinar códigos exactos según el régimen (Personales y Patronales)
                            if regime_code == 'LOSEP':
                                target_iess_code = 'IESS_PER_EMP'
                                target_patronal_code = 'APORTE_PATRONAL_EMP'
                            elif regime_code == 'CT':
                                target_iess_code = 'IESS_PER_TRA'
                                target_patronal_code = 'APORTE_PATRONAL_TRA'
                            else:
                                target_iess_code = 'IESS_PER'
                                target_patronal_code = 'APORTE_PATRONAL'

                            # 2. Aporte Personal IESS
                            iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')
                            if iess_ded:
                                iess_pct = self.config.get(target_iess_code,
                                                           self.config.get('IESS_PER', Decimal('9.45')))
                                val = taxable_base * (Decimal(iess_pct) / Decimal(100))
                                if val > 0:
                                    items_buffer.append(
                                        PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION',
                                                    value=val))
                                    total_desc += val

                            # 3. Aporte Patronal (Ahora sí usa el código dinámico _EMP o _TRA)
                            patronal_ded = ded_map.get(target_patronal_code) or ded_map.get('APORTE_PATRONAL')
                            if patronal_ded:
                                try:
                                    patronal_pct = Decimal(self.config.get(target_patronal_code,
                                                                           self.config.get('APORTE_PATRONAL', '11.15')))
                                except Exception:
                                    patronal_pct = Decimal('11.15')

                                val_patronal = taxable_base * (patronal_pct / Decimal(100))
                                if val_patronal > 0:
                                    items_buffer.append(
                                        PayslipItem(payslip=slip, deduction_ref=patronal_ded, item_type='DEDUCTION',
                                                    value=val_patronal))

                            slip.total_income = total_ing
                            slip.total_deduction = total_desc
                            slip.net_pay = total_ing - total_desc
                            payslips_to_update.append(slip)

            # 7. Guardado Masivo
            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update, ['total_income', 'total_deduction', 'net_pay'])

            # 8. Asignación de partidas optimizada
            created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                'payslip__employee', 'income_ref', 'deduction_ref'
            )

            items_to_update = []
            for it in created_items:
                if getattr(it, 'budget_line_code', None):
                    continue

                rubro_code = None
                rubro_type = None
                if it.item_type == 'INCOME' and it.income_ref:
                    rubro_code = it.income_ref.code.strip().upper()
                    rubro_type = 'INCOME'
                elif it.item_type == 'DEDUCTION' and it.deduction_ref:
                    rubro_code = it.deduction_ref.code.strip().upper()
                    rubro_type = 'DEDUCTION'

                mapping = None
                if rubro_code:
                    mapping = RubroBudgetMapping.objects.filter(
                        is_active=True, rubro_type=rubro_type, rubro_code=rubro_code
                    ).first()

                base_bl = BudgetLine.objects.filter(current_employee_id=it.payslip.employee_id).first()

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

            # 9. Agregación contable
            journal_ids = list(
                JournalItem.objects.filter(reference=str(self.period)).values_list('journal_id', flat=True))
            if journal_ids:
                Journal.objects.filter(id__in=journal_ids).delete()

            items_with_account = PayslipItem.objects.filter(payslip__period=self.period).select_related(
                'income_ref__debit_account', 'income_ref__credit_account',
                'deduction_ref__debit_account', 'deduction_ref__credit_account', 'budget_line'
            )

            aggregation = {}
            warnings = []

            for it in items_with_account:
                if it.item_type == 'INCOME' and it.income_ref:
                    if it.income_ref.debit_account:
                        key_debit = (it.income_ref.debit_account.id, it.budget_line_id, 'debit')
                        aggregation.setdefault(key_debit, Decimal(0))
                        aggregation[key_debit] += Decimal(it.value)
                    if it.income_ref.credit_account:
                        key_credit = (it.income_ref.credit_account.id, None, 'credit')
                        aggregation.setdefault(key_credit, Decimal(0))
                        aggregation[key_credit] += Decimal(it.value)

                elif it.item_type == 'DEDUCTION' and it.deduction_ref:
                    if it.deduction_ref.debit_account:
                        key_debit = (it.deduction_ref.debit_account.id, None, 'debit')
                        aggregation.setdefault(key_debit, Decimal(0))
                        aggregation[key_debit] += Decimal(it.value)
                    if it.deduction_ref.credit_account:
                        key_credit = (it.deduction_ref.credit_account.id, None, 'credit')
                        aggregation.setdefault(key_credit, Decimal(0))
                        aggregation[key_credit] += Decimal(it.value)

            if aggregation:
                journal = Journal.objects.create(date=self.period.end_date, description=f"Asiento Nómina {self.period}")
                total_debits = Decimal(0)
                total_credits = Decimal(0)

                for (account_id, budget_line_id, side), amount in aggregation.items():
                    if amount == 0:
                        continue
                    account = Account.objects.get(pk=account_id)
                    budget_line = BudgetLine.objects.filter(pk=budget_line_id).first() if budget_line_id else None
                    debit = amount if side == 'debit' else Decimal(0)
                    credit = amount if side == 'credit' else Decimal(0)

                    JournalItem.objects.create(
                        journal=journal, account=account, debit=debit, credit=credit,
                        budget_line=budget_line, reference=str(self.period)
                    )
                    total_debits += debit
                    total_credits += credit

                total_net_pay = sum(slip.net_pay for slip in created_payslips)
                if total_net_pay > 0:
                    try:
                        cta_gastos_personal = Account.objects.get(code='2.1.3.51')
                        cta_banco = Account.objects.get(code='1.1.1.03.01')

                        JournalItem.objects.create(journal=journal, account=cta_gastos_personal, debit=total_net_pay,
                                                   credit=Decimal(0), reference=str(self.period))
                        total_debits += total_net_pay

                        JournalItem.objects.create(journal=journal, account=cta_banco, debit=Decimal(0),
                                                   credit=total_net_pay, reference=str(self.period))
                        total_credits += total_net_pay
                    except Account.DoesNotExist:
                        warnings.append("Crea las cuentas 2.1.3.51 y 1.1.1.03.01 en Contabilidad para el Líquido.")

                if total_debits != total_credits:
                    diff = (total_debits - total_credits)
                    balancing_account = Account.objects.filter(code__icontains='PAYROLL').first()
                    if balancing_account:
                        if diff > 0:
                            JournalItem.objects.create(journal=journal, account=balancing_account, debit=Decimal(0),
                                                       credit=diff)
                        else:
                            JournalItem.objects.create(journal=journal, account=balancing_account, debit=abs(diff),
                                                       credit=Decimal(0))

            return {"success": True, "warnings": warnings}
