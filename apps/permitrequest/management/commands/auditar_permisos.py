import psycopg2
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from employee.models import Employee
from permitrequest.models import PermitRequest, PermitType


class Command(BaseCommand):
    help = 'Auditoría con validación de mapeo: Muestra tipos encontrados y faltantes'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, required=True)
        parser.add_argument('--mes', type=int, help='Opcional')

    def handle(self, *args, **options):
        User = get_user_model()
        anio, mes = options['anio'], options['mes']

        # --- MAPEO QUE ESTÁS PROBANDO ---
        MAPEO_ESTRICTO = {
            8: 8,  # Compensacion
            10: 14,  # Asuntos Oficiales
            7: 13,  # CALAMIDAD DOMESTICA
            2: 5,  # Cargo a vacaciones
            13: 11,  # Maternidad
            12: 12,  # Paternidad
            9: 9,  #  DESCUENTO A ROL
            5: 7,  #  Permiso Médico
        }

        tipos_encontrados = set()  # Formato: "Nombre S1 (ID: X) -> Nombre S2 (ID: Y)"
        tipos_faltantes = set()
        cedulas_faltantes = set()

        ya_migrados, pendientes, total_analizados = 0, 0, 0
        db_config = settings.DATABASES['old_db']

        self.stdout.write(self.style.SUCCESS(f"🔍 Auditoría de Mapeo: Año {anio}"))

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                sql = """
                      SELECT per.cedula, \
                             tp.id             as id_old, \
                             tp.type_of_permit as nombre_old,
                             p.date_permission_start, \
                             p.start_time, \
                             p.end_time
                      FROM permissions_permission p
                               INNER JOIN employee_employee e ON p.employee_id = e.id
                               INNER JOIN person_person per ON e.person_id = per.id
                               INNER JOIN permissions_typeofpermit tp ON p.type_of_permit_id = tp.id
                      WHERE EXTRACT(YEAR FROM p.date_permission_start) = %s
                      """
                params = [anio]
                if mes:
                    sql += " AND EXTRACT(MONTH FROM p.date_permission_start) = %s"
                    params.append(mes)

                cursor.execute(sql, params)

                for row in cursor.fetchall():
                    total_analizados += 1
                    cedula, id_old, nombre_old, f_ini, h_ini, h_fin = row

                    # 1. VALIDAR MAPEO Y EXISTENCIA EN SIGETH 2
                    id_nuevo_mapeado = MAPEO_ESTRICTO.get(id_old)
                    tipo_nuevo_obj = None

                    if id_nuevo_mapeado:
                        tipo_nuevo_obj = PermitType.objects.filter(id=id_nuevo_mapeado).first()
                    else:
                        # Si no hay mapeo manual, intenta buscar por nombre exacto
                        tipo_nuevo_obj = PermitType.objects.filter(name__iexact=nombre_old).first()

                    # 2. CLASIFICAR PARA EL REPORTE
                    if tipo_nuevo_obj:
                        # Si existe el destino, lo agregamos a los "Encontrados"
                        tipos_encontrados.add(
                            f"{nombre_old} (ID S1: {id_old}) -> {tipo_nuevo_obj.name} (ID S2: {tipo_nuevo_obj.id})"
                        )
                    else:
                        # Si no hay forma de encontrarlo, va a "Faltantes"
                        tipos_faltantes.add(f"{nombre_old} (ID S1: {id_old})")

                    # 3. ESTADO DE MIGRACIÓN Y EMPLEADOS
                    if not Employee.objects.filter(person__document_number=cedula).exists():
                        cedulas_faltantes.add(cedula)

                    if PermitRequest.objects.filter(employee__person__document_number=cedula, start_date=f_ini,
                                                    start_time=h_ini).exists():
                        ya_migrados += 1
                    else:
                        pendientes += 1

            conn.close()

            # --- REPORTE FINAL ---
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.SUCCESS(f"🏁 REPORTE DE AUDITORÍA Y VERIFICACIÓN DE MAPEO"))
            self.stdout.write("=" * 70)

            # SECCIÓN NUEVA: TIPOS ENCONTRADOS
            self.stdout.write(self.style.SUCCESS("✅ TIPOS ENCONTRADOS Y VINCULADOS (Mapeo Correcto):"))
            if tipos_encontrados:
                for mapping in sorted(tipos_encontrados):
                    self.stdout.write(f"   {mapping}")
            else:
                self.stdout.write("   Ninguno.")

            self.stdout.write("-" * 70)

            # SECCIÓN: TIPOS FALTANTES
            if tipos_faltantes:
                self.stdout.write(self.style.ERROR("❌ TIPOS QUE NO TIENEN DESTINO (Revisar Mapeo):"))
                for t in sorted(tipos_faltantes):
                    self.stdout.write(f"   -> {t}")
                self.stdout.write("-" * 70)

            # RESUMEN NUMÉRICO
            self.stdout.write(f"📊 Total analizados:  {total_analizados}")
            self.stdout.write(f"✅ Ya en SIGETH 2:    {ya_migrados}")
            self.stdout.write(f"⏳ Pendientes:         {pendientes}")
            if cedulas_faltantes:
                self.stdout.write(self.style.ERROR(f"👤 Empleados faltantes: {len(cedulas_faltantes)}"))
            self.stdout.write("=" * 70 + "\n")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))