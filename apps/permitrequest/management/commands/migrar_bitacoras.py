import psycopg2
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from employee.models import Employee
from permitrequest.models import PermitRequest, PermitType


class Command(BaseCommand):
    help = 'Migración estricta de Bitácoras con mapeo manual y gestión de estados inactivos'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=str, default='2026', help='Año a migrar')

    def handle(self, *args, **options):
        User = get_user_model()
        anio = options['anio']

        # ==========================================================
        # 1. MAPEO MANUAL: Aquí asocias el nombre de Oracle con el ID de SIGETH2
        # ==========================================================
        mapeo_manual = {
            "Bitacora": 3,
            "Cargo a vacaciones": 2,
            "Enfermedad": 5,
            "Calamidad Doméstica": 7,
        }

        self.stdout.write(self.style.SUCCESS(f"🚀 Iniciando migración manual del año {anio}..."))

        db_config = settings.DATABASES['old_db']
        migrados, saltados_tipo, saltados_empleado = 0, 0, 0
        tipos_no_mapeados = set()

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # 2. SELECCIÓN DE DATOS (Incluyendo edit_by y edit_date de SIGETH1)
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
                        rows = cursor.fetchmany(1000)
                        if not rows: break

                        for cedula, reg_by, f_ini, h_ini, h_fin, n_h, n_m, estado, f_reg, archivo, cargo_permiso, edit_date, edit_by in rows:

                            # A. Verificar Mapeo Manual
                            id_tipo_mapeado = mapeo_manual.get(cargo_permiso)
                            if not id_tipo_mapeado:
                                tipos_no_mapeados.add(cargo_permiso)
                                saltados_tipo += 1
                                continue

                            # B. Verificar Empleado por Cédula
                            empleado = Employee.objects.filter(person__document_number=cedula).first()
                            if not empleado:
                                saltados_empleado += 1
                                continue

                            # C. Obtener Tipo de Permiso (se migra aunque esté inactivo en SIGETH2)
                            tipo_obj = PermitType.objects.get(id=id_tipo_mapeado)

                            # D. Mapeo de Usuarios (Creador y Editor)
                            nombre_creador = reg_by.split()[0] if reg_by else "ADMIN"
                            usuario_creador = User.objects.filter(first_name__icontains=nombre_creador).first()

                            nombre_editor = edit_by.split()[0] if edit_by else nombre_creador
                            usuario_editor = User.objects.filter(first_name__icontains=nombre_editor).first()

                            # Si no se encuentra el usuario, usar el primer superusuario disponible
                            admin_fallback = User.objects.filter(is_superuser=True).first()
                            if not usuario_creador: usuario_creador = admin_fallback
                            if not usuario_editor: usuario_editor = admin_fallback

                            # E. Determinación del Estado (Ajustado según tu solicitud)
                            # Si el estado es 'INACTIVO' en Oracle, se guarda como 'INACTIVE' en SIGETH2
                            # Si es 'APROBADO', se guarda como 'APPROVED', de lo contrario 'REQUESTED'
                            if estado == 'INACTIVO':
                                estado_sigeth2 = 'CANCELED'
                            elif estado == 'APROBADO':
                                estado_sigeth2 = 'APPROVED'
                            else:
                                estado_sigeth2 = 'REQUESTED'

                            # F. Creación/Actualización del Registro
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
                                    'created_at': f_reg if f_reg else datetime.datetime.now(),
                                    'created_by': usuario_creador,
                                    # Mapeo de campos de auditoría de edición
                                    'updated_by': usuario_editor,
                                    'updated_at': edit_date if edit_date else (
                                        f_reg if f_reg else datetime.datetime.now()),
                                    'response_note': f"Migración Consolidada SIGETH1. Orig: {reg_by} | Cargo: {cargo_permiso}"
                                }
                            )
                            migrados += 1

                        self.stdout.write(f"⏳ Procesando... Migrados: {migrados}", ending='\r')

            conn.close()

            # --- REPORTE FINAL ---
            self.stdout.write("\n" + "=" * 50)
            self.stdout.write(self.style.SUCCESS(f"✅ MIGRACIÓN {anio} FINALIZADA"))
            if tipos_no_mapeados:
                self.stdout.write(self.style.ERROR(f"❌ TIPOS NO MAPEADOS: {tipos_no_mapeados}"))
            self.stdout.write(f"✨ Registros nuevos: {migrados}")
            self.stdout.write(f"❌ Sin empleado:     {saltados_empleado}")
            self.stdout.write("=" * 50)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error Crítico: {e}"))
