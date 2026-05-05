import psycopg2
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from employee.models import Employee
from core.models import User
# Rutas actualizadas según tu proyecto SIGETH 2
from personnel_actions.models import PersonnelAction, ActionType, ActionMovement

class Command(BaseCommand):
    help = 'Migración directa de Acciones de Personal: Unidades y Puestos como texto'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, required=True)
        parser.add_argument('--mes', type=int, help='Opcional (1-12)')

    def limpiar_monto(self, valor):
        if not valor:
            return Decimal('0.00')
        try:
            limpio = re.sub(r'[^\d,\.]', '', str(valor))
            if ',' in limpio and '.' in limpio:
                limpio = limpio.replace(',', '')
            elif ',' in limpio:
                limpio = limpio.replace(',', '.')
            return Decimal(limpio)
        except Exception:
            return Decimal('0.00')

    def convertir_booleano(self, valor):
        if valor in (True, 't', 'T', 'true', 'True', 1, '1'):
            return True
        return False

    def handle(self, *args, **options):
        anio, mes = options['anio'], options['mes']
        USER_ID_MIGRACION = 4 # ID fijo solicitado para firmas[cite: 6]

        # Mapeo de Tipos de Acción (Sigue siendo necesario por ser ForeignKey)
        MAPEO_ACCIONES = {
            20: 2,  # Ejemplo: Vacaciones[cite: 5]
            6: 4,  # Ejemplo: Encargo[cite: 5]
            16: 6,  # Ejemplo: Renuncia[cite: 5]
            19: 7,  # Ejemplo: Renuncia[cite: 5]
            22: 7,  # Ejemplo: Renuncia[cite: 5]
            28: 8,  # Ejemplo: Renuncia[cite: 5]
            14: 9,  # Ejemplo: Renuncia[cite: 5]
            12: 10,  # Ejemplo: Renuncia[cite: 5]
            18: 11,  # Ejemplo: Renuncia[cite: 5]
            24: 3,  # Ejemplo: Renuncia[cite: 5]
            17: 12,  # Ejemplo: Renuncia[cite: 5]
        }

        migrados, ya_existentes, saltados, total_procesados = 0, 0, 0, 0
        db_config = settings.DATABASES['old_db']

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # SQL para traer todos los campos de texto del historial[cite: 3]
                sql = """
                    SELECT per.cedula, pa.action_id, pa.number, pa.explanation, 
                           pa.date_issue, pa.date_valid, pa.registered, pa.date_register,
                           ha.remuneration_actual, ha.remuneration_new, 
                           ha.direction_actual, ha.direction_new,
                           ha.charge_actual, ha.charge_new,
                           ha.place_work_new
                    FROM actions_personnelaction pa
                    INNER JOIN employee_employee e ON pa.employee_id = e.id
                    INNER JOIN person_person per ON e.person_id = per.id
                    LEFT JOIN actions_history_actions ha ON ha.personnel_action_id = pa.id
                    WHERE EXTRACT(YEAR FROM pa.date_issue) = %s
                """
                params = [anio]
                if mes:
                    sql += " AND EXTRACT(MONTH FROM pa.date_issue) = %s"
                    params.append(mes)

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                self.stdout.write(f"Iniciando migración directa de {len(rows)} registros...")

                for row in rows:
                    total_procesados += 1
                    (cedula, id_act_old, num, exp, f_emision, f_vence, reg_old, f_reg_old,
                     r_old, r_new, u_ant, u_new, p_ant, p_new, lugar) = row

                    if PersonnelAction.objects.filter(number=num).exists():
                        ya_existentes += 1
                        continue

                    emp = Employee.objects.filter(person__document_number=cedula).first()
                    tipo_id = MAPEO_ACCIONES.get(id_act_old)

                    if not emp or not tipo_id:
                        saltados += 1
                        continue

                    try:
                        with transaction.atomic():
                            # 1. Cabecera[cite: 7]
                            nueva_pa = PersonnelAction.objects.create(
                                employee=emp,
                                action_type_id=tipo_id,
                                number=num,
                                explanation=exp or "Migración Histórica",
                                date_issue=f_emision,
                                date_effective=f_vence,
                                is_registered=self.convertir_booleano(reg_old),
                                date_registered=f_reg_old,
                                created_by_id=USER_ID_MIGRACION,
                                authority_1_id=USER_ID_MIGRACION
                            )

                            # 2. Movimiento: Migración directa a CharField[cite: 7]
                            ActionMovement.objects.create(
                                personnel_action=nueva_pa,
                                previous_unit=u_ant,
                                new_unit=u_new,
                                previous_position=p_ant,
                                new_position=p_new,
                                previous_remuneration=self.limpiar_monto(r_old),
                                new_remuneration=self.limpiar_monto(r_new),
                                location_text=lugar or u_new
                            )
                            migrados += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error en {num}: {str(e)}"))

            conn.close()
            self.stdout.write(self.style.SUCCESS(f"\n🏁 FINALIZADO: {migrados} migrados, {ya_existentes} ya existían."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Fallo crítico: {str(e)}"))