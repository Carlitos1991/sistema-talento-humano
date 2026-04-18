import psycopg2
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from employee.models import Employee
from permitrequest.models import PermitRequest, PermitType
from django.db.models import Q


class Command(BaseCommand):
    help = 'Migración de Bitácoras filtrable por año y mes con fechas históricas exactas'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=str, default='2026', help='Año a migrar')
        parser.add_argument('--mes', type=str, default=None, help='Mes a migrar (1-12) opcional')

    def handle(self, *args, **options):
        User = get_user_model()
        anio = options['anio']
        mes = options['mes']
        mapeo_manual = {"Bitacora": 3}

        db_config = settings.DATABASES['old_db']
        migrados, total = 0, 0

        texto_periodo = f"año {anio} - mes {mes}" if mes else f"año {anio} completo"

        try:
            self.stdout.write(self.style.SUCCESS(f"🚀 Iniciando migración para el {texto_periodo}..."))
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # Consulta SQL base
                sql = """
                      SELECT per.cedula, \
                             p.registered_by, \
                             p.date_permission_start,
                             p.start_time, \
                             p.end_time, \
                             p.num_horas, \
                             p.num_minutos,
                             p.status, \
                             p.registration_date, \
                             p.file_pdf, \
                             p.action,
                             p.edit_date, \
                             p.edit_by
                      FROM permissions_permission p
                               INNER JOIN employee_employee e ON p.employee_id = e.id
                               INNER JOIN person_person per ON e.person_id = per.id
                      WHERE p.action = 'Bitacora'
                        AND EXTRACT(YEAR FROM p.date_permission_start) = %s
                      """
                params = [anio]

                # Añadimos el filtro por mes si el usuario lo proporcionó
                if mes:
                    sql += " AND EXTRACT(MONTH FROM p.date_permission_start) = %s"
                    params.append(mes)

                cursor.execute(sql, tuple(params))

                with transaction.atomic():
                    while True:
                        rows = cursor.fetchmany(500)
                        if not rows: break

                        for row in rows:
                            total += 1
                            cedula, reg_by, f_ini, h_ini, h_fin, n_h, n_m, estado, f_reg, archivo, cargo_permiso, edit_date, edit_by = row

                            id_tipo = mapeo_manual.get(cargo_permiso)
                            empleado = Employee.objects.filter(person__document_number=cedula).first()
                            if not id_tipo or not empleado: continue

                            def buscar_usuario_real(texto):
                                if not texto: return None
                                nombre = texto.split()[0]
                                return User.objects.filter(
                                    Q(first_name__icontains=nombre) | Q(username__icontains=nombre)
                                ).first()

                            u_creador = buscar_usuario_real(reg_by)
                            u_editor = buscar_usuario_real(edit_by)

                            estado_sigeth2 = 'INACTIVE' if estado == 'INACTIVO' else (
                                'APPROVED' if estado == 'APROBADO' else 'REQUESTED')

                            # 1. Creamos el registro
                            obj, created = PermitRequest.objects.get_or_create(
                                employee=empleado,
                                start_date=f_ini,
                                start_time=h_ini,
                                end_time=h_fin,
                                defaults={
                                    'permit_type_id': id_tipo,
                                    'status': estado_sigeth2,
                                    'hours': n_h or 0,
                                    'minutes': n_m or 0,
                                    'justification_file': archivo,
                                    'created_by': u_creador,
                                    'response_date': edit_date,
                                    'response_by': u_editor,
                                    'updated_by': u_editor,
                                    'response_note': "Migración"
                                }
                            )

                            # 2. Forzamos las fechas históricas
                            fecha_creacion = f_reg if f_reg else datetime.datetime.now()
                            fecha_edicion = edit_date if edit_date else fecha_creacion

                            PermitRequest.objects.filter(id=obj.id).update(
                                created_at=fecha_creacion,
                                updated_at=fecha_edicion
                            )

                            migrados += 1

                        self.stdout.write(f"⏳ Procesando... {total} revisados | {migrados} migrados", ending='\r')

            conn.close()
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ Período terminado ({texto_periodo}). Registros migrados: {migrados}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error: {e}"))
