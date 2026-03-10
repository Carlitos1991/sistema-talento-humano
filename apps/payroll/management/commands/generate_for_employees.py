from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Genera rol para empleados indicados: --employees 5828,5849 --period-id 12 (opcional)'

    def add_arguments(self, parser):
        parser.add_argument('--employees', required=True, help='Lista separada por comas de employee IDs')
        parser.add_argument('--period-id', type=int, help='ID de PayrollPeriod (si no se indica, se usa el último)')

    def handle(self, *args, **options):
        from payroll.models import PayrollPeriod
        from payroll.services import PayrollCalculatorService
        from employee.models import Employee

        emp_arg = options.get('employees')
        if not emp_arg:
            self.stdout.write(self.style.ERROR('Debe indicar --employees'))
            return

        emp_ids = [int(x.strip()) for x in emp_arg.split(',') if x.strip()]

        period_id = options.get('period_id')
        if period_id:
            period = PayrollPeriod.objects.filter(pk=period_id).first()
            if not period:
                self.stdout.write(self.style.ERROR(f'Periodo id={period_id} no encontrado'))
                return
        else:
            period = PayrollPeriod.objects.order_by('-year', '-id').first()
            if not period:
                self.stdout.write(self.style.ERROR('No hay periodos definidos en la base de datos'))
                return

        employees = list(Employee.objects.filter(id__in=emp_ids))
        if not employees:
            self.stdout.write(self.style.ERROR('No se encontraron empleados para los IDs proporcionados'))
            return

        # Preparar pares (employee, worked_days) usando days completos del periodo
        pairs = [(e, period.working_days) for e in employees]

        svc = PayrollCalculatorService(period, employees)
        try:
            svc.generate_for_selected(pairs)
            self.stdout.write(self.style.SUCCESS(f'Generación completada para empleados: {emp_ids} en periodo {period}'))
        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.stdout.write(self.style.ERROR(f'Error durante generación: {ex}'))
