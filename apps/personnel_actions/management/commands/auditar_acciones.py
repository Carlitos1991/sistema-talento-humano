import psycopg2
from django.core.management.base import BaseCommand
from django.conf import settings
from employee.models import Employee
from core.models import User
# Ajusta los imports según la ruta real de tu app en SIGETH 2
from personnel_actions.models import PersonnelAction, ActionType

class Command(BaseCommand):
    help = 'Auditoría de Acciones de Personal: Mapeo de tipos y validación de empleados'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, required=True)
        parser.add_argument('--mes', type=int, help='Opcional')

    def handle(self, *args, **options):
        anio, mes = options['anio'], options['mes']

        # --- MAPEO A AUDITAR ---
        # { ID_TIPO_ACCION_ORIGEN : ID_ACTIONTYPE_DESTINO }
        MAPEO_TIPO_ACCION = {
            2: 20,  # Ej: Vacaciones
        }

        tipos_encontrados = set()
        tipos_faltantes = set()
        cedulas_faltantes = set()

        ya_migrados, pendientes, total_analizados = 0, 0, 0
        db_config = settings.DATABASES['old_db']

        self.stdout.write(self.style.SUCCESS(f"🔍 Auditoría de Acciones de Personal: Año {anio}"))

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # OJO: Cambia "app_personnelaction" por el nombre real de tu tabla en la BD antigua
                sql = """
                      SELECT per.cedula, 
                             pa.type_of_action_id as id_old, 
                             ta.name as nombre_old,
                             pa.number, 
                             pa.date_issue
                      FROM app_personnelaction pa
                      INNER JOIN employee_employee e ON pa.employee_id = e.id
                      INNER JOIN person_person per ON e.person_id = per.id
                      LEFT JOIN app_typesofaction ta ON pa.type_of_action_id = ta.id
                      WHERE EXTRACT(YEAR FROM pa.date_issue) = %s
                      """
                params = [anio]
                if mes:
                    sql += " AND EXTRACT(MONTH FROM pa.date_issue) = %s"
                    params.append(mes)

                cursor.execute(sql, params)

                for row in cursor.fetchall():
                    total_analizados += 1
                    cedula, id_old, nombre_old, numero_accion, fecha_emision = row

                    # 1. VALIDAR MAPEO DE TIPOS
                    id_nuevo_mapeado = MAPEO_TIPO_ACCION.get(id_old)
                    tipo_nuevo_obj = None

                    if id_nuevo_mapeado:
                        tipo_nuevo_obj = ActionType.objects.filter(id=id_nuevo_mapeado).first()
                    else:
                        tipo_nuevo_obj = ActionType.objects.filter(name__iexact=nombre_old).first()

                    if tipo_nuevo_obj:
                        tipos_encontrados.add(f"{nombre_old} (ID: {id_old}) -> {tipo_nuevo_obj.name} (ID: {tipo_nuevo_obj.id})")
                    else:
                        tipos_faltantes.add(f"{nombre_old} (ID Origen: {id_old})")

                    # 2. VALIDAR EMPLEADO
                    if not Employee.objects.filter(person__document_number=cedula).exists():
                        cedulas_faltantes.add(cedula)

                    # 3. VERIFICAR SI YA SE MIGRÓ
                    if PersonnelAction.objects.filter(number=numero_accion, date_issue=fecha_emision).exists():
                        ya_migrados += 1
                    else:
                        pendientes += 1

            conn.close()

            # --- REPORTE FINAL ---
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.SUCCESS(f"🏁 REPORTE DE AUDITORÍA: ACCIONES DE PERSONAL"))
            self.stdout.write("=" * 70)

            self.stdout.write(self.style.SUCCESS("✅ TIPOS ENCONTRADOS:"))
            for mapping in sorted(tipos_encontrados) if tipos_encontrados else ["Ninguno."]:
                self.stdout.write(f"   {mapping}")

            self.stdout.write("-" * 70)
            if tipos_faltantes:
                self.stdout.write(self.style.ERROR("❌ TIPOS SIN DESTINO (Agrega a MAPEO_TIPO_ACCION):"))
                for t in sorted(tipos_faltantes):
                    self.stdout.write(f"   -> {t}")
                self.stdout.write("-" * 70)

            self.stdout.write(f"📊 Total analizados:  {total_analizados}")
            self.stdout.write(f"✅ Ya en SIGETH 2:    {ya_migrados}")
            self.stdout.write(f"⏳ Pendientes:         {pendientes}")
            if cedulas_faltantes:
                self.stdout.write(self.style.ERROR(f"👤 Empleados faltantes: {len(cedulas_faltantes)}"))
            self.stdout.write("=" * 70 + "\n")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))