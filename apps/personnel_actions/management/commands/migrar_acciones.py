import psycopg2
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from employee.models import Employee
from core.models import User
from personnel_actions.models import PersonnelAction, ActionType, ActionMovement


class Command(BaseCommand):
    help = 'Migración directa de Acciones de Personal con Auditoría Detallada'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, required=True)
        parser.add_argument('--mes', type=int, help='Opcional (1-12)')

    def limpiar_monto(self, valor):
        if not valor: return Decimal('0.00')
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
        return valor in (True, 't', 'T', 'true', 'True', 1, '1')

    def handle(self, *args, **options):
        anio, mes = options['anio'], options['mes']
        USER_ID_MIGRACION = 4

        MAPEO_ACCIONES = {
            20: 2, 6: 4, 16: 6, 19: 7, 22: 7, 28: 8, 14: 9, 12: 10, 18: 11, 24: 3, 17: 12, 2: 5, 11: 1, 9: 13, 5: 14,
            7: 15, 10: 16, 3: 17, 8: 18, 15:19, 1:20
        }

        # Contadores de auditoría
        stats = {
            'migrados': 0,
            'ya_existentes': 0,
            'error_empleado': 0,
            'error_mapeo': 0,
            'error_db': 0,
            'total': 0
        }

        db_config = settings.DATABASES['old_db']

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                sql = """
                      SELECT per.cedula, \
                             pa.action_id, \
                             pa.number, \
                             pa.explanation,
                             pa.date_issue, \
                             pa.date_valid, \
                             pa.registered, \
                             pa.date_register,
                             ha.remuneration_actual, \
                             ha.remuneration_new,
                             ha.direction_actual, \
                             ha.direction_new,
                             ha.charge_actual, \
                             ha.charge_new,
                             ha.place_work_new
                      FROM actions_personnelaction pa
                               INNER JOIN employee_employee e ON pa.employee_id = e.id
                               INNER JOIN person_person per ON e.person_id = per.id
                               LEFT JOIN actions_history_actions ha ON ha.personnel_action_id = pa.id
                      WHERE EXTRACT(YEAR FROM pa.date_issue) = %s \
                      """
                params = [anio]
                if mes:
                    sql += " AND EXTRACT(MONTH FROM pa.date_issue) = %s"
                    params.append(mes)

                cursor.execute(sql, params)
                rows = cursor.fetchall()
                stats['total'] = len(rows)

                self.stdout.write(self.style.HTTP_INFO(f"Analizando {stats['total']} registros..."))

                for row in rows:
                    (cedula, id_act_old, num, exp, f_emision, f_vence, reg_old, f_reg_old,
                     r_old, r_new, u_ant, u_new, p_ant, p_new, lugar) = row

                    # 1. Verificar si ya existe (Evitar duplicados)
                    if PersonnelAction.objects.filter(number=num).exists():
                        stats['ya_existentes'] += 1
                        continue

                    # 2. Verificar Empleado
                    emp = Employee.objects.filter(person__document_number=cedula).first()
                    if not emp:
                        self.stdout.write(self.style.WARNING(f"✘ Saltado: Cédula {cedula} no existe en la base nueva."))
                        stats['error_empleado'] += 1
                        continue

                    # 3. Verificar Mapeo de Acción
                    tipo_id = MAPEO_ACCIONES.get(id_act_old)
                    if not tipo_id:
                        self.stdout.write(self.style.WARNING(
                            f"⚠ Saltado: Tipo de acción {id_act_old} no está en MAPEO_ACCIONES (Número: {num})."))
                        stats['error_mapeo'] += 1
                        continue

                    # 4. Intento de creación
                    try:
                        with transaction.atomic():
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
                            stats['migrados'] += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"‼ Error DB en Acción {num}: {str(e)}"))
                        stats['error_db'] += 1

            conn.close()

            # Reporte Final Consolidado
            self.stdout.write("\n" + "=" * 40)
            self.stdout.write(self.style.SUCCESS(f"🏁 PROCESO FINALIZADO"))
            self.stdout.write(f"Total encontrados: {stats['total']}")
            self.stdout.write(self.style.SUCCESS(f"✔ Migrados con éxito: {stats['migrados']}"))
            self.stdout.write(f"○ Ya existían en DB: {stats['ya_existentes']}")
            self.stdout.write(self.style.NOTICE(f"❌ Fallos por Cédula/Empleado: {stats['error_empleado']}"))
            self.stdout.write(self.style.NOTICE(f"❌ Fallos por Mapeo de Tipo: {stats['error_mapeo']}"))
            self.stdout.write(self.style.ERROR(f"❌ Fallos por Errores de BD: {stats['error_db']}"))
            self.stdout.write("=" * 40)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Fallo crítico: {str(e)}"))
