import psycopg2
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from employee.models import Employee
from biometric.models import BiometricDevice, BiometricLoad, AttendanceRegistry


class Command(BaseCommand):
    help = 'Migración automatizada de asistencias de sigeth1 a SIGETH2 (Por mes o año completo)'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, required=True, help='Año a migrar')
        parser.add_argument('--mes', type=int, required=False,
                            help='Mes a migrar (Opcional, si se omite migra todo el año)')
        parser.add_argument('--motivo', type=str, required=True, help='Motivo que aparecerá en la carga de SIGETH2')

    def handle(self, *args, **options):
        anio = options['anio']
        mes = options.get('mes')
        motivo_usuario = options['motivo']

        cedulas_faltantes = set()
        bios_no_mapeados = set()

        total_global_migrados = 0
        total_global_duplicados = 0
        total_global_saltados = 0

        periodo_log = f"{mes}/{anio}" if mes else f"AÑO COMPLETO {anio}"
        db_config = settings.DATABASES['old_db']

        self.stdout.write(self.style.SUCCESS(f"🚀 Iniciando Escaneo: {periodo_log}"))

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # 1. BUSCAR DISPOSITIVOS CON ACTIVIDAD (Consulta dinámica)
                sql_bios = """
                           SELECT DISTINCT b.id, b.name
                           FROM biometric_biometric b
                                    JOIN biometric_biometric_load bl ON bl.biometric_id = b.id
                                    JOIN biometric_registry r ON r.biometric_load_id = bl.id
                           WHERE EXTRACT(YEAR FROM r.registry_date) = %s
                           """
                params_bios = [anio]
                if mes:
                    sql_bios += " AND EXTRACT(MONTH FROM r.registry_date) = %s"
                    params_bios.append(mes)

                cursor.execute(sql_bios, tuple(params_bios))
                biometricos_antiguos = cursor.fetchall()

                if not biometricos_antiguos:
                    self.stdout.write(self.style.WARNING(f"⚠️ No se encontró actividad en el periodo {periodo_log}."))
                    return

                self.stdout.write(f"📊 Se detectaron {len(biometricos_antiguos)} biométricos con registros.")

                for id_old, nombre_old in biometricos_antiguos:
                    self.stdout.write(f"🔍 Procesando: '{nombre_old}'...", ending=' ')

                    dispositivo_nuevo = BiometricDevice.objects.filter(name__iexact=nombre_old).first()
                    if not dispositivo_nuevo:
                        self.stdout.write(self.style.ERROR("❌ NO HALLADO EN DESTINO"))
                        bios_no_mapeados.add(nombre_old)
                        continue

                    # 2. TRAER MARCACIONES (Consulta dinámica respetando per.cedula)
                    sql_regs = """
                               SELECT per.cedula, r.employee_id_bio, r.registry_date, bl.load_type
                               FROM biometric_registry r
                                        JOIN employee_employee e ON r.employee_id = e.id
                                        JOIN person_person per ON e.person_id = per.id
                                        JOIN biometric_biometric_load bl ON r.biometric_load_id = bl.id
                               WHERE bl.biometric_id = %s
                                 AND EXTRACT(YEAR FROM r.registry_date) = %s
                               """
                    params_regs = [id_old, anio]
                    if mes:
                        sql_regs += " AND EXTRACT(MONTH FROM r.registry_date) = %s"
                        params_regs.append(mes)

                    cursor.execute(sql_regs, tuple(params_regs))
                    registros = cursor.fetchall()

                    migrados_este_bio = 0
                    duplicados_este_bio = 0

                    with transaction.atomic():
                        nueva_carga = BiometricLoad.objects.create(
                            biometric=dispositivo_nuevo,
                            reason=f"{motivo_usuario} ({periodo_log})",
                            load_type="MIGRACION",
                            num_records=0
                        )

                        for cedula, id_bio_emp, fecha_reg, tipo_carga_old in registros:
                            # Buscar empleado en SIGETH2
                            empleado = Employee.objects.filter(person__document_number=cedula).first()

                            if not empleado:
                                cedulas_faltantes.add(cedula)
                                total_global_saltados += 1
                                continue

                            # Control de duplicados usando registry_date
                            registro_existe = AttendanceRegistry.objects.filter(
                                employee=empleado,
                                registry_date=fecha_reg
                            ).exists()

                            if not registro_existe:
                                AttendanceRegistry.objects.create(
                                    employee=empleado,
                                    registry_date=fecha_reg,
                                    biometric_load=nueva_carga,
                                    employee_id_bio=id_bio_emp
                                )
                                migrados_este_bio += 1
                            else:
                                duplicados_este_bio += 1

                        nueva_carga.num_records = migrados_este_bio
                        nueva_carga.save()

                    total_global_migrados += migrados_este_bio
                    total_global_duplicados += duplicados_este_bio
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ OK (Nuevos: {migrados_este_bio} | Duplicados: {duplicados_este_bio})"))

            conn.close()

            # --- REPORTE FINAL ---
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS(f"🏁 RESUMEN FINAL: {periodo_log}"))
            self.stdout.write("=" * 60)
            self.stdout.write(f"✅ Registros nuevos migrados:   {total_global_migrados}")
            self.stdout.write(self.style.WARNING(f"⚠️  Omitidos por duplicado:      {total_global_duplicados}"))
            self.stdout.write(f"❌ Saltados (Emp. no hallados): {total_global_saltados}")
            self.stdout.write("-" * 60)

            if cedulas_faltantes:
                self.stdout.write(self.style.ERROR(f"❌ CEDULAS NO ENCONTRADAS ({len(cedulas_faltantes)})"))

            if bios_no_mapeados:
                self.stdout.write(self.style.ERROR(f"🚫 BIOMÉTRICOS NO MAPEADOS: {list(bios_no_mapeados)}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error General: {e}"))
