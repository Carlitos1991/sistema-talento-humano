import psycopg2
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from django.conf import settings
from employee.models import Employee
from schedule.models import Schedule, EmployeeScheduleHistory

User = get_user_model()


class Command(BaseCommand):
    help = 'Migración de historial buscando empleados por Cédula (Identificación)'

    def handle(self, *args, **options):
        # --- 1. CONFIGURACIÓN DE MAPEOS ---
        MAPEO_HORARIOS = {
            1: 1, 2: 1, 3: 1, 4: 2, 7: 1, 8: 2, 9: 1, 10: 4, 11: 5, 12: 6, 13: 7, 14: 8, 15: 9, 16: 10, 18: 11, 20: 12,
            27: 8
        }

        MAPEO_USUARIOS = {
            'JESSICA LOAIZA  - 0705740082': '1104898679',
            'ALBA BEATRIZ JARAMILLO JUMBO - 1103419295': '1103419295',
            'GABRIELA YESENIA MERCHAN FLORES': '1105127250',
            'VERONICA LUCIA LOAIZA CASTILLO - 1103657621': '1103657621',
            'SILVANA EUGENIA JARAMILLO IDROBO - 1102111752': '1102111752',
            'SILVANA EUGENIA JARAMILLO IDROBO': '1102111752',
            'ANA CRISTINA ERAZO JARAMILLO': '1104065568',
            'ANA LUCIA GONZALEZ MINCHALO - 1104479900': '1104479900',
            'ANGEL MEDARDO AMAY ORTIZ - 1103713051': '1103713051',
            'JOSE ANTONIO PALACIO EGUIGUREN': '1104879117',
            'JUAN CARLOS SAA SOTOMAYOR': '1102943576',
            'MARCO OSWALDO SACTA OCHOA - 1102936653': '1102936653',
            'MARIA JOSE CASTRO CELI': '1104860141',
            'MARIA VERONICA SOLANO DE LA SALA LOZANO - 0703172817': '0703172817',
        }

        # Contadores
        total_analizados = 0
        migrados_nuevos = 0
        duplicados_actualizados = 0
        errores_emp = 0
        errores_horario = 0

        cedulas_faltantes = set()
        usuarios_en_fallback = set()

        self.stdout.write(self.style.SUCCESS('🚀 Iniciando migración basada en Cédulas...'))
        db_config = settings.DATABASES['old_db']

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )
            cur = conn.cursor()

            # SQL para traer historial con cédula del empleado
            query = """
                    SELECT h.employee_id, \
                           h.schedule_id, \
                           h.date_of_assignment, \
                           h.user_change, \
                           h.reason, \
                           h.status, \
                           p.cedula -- Campo clave para buscar en el nuevo sistema
                    FROM employee_employeeschedulehistory h
                             LEFT JOIN employee_employee e ON h.employee_id = e.id
                             LEFT JOIN person_person p ON e.person_id = p.id \
                    """
            cur.execute(query)
            rows = cur.fetchall()

            with transaction.atomic():
                for row in rows:
                    total_analizados += 1
                    old_emp_id, old_sched_id, old_date, old_user_txt, old_reason, old_status, old_cedula = row

                    # --- A. BUSCAR EMPLEADO POR CÉDULA (Más seguro que por ID) ---
                    if not old_cedula:
                        errores_emp += 1
                        continue

                    # Buscamos en el nuevo sistema al empleado que tenga esa cédula
                    empleado = Employee.objects.filter(person__document_number=old_cedula.strip()).first()

                    if not empleado:
                        cedulas_faltantes.add(str(old_cedula))
                        errores_emp += 1
                        continue

                    # --- B. MAPEO DE HORARIO ---
                    nuevo_sched_id = MAPEO_HORARIOS.get(old_sched_id)
                    if not nuevo_sched_id:
                        errores_horario += 1
                        continue

                    horario_obj = Schedule.objects.filter(id=nuevo_sched_id).first()
                    if not horario_obj:
                        errores_horario += 1
                        continue

                    # --- C. RESOLUCIÓN DE USUARIO (Fallback ID 3) ---
                    username_nuevo = MAPEO_USUARIOS.get(old_user_txt, old_user_txt)
                    creador = User.objects.filter(username=username_nuevo).first()
                    if not creador:
                        creador = User.objects.filter(id=3).first() or User.objects.filter(is_superuser=True).first()
                        usuarios_en_fallback.add(old_user_txt)

                    # --- D. GUARDAR / ACTUALIZAR ---
                    fecha_inicio = old_date.date() if isinstance(old_date, datetime.datetime) else old_date
                    estado_logico = bool(old_status)

                    history, created = EmployeeScheduleHistory.objects.update_or_create(
                        employee=empleado,
                        schedule=horario_obj,
                        start_date=fecha_inicio,
                        defaults={
                            'reason': old_reason or "Migración Historial SIGETH",
                            'created_by': creador,
                            'is_active': estado_logico,
                            'is_current': estado_logico
                        }
                    )

                    if created:
                        migrados_nuevos += 1
                    else:
                        duplicados_actualizados += 1

                    if total_analizados % 100 == 0:
                        self.stdout.write(f"⏳ Procesando... {total_analizados}", ending='\r')

            conn.close()

            # --- REPORTE FINAL ---
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.SUCCESS(f"🏁 RESULTADO DE LA MIGRACIÓN"))
            self.stdout.write("=" * 70)
            self.stdout.write(f"📊 Registros analizados:       {total_analizados}")
            self.stdout.write(f"✅ Migrados (Nuevos):          {migrados_nuevos}")
            self.stdout.write(f"⚠️  Duplicados (Actualizados):  {duplicados_actualizados}")
            self.stdout.write(f"❌ Saltados por falta de Emp:  {errores_emp}")
            self.stdout.write(f"❌ Saltados por Horario:       {errores_horario}")
            self.stdout.write("-" * 70)

            if cedulas_faltantes:
                self.stdout.write(self.style.ERROR(f"📋 CÉDULAS NO ENCONTRADAS EN SIGETH (Debes crearlos):"))
                self.stdout.write(f"   {', '.join(sorted(list(cedulas_faltantes)))}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERROR: {e}"))