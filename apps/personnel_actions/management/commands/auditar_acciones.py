import psycopg2
from django.core.management.base import BaseCommand
from django.conf import settings
from employee.models import Employee
# Asegúrate de que este import coincida con tu app en SIGETH 2[cite: 4]
from personnel_actions.models import PersonnelAction, ActionType
from institution.models import AdministrativeUnit


class Command(BaseCommand):
    help = 'Auditoría completa de Acciones: Detecta Tipos de Acción, Unidades y Empleados faltantes'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, required=True)
        parser.add_argument('--mes', type=int, help='Opcional')

    def handle(self, *args, **options):
        anio, mes = options['anio'], options['mes']

        # --- CONFIGURACIÓN DE MAPEOS (Llénalos conforme el reporte te dé errores) ---
        MAPEO_TIPO_ACCION = {
            20: 2,  # Ejemplo: Vacaciones[cite: 5]
            6: 4,  # Ejemplo: Encargo[cite: 5]
            16: 6,  # Ejemplo: Renuncia[cite: 5]
            19: 7,  # Ejemplo: Renuncia[cite: 5]
            22: 7,  # Ejemplo: Renuncia[cite: 5]
            28: 8,  # Ejemplo: Renuncia[cite: 5]
            14: 9,  # Ejemplo: Renuncia[cite: 5]
            12: 10,  # Ejemplo: Renuncia[cite: 5]
            18: 11,  # Ejemplo: Renuncia[cite: 5]
            24: 3,  # Ejemplo: Renuncia[cite: 5]
            17: 12,  # Ejemplo: Renuncia[cite: 5]
        }

        MAPEO_UNIDADES = {
            "Centro de Apoyo Social Municipal": 128,  # Formato pedido: "TEXTO_ORIGEN": ID_DESTINO
            "Dirección Administrativa": 30,
            "Dirección de Higiene": 73,
            "UMAPAL": 67,
            "Dirección de Seguridad Ciudadana y Control Público": 70,
            "Dirección Estratégica de Tránsito": 87,
            "Dirección de Cultura": 95,
            "Dirección de Educación, Deportes y Recreación": 93,
            "Dirección de Gestión Ambiental": 72,
            "Dirección de Gestión Económica": 68,
            "Dirección de Gestión Territorial": 65,
            "Dirección de Movilidad y Transporte": 69,
            "Dirección de Obras Públicas": 66,
            "Dirección de Planificación": 15,
            "Dirección de Talento Humano": 32,
            "Secretaría General": 5,
        }

        # Sets para recolectar lo que falta (evita duplicados en el reporte)
        tipos_faltantes = set()
        unidades_faltantes = set()
        cedulas_faltantes = set()

        total_analizados = 0
        db_config = settings.DATABASES['old_db']

        self.stdout.write(self.style.SUCCESS(f"🔍 Iniciando Auditoría de Acciones - Año: {anio}"))

        try:
            conn = psycopg2.connect(
                dbname=db_config['NAME'], user=db_config['USER'],
                password=db_config['PASSWORD'], host=db_config['HOST'], port=db_config['PORT']
            )

            with conn.cursor() as cursor:
                # SQL: Cruza la acción con su nombre y su historial de movimiento[cite: 3, 5]
                sql = """
                      SELECT per.cedula,
                             pa.action_id     as id_old,
                             act.name         as nombre_tipo_old,
                             ha.direction_new as unidad_texto_old,
                             pa.number
                      FROM actions_personnelaction pa
                               INNER JOIN employee_employee e ON pa.employee_id = e.id
                               INNER JOIN person_person per ON e.person_id = per.id
                               INNER JOIN actions_actions act ON pa.action_id = act.id
                               LEFT JOIN actions_history_actions ha ON ha.personnel_action_id = pa.id
                      WHERE EXTRACT(YEAR FROM pa.date_issue) = %s
                      """
                params = [anio]
                if mes:
                    sql += " AND EXTRACT(MONTH FROM pa.date_issue) = %s"
                    params.append(mes)

                cursor.execute(sql, params)

                for row in cursor.fetchall():
                    total_analizados += 1
                    cedula, id_tipo_old, nombre_tipo_old, unidad_txt, numero = row

                    # 1. Validar Tipo de Acción
                    id_nuevo = MAPEO_TIPO_ACCION.get(id_tipo_old)
                    if not id_nuevo and not ActionType.objects.filter(name__iexact=nombre_tipo_old).exists():
                        tipos_faltantes.add(f"{nombre_tipo_old} (ID:{id_tipo_old})")

                    # 2. Validar Unidades (Departamentos)
                    if unidad_txt and unidad_txt not in MAPEO_UNIDADES:
                        # Si no está en el mapa, buscamos si existe por nombre en SIGETH 2[cite: 4]
                        if not AdministrativeUnit.objects.filter(name__iexact=unidad_txt).exists():
                            unidades_faltantes.add(unidad_txt)

                    # 3. Validar Empleado
                    if not Employee.objects.filter(person__document_number=cedula).exists():
                        cedulas_faltantes.add(cedula)

            conn.close()

            # --- REPORTE DE RESULTADOS ---
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.SUCCESS(f"🏁 REPORTE DE AUDITORÍA: {total_analizados} REGISTROS"))
            self.stdout.write("=" * 70)

            if tipos_faltantes:
                self.stdout.write(self.style.ERROR("❌ TIPOS DE ACCIÓN SIN MAPEAR (Agrega a MAPEO_TIPO_ACCION):"))
                for t in sorted(tipos_faltantes):
                    self.stdout.write(f"   -> {t}")
            else:
                self.stdout.write(self.style.SUCCESS("✅ Todos los tipos de acción están mapeados."))

            self.stdout.write("-" * 70)

            if unidades_faltantes:
                self.stdout.write(self.style.ERROR("❌ UNIDADES/DEPARTAMENTOS SIN MAPEAR (Agrega a MAPEO_UNIDADES):"))
                for u in sorted(unidades_faltantes):
                    # Aquí te imprime el formato exacto para que solo copies y pegues
                    self.stdout.write(f'   -> "{u}": ID_NUEVO')
            else:
                self.stdout.write(self.style.SUCCESS("✅ Todas las unidades están mapeadas."))

            self.stdout.write("-" * 70)

            if cedulas_faltantes:
                self.stdout.write(
                    self.style.WARNING(f"👤 EMPLEADOS NO ENCONTRADOS EN SIGETH 2: {len(cedulas_faltantes)}"))

            self.stdout.write("=" * 70 + "\n")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error en la auditoría: {e}"))