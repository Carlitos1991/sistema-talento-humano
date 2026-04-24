import psycopg2
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from employee.models import Employee
from permitrequest.models import PermitRequest, PermitType


class Command(BaseCommand):
    help = 'Migración universal: Mapeo por ID real + Nota de referencia desde action'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, required=True)
        parser.add_argument('--mes', type=int, help='Opcional')

    def handle(self, *args, **options):
        anio, mes = options['anio'], options['mes']

        # --- EL MAPEO QUE DEFINIMOS ---
        # { ID_SIGETH1 : ID_SIGETH2 }
        MAPEO_ESTRICTO = {
            8: 9,  # De 'Otros' (ID 9 en viejo) a 'DESCUENTO A ROL' (ID 9 en nuevo)
            9: 7,  # De 'Calamidad doméstica' (7) a 'CALAMIDAD DOMESTICA' (7)
            5: 13,  # Maternidad
        }

        cedulas_faltantes = set()
        tipos_no_mapeados = set()
        migrados, saltados = 0, 0

        db_config = settings.DATABASES['old_db']

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # Traemos el type_of_permit_id (el número) y el action (el texto)
                sql = """
                      SELECT per.cedula, \
                             p.type_of_permit_id, \
                             p.action, \
                             p.date_permission_start,
                             p.start_time, \
                             p.end_time, \
                             p.num_horas, \
                             p.num_minutos, \
                             p.status,
                             p.registration_date, \
                             p.file_pdf
                      FROM permissions_permission p
                               INNER JOIN employee_employee e ON p.employee_id = e.id
                               INNER JOIN person_person per ON e.person_id = per.id
                      WHERE EXTRACT(YEAR FROM p.date_permission_start) = %s \
                      """
                params = [anio]
                if mes:
                    sql += " AND EXTRACT(MONTH FROM p.date_permission_start) = %s"
                    params.append(mes)

                cursor.execute(sql, params)
                filas = cursor.fetchall()

                for row in filas:
                    cedula, id_tipo_old, action_txt, f_ini, h_ini, h_fin, n_h, n_m, estado, f_reg, archivo = row

                    # 1. Buscar el nuevo ID en nuestro diccionario
                    id_tipo_nuevo = MAPEO_ESTRICTO.get(id_tipo_old)

                    # 2. Buscar empleado por document_number
                    empleado = Employee.objects.filter(person__document_number=cedula).first()

                    if not empleado or not id_tipo_nuevo:
                        saltados += 1
                        if not empleado: cedulas_faltantes.add(cedula)
                        if not id_tipo_nuevo: tipos_no_mapeados.add(f"ID Antiguo: {id_tipo_old} ({action_txt})")
                        continue

                    # 3. MIGRACIÓN CON NOTA PERSONALIZADA
                    with transaction.atomic():
                        # Creamos la nota: "Migrado: Otros" o lo que diga el campo action
                        nota = f"Migrado: {action_txt}" if action_txt else "Migración Histórica"

                        obj, created = PermitRequest.objects.get_or_create(
                            employee=empleado,
                            start_date=f_ini,
                            start_time=h_ini,
                            end_time=h_fin,
                            defaults={
                                'permit_type_id': id_tipo_nuevo,
                                'status': 'APPROVED' if estado == 'APROBADO' else 'REQUESTED',
                                'hours': n_h or 0,
                                'minutes': n_m or 0,
                                'justification_file': archivo,
                                'response_note': nota  # AQUÍ SE GUARDA EL TEXTO "OTROS"
                            }
                        )

                        # Forzar fecha de registro original
                        PermitRequest.objects.filter(id=obj.id).update(created_at=f_reg)
                        migrados += 1

            conn.close()

            # --- REPORTE ---
            self.stdout.write(self.style.SUCCESS(f"\n✅ MIGRACIÓN EXITOSA"))
            self.stdout.write(f"🚀 Registros migrados: {migrados}")
            if tipos_no_mapeados:
                self.stdout.write(self.style.ERROR(f"❌ FALTAN MAPEAR EN EL SCRIPT: {tipos_no_mapeados}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))