from decimal import Decimal
from django.db import transaction
from .models import Payslip, PayslipItem, PayrollConstant, Income, Deduction, RubroBudgetMapping
from accounting.models import Journal, JournalItem, Account
from budget.models import BudgetLine


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

            # Obtener datos económicos (Sueldos)
            emp_ids = [emp.id for emp in eligible_employees]
            salary_map = {}
            bl_qs = BudgetLine.objects.filter(current_employee_id__in=emp_ids).values('current_employee_id',
                                                                                      'remuneration')
            for b in bl_qs:
                try:
                    salary_map[b['current_employee_id']] = Decimal(b['remuneration'])
                except (ValueError, TypeError, KeyError):
                    salary_map[b['current_employee_id']] = Decimal(0)

            # 2. Calcular valores
            for slip in created_payslips:
                salary = salary_map.get(slip.employee_id, Decimal(0))
                total_ing = Decimal(0)
                total_desc = Decimal(0)
                taxable_base = Decimal(0)

                payroll_info = None
                try:
                    payroll_info = getattr(getattr(slip.employee, 'person', None), 'economic_data', None)
                    if payroll_info:
                        payroll_info = getattr(payroll_info, 'payroll_info', None)
                except Exception:
                    payroll_info = None

                monthlyize = bool(getattr(payroll_info, 'monthly_payment', False))

                # --- Lógica de Ingresos ---
                for inc in active_incomes:
                    val = Decimal(0)
                    if inc.code == 'REMUNERACION':
                        val = (salary / 30) * slip.worked_days
                    elif inc.code == 'DECIMO_TERCERO':
                        if monthlyize and self.period.working_days:
                            val = (salary / Decimal(12)) * (
                                    Decimal(slip.worked_days) / Decimal(self.period.working_days))
                    elif inc.code == 'DECIMO_CUARTO':
                        try:
                            sbu = Decimal(self.config.get('SBU', 0))
                        except Exception:
                            sbu = Decimal(0)
                        if monthlyize and self.period.working_days:
                            val = (sbu / Decimal(12)) * (Decimal(slip.worked_days) / Decimal(self.period.working_days))

                    if val > 0:
                        items_buffer.append(PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val))
                        total_ing += val
                        if inc.code == 'REMUNERACION':
                            taxable_base += val

                # --- Lógica de Descuentos ---
                from contract.models import ManagementPeriod
                mp = ManagementPeriod.objects.filter(employee_id=slip.employee_id).order_by('-start_date').first()
                regime_code = mp.contract_type.labor_regime.code if (
                        mp and mp.contract_type and mp.contract_type.labor_regime) else None

                if regime_code == 'LOSEP':
                    target_iess_code = 'IESS_PER_EMP'
                elif regime_code == 'CT':
                    target_iess_code = 'IESS_PER_TRA'
                else:
                    target_iess_code = 'IESS_PER'

                iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')

                if iess_ded:
                    iess_pct = self.config.get(target_iess_code, self.config.get('IESS_PER', Decimal('9.45')))
                    val = taxable_base * (Decimal(iess_pct) / Decimal(100))
                    if val > 0:
                        items_buffer.append(
                            PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION', value=val))
                        total_desc += val

                slip.total_income = total_ing
                slip.total_deduction = total_desc
                slip.net_pay = total_ing - total_desc
                payslips_to_update.append(slip)

            # 3. Guardado Masivo
            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update, ['total_income', 'total_deduction', 'net_pay'])

            # 4. Asignar partidas presupuestarias
            created_items = PayslipItem.objects.filter(payslip__period=self.period).select_related(
                'payslip__employee', 'income_ref', 'deduction_ref'
            )

            items_to_update = []
            for it in created_items:
                if it.budget_line_id:
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
                emp_unit_id = getattr(getattr(it.payslip, 'employee', None), 'administrative_unit_id', None)
                if rubro_code:
                    if emp_unit_id:
                        mapping = RubroBudgetMapping.objects.filter(
                            is_active=True, rubro_type=rubro_type, rubro_code=rubro_code,
                            administrative_unit_id=emp_unit_id
                        ).first()
                    if mapping is None:
                        mapping = RubroBudgetMapping.objects.filter(
                            is_active=True, rubro_type=rubro_type, rubro_code=rubro_code,
                            administrative_unit__isnull=True
                        ).first()

                if mapping:
                    it.budget_line = mapping.budget_line
                    items_to_update.append(it)
                    continue

                bl = BudgetLine.objects.filter(current_employee_id=it.payslip.employee_id).first()
                if bl:
                    it.budget_line = bl
                    items_to_update.append(it)

            if items_to_update:
                PayslipItem.objects.bulk_update(items_to_update, ['budget_line'])

            # 5. Agregar asientos contables (Partida Doble)
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
                    else:
                        warnings.append(
                            f"Asiento {journal.id} no balanceado (D:{total_debits} C:{total_credits}) y no se encontró cuenta de compensación")

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
            ded_map = {d.code: d for d in active_deductions}

            emp_ids = [p.employee.id for p in created_payslips]
            salary_map = {}
            bl_qs = BudgetLine.objects.filter(current_employee_id__in=emp_ids).values('current_employee_id',
                                                                                      'remuneration')
            for b in bl_qs:
                try:
                    salary_map[b['current_employee_id']] = Decimal(b['remuneration'])
                except (ValueError, TypeError, KeyError):
                    salary_map[b['current_employee_id']] = Decimal(0)

            for slip in created_payslips:
                salary = salary_map.get(slip.employee_id, Decimal(0))
                total_ing = Decimal(0)
                total_desc = Decimal(0)
                taxable_base = Decimal(0)

                payroll_info = None
                try:
                    payroll_info = getattr(getattr(slip.employee, 'person', None), 'economic_data', None)
                    if payroll_info:
                        payroll_info = getattr(payroll_info, 'payroll_info', None)
                except Exception:
                    payroll_info = None

                monthlyize = bool(getattr(payroll_info, 'monthly_payment', False))

                for inc in active_incomes:
                    val = Decimal(0)
                    if inc.code == 'REMUNERACION':
                        val = (salary / 30) * slip.worked_days
                    elif inc.code == 'DECIMO_TERCERO':
                        if monthlyize and self.period.working_days:
                            val = (salary / Decimal(12)) * (
                                    Decimal(slip.worked_days) / Decimal(self.period.working_days))
                    elif inc.code == 'DECIMO_CUARTO':
                        try:
                            sbu = Decimal(self.config.get('SBU', 0))
                        except Exception:
                            sbu = Decimal(0)
                        if monthlyize and self.period.working_days:
                            val = (sbu / Decimal(12)) * (Decimal(slip.worked_days) / Decimal(self.period.working_days))

                    if val > 0:
                        items_buffer.append(PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val))
                        total_ing += val
                        if inc.code == 'REMUNERACION':
                            taxable_base += val

                from contract.models import ManagementPeriod
                mp = ManagementPeriod.objects.filter(employee_id=slip.employee_id).order_by('-start_date').first()
                regime_code = mp.contract_type.labor_regime.code if (
                        mp and mp.contract_type and mp.contract_type.labor_regime) else None

                if regime_code == 'LOSEP':
                    target_iess_code = 'IESS_PER_EMP'
                elif regime_code == 'CT':
                    target_iess_code = 'IESS_PER_TRA'
                else:
                    target_iess_code = 'IESS_PER'

                iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')
                if iess_ded:
                    iess_pct = self.config.get(target_iess_code, self.config.get('IESS_PER', Decimal('9.45')))
                    val = taxable_base * (Decimal(iess_pct) / Decimal(100))
                    if val > 0:
                        items_buffer.append(
                            PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION', value=val))
                        total_desc += val

                slip.total_income = total_ing
                slip.total_deduction = total_desc
                slip.net_pay = total_ing - total_desc
                payslips_to_update.append(slip)

            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update, ['total_income', 'total_deduction', 'net_pay'])

            # Asignación de partidas
            created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                'payslip__employee', 'income_ref', 'deduction_ref'
            )

            items_to_update = []
            for it in created_items:
                if it.budget_line_id:
                    continue
                bl = BudgetLine.objects.filter(current_employee_id=it.payslip.employee_id).first()
                if bl:
                    it.budget_line = bl
                    items_to_update.append(it)

            if items_to_update:
                PayslipItem.objects.bulk_update(items_to_update, ['budget_line'])

            # Agregación contable
            items_with_account = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
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
                journal = Journal.objects.create(date=self.period.end_date,
                                                 description=f"Asiento Nómina {self.period} (Seleccionados)")
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
                    else:
                        warnings.append(
                            f"Asiento {journal.id} no balanceado (D:{total_debits} C:{total_credits}) y no se encontró cuenta de compensación")

            return {"success": True, "warnings": warnings}
