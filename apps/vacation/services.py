# vacation/services.py
import math
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from institution.models import AdministrativeUnit
from contract.models import ManagementPeriod


def calcular_dias_ganados(fecha_ingreso, fecha_aniversario, regimen_codigo):
    """
    Calcula los días ganados en un aniversario específico.
    """
    if not regimen_codigo:
        return Decimal('30.0')

    regimen = regimen_codigo.upper()

    # LOSEP o Nombramiento
    if 'LOSEP' in regimen or 'NOMBRAMIENTO' in regimen:
        return Decimal('30.0')

    # TRABAJADOR (Código del Trabajo)
    if 'TRABAJADOR' in regimen or 'CÓDIGO' in regimen or 'CODIGO' in regimen:
        anios_cumplidos = relativedelta(fecha_aniversario, fecha_ingreso).years

        # Ganan 15 días fijos. A partir de cumplir 5 años (al iniciar su año 6), ganan 1 día extra
        base_days = Decimal('15.0')
        dias_extra = Decimal('0.0')

        if anios_cumplidos >= 5:
            years_bonus = min(anios_cumplidos - 4, 15)  # Tope legal suele ser 15 días extra (máximo 30 total)
            dias_extra = Decimal(str(years_bonus))

        return base_days + dias_extra

    return Decimal('15.0')  # Por defecto si es otro contrato


def get_employee_vacation_entitlement(employee, target_year):
    """
    Retorna el número máximo de días de vacación para un empleado en un año dado.
    - Servidor LOSEP (Nombramiento / Contrato Ocasional): 30 días.
    - Obrero / Código del Trabajo: 15 días base + 1 día adicional por cada año
      a partir del sexto año de servicio (cumplidos 5 años completos).
    """
    # 1. Obtener el régimen laboral o estado de contratación
    regime_code = ''
    employment_status = getattr(employee, 'employment_status', None)
    if employment_status:
        regime_code = (getattr(employment_status, 'code', '') or getattr(employment_status, 'name', '')).upper()

    # También verificar si tiene contrato laboral registrado
    current_contract = getattr(employee, 'current_contract', None)
    if not regime_code and current_contract and hasattr(current_contract, 'regime'):
        regime_code = (getattr(current_contract.regime, 'code', '') or getattr(current_contract.regime, 'name',
                                                                               '')).upper()

    # Si es Código del Trabajo / Obrero / Trabajador
    is_codigo_trabajo = any(k in regime_code for k in ['TRABAJADOR', 'OBRERO', 'CODIGO_TRABAJO', 'CÓDIGO', 'CT'])

    if not is_codigo_trabajo:
        return 30

    # 2. Código del Trabajo: 15 días base
    base_days = 15
    hire_date = getattr(employee, 'entry_date', None) or getattr(employee, 'hire_date', None)

    # Si no tiene fecha de ingreso registrada en la ficha
    if not hire_date:
        return base_days

    # Fecha de corte al 31 de diciembre del año del cronograma planificado
    eval_date = date(int(target_year), 12, 31)

    if hire_date > eval_date:
        return 0

    # Calcular años completos de servicio cumplidos
    years_of_service = relativedelta(eval_date, hire_date).years

    # Ley Código del Trabajo Art. 69:
    # "Los trabajadores que hubieren prestado servicios durante más de cinco años
    # tendrán derecho a gozar adicionalmente de un día de vacación por cada uno de
    # los años excedentes"
    # Años 1 a 5: 15 días
    # Año 6 (5 años completos cumplidos): 15 + 1 = 16 días
    # Año 7 (6 años completos cumplidos): 15 + 2 = 17 días
    if years_of_service >= 5:
        additional_days = years_of_service - 5
        # El tope máximo por ley suele ser 30 días
        return min(base_days + additional_days, 30)

    return base_days


import math
from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from contract.models import ManagementPeriod


def get_real_entry_date(employee):
    """
    Obtiene la fecha de ingreso oficial del empleado:
    1. Expediente Institucional (institutional_data.entry_date).
    2. Contrato o Nombramiento vigente (FIRMADO, ACTIVO o sin fecha fin).
    """
    inst_data = getattr(employee, 'institutional_data', None)
    if inst_data and getattr(inst_data, 'entry_date', None):
        return inst_data.entry_date

    # Contrato vigente: ya sea con estado FIRMADO, ACTIVO o end_date None
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


def calculate_available_days_for_month(employee, plan_year, target_month):
    """
    Calcula los días de vacación proporcionales disponibles para un funcionario.

    Regla:
    - LOSEP: 2.5 días por cada mes laborado (Tope 30 días).
    - Código del Trabajo: 1.25 días por cada mes laborado (Tope 15 + extras).

    Ejemplo real (Jason Cabrera):
      Ingreso: 02/02/2026. Plan: 2027. Mes evaluado: Enero (1).
      - Meses laborados en 2026 (Febrero a Diciembre): 11 meses.
      - Días generados al 1 de Enero de 2027: 11 * 2.5 = 27.5 días.
    """
    entry_date = get_real_entry_date(employee)
    is_ct, base_annual, monthly_factor = get_vacation_regime_info(employee)

    # 1. Si no tiene fecha de ingreso registrada, asume derecho completo
    if not entry_date:
        return base_annual, base_annual, False, f"{base_annual}"

    plan_year = int(plan_year)
    target_month = int(target_month)

    # 2. Techo legal máximo para el año del plan
    if is_ct:
        plan_end = date(plan_year, 12, 31)
        years_completed = relativedelta(plan_end, entry_date).years
        bonus = max(0, years_completed - 4) if years_completed >= 5 else 0
        ceiling_days = min(15 + bonus, 30)
    else:
        ceiling_days = 30

    # 3. Caso: Más de 1 año cumplido ANTES de iniciar el año del plan
    # (Ejemplo: ingresó en 2025 o antes, y el plan es 2027)
    plan_start = date(plan_year, 1, 1)
    if relativedelta(plan_start, entry_date).years >= 1:
        return ceiling_days, ceiling_days, False, f"{ceiling_days}"

    # 4. Cálculo de meses trabajados acumulados al inicio del mes evaluado
    # Normalizamos el mes de inicio: si ingresó cualquier día de ese mes (ej: día 2),
    # ese mes se considera trabajado si el mes ya concluyó.
    entry_year = entry_date.year
    entry_month = entry_date.month

    # Si la fecha de ingreso es posterior al mes que se está evaluando:
    if (entry_year > plan_year) or (entry_year == plan_year and entry_month > target_month):
        return 0, ceiling_days, True, "0"

    # Conteo exacto de meses completos transcurridos entre (entry_year, entry_month)
    # y el 1ro del mes evaluado (plan_year, target_month)
    total_months_worked = (plan_year - entry_year) * 12 + (target_month - entry_month)

    # Si ingresó después del día 15 del mes de entrada, se le podría descontar medio mes,
    # pero bajo la norma habitual de Talento Humano si ingresó a inicios de mes (ej: día 2),
    # se computa el mes completo.
    if total_months_worked <= 0:
        return 0, ceiling_days, True, "0"

    # Multiplicar meses por factor (2.5 en LOSEP, 1.25 en CT)
    raw_accrued = total_months_worked * monthly_factor

    # Tope máximo estricto: nunca superar el ceiling legal
    accrued = min(raw_accrued, float(ceiling_days))

    # Formatear el valor visual
    if accrued % 1 == 0:
        display_val = f"{int(accrued)}"
    else:
        display_val = f"{accrued:.1f}"

    allowed_int = math.floor(accrued)
    is_proportional = (allowed_int < ceiling_days)

    return allowed_int, ceiling_days, is_proportional, display_val


def get_vacation_regime_info(employee):
    """
    Determina si el empleado pertenece al Código del Trabajo (15 días) o a la LOSEP (30 días).
    """
    regime_name = ""
    regime_code = ""

    # Buscar contrato vigente (excluyendo FINALIZADOS)
    active_contract = ManagementPeriod.objects.filter(
        employee=employee
    ).exclude(
        status__code='FINALIZADO'
    ).exclude(
        contract_type__code='SERVICIOS_PROFESIONALES'
    ).select_related('contract_type__labor_regime').order_by('-start_date').first()

    if active_contract and active_contract.contract_type:
        c_type = active_contract.contract_type
        if c_type.labor_regime:
            regime_code = (c_type.labor_regime.code or '').upper()
            regime_name = (c_type.labor_regime.name or '').upper()
        else:
            regime_code = (c_type.code or '').upper()
            regime_name = (c_type.name or '').upper()

    if not regime_code and not regime_name and employee.employment_status:
        regime_code = (employee.employment_status.code or '').upper()
        regime_name = (employee.employment_status.name or '').upper()

    combined_text = f"{regime_code} {regime_name}".strip()

    # Si es LOSEP / Ocasional / Nombramiento -> 30 días
    if 'LOSEP' in combined_text or 'NOMBRAMIENTO' in combined_text or 'OCASIONAL' in combined_text:
        return False, 30, 2.50

    ct_keywords = ['CODIGO DEL TRABAJO', 'CÓDIGO DEL TRABAJO', 'CODIGO_TRABAJO', 'OBRERO', 'TRABAJADOR']
    if any(keyword in combined_text for keyword in ct_keywords):
        return True, 15, 1.25

    return False, 30, 2.50


def resolve_scheduling_hierarchy(user, requested_unit_id=None):
    """
    Determina la unidad principal de planificación y todos sus descendientes.
    1. Si un administrador solicita un 'unit_id', lo respeta.
    2. Si es un usuario regular (secretaria/jefatura), busca su unidad y
       asciende hasta la dependencia que tenga is_main_unit=True.
    3. Retorna la unidad principal y la lista completa de IDs (ella + todas sus hijas).
    """
    base_unit = None

    if requested_unit_id and (user.is_staff or user.has_perm('vacation.change_vacationscheduleplan')):
        base_unit = AdministrativeUnit.objects.filter(pk=requested_unit_id, is_active=True).first()
    else:
        user_emp = getattr(user, 'person', None)
        user_emp = getattr(user_emp, 'employee_profile', None) if user_emp else None

        if user_emp and user_emp.area:
            # Ascender hasta la dependencia marcada como principal
            base_unit = user_emp.area.get_scheduling_root_unit()

    if not base_unit:
        # Fallback a la primera unidad principal del sistema o raíz
        base_unit = AdministrativeUnit.objects.filter(
            is_active=True, is_main_unit=True
        ).first() or AdministrativeUnit.objects.filter(
            is_active=True, parent__isnull=True
        ).first()

    # Obtener la unidad principal y todas sus subdependencias recursivamente
    unit_ids = []
    if base_unit:
        unit_ids = [base_unit.id]
        descendants = [base_unit]
        while descendants:
            curr = descendants.pop(0)
            children = list(AdministrativeUnit.objects.filter(parent=curr, is_active=True))
            for child in children:
                unit_ids.append(child.id)
                descendants.append(child)

    return base_unit, unit_ids
