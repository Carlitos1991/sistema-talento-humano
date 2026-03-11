from decimal import Decimal
from django.db import transaction
from .models import Payslip, PayslipItem, PayrollConstant, Income, Deduction, RubroBudgetMapping, \
    InstitutionalContribution
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

            from .models import PayrollNovelty  # Asegúrate de que esté importado arriba
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

            # 3. Calcular valores
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

                regime_code = ''
                if mp and mp.contract_type and mp.contract_type.labor_regime and mp.contract_type.labor_regime.code:
                    regime_code = mp.contract_type.labor_regime.code.strip().upper()

                # ====================================================
                # 1. BUCLE DE INGRESOS (Inicia aquí)
                # ====================================================
                for inc in active_incomes:
                    val = Decimal(0)
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
                    elif code_clean == 'ALIMENTACION':
                        if regime_code == 'CT':  # Solo Trabajadores
                            try:
                                const_alim = Decimal(self.config.get('ALIMENTACION', '0.00'))
                            except Exception:
                                const_alim = Decimal(0)
                            # Si trabaja 30 días, cobra completo. Si trabaja menos, se prorratea.
                            val = (const_alim / Decimal(30)) * Decimal(slip.worked_days)

                    if val > 0:
                        items_buffer.append(PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val))
                        total_ing += val
                        if code_clean == 'REMUNERACION':
                            taxable_base += val
                # ====================================================
                # FIN DEL BUCLE DE INGRESOS
                # ====================================================

                # ====================================================
                # 2. LÓGICA DE DESCUENTOS (Totalmente FUERA del for)
                # ====================================================
                # Determinar códigos exactos según el régimen
                if regime_code == 'LOSEP':
                    target_iess_code = 'IESS_PER_EMP'
                    target_patronal_code = 'APORTE_PATRONAL_EMP'
                elif regime_code == 'CT':
                    target_iess_code = 'IESS_PER_TRA'
                    target_patronal_code = 'APORTE_PATRONAL_TRA'
                else:
                    target_iess_code = 'IESS_PER'
                    target_patronal_code = 'APORTE_PATRONAL'

                # Aporte Personal IESS
                iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')
                if iess_ded:
                    iess_pct = self.config.get(target_iess_code, self.config.get('IESS_PER', Decimal('9.45')))
                    val = taxable_base * (Decimal(iess_pct) / Decimal(100))
                    if val > 0:
                        items_buffer.append(
                            PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION', value=val))
                        total_desc += val

                        # ====================================================
                        # NUEVO: APORTES INSTITUCIONALES (Ej: Patronal)
                        # ====================================================
                        # Buscamos el Aporte Institucional correspondiente
                        contrib_ref = InstitutionalContribution.objects.filter(code=target_patronal_code).first()
                        if not contrib_ref:
                            contrib_ref = InstitutionalContribution.objects.filter(code='APORTE_PATRONAL').first()

                        if contrib_ref:
                            try:
                                patronal_pct = Decimal(
                                    self.config.get(target_patronal_code, self.config.get('APORTE_PATRONAL', '11.15')))
                            except Exception:
                                patronal_pct = Decimal('11.15')

                            val_patronal = taxable_base * (patronal_pct / Decimal(100))
                            if val_patronal > 0:
                                # Se guarda como CONTRIBUTION, no como DEDUCTION. Así no ensucia el rol del empleado.
                                items_buffer.append(
                                    PayslipItem(
                                        payslip=slip,
                                        contribution_ref=contrib_ref,
                                        item_type='CONTRIBUTION',
                                        value=val_patronal
                                    ))

                        # ====================================================
                        # 3. PROCESAR NOVEDADES (Anticipos, Horas Extras, etc)
                        # ====================================================
                        emp_novelties = novelties_map.get(slip.employee_id, {'incomes': [], 'deductions': []})

                        # A. Sumar Novedades de Ingresos
                        for nov in emp_novelties['incomes']:
                            if nov.value > 0:
                                items_buffer.append(
                                    PayslipItem(payslip=slip, income_ref=nov.income_ref, item_type='INCOME',
                                                value=nov.value))
                                total_ing += nov.value

                        # B. Sumar Novedades de Egresos
                        for nov in emp_novelties['deductions']:
                            if nov.value > 0:
                                items_buffer.append(
                                    PayslipItem(payslip=slip, deduction_ref=nov.deduction_ref, item_type='DEDUCTION',
                                                value=nov.value))
                                total_desc += nov.value

                # Asignación final al rol
                slip.total_income = total_ing
                slip.total_deduction = total_desc
                slip.net_pay = total_ing - total_desc
                payslips_to_update.append(slip)

            # 7. Guardado Masivo
            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update, ['total_income', 'total_deduction', 'net_pay'])

            # =====================================================================
            # 8. ASIGNACIÓN DE PARTIDAS OPTIMIZADA (Usando las nuevas Claves Foráneas)
            # =====================================================================
            # Agregamos contribution_ref si existe en tu modelo PayslipItem
            try:
                created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                    'payslip__employee', 'income_ref', 'deduction_ref', 'contribution_ref'
                )
            except Exception:
                # Fallback por si contribution_ref aún no está en select_related
                created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                    'payslip__employee', 'income_ref', 'deduction_ref'
                )

            items_to_update = []
            for it in created_items:
                if getattr(it, 'budget_line_code', None):
                    continue

                # Extraemos el mapeo directamente usando la relación (ForeignKey)
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

                # Buscamos la partida base del empleado
                base_bl = BudgetLine.objects.filter(current_employee_id=it.payslip.employee_id).first()

                # Si el rubro tiene mapeo y el empleado tiene partida base
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

                # Si no hay mapeo (Ej: Sueldo base), se le asigna la partida tal cual
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

            # Calcular el líquido total a pagar en este mes (para el asiento del Banco)
            total_net_pay = sum(slip.net_pay for slip in created_payslips)

            for it in created_items:
                # ------ A. MAPEO PRESUPUESTARIO CON CLAVES FORÁNEAS ------
                budget_code = getattr(it, 'budget_line_code', None)

                if budget_code:
                    nombre_rubro = getattr(it.income_ref, 'name',
                                           getattr(it.deduction_ref, 'name', getattr(it.contribution_ref, 'name', '')))
                    key_budget = (budget_code, nombre_rubro)
                    budget_aggregation.setdefault(key_budget, Decimal(0))
                    budget_aggregation[key_budget] += Decimal(it.value)

                # ------ B. JORNALIZACIÓN CONTABLE ------
                if it.item_type == 'INCOME' and it.income_ref:
                    if it.income_ref.debit_account:
                        key_debit = (it.income_ref.debit_account.id, budget_code, 'debit')
                        aggregation.setdefault(key_debit, Decimal(0))
                        aggregation[key_debit] += Decimal(it.value)
                    if it.income_ref.credit_account:
                        key_credit = (it.income_ref.credit_account.id, budget_code, 'credit')
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

                elif it.item_type == 'CONTRIBUTION' and getattr(it, 'contribution_ref', None):
                    if it.contribution_ref.debit_account:
                        key_debit = (it.contribution_ref.debit_account.id, None, 'debit')
                        aggregation.setdefault(key_debit, Decimal(0))
                        aggregation[key_debit] += Decimal(it.value)
                    if it.contribution_ref.credit_account:
                        key_credit = (it.contribution_ref.credit_account.id, None, 'credit')
                        aggregation.setdefault(key_credit, Decimal(0))
                        aggregation[key_credit] += Decimal(it.value)

                    # Mantenemos el Truco de Contraloría para el Patronal
                    if 'PATRONAL' in it.contribution_ref.code.upper():
                        try:
                            cta_gastos_personal = Account.objects.get(code='2.1.3.51')
                            key_debit_puente = (cta_gastos_personal.id, None, 'debit')
                            aggregation.setdefault(key_debit_puente, Decimal(0))
                            aggregation[key_debit_puente] += Decimal(it.value)
                            key_credit_puente = (cta_gastos_personal.id, None, 'credit')
                            aggregation.setdefault(key_credit_puente, Decimal(0))
                            aggregation[key_credit_puente] += Decimal(it.value)
                        except Exception:
                            pass

                        # =====================================================================
                        # 10. GUARDADO EN BASE DE DATOS (Asientos Journal y JournalItems)
                        # =====================================================================
                        if aggregation or total_net_pay > 0:
                            # Armamos el texto exacto con el que vamos a identificar este asiento
                            desc_asiento = f"Nómina {self.period.month} {self.period.year}"

                            # 1. Borramos asientos anteriores de este mismo periodo para no duplicar
                            Journal.objects.filter(description=desc_asiento).delete()

                            # 2. Creamos el Asiento Cabecera (usando tu campo real 'description')
                            journal = Journal.objects.create(
                                date=self.period.end_date,
                                description=desc_asiento
                            )

                            total_debits = Decimal(0)
                            total_credits = Decimal(0)

                            # 10.1. Guardar items agrupados
                            for key, val in aggregation.items():
                                if val <= 0: continue
                                acc_id, b_code, mov_type = key
                                try:
                                    acc = Account.objects.get(id=acc_id)
                                    if mov_type == 'debit':
                                        JournalItem.objects.create(journal=journal, account=acc, debit=val,
                                                                   credit=Decimal(0))
                                        total_debits += val
                                    else:
                                        JournalItem.objects.create(journal=journal, account=acc, debit=Decimal(0),
                                                                   credit=val)
                                        total_credits += val
                                except Account.DoesNotExist:
                                    pass

                            # 10.2. Asiento automático del Líquido a Pagar (Banco)
                            if total_net_pay > 0:
                                try:
                                    cta_gastos_personal = Account.objects.get(code='2.1.3.51')
                                    cta_banco = Account.objects.get(code='1.1.1.03.01')

                                    JournalItem.objects.create(journal=journal, account=cta_gastos_personal,
                                                               debit=total_net_pay, credit=Decimal(0))
                                    total_debits += total_net_pay

                                    JournalItem.objects.create(journal=journal, account=cta_banco, debit=Decimal(0),
                                                               credit=total_net_pay)
                                    total_credits += total_net_pay
                                except Account.DoesNotExist:
                                    warnings.append(
                                        "Crea las cuentas 2.1.3.51 y 1.1.1.03.01 en Contabilidad para registrar el Líquido a Pagar.")

                            # 10.3. Cuadrar céntimos si hay diferencia
                            if total_debits != total_credits:
                                diff = (total_debits - total_credits)
                                balancing_account = Account.objects.filter(code__icontains='PAYROLL').first()
                                if balancing_account:
                                    if diff > 0:
                                        JournalItem.objects.create(journal=journal, account=balancing_account,
                                                                   debit=Decimal(0), credit=diff)
                                    else:
                                        JournalItem.objects.create(journal=journal, account=balancing_account,
                                                                   debit=abs(diff), credit=Decimal(0))

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

                    # --- NUEVO: Pre-cargar Novedades (Cargas masivas/manuales del mes) ---
                    from .models import PayrollNovelty  # Asegúrate de que esté importado arriba
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
                    # ----------------------------------------------------------------------

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

                regime_code = mp.contract_type.labor_regime.code if (
                        mp and mp.contract_type and mp.contract_type.labor_regime) else None

                # ====================================================
                # 1. BUCLE DE INGRESOS (Inicia aquí)
                # ====================================================
                for inc in active_incomes:
                    val = Decimal(0)
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
                    elif code_clean == 'ALIMENTACION':
                        if regime_code == 'CT':  # Solo Trabajadores
                            try:
                                const_alim = Decimal(self.config.get('ALIMENTACION', '0.00'))
                            except Exception:
                                const_alim = Decimal(0)
                            # Si trabaja 30 días, cobra completo. Si trabaja menos, se prorratea.
                            val = (const_alim / Decimal(30)) * Decimal(slip.worked_days)
                    if val > 0:
                        items_buffer.append(PayslipItem(payslip=slip, income_ref=inc, item_type='INCOME', value=val))
                        total_ing += val
                        if code_clean == 'REMUNERACION':
                            taxable_base += val
                # ====================================================
                # FIN DEL BUCLE DE INGRESOS
                # ====================================================

                # ====================================================
                # 2. LÓGICA DE DESCUENTOS (Totalmente FUERA del for)
                # ====================================================

                # Determinar códigos exactos según el régimen
                if regime_code == 'LOSEP':
                    target_iess_code = 'IESS_PER_EMP'
                    target_patronal_code = 'APORTE_PATRONAL_EMP'
                elif regime_code == 'CT':
                    target_iess_code = 'IESS_PER_TRA'
                    target_patronal_code = 'APORTE_PATRONAL_TRA'
                else:
                    target_iess_code = 'IESS_PER'
                    target_patronal_code = 'APORTE_PATRONAL'

                # Aporte Personal IESS
                iess_ded = ded_map.get(target_iess_code) or ded_map.get('IESS_PER')
                if iess_ded:
                    iess_pct = self.config.get(target_iess_code, self.config.get('IESS_PER', Decimal('9.45')))
                    val = taxable_base * (Decimal(iess_pct) / Decimal(100))
                    if val > 0:
                        items_buffer.append(
                            PayslipItem(payslip=slip, deduction_ref=iess_ded, item_type='DEDUCTION', value=val))
                        total_desc += val

                        # ====================================================
                        # NUEVO: APORTES INSTITUCIONALES (Ej: Patronal)
                        # ====================================================
                        # Buscamos el Aporte Institucional correspondiente
                        contrib_ref = InstitutionalContribution.objects.filter(code=target_patronal_code).first()
                        if not contrib_ref:
                            contrib_ref = InstitutionalContribution.objects.filter(code='APORTE_PATRONAL').first()

                        if contrib_ref:
                            try:
                                patronal_pct = Decimal(
                                    self.config.get(target_patronal_code, self.config.get('APORTE_PATRONAL', '11.15')))
                            except Exception:
                                patronal_pct = Decimal('11.15')

                            val_patronal = taxable_base * (patronal_pct / Decimal(100))
                            if val_patronal > 0:
                                # Se guarda como CONTRIBUTION, no como DEDUCTION. Así no ensucia el rol del empleado.
                                items_buffer.append(
                                    PayslipItem(
                                        payslip=slip,
                                        contribution_ref=contrib_ref,
                                        item_type='CONTRIBUTION',
                                        value=val_patronal
                                    ))

                        # ====================================================
                        # 3. PROCESAR NOVEDADES (Anticipos, Horas Extras, etc)
                        # ====================================================
                        emp_novelties = novelties_map.get(slip.employee_id, {'incomes': [], 'deductions': []})

                        # A. Sumar Novedades de Ingresos
                        for nov in emp_novelties['incomes']:
                            if nov.value > 0:
                                items_buffer.append(
                                    PayslipItem(payslip=slip, income_ref=nov.income_ref, item_type='INCOME',
                                                value=nov.value))
                                total_ing += nov.value

                        # B. Sumar Novedades de Egresos
                        for nov in emp_novelties['deductions']:
                            if nov.value > 0:
                                items_buffer.append(
                                    PayslipItem(payslip=slip, deduction_ref=nov.deduction_ref, item_type='DEDUCTION',
                                                value=nov.value))
                                total_desc += nov.value

                # Asignación final al rol
                slip.total_income = total_ing
                slip.total_deduction = total_desc
                slip.net_pay = total_ing - total_desc
                payslips_to_update.append(slip)

            # 7. Guardado Masivo
            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update, ['total_income', 'total_deduction', 'net_pay'])

            # =====================================================================
            # 8. ASIGNACIÓN DE PARTIDAS OPTIMIZADA (Usando las nuevas Claves Foráneas)
            # =====================================================================
            # Agregamos contribution_ref si existe en tu modelo PayslipItem
            try:
                created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                    'payslip__employee', 'income_ref', 'deduction_ref', 'contribution_ref'
                )
            except Exception:
                # Fallback por si contribution_ref aún no está en select_related
                created_items = PayslipItem.objects.filter(payslip__in=created_payslips).select_related(
                    'payslip__employee', 'income_ref', 'deduction_ref'
                )

            items_to_update = []
            for it in created_items:
                if getattr(it, 'budget_line_code', None):
                    continue

                # Extraemos el mapeo directamente usando la relación (ForeignKey)
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

                # Buscamos la partida base del empleado
                base_bl = BudgetLine.objects.filter(current_employee_id=it.payslip.employee_id).first()

                # Si el rubro tiene mapeo y el empleado tiene partida base
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

                # Si no hay mapeo (Ej: Sueldo base), se le asigna la partida tal cual
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

            # Calcular el líquido total a pagar en este mes (para el asiento del Banco)
            total_net_pay = sum(slip.net_pay for slip in created_payslips)

            for it in created_items:
                # ------ A. MAPEO PRESUPUESTARIO CON CLAVES FORÁNEAS ------
                budget_code = getattr(it, 'budget_line_code', None)

                if budget_code:
                    nombre_rubro = getattr(it.income_ref, 'name',
                                           getattr(it.deduction_ref, 'name', getattr(it.contribution_ref, 'name', '')))
                    key_budget = (budget_code, nombre_rubro)
                    budget_aggregation.setdefault(key_budget, Decimal(0))
                    budget_aggregation[key_budget] += Decimal(it.value)

                # ------ B. JORNALIZACIÓN CONTABLE ------
                if it.item_type == 'INCOME' and it.income_ref:
                    if it.income_ref.debit_account:
                        key_debit = (it.income_ref.debit_account.id, budget_code, 'debit')
                        aggregation.setdefault(key_debit, Decimal(0))
                        aggregation[key_debit] += Decimal(it.value)
                    if it.income_ref.credit_account:
                        key_credit = (it.income_ref.credit_account.id, budget_code, 'credit')
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

                elif it.item_type == 'CONTRIBUTION' and getattr(it, 'contribution_ref', None):
                    if it.contribution_ref.debit_account:
                        key_debit = (it.contribution_ref.debit_account.id, None, 'debit')
                        aggregation.setdefault(key_debit, Decimal(0))
                        aggregation[key_debit] += Decimal(it.value)
                    if it.contribution_ref.credit_account:
                        key_credit = (it.contribution_ref.credit_account.id, None, 'credit')
                        aggregation.setdefault(key_credit, Decimal(0))
                        aggregation[key_credit] += Decimal(it.value)

                    # Mantenemos el Truco de Contraloría para el Patronal
                    if 'PATRONAL' in it.contribution_ref.code.upper():
                        try:
                            cta_gastos_personal = Account.objects.get(code='2.1.3.51')
                            key_debit_puente = (cta_gastos_personal.id, None, 'debit')
                            aggregation.setdefault(key_debit_puente, Decimal(0))
                            aggregation[key_debit_puente] += Decimal(it.value)
                            key_credit_puente = (cta_gastos_personal.id, None, 'credit')
                            aggregation.setdefault(key_credit_puente, Decimal(0))
                            aggregation[key_credit_puente] += Decimal(it.value)
                        except Exception:
                            pass

                        # =====================================================================
                        # 10. GUARDADO EN BASE DE DATOS (Asientos Journal y JournalItems)
                        # =====================================================================
                        if aggregation or total_net_pay > 0:
                            # Armamos el texto exacto con el que vamos a identificar este asiento
                            desc_asiento = f"Nómina {self.period.month} {self.period.year}"

                            # 1. Borramos asientos anteriores de este mismo periodo para no duplicar
                            Journal.objects.filter(description=desc_asiento).delete()

                            # 2. Creamos el Asiento Cabecera (usando tu campo real 'description')
                            journal = Journal.objects.create(
                                date=self.period.end_date,
                                description=desc_asiento
                            )

                            total_debits = Decimal(0)
                            total_credits = Decimal(0)

                            # 10.1. Guardar items agrupados
                            for key, val in aggregation.items():
                                if val <= 0: continue
                                acc_id, b_code, mov_type = key
                                try:
                                    acc = Account.objects.get(id=acc_id)
                                    if mov_type == 'debit':
                                        JournalItem.objects.create(journal=journal, account=acc, debit=val,
                                                                   credit=Decimal(0))
                                        total_debits += val
                                    else:
                                        JournalItem.objects.create(journal=journal, account=acc, debit=Decimal(0),
                                                                   credit=val)
                                        total_credits += val
                                except Account.DoesNotExist:
                                    pass

                            # 10.2. Asiento automático del Líquido a Pagar (Banco)
                            if total_net_pay > 0:
                                try:
                                    cta_gastos_personal = Account.objects.get(code='2.1.3.51')
                                    cta_banco = Account.objects.get(code='1.1.1.03.01')

                                    JournalItem.objects.create(journal=journal, account=cta_gastos_personal,
                                                               debit=total_net_pay, credit=Decimal(0))
                                    total_debits += total_net_pay

                                    JournalItem.objects.create(journal=journal, account=cta_banco, debit=Decimal(0),
                                                               credit=total_net_pay)
                                    total_credits += total_net_pay
                                except Account.DoesNotExist:
                                    warnings.append(
                                        "Crea las cuentas 2.1.3.51 y 1.1.1.03.01 en Contabilidad para registrar el Líquido a Pagar.")

                            # 10.3. Cuadrar céntimos si hay diferencia
                            if total_debits != total_credits:
                                diff = (total_debits - total_credits)
                                balancing_account = Account.objects.filter(code__icontains='PAYROLL').first()
                                if balancing_account:
                                    if diff > 0:
                                        JournalItem.objects.create(journal=journal, account=balancing_account,
                                                                   debit=Decimal(0), credit=diff)
                                    else:
                                        JournalItem.objects.create(journal=journal, account=balancing_account,
                                                                   debit=abs(diff), credit=Decimal(0))

                        return {"success": True, "warnings": warnings}
