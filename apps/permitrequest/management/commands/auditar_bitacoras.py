import psycopg2
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from employee.models import Employee
from permitrequest.models import PermitRequest, PermitType
from django.db.models import Q


class Command(BaseCommand):
    help = 'Audita bitácoras detallando usuarios y tipos faltantes'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=str, default='2025', help='Año a auditar')

    def handle(self, *args, **options):
        User = get_user_model()
        anio = options['anio']
        self.stdout.write(self.style.SUCCESS(f"🚀 Analizando año {anio}..."))

        db_config = settings.DATABASES['old_db']
        cedulas_faltantes = set()
        usuarios_faltantes = set()
        tipos_faltantes = set()

        migrados = 0
        pendientes = 0
        total_periodo = 0

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # Traemos también edit_by para auditar editores
                sql = """
                      SELECT per.cedula, \
                             p.registered_by, \
                             p.action, \
                             p.date_permission_start,
                             p.start_time, \
                             p.end_time, \
                             p.edit_by
                      FROM permissions_permission p
                               INNER JOIN employee_employee e ON p.employee_id = e.id
                               INNER JOIN person_person per ON e.person_id = per.id
                      WHERE p.action = 'Bitacora' \
                        AND EXTRACT(YEAR FROM p.date_permission_start) = %s
                      """
                cursor.execute(sql, (anio,))

                while True:
                    rows = cursor.fetchmany(1000)
                    if not rows: break

                    for cedula, reg_by, accion, fecha, h_ini, h_fin, edit_by in rows:
                        total_periodo += 1

                        # 1. VERIFICAR MIGRACIÓN
                        ya_migrado = PermitRequest.objects.filter(
                            employee__person__document_number=cedula,
                            start_date=fecha,
                            start_time=h_ini,
                            end_time=h_fin
                        ).exists()

                        if ya_migrado:
                            migrados += 1
                        else:
                            pendientes += 1

                            # 2. AUDITORÍA DE TIPOS (Validar contra ID 3 o Nombre)
                            if not PermitType.objects.filter(Q(id=3) | Q(name__iexact=accion)).exists():
                                tipos_faltantes.add(accion)

                            # 3. AUDITORÍA DE EMPLEADOS
                            if not Employee.objects.filter(person__document_number=cedula).exists():
                                cedulas_faltantes.add(cedula)

                            # 4. AUDITORÍA DE USUARIOS (Quien registró y quien editó)
                            for user_name in [reg_by, edit_by]:
                                if user_name:
                                    search_term = user_name.strip().split()[0]
                                    if not User.objects.filter(Q(first_name__icontains=search_term) | Q(
                                            username__icontains=search_term)).exists():
                                        usuarios_faltantes.add(user_name.strip())

                    self.stdout.write(f"⏳ Procesando registros... {total_periodo}", ending='\r')

            conn.close()

            # --- REPORTE DETALLADO ---
            self.stdout.write("\n\n" + "=" * 50)
            self.stdout.write(f"📊 ESTADO DE MIGRACIÓN - AÑO {anio}")
            self.stdout.write("=" * 50)
            self.stdout.write(f"✅ Ya migrados en SIGETH2:  {migrados}")
            self.stdout.write(f"⏳ Pendientes por subir:   {pendientes}")
            self.stdout.write("-" * 50)

            # MOSTRAR DETALLES
            if usuarios_faltantes:
                self.stdout.write(self.style.WARNING(f"⚠️  USUARIOS NO ENCONTRADOS ({len(usuarios_faltantes)}):"))
                for u in sorted(usuarios_faltantes):
                    self.stdout.write(f"   - {u}")
                self.stdout.write("-" * 50)

            if cedulas_faltantes:
                self.stdout.write(self.style.ERROR(f"❌ CÉDULAS FALTANTES EN SIGETH2 ({len(cedulas_faltantes)}):"))
                for c in sorted(cedulas_faltantes):
                    self.stdout.write(f"   -> {c}")
                self.stdout.write("-" * 50)

            if tipos_faltantes:
                self.stdout.write(self.style.ERROR(f"❌ TIPOS FALTANTES: {tipos_faltantes}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error: {e}"))