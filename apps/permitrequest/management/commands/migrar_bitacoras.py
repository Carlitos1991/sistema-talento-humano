import psycopg2
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from employee.models import Employee
from permitrequest.models import PermitRequest, PermitType


class Command(BaseCommand):
    help = 'Migración optimizada con mapeo a campos de Response y auditoría'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=str, default='2026', help='Año a migrar')

    def handle(self, *args, **options):
        User = get_user_model()
        anio = options['anio']

        mapeo_manual = {
            "Bitacora": 3,
            "Cargo a vacaciones": 2,
            "Enfermedad": 5,
            "Calamidad Doméstica": 7,
        }

        # OPTIMIZACIÓN: Cargamos usuarios en un diccionario para evitar miles de consultas a la BD
        self.stdout.write("🚀 Precargando usuarios para velocidad...")
        usuarios_cache = {u.first_name.upper() if u.first_name else "": u for u in User.objects.all()}
        admin_fallback = User.objects.filter(is_superuser=True).first()

        db_config = settings.DATABASES['old_db']
        migrados, total_procesados = 0, 0

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # Traemos edit_date y edit_by (updated_at/by en la tabla de origen)
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
                cursor.execute(sql, (anio,))

                with transaction.atomic():
                    while True:
                        rows = cursor.fetchmany(500)
                        if not rows: break

                        for row in rows:
                            total_procesados += 1
                            cedula, reg_by, f_ini, h_ini, h_fin, n_h, n_m, estado, f_reg, archivo, cargo_permiso, edit_date, edit_by = row

                            id_tipo_mapeado = mapeo_manual.get(cargo_permiso)
                            if not id_tipo_mapeado: continue

                            empleado = Employee.objects.filter(person__document_number=cedula).first()
                            if not empleado: continue

                            tipo_obj = PermitType.objects.get(id=id_tipo_mapeado)

                            # Búsqueda rápida en caché de usuarios
                            nombre_reg = reg_by.split()[0].upper() if reg_by else ""
                            nombre_edit = edit_by.split()[0].upper() if edit_by else ""

                            u_creador = usuarios_cache.get(nombre_reg, admin_fallback)
                            u_editor = usuarios_cache.get(nombre_edit, u_creador)

                            # Definición de Estado
                            estado_sigeth2 = 'INACTIVE' if estado == 'INACTIVO' else (
                                'APPROVED' if estado == 'APROBADO' else 'REQUESTED')

                            # Creación del Registro con el nuevo mapeo solicitado
                            PermitRequest.objects.get_or_create(
                                employee=empleado,
                                start_date=f_ini,
                                start_time=h_ini,
                                end_time=h_fin,
                                defaults={
                                    'end_date': f_ini,
                                    'permit_type': tipo_obj,
                                    'status': estado_sigeth2,
                                    'hours': n_h or 0,
                                    'minutes': n_m or 0,
                                    'justification_file': archivo,

                                    # Auditoría de Creación
                                    'created_at': f_reg if f_reg else datetime.datetime.now(),
                                    'created_by': u_creador,

                                    # MAPEO SOLICITADO A CAMPOS DE RESPONSE
                                    'response_date': edit_date,  # edit_date (updated_at de origen) -> response_date
                                    'response_by': u_editor,  # edit_by (updated_by de origen) -> response_by

                                    # Auditoría de Sistema (updated_at/by se llenan automáticamente o igualamos)
                                    'updated_at': edit_date if edit_date else (
                                        f_reg if f_reg else datetime.datetime.now()),
                                    'updated_by': u_editor,

                                    'response_note': f"Migrado. Creado por: {reg_by} | Gestionado por: {edit_by}"
                                }
                            )
                            migrados += 1

                        self.stdout.write(f"⏳ Procesando... {total_procesados} revisados | {migrados} migrados",
                                          ending='\r')

            conn.close()
            self.stdout.write(self.style.SUCCESS(f"\n✅ Año {anio} terminado satisfactoriamente."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error: {e}"))