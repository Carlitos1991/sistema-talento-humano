# permitrequest/management/commands/migrar_permisos_oracle.py
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from employee.models import Employee
from permitrequest.models import PermitRequest, PermitType

try:
    import oracledb
except ImportError:
    oracledb = None


class Command(BaseCommand):
    help = 'Migra permisos desde la base Oracle antigua a PostgreSQL usando el ORM de Django'

    def add_arguments(self, parser):
        # Permite pasar fechas por consola, igual que tus variables fechaConsultaIni/Fin en Java
        parser.add_argument('--ini', type=str, default='01/12/2024', help='Fecha inicio (DD/MM/YYYY)')
        parser.add_argument('--fin', type=str, default='05/12/2025', help='Fecha fin (DD/MM/YYYY)')

    def handle(self, *args, **options):
        if not oracledb:
            self.stdout.write(
                self.style.ERROR("La librería 'oracledb' no está instalada. Ejecuta: pip install oracledb"))
            return

        fecha_ini_str = options['ini']
        fecha_fin_str = options['fin']

        # 🟢 NUEVO: Convertir los textos a objetos de fecha en Python para hacer matemáticas
        import datetime
        try:
            fecha_ini_dt = datetime.datetime.strptime(fecha_ini_str, "%d/%m/%Y").date()
            fecha_fin_dt = datetime.datetime.strptime(fecha_fin_str, "%d/%m/%Y").date()
        except ValueError:
            self.stdout.write(self.style.ERROR("Error: El formato de las fechas debe ser DD/MM/YYYY"))
            return

        # Usuario administrador para dejar rastro de la auditoría
        User = get_user_model()
        admin_user = User.objects.filter(is_superuser=True).first()

        # Configuración de Conexión a Oracle
        dsn = "192.168.1.113:1521/XE"
        usuario_oracle = "sisem_prod1"
        password_oracle = "4B9Vu1fL5z0M"  # 🔴 REEMPLAZA CON LA CONTRASEÑA REAL

        try:
            self.stdout.write(self.style.WARNING(f"Conectando a Oracle ({dsn})..."))

            # 1. INICIALIZAR CLIENTE THICK PARA ORACLE (thick mode)
            # Para servidores antiguos python-oracledb necesita el Instant Client (thick mode).
            # Intentamos inicializar desde una variable de entorno o rutas comunes en Linux/Windows.
            try:
                instant_dir = None
                try:
                    import os
                    instant_dir = os.environ.get('ORACLE_INSTANTCLIENT_DIR')
                except Exception:
                    instant_dir = None

                candidates = []
                if instant_dir:
                    candidates.append(instant_dir)
                # rutas comunes en Linux
                candidates.extend([
                    '/opt/oracle/instantclient_23_0',
                    '/opt/oracle/instantclient_21_3',
                    '/usr/lib/oracle/21/client64/lib'
                ])
                # ruta común en Windows (por si se ejecuta localmente)
                candidates.append(r"D:\oracle\instantclient_23_0")

                initialized = False
                for path in candidates:
                    try:
                        if path:
                            oracledb.init_oracle_client(lib_dir=path)
                            self.stdout.write(self.style.SUCCESS(f"Inicializado Oracle Instant Client desde: {path}"))
                            initialized = True
                            break
                    except Exception:
                        continue

                if not initialized:
                    # no pudo inicializar thick client; seguirá en thin y quizá falle con DPY-3010
                    self.stdout.write(self.style.WARNING('No se pudo inicializar Oracle Instant Client (thick mode). Se intentará conectar en thin mode).'))
            except Exception:
                pass

            # 2. CREAR CONEXIÓN Y CURSOR
            con_oracle = oracledb.connect(user=usuario_oracle, password=password_oracle, dsn=dsn)
            cursor = con_oracle.cursor()

            # 3. EJECUTAR CONSULTA
            consulta = """
                       SELECT PERMISOS.FECHA, \
                              PERMISOS.HORAENTRADA, \
                              PERMISOS.HORASALIDA,
                              PERMISOS.CEDULA, \
                              PERMISOS.MOTIVO, \
                              PERMISOS.CARGOPERMISO
                       FROM PERMISOS
                       WHERE to_date(PERMISOS.FECHA, 'DD/MM/YY') >= to_date(:ini, 'DD/MM/YYYY')
                         AND to_date(PERMISOS.FECHA, 'DD/MM/YY') <= to_date(:fin, 'DD/MM/YYYY') \
                       """

            self.stdout.write("Ejecutando consulta en Oracle...")
            cursor.execute(consulta, ini=fecha_ini_str, fin=fecha_fin_str)
            registros = cursor.fetchall()

            num_migrados = 0

            # Listas para reportes detallados
            lista_errores = []
            lista_duplicados = []
            lista_fechas_invalidas = []  # 🟢 NUEVA LISTA

            # Usamos atomic para proteger la base de datos de PostgreSQL
            with transaction.atomic():
                for row in registros:
                    fecha_oracle, hora_entrada, hora_salida, cedula, motivo, cargo_permiso = row

                    empleado = Employee.objects.filter(person__document_number=cedula).first()

                    if not empleado:
                        lista_errores.append(cedula)
                        continue

                    # Extraemos la fecha que nos envió Oracle
                    fecha_permiso = fecha_oracle.date() if isinstance(fecha_oracle, datetime.datetime) else fecha_oracle

                    # 🟢 NUEVA VALIDACIÓN: Verificar que la fecha no sea un error de digitación viejo
                    if not (fecha_ini_dt <= fecha_permiso <= fecha_fin_dt):
                        detalle_invalido = f"Cédula: {cedula} | Fecha fuera de rango: {fecha_permiso.strftime('%d/%m/%Y')} | Motivo: {motivo}"
                        lista_fechas_invalidas.append(detalle_invalido)
                        continue

                    tipo_permiso, _ = PermitType.objects.get_or_create(
                        name=motivo,
                        defaults={
                            'is_active': True,
                            'needs_justification': False,
                            'affects_vacation': False
                        }
                    )

                    # CORRECCIÓN DE HORAS: SALIDA es cuando inicia el permiso, ENTRADA es cuando termina
                    t_inicio_permiso = hora_salida.time() if isinstance(hora_salida, datetime.datetime) else hora_salida
                    t_fin_permiso = hora_entrada.time() if isinstance(hora_entrada, datetime.datetime) else hora_entrada

                    delta = hora_entrada - hora_salida
                    total_seconds = delta.total_seconds()

                    # Seguro por si en la base antigua digitaron al revés
                    if total_seconds < 0:
                        t_inicio_permiso, t_fin_permiso = t_fin_permiso, t_inicio_permiso
                        total_seconds = abs(total_seconds)

                    existe = PermitRequest.objects.filter(
                        employee=empleado,
                        start_date=fecha_permiso,
                        start_time=t_inicio_permiso,
                        end_time=t_fin_permiso
                    ).exists()

                    if existe:
                        detalle_duplicado = f"Cédula: {cedula} | Fecha: {fecha_permiso.strftime('%d/%m/%Y')} | Horario: {t_inicio_permiso.strftime('%H:%M')} - {t_fin_permiso.strftime('%H:%M')}"
                        lista_duplicados.append(detalle_duplicado)
                        continue

                    if total_seconds >= 8 * 3600:
                        horas_calc = 8
                        minutos_calc = 0
                    else:
                        horas_calc = int(total_seconds // 3600)
                        minutos_calc = int((total_seconds % 3600) // 60)

                    PermitRequest.objects.create(
                        employee=empleado,
                        permit_type=tipo_permiso,
                        start_date=fecha_permiso,
                        end_date=fecha_permiso,
                        start_time=t_inicio_permiso,
                        end_time=t_fin_permiso,
                        days=0,
                        hours=horas_calc,
                        minutes=minutos_calc,
                        status='APPROVED',
                        response_note=f"Migración de sistema antiguo. Cargo original: {cargo_permiso}",
                        response_date=timezone.now(),
                        response_by=admin_user,
                        created_by=admin_user
                    )

                    num_migrados += 1

            cursor.close()
            con_oracle.close()

            # =========================================================
            # IMPRESIÓN DEL REPORTE DETALLADO
            # =========================================================
            self.stdout.write(self.style.SUCCESS(f"\n--- RESUMEN DE MIGRACIÓN ---"))
            self.stdout.write(self.style.SUCCESS(f"Permisos migrados exitosamente: {num_migrados}"))

            # 🟢 Imprimir Fechas Inválidas
            if lista_fechas_invalidas:
                self.stdout.write(
                    self.style.ERROR(f"\nFechas fuera de rango detectadas y omitidas: {len(lista_fechas_invalidas)}"))
                for inv in lista_fechas_invalidas:
                    self.stdout.write(f"  - {inv}")

            # Imprimir Duplicados
            self.stdout.write(self.style.WARNING(f"\nDuplicados omitidos: {len(lista_duplicados)}"))
            if lista_duplicados:
                self.stdout.write("Detalle de permisos que ya existían en PostgreSQL:")
                for duplicado in lista_duplicados:
                    self.stdout.write(f"  - {duplicado}")

            # Imprimir Errores
            cedulas_unicas_no_encontradas = set(lista_errores)
            self.stdout.write(
                self.style.ERROR(f"\nErrores (permisos saltados por empleado no encontrado): {len(lista_errores)}"))
            if cedulas_unicas_no_encontradas:
                self.stdout.write(
                    f"Cédulas no encontradas en el sistema nuevo ({len(cedulas_unicas_no_encontradas)} personas distintas):")
                for cedula_error in cedulas_unicas_no_encontradas:
                    self.stdout.write(f"  - {cedula_error}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error crítico en la conexión o proceso: {str(e)}"))
