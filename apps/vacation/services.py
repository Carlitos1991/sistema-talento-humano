# vacation/services.py
from dateutil.relativedelta import relativedelta
from decimal import Decimal


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