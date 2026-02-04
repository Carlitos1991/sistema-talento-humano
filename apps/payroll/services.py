from decimal import Decimal
from django.db import transaction
from .models import Payslip, PayslipItem, PayrollConstant, Income, Deduction


# from apps.economicdata.models import EconomicData (Asumiendo existencia)

class PayrollCalculatorService:
    def __init__(self, period, employees):
        self.period = period
        self.employees = employees

        # CARGA OPTIMIZADA DE CONSTANTES (Solo 1 consulta a BD)
        # Convertimos a diccionario para acceso O(1): {'SBU': 460.00, 'IESS_PER': 9.45}
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

        # 1. Instanciar Payslips en memoria
        for emp in self.employees:
            payslip_buffer.append(Payslip(
                employee=emp,
                period=self.period,
                worked_days=self.period.working_days
            ))

        with transaction.atomic():
            # Limpieza previa del periodo (para evitar duplicados si se regenera)
            Payslip.objects.filter(period=self.period).delete()

            # BULK INSERT (La clave de la velocidad)
            created_payslips = Payslip.objects.bulk_create(payslip_buffer)

            # Preparar buffers para items
            items_buffer = []
            payslips_to_update = []

            # Cargar Ingresos y Descuentos activos una sola vez
            active_incomes = list(Income.objects.filter(is_active=True))
            active_deductions = list(Deduction.objects.filter(is_active=True))

            # Obtener datos económicos (Sueldos) en una sola consulta para evitar N+1
            # salary_map = {ed.employee_id: ed.salary for ed in EconomicData.objects.filter(...)}
            # Simulación por si no tienes el modelo EconomicData a mano:
            salary_map = {emp.id: Decimal(500.00) for emp in self.employees}  # Reemplazar con lógica real

            # 2. Calcular valores
            for slip in created_payslips:
                salary = salary_map.get(slip.employee_id, Decimal(0))
                total_ing = Decimal(0)
                total_desc = Decimal(0)

                # --- Lógica de Ingresos ---
                for inc in active_incomes:
                    val = Decimal(0)
                    if inc.code == 'REMUNERACION':
                        val = (salary / 30) * slip.worked_days

                    # Ejemplo uso de constante nueva
                    elif inc.code == 'BONO_ANTIGUEDAD':
                        # val = salary * self.config.get('PCT_ANTIGUEDAD', 0)
                        pass

                    if val > 0:
                        items_buffer.append(PayslipItem(
                            payslip=slip, income_ref=inc, item_type='INCOME', value=val
                        ))
                        total_ing += val

                # --- Lógica de Descuentos ---
                for ded in active_deductions:
                    val = Decimal(0)
                    if ded.code == 'IESS_PER':
                        # Usamos la constante cargada dinámicamente
                        iess_pct = self.config.get('IESS_PER', Decimal(9.45))
                        val = total_ing * (iess_pct / 100)

                    if val > 0:
                        items_buffer.append(PayslipItem(
                            payslip=slip, deduction_ref=ded, item_type='DEDUCTION', value=val
                        ))
                        total_desc += val

                # Asignar totales
                slip.total_income = total_ing
                slip.total_deduction = total_desc
                slip.net_pay = total_ing - total_desc
                payslips_to_update.append(slip)

            # 3. Guardado Masivo de Detalles y Actualización de Cabeceras
            PayslipItem.objects.bulk_create(items_buffer)
            Payslip.objects.bulk_update(payslips_to_update, ['total_income', 'total_deduction', 'net_pay'])
