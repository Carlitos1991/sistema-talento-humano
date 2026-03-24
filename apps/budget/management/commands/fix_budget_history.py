from django.core.management.base import BaseCommand
from django.db import transaction
from budget.models import BudgetAssignmentHistory
from employee.models import Employee


class Command(BaseCommand):
    help = 'Corrige historiales de partidas duplicadas, cerrando las antiguas y dejando solo la más reciente abierta.'

    def handle(self, *args, **options):
        # Buscamos solo empleados que tengan algún historial de partida
        empleados = Employee.objects.filter(budget_history__isnull=False).distinct()

        registros_corregidos = 0
        empleados_afectados = 0

        self.stdout.write("Iniciando escaneo de historiales de partidas duplicadas...")

        for empleado in empleados:
            # Traemos el historial de partidas del empleado, de la más nueva a la más vieja
            historial = BudgetAssignmentHistory.objects.filter(employee=empleado).order_by('-start_date', '-id')

            if historial.count() > 1:
                with transaction.atomic():
                    # 1. La partida más reciente (la vigente)
                    partida_actual = historial[0]

                    if not partida_actual.is_current or partida_actual.end_date is not None:
                        partida_actual.is_current = True
                        partida_actual.end_date = None
                        partida_actual.save()

                    # 2. Las partidas antiguas (del segundo en adelante)
                    arreglado_para_este_empleado = False

                    for i in range(1, len(historial)):
                        partida_antigua = historial[i]
                        partida_siguiente = historial[i - 1]  # La partida que lo reemplazó

                        cambio = False

                        # Si quedó marcada como actual por error, la desmarcamos
                        if partida_antigua.is_current:
                            partida_antigua.is_current = False
                            cambio = True

                        # Si se quedó sin fecha de fin, la cerramos con la fecha de inicio de la nueva
                        if partida_antigua.end_date is None:
                            partida_antigua.end_date = partida_siguiente.start_date
                            partida_antigua.observation = "Cierre automático por nueva asignación de partida"
                            cambio = True

                        if cambio:
                            partida_antigua.save()
                            registros_corregidos += 1
                            arreglado_para_este_empleado = True

                    if arreglado_para_este_empleado:
                        empleados_afectados += 1

        self.stdout.write(self.style.SUCCESS(f"\n✅ AUDITORÍA DE PARTIDAS FINALIZADA"))
        self.stdout.write(f"------------------------------------------------")
        self.stdout.write(f"Empleados con conflictos resueltos: {empleados_afectados}")
        self.stdout.write(f"Partidas históricas cerradas:       {registros_corregidos}")
        self.stdout.write(f"------------------------------------------------\n")