import psycopg2
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from employee.models import Employee
from permitrequest.models import PermitRequest, PermitType


class Command(BaseCommand):
    help = 'Migración universal de permisos con validación de estado para evitar duplicados erróneos'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, required=True)
        parser.add_argument('--mes', type=int, help='Opcional (1-12)')

    def handle(self, *args, **options):
        anio, mes = options['anio'], options['mes']

        # --- MAPEO ESTRICTO DE IDs (Basado en tus capturas de SIGETH 1 y 2) ---
        # { ID_SIGETH1 : ID_SIGETH2 }
        MAPEO_ESTRICTO = {
            8: 8,  # Compensacion
            14: 15,  # Matrimonio
            10: 14,  # Asuntos Oficiales
            7: 13,  # CALAMIDAD DOMESTICA
            2: 5,  # Cargo a vacaciones
            13: 11,  # Maternidad
            12: 12,  # Paternidad
            9: 9,  # DESCUENTO A ROL
            5: 7,  # Permiso Médico
            29: 3,  # Bitácora (según tu mapeo anterior)
        }

        # Sets para auditoría
        cedulas_faltantes = set()
        tipos_no_mapeados = set()

        # Contadores de estadísticas
        migrados = 0
        duplicados = 0
        saltados = 0
        total_analizados = 0

        db_config = settings.DATABASES['old_db']

        try:
            self.stdout.write(self.style.SUCCESS(f"🚀 Iniciando migración segura: Año {anio} Mes /{mes}"))
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # Consulta SQL universal
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

                for row in cursor.fetchall():
                    total_analizados += 1
                    cedula, id_tipo_old, action_txt, f_ini, h_ini, h_fin, n_h, n_m, estado_old, f_reg, archivo = row

                    # 1. VALIDAR MAPEO Y EMPLEADO
                    id_tipo_nuevo = MAPEO_ESTRICTO.get(id_tipo_old)
                    empleado = Employee.objects.filter(person__document_number=cedula).first()

                    if not empleado or not id_tipo_nuevo:
                        saltados += 1
                        if not empleado: cedulas_faltantes.add(cedula)
                        if not id_tipo_nuevo: tipos_no_mapeados.add(f"ID: {id_tipo_old} ({action_txt})")
                        continue

                    # 2. MAPEO DE ESTADO
                    # Importante para diferenciar Aprobados de Rechazados
                    estado_sigeth2 = 'APPROVED' if estado_old == 'APROBADO' else (
                        'REJECTED' if estado_old == 'RECHAZADO' else (
                            'INACTIVE' if estado_old == 'INACTIVO' else 'REQUESTED'
                        )
                    )

                    # 3. DETECCIÓN DE DUPLICADOS INCLUYENDO EL ESTADO
                    # Esto evita el error "MultipleObjectsReturned"
                    existe = PermitRequest.objects.filter(
                        employee=empleado,
                        start_date=f_ini,
                        start_time=h_ini,
                        end_time=h_fin,
                        status=estado_sigeth2  # <--- Filtro clave
                    ).first()

                    if existe:
                        duplicados += 1
                        continue

                    # 4. CREACIÓN DEL REGISTRO
                    try:
                        with transaction.atomic():
                            nota = f"Migrado: {action_txt}" if action_txt else "Migración Histórica"

                            nuevo_permiso = PermitRequest.objects.create(
                                employee=empleado,
                                start_date=f_ini,
                                start_time=h_ini,
                                end_time=h_fin,
                                permit_type_id=id_tipo_nuevo,
                                status=estado_sigeth2,
                                hours=n_h or 0,
                                minutes=n_m or 0,
                                justification_file=archivo,
                                response_note=nota
                            )

                            # Forzar la fecha de registro original
                            PermitRequest.objects.filter(id=nuevo_permiso.id).update(created_at=f_reg)
                            migrados += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error en cédula {cedula}: {e}"))
                        saltados += 1

                    self.stdout.write(f"⏳ Analizando... {total_analizados}", ending='\r')

            conn.close()

            # --- REPORTE FINAL ---
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS(f"🏁 RESUMEN FINAL DE MIGRACIÓN: {anio}/{mes}"))
            self.stdout.write("=" * 60)
            self.stdout.write(f"📊 Registros analizados en SIGETH 1: {total_analizados}")
            self.stdout.write(f"✅ Registros nuevos migrados:        {migrados}")
            self.stdout.write(f"⚠️  Registros duplicados (omitidos):   {duplicados}")
            self.stdout.write(f"✖  Registros saltados (errores/faltantes): {saltados}")
            self.stdout.write("-" * 60)

            if tipos_no_mapeados:
                self.stdout.write(self.style.ERROR(f"❌ TIPOS POR AGREGAR AL MAPEO_ESTRICTO:"))
                for t in sorted(tipos_no_mapeados):
                    self.stdout.write(f"   -> {t}")

            if cedulas_faltantes:
                self.stdout.write(
                    self.style.ERROR(f"❌ EMPLEADOS NO ENCONTRADOS EN SIGETH 2 ({len(cedulas_faltantes)})"))

            self.stdout.write("=" * 60 + "\n")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Fallo crítico en la conexión: {e}"))
