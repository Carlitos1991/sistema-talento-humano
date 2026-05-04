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
    help = 'Migración de historial de horarios con reporte de duplicados, cédulas y horarios por estado'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, help='Opcional: Filtrar por año')

    def handle(self, *args, **options):
        anio = options['anio']

        # --- 1. CONFIGURACIÓN DE MAPEOS ---
        MAPEO_HORARIOS = {
            1: 1, 2: 1, 3: 1, 4: 2, 7: 1, 8: 2, 9: 1, 10: 4, 11: 5, 12: 6, 13: 7, 14: 8, 15: 9, 16: 10, 18: 11, 20: 12, 27: 8
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

        # Contadores de control
        total_analizados = 0
        migrados_nuevos = 0
        duplicados_actualizados = 0
        saltados_errores = 0

        # Colecciones para el reporte
        cedulas_faltantes = set()
        sched_no_map_activos = set()  # Horarios en la vieja DB que están con status=True
        sched_no_map_inactivos = set()  # Horarios en la vieja DB que están con status=False
        usuarios_en_fallback = set()

        self.stdout.write(self.style.SUCCESS('🚀 Iniciando migración avanzada de Historial de Horarios...'))

        db_config = settings.DATABASES['old_db']

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )
            cur = conn.cursor()

            # --- 2. SQL CON JOIN PARA TRAER CÉDULA (identification) ---
            query = """
                    SELECT h.employee_id, \
                           h.schedule_id, \
                           h.date_of_assignment, \
                           h.user_change, \
                           h.reason, \
                           h.status, \
                           p.cedula
                    FROM employee_employeeschedulehistory h
                             LEFT JOIN employee_employee e ON h.employee_id = e.id
                             LEFT JOIN person_person p ON e.person_id = p.id \
                    """
            if anio:
                query += f" WHERE EXTRACT(YEAR FROM h.date_of_assignment) = {anio}"

            cur.execute(query)
            rows = cur.fetchall()

            with transaction.atomic():
                for row in rows:
                    total_analizados += 1
                    old_emp_id, old_sched_id, old_date, old_user_txt, old_reason, old_status, old_cedula = row

                    # A. Buscar Empleado (Si no existe, guardamos la CÉDULA para el reporte)
                    try:
                        empleado = Employee.objects.get(id=old_emp_id)
                    except Employee.DoesNotExist:
                        cedulas_faltantes.add(str(old_cedula or f"ID:{old_emp_id}"))
                        saltados_errores += 1
                        continue

                    # B. Clasificación de Horarios No Mapeados
                    nuevo_sched_id = MAPEO_HORARIOS.get(old_sched_id)
                    if not nuevo_sched_id:
                        if old_status:  # Si el registro es activo en la vieja DB
                            sched_no_map_activos.add(old_sched_id)
                        else:
                            sched_no_map_inactivos.add(old_sched_id)
                        saltados_errores += 1
                        continue

                    horario_obj = Schedule.objects.filter(id=nuevo_sched_id).first()
                    if not horario_obj:
                        saltados_errores += 1
                        continue

                    # C. Resolución de Usuario (Fallback ID 3)
                    username_nuevo = MAPEO_USUARIOS.get(old_user_txt, old_user_txt)
                    creador = User.objects.filter(username=username_nuevo).first()

                    if not creador:
                        creador = User.objects.filter(id=3).first()
                        if not creador:  # Fallback de emergencia si el ID 3 no existe
                            creador = User.objects.filter(is_superuser=True).first()
                        usuarios_en_fallback.add(old_user_txt)

                    # D. Preparar estado y fecha
                    estado_logico = bool(old_status)
                    fecha_inicio = old_date.date() if isinstance(old_date, datetime.datetime) else old_date

                    # E. GUARDAR O ACTUALIZAR (Detección de duplicidad)
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

            # --- 3. REPORTE FINAL DETALLADO ---
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.SUCCESS(f"🏁 RESUMEN DE MIGRACIÓN DE HISTORIAL"))
            self.stdout.write("=" * 70)
            self.stdout.write(f"📊 Total analizados en DB Old:   {total_analizados}")
            self.stdout.write(self.style.SUCCESS(f"✅ Registros nuevos creados:    {migrados_nuevos}"))
            self.stdout.write(self.style.WARNING(f"⚠️  Duplicados (Actualizados):   {duplicados_actualizados}"))
            self.stdout.write(self.style.ERROR(f"✖  Saltados (Errores/Faltas):   {saltados_errores}"))
            self.stdout.write("-" * 70)

            if cedulas_faltantes:
                self.stdout.write(self.style.ERROR(f"❌ EMPLEADOS NO ENCONTRADOS (Cédulas):"))
                self.stdout.write(f"   {', '.join(sorted(list(cedulas_faltantes)))}")
                self.stdout.write(f"   (Total: {len(cedulas_faltantes)})")

            if sched_no_map_activos or sched_no_map_inactivos:
                self.stdout.write(self.style.NOTICE(f"📋 HORARIOS PENDIENTES DE MAPEAR (IDs antiguos):"))
                if sched_no_map_activos:
                    self.stdout.write(f"   🟢 ACTIVO en DB vieja: {list(sched_no_map_activos)}")
                if sched_no_map_inactivos:
                    self.stdout.write(f"   ⚪ INACTIVO en DB vieja: {list(sched_no_map_inactivos)}")

            if usuarios_en_fallback:
                self.stdout.write(self.style.NOTICE(f"👤 USUARIOS ASIGNADOS AL ID 3 (Fallback):"))
                self.stdout.write(f"   -> {', '.join(list(usuarios_en_fallback)[:15])}...")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ ERROR CRÍTICO: {e}"))
