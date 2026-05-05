import psycopg2
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from employee.models import Employee
from core.models import User
# Asegúrate de que estas rutas sean las correctas en tu proyecto SIGETH 2
from personnel_actions.models import PersonnelAction, ActionType, ActionMovement
from institution.models import AdministrativeUnit

class Command(BaseCommand):
    help = 'Migración detallada de Acciones de Personal usando Usuario ID 4'

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
        USER_ID_MIGRACION = 4

        # --- AQUÍ DEBES AGREGAR LOS IDs QUE TE SALTEN ---
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
            2: 5,  # Ejemplo: Renuncia[cite: 5]
            17: 11,  # Ejemplo: Renuncia[cite: 5]
        }

        MAPEO_UNIDADES = {
            "Centro de Apoyo Social Municipal": 128,  # Formato pedido: "TEXTO_ORIGEN": ID_DESTINO
            "Dirección Administrativa": 30,
            "Dirección de Higiene": 73,
            "UMAPAL": 67,
            "Dirección de Seguridad Ciudadana y Control Público": 70,
            "Dirección Estratégica de Tránsito": 87,
            "Dirección de Cultura": 95,
            "Dirección de Educación, Deportes y Recreación": 93,
            "Dirección de Gestión Ambiental": 72,
            "Dirección de Gestión Económica": 68,
            "Dirección de Gestión Territorial": 65,
            "Dirección de Movilidad y Transporte": 69,
            "Dirección de Obras Públicas": 66,
            "Dirección de Planificación": 15,
            "Dirección de Talento Humano": 32,
            "Secretaría General": 5,
        }

        migrados = 0
        ya_existentes = 0
        sin_empleado = 0
        sin_mapeo_tipo = 0
        errores_db = 0
        total_procesados = 0

        db_config = settings.DATABASES['old_db']

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # SQL mejorado para traer el nombre de la acción desde el origen[cite: 3, 5]
                sql = """
                    SELECT per.cedula, pa.action_id, pa.number, pa.explanation, 
                           pa.date_issue, pa.date_valid, pa.registered, pa.date_register,
                           ha.remuneration_actual, ha.remuneration_new, 
                           ha.direction_new, ha.place_work_new,
                           act.name as nombre_accion_old
                    FROM actions_personnelaction pa
                    INNER JOIN employee_employee e ON pa.employee_id = e.id
                    INNER JOIN person_person per ON e.person_id = per.id
                    INNER JOIN actions_actions act ON pa.action_id = act.id
                    LEFT JOIN actions_history_actions ha ON ha.personnel_action_id = pa.id
                    WHERE EXTRACT(YEAR FROM pa.date_issue) = %s
                """
                params = [anio]
                if mes:
                    sql += " AND EXTRACT(MONTH FROM pa.date_issue) = %s"
                    params.append(mes)

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                self.stdout.write(f"Analizando {len(rows)} registros...")

                for row in rows:
                    total_procesados += 1
                    (cedula, id_act_old, num, exp, f_emision, f_vence,
                     reg_old, f_reg_old, r_old, r_new, unidad_txt, lugar, nombre_accion_old) = row

                    if PersonnelAction.objects.filter(number=num).exists():
                        ya_existentes += 1
                        continue

                    emp = Employee.objects.filter(person__document_number=cedula).first()
                    if not emp:
                        sin_empleado += 1
                        continue

                    tipo_id_nuevo = MAPEO_ACCIONES.get(id_act_old)
                    if not tipo_id_nuevo:
                        # AHORA TE DIRÁ EL NOMBRE
                        self.stdout.write(self.style.WARNING(
                            f"[-] Saltado {num}: El ID {id_act_old} ({nombre_accion_old}) no está mapeado."
                        ))
                        sin_mapeo_tipo += 1
                        continue

                    try:
                        with transaction.atomic():
                            nueva_pa = PersonnelAction.objects.create(
                                employee=emp,
                                action_type_id=tipo_id_nuevo,
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
                                previous_remuneration=self.limpiar_monto(r_old),
                                new_remuneration=self.limpiar_monto(r_new),
                                new_unit_id=MAPEO_UNIDADES.get(unidad_txt),
                                location_text=lugar or unidad_txt
                            )
                            migrados += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"[!] Error DB en {num}: {str(e)}"))
                        errores_db += 1

            conn.close()
            self.stdout.write(self.style.SUCCESS(f"\n🏁 FINALIZADO: {migrados} nuevos, {ya_existentes} ya estaban."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Fallo crítico: {str(e)}"))