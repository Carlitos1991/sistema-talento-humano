# vacation/services.py
import math
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

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
    Obtiene la fecha de ingreso real del empleado:
    1. Si tiene contrato/nombramiento en ManagementPeriod, toma su start_date más reciente activo.
    2. Si tiene fecha en institutional_data previa, la respeta.
    """
    # Contrato o Nombramiento vigente
    active_contract = ManagementPeriod.objects.filter(
        employee=employee,
        status__code='ACTIVO'
    ).exclude(
        contract_type__code='SERVICIOS_PROFESIONALES'
    ).order_by('-start_date').first()

    if active_contract and active_contract.start_date:
        return active_contract.start_date

    # Fallback al contrato más reciente si no está marcado como ACTIVO
    last_contract = ManagementPeriod.objects.filter(
        employee=employee
    ).exclude(
        contract_type__code='SERVICIOS_PROFESIONALES'
    ).order_by('-start_date').first()

    if last_contract and last_contract.start_date:
        return last_contract.start_date

    inst_data = getattr(employee, 'institutional_data', None)
    if inst_data and getattr(inst_data, 'entry_date', None):
        return inst_data.entry_date

    return getattr(employee, 'entry_date', None) or getattr(employee.person, 'entry_date', None)


def get_vacation_regime_info(employee):
    """
    LOSEP: 30 días anuales (2.5 días/mes)
    Código del Trabajo: 15 días anuales (1.25 días/mes)
    """
    regime_texts = []
    if employee.employment_status:
        regime_texts.append(str(employee.employment_status.code or ''))
        regime_texts.append(str(employee.employment_status.name or ''))

    active_contract = ManagementPeriod.objects.filter(
        employee=employee
    ).select_related('contract_type__labor_regime').order_by('-start_date').first()

    if active_contract and active_contract.contract_type:
        c_type = active_contract.contract_type
        regime_texts.append(str(c_type.code or ''))
        regime_texts.append(str(c_type.name or ''))
        if c_type.labor_regime:
            regime_texts.append(str(c_type.labor_regime.code or ''))
            regime_texts.append(str(c_type.labor_regime.name or ''))

    full_check = ' '.join(regime_texts).upper()
    is_ct = any(k in full_check for k in ['TRABAJADOR', 'OBRERO', 'CODIGO_TRABAJO', 'CÓDIGO', 'CT'])

    if is_ct:
        return True, 15, 1.25
    return False, 30, 2.50


def calculate_available_days_for_month(employee, plan_year, target_month):
    """
    Calcula los días acumulados disponibles para tomar al 1ro del mes evaluado.
    Ej: Ingreso 01/06/2026. Plan 2027.
    - Enero 2027: 7 meses cumplidos = 7 * 2.5 = 17.5 días disponibles.
    - Febrero 2027: 8 meses cumplidos = 8 * 2.5 = 20.0 días disponibles.
    - Marzo 2027: 9 meses cumplidos = 9 * 2.5 = 22.5 días disponibles.
    """
    entry_date = get_real_entry_date(employee)
    is_ct, base_annual, monthly_factor = get_vacation_regime_info(employee)

    if not entry_date:
        return base_annual, base_annual, False, f"{base_annual}"

    eval_date = date(int(plan_year), int(target_month), 1)

    if entry_date >= eval_date:
        return 0, base_annual, True, "0"

    diff = relativedelta(eval_date, entry_date)
    total_months_worked = diff.years * 12 + diff.months

    # Si ya tenía más de 1 año cumplido ANTES de iniciar el año del plan (ej. ingreso en 2025 o antes):
    # Ya tiene su derecho pleno anual completo (30 o 15+)
    plan_start = date(int(plan_year), 1, 1)
    diff_at_start = relativedelta(plan_start, entry_date)

    if diff_at_start.years >= 1:
        if is_ct:
            bonus = max(0, diff_at_start.years - 5) if diff_at_start.years >= 5 else 0
            full_ct = min(15 + bonus, 30)
            return full_ct, full_ct, False, f"{full_ct}"
        return 30, 30, False, "30"

    # CASO PROPORCIONAL (Entró en el año previo o en el año en curso):
    # Meses cumplidos a la fecha solicitada * factor mensual
    accrued = total_months_worked * monthly_factor

    # Formato visual: si tiene .5 muestra 17.5, si es entero muestra 20
    if accrued % 1 == 0:
        display_val = f"{int(accrued)}"
    else:
        display_val = f"{accrued:.1f}"

    allowed_int = math.floor(accrued)
    return allowed_int, base_annual, True, display_val
