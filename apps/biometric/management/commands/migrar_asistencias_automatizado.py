import psycopg2
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from employee.models import Employee
from biometric.models import BiometricDevice, BiometricLoad, AttendanceRegistry


class Command(BaseCommand):
    help = 'Migración automatizada de todas las asistencias de sigeth1 a SIGETH2 por año y mes'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, required=True, help='Año a migrar')
        parser.add_argument('--mes', type=int, required=True, help='Mes a migrar (1-12)')
        parser.add_argument('--motivo', type=str, required=True, help='Motivo que aparecerá en la carga de SIGETH2')

    def handle(self, *args, **options):
        anio, mes = options['anio'], options['mes']
        motivo_usuario = options['motivo']

        cedulas_faltantes = set()
        bios_no_mapeados = set()

        total_global_migrados = 0
        total_global_saltados = 0

        db_config = settings.DATABASES['old_db']
        self.stdout.write(self.style.SUCCESS(f"🚀 Iniciando Escaneo Global: Período {mes}/{anio}"))

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # 1. BUSCAR TODOS LOS BIOMÉTRICOS CON ACTIVIDAD EN EL PERIODO
                sql_bios = """
                           SELECT DISTINCT b.id, b.name
                           FROM biometric_biometric b
                                    JOIN biometric_biometric_load bl ON bl.biometric_id = b.id
                                    JOIN biometric_registry r ON r.biometric_load_id = bl.id
                           WHERE EXTRACT(YEAR FROM r.registry_date) = %s
                             AND EXTRACT(MONTH FROM r.registry_date) = %s \
                           """
                cursor.execute(sql_bios, (anio, mes))
                biometricos_antiguos = cursor.fetchall()

                if not biometricos_antiguos:
                    self.stdout.write(
                        self.style.WARNING("⚠️ No se encontró actividad de biométricos en este periodo en sigeth1."))
                    return

                self.stdout.write(
                    f"📊 Se detectaron {len(biometricos_antiguos)} biométricos con registros. Iniciando proceso...")

                for id_old, nombre_old in biometricos_antiguos:
                    self.stdout.write(f"🔍 Dispositivo: '{nombre_old}'...", ending=' ')

                    # 2. BUSCAR POR NOMBRE EN SIGETH2
                    dispositivo_nuevo = BiometricDevice.objects.filter(name__iexact=nombre_old).first()

                    if not dispositivo_nuevo:
                        self.stdout.write(self.style.ERROR("❌ NO ENCONTRADO EN SIGETH2"))
                        bios_no_mapeados.add(nombre_old)
                        continue

                    # 3. TRAER MARCACIONES ASOCIADAS A ESTE BIOMÉTRICO
                    sql_regs = """
                               SELECT per.cedula, r.employee_id_bio, r.registry_date, bl.load_type
                               FROM biometric_registry r
                                        JOIN employee_employee e ON r.employee_id = e.id
                                        JOIN person_person per ON e.person_id = per.id
                                        JOIN biometric_biometric_load bl ON r.biometric_load_id = bl.id
                               WHERE bl.biometric_id = %s
                                 AND EXTRACT(YEAR FROM r.registry_date) = %s
                                 AND EXTRACT(MONTH FROM r.registry_date) = %s \
                               """
                    cursor.execute(sql_regs, (id_old, anio, mes))
                    registros = cursor.fetchall()

                    migrados_este_bio = 0

                    # Usamos una sola carga por biométrico/periodo para SIGETH2
                    with transaction.atomic():
                        # Creamos la cabecera de carga con el motivo del usuario
                        nueva_carga = BiometricLoad.objects.create(
                            biometric=dispositivo_nuevo,
                            reason=motivo_usuario,
                            load_type="MIGRACION",
                            num_records=0  # Se actualizará al final
                        )

                        for cedula, id_bio_emp, fecha_reg, tipo_carga_old in registros:
                            # Buscar empleado por document_number
                            empleado = Employee.objects.filter(person__document_number=cedula).first()

                            if not empleado:
                                cedulas_faltantes.add(cedula)
                                total_global_saltados += 1
                                continue

                            # Insertar marcación
                            AttendanceRegistry.objects.get_or_create(
                                employee=empleado,
                                registry_date=fecha_reg,
                                defaults={
                                    'biometric_load': nueva_carga,
                                    'employee_id_bio': id_bio_emp
                                }
                            )
                            migrados_este_bio += 1

                        # ACTUALIZAR NUM_RECORDS EN LA CARGA
                        nueva_carga.num_records = migrados_este_bio
                        nueva_carga.save()

                    total_global_migrados += migrados_este_bio
                    self.stdout.write(self.style.SUCCESS(f"✅ OK ({migrados_este_bio} registros migrados)"))

            conn.close()

            # --- REPORTE DE AUDITORÍA ---
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS(f"🏁 RESUMEN FINAL DE MIGRACIÓN: {anio}//{mes}"))
            self.stdout.write("=" * 60)
            self.stdout.write(f"🚀 Total registros migrados:    {total_global_migrados}")
            self.stdout.write(f"⚠️  Total registros saltados:    {total_global_saltados}")
            self.stdout.write("-" * 60)

            if bios_no_mapeados:
                self.stdout.write(self.style.ERROR(f"🚫 BIOMÉTRICOS FALTANTES EN SIGETH2 ({len(bios_no_mapeados)}):"))
                for b in sorted(bios_no_mapeados):
                    self.stdout.write(f"   -> '{b}'")

            if cedulas_faltantes:
                self.stdout.write(
                    self.style.ERROR(f"\n❌ EMPLEADOS NO ENCONTRADOS EN SIGETH2 ({len(cedulas_faltantes)}):"))
                for c in sorted(cedulas_faltantes):
                    self.stdout.write(f"   -> {c}")

            self.stdout.write("=" * 60 + "\n")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error General: {e}"))
