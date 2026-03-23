# vacation/management/commands/migrar_vacaciones.py
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F

from employee.models import Employee
from vacation.models import VacationPeriod, EmployeeVacationBalance, VacationHistory, VacationRequest
from permitrequest.models import PermitRequest, PermitType
from vacation.services import calcular_dias_ganados


class Command(BaseCommand):
    help = 'Automatiza la creación de periodos históricos y descuenta permisos/vacaciones migradas.'

    def handle(self, *args, **kwargs):
        hoy = datetime.date.today()
        empleados = Employee.objects.filter(is_active=True, person__is_active=True).select_related('employment_status')

        # Constantes de descuento extraídas de tus vistas
        FACTOR_DAY = Decimal('1.0')
        PROPORTIONAL_DAY = Decimal('0.4')
        FACTOR_HOUR = Decimal('0.125')
        FACTOR_MINUTE = Decimal('0.00208333')
        PROPORTIONAL_HOUR = Decimal('0.05')
        PROPORTIONAL_MINUTE = Decimal('0.00083333')

        for emp in empleados:
            try:
                # 1. Determinar Fecha de Ingreso y Régimen
                inst_data = getattr(emp, 'institutional_data', None)
                fecha_ingreso = getattr(inst_data, 'entry_date', None) or emp.date_joined

                if not fecha_ingreso:
                    self.stdout.write(self.style.WARNING(f"Saltando a {emp}: Sin fecha de ingreso."))
                    continue

                regimen = emp.employment_status.code if emp.employment_status else 'LOSEP'
                is_trabajador = 'TRABAJADOR' in regimen.upper()
                max_limit = Decimal('45.0') if is_trabajador else Decimal('60.0')

                with transaction.atomic():
                    # El empleado comienza su historia en su fecha de ingreso
                    current_aniversario = fecha_ingreso
                    last_balance = None

                    # Viajamos en el tiempo año por año hasta el día de hoy
                    while current_aniversario <= hoy:
                        next_aniversario = current_aniversario + relativedelta(years=1)

                        # 2. CREAR PERIODO DEL AÑO EN CURSO
                        nombre_periodo = f"{current_aniversario.year}-{next_aniversario.year}"
                        periodo, _ = VacationPeriod.objects.get_or_create(
                            name=nombre_periodo,
                            defaults={'is_active': (next_aniversario > hoy)}  # Activo si sigue vigente
                        )

                        # Verificar si ya generamos este balance antes para no duplicar
                        balance, created = EmployeeVacationBalance.objects.get_or_create(
                            employee=emp,
                            period=periodo,
                            defaults={
                                'is_active': True,
                                'total_days': Decimal('0'),
                                'additional_days': Decimal('0'),
                                'balance_days': Decimal('0')
                            }
                        )

                        if created:
                            # 3. MATEMÁTICA DEL BOLSILLO (Absorber año anterior)
                            if last_balance:
                                last_balance.is_active = False
                                last_balance.save()
                                saldo_anterior = last_balance.balance_days
                            else:
                                saldo_anterior = Decimal('0.0')

                            dias_ganados = calcular_dias_ganados(fecha_ingreso, current_aniversario, regimen)
                            saldo_calculado = saldo_anterior + dias_ganados

                            # Aplicar el tope legal (45 o 60)
                            dias_perdidos = max(Decimal('0'), saldo_calculado - max_limit)
                            saldo_final = min(saldo_calculado, max_limit)

                            # Actualizar el balance nuevo
                            balance.total_days = dias_ganados
                            balance.additional_days = saldo_anterior
                            balance.balance_days = saldo_final
                            balance.observation = f"Generación automática. Días perdidos por tope: {dias_perdidos}"
                            balance.save()

                        # 4. APLICAR DESCUENTOS DE ACCIONES Y PERMISOS DE ESE AÑO
                        # Buscamos todo lo que el empleado solicitó entre este aniversario y el siguiente

                        # A. Liquidaciones de Vacaciones (Acciones de Personal)
                        vacaciones = VacationRequest.objects.filter(
                            employee=emp, status='APPROVED', start_date__gte=current_aniversario,
                            start_date__lt=next_aniversario,
                            vacationhistory__isnull=True  # Solo las que no han sido descontadas
                        )

                        for vac in vacaciones:
                            descuento = Decimal(str(vac.days_quantity))

                            # Actualizamos balance
                            balance.balance_days -= descuento
                            balance.vacation_days += descuento
                            balance.save()

                            # Dejamos rastro en el historial
                            VacationHistory.objects.create(
                                vacation_balance=balance, vacation_request=vac,
                                value_discount=float(descuento), days_discount=float(descuento),
                                proportional_discount=0.0, hours_discount=0.0, minutes_discount=0.0,
                                observation=f"Migración: Descuento Vacación del {vac.start_date}",
                                created_by_id=1  # Usuario admin por defecto
                            )

                        # B. Permisos por Horas o Días
                        permisos = PermitRequest.objects.filter(
                            employee=emp, status='APPROVED', permit_type__name__icontains='Personal',
                            start_date__gte=current_aniversario, start_date__lt=next_aniversario,
                            vacationhistory__isnull=True
                        )

                        for perm in permisos:
                            if perm.days > 0:
                                val_base = Decimal(str(perm.days)) * FACTOR_DAY
                                val_prop = Decimal(str(perm.days)) * PROPORTIONAL_DAY
                            else:
                                val_base = (Decimal(str(perm.hours)) * FACTOR_HOUR) + (
                                            Decimal(str(perm.minutes)) * FACTOR_MINUTE)
                                val_prop = (Decimal(str(perm.hours)) * PROPORTIONAL_HOUR) + (
                                            Decimal(str(perm.minutes)) * PROPORTIONAL_MINUTE)

                            total_descuento = val_base + val_prop

                            balance.balance_days -= total_descuento
                            balance.permit_days += total_descuento
                            balance.save()

                            VacationHistory.objects.create(
                                vacation_balance=balance, permit_request=perm,
                                value_discount=float(val_base), proportional_discount=float(val_prop),
                                days_discount=float(perm.days) if perm.days > 0 else 0.0,
                                hours_discount=float(perm.hours) if not perm.days else 0.0,
                                minutes_discount=float(perm.minutes) if not perm.days else 0.0,
                                observation=f"Migración: Descuento Permiso del {perm.start_date}",
                                created_by_id=1
                            )

                        # Avanzamos al siguiente año
                        last_balance = balance
                        current_aniversario = next_aniversario

                self.stdout.write(self.style.SUCCESS(
                    f"Migrado exitosamente: {emp} | Saldo final: {last_balance.balance_days if last_balance else 0}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error con {emp}: {str(e)}"))