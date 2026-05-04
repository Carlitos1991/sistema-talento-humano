import psycopg2
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from employee.models import Employee
from core.models import User
# Ajusta los imports según tu app
from actions.models import PersonnelAction, ActionType, ActionMovement

class Command(BaseCommand):
    help = 'Migración de Acciones de Personal y sus Movimientos'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, required=True)
        parser.add_argument('--mes', type=int, help='Opcional (1-12)')

    def limpiar_monto(self, valor_texto):
        """Convierte CharField ('$ 1,200.50' o '1200,50') a Decimal"""
        if not valor_texto:
            return Decimal('0.00')
        try:
            # Eliminar símbolos de moneda y limpiar comas/puntos
            limpio = re.sub(r'[^\d,\.]', '', str(valor_texto))
            if ',' in limpio and '.' in limpio:
                limpio = limpio.replace(',', '') # 1,200.50 -> 1200.50
            elif ',' in limpio:
                limpio = limpio.replace(',', '.') # 1200,50 -> 1200.50
            return Decimal(limpio)
        except Exception:
            return Decimal('0.00')

    def handle(self, *args, **options):
        anio, mes = options['anio'], options['mes']

        # --- MAPEOS ---
        MAPEO_TIPO_ACCION = {
            1: 1,
            # Llenar según los resultados de la auditoría
        }

        # En SIGETH 1 las firmas vienen por ID de Authority.
        # Si no tienes las equivalencias de usuarios en SIGETH 2, puedes definir un admin por defecto.
        USUARIO_SISTEMA_ID = User.objects.filter(is_active=True).first().id # ID de respaldo

        cedulas_faltantes = set()
        tipos_no_mapeados = set()
        migrados, duplicados, saltados, total_analizados = 0, 0, 0, 0

        db_config = settings.DATABASES['old_db']

        try:
            self.stdout.write(self.style.SUCCESS(f"🚀 Iniciando migración de Acciones: Año {anio}"))
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # Hacemos un JOIN con History_Actions para traer la info de movimiento en la misma consulta
                sql = """
                      SELECT per.cedula, 
                             pa.type_of_action_id, 
                             pa.number, 
                             pa.explanation,
                             pa.date_issue, 
                             pa.date_valid, 
                             pa.registered, 
                             pa.date_register,
                             ha.remuneration_actual, 
                             ha.remuneration_new, 
                             ha.place_work_new
                      FROM app_personnelaction pa
                      INNER JOIN employee_employee e ON pa.employee_id = e.id
                      INNER JOIN person_person per ON e.person_id = per.id
                      LEFT JOIN app_history_actions ha ON ha.personnel_action_id = pa.id
                      WHERE EXTRACT(YEAR FROM pa.date_issue) = %s
                      """
                params = [anio]
                if mes:
                    sql += " AND EXTRACT(MONTH FROM pa.date_issue) = %s"
                    params.append(mes)

                cursor.execute(sql, params)

                for row in cursor.fetchall():
                    total_analizados += 1
                    (cedula, id_tipo_old, numero_accion, explicacion,
                     fecha_emision, fecha_vigente, registrado, fecha_registro,
                     rmu_actual, rmu_nuevo, lugar_trabajo) = row

                    id_tipo_nuevo = MAPEO_TIPO_ACCION.get(id_tipo_old)
                    empleado = Employee.objects.filter(person__document_number=cedula).first()

                    if not empleado or not id_tipo_nuevo:
                        saltados += 1
                        if not empleado: cedulas_faltantes.add(cedula)
                        if not id_tipo_nuevo: tipos_no_mapeados.add(str(id_tipo_old))
                        continue

                    # Detección de duplicados por número de acción (que ahora es unique=True en destino)
                    if PersonnelAction.objects.filter(number=numero_accion).exists():
                        duplicados += 1
                        continue

                    try:
                        with transaction.atomic():
                            # 1. Crear Cabecera (PersonnelAction)
                            nueva_accion = PersonnelAction.objects.create(
                                employee=empleado,
                                action_type_id=id_tipo_nuevo,
                                number=numero_accion,
                                explanation=explicacion,
                                date_issue=fecha_emision,
                                date_effective=fecha_vigente,
                                is_registered=registrado,
                                date_registered=fecha_registro,
                                created_by_id=USUARIO_SISTEMA_ID,
                                authority_1_id=USUARIO_SISTEMA_ID # Usamos el de respaldo para evitar crasheos FK
                            )

                            # 2. Crear Detalle de Movimiento (ActionMovement)
                            # Nota: Puestos y Unidades (FK) se dejan en None de momento si en el origen eran simples strings.
                            # Si tienes catálogo para cruzar, habría que hacer un mapeo extra aquí.
                            ActionMovement.objects.create(
                                personnel_action=nueva_accion,
                                previous_remuneration=self.limpiar_monto(rmu_actual),
                                new_remuneration=self.limpiar_monto(rmu_nuevo),
                                location_text=lugar_trabajo
                            )

                            migrados += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error en acción {numero_accion} (Ced: {cedula}): {e}"))
                        saltados += 1

                    self.stdout.write(f"⏳ Analizando... {total_analizados}", ending='\r')

            conn.close()

            # --- REPORTE FINAL ---
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS(f"🏁 RESUMEN FINAL MIGRACIÓN ACCIONES"))
            self.stdout.write("=" * 60)
            self.stdout.write(f"📊 Analizados en BD antigua:        {total_analizados}")
            self.stdout.write(f"✅ Acciones + Movimientos creados:  {migrados}")
            self.stdout.write(f"⚠️  Acciones duplicadas (omitidas):  {duplicados}")
            self.stdout.write(f"✖  Saltados (errores/faltantes):    {saltados}")
            self.stdout.write("=" * 60 + "\n")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Fallo crítico: {e}"))