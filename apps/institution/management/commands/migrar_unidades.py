import psycopg2
from django.core.management.base import BaseCommand
from django.db import transaction
from institution.models import AdministrativeUnit, OrganizationalLevel


class Command(BaseCommand):
    help = 'Migra la jerarquía antigua a la nueva tabla AdministrativeUnit mediante psycopg2 directo'

    def handle(self, *args, **options):
        # 🔴 REEMPLAZA ESTOS DATOS CON LOS DEL SERVIDOR ANTIGUO
        DB_HOST = "192.168.1.253"
        DB_PORT = "5432"
        DB_NAME = "db_talento_2020"
        DB_USER = "postgres"
        DB_PASS = r"Talento2023**"

        self.stdout.write(self.style.WARNING(f"Conectando a BD antigua (PG 10.10) en {DB_HOST}..."))

        map_institucion = {}
        map_directivo = {}
        map_direccion = {}
        map_jefatura = {}
        stats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        con_old = None
        try:
            # 🟢 MAGIA: Conexión directa con psycopg2 para evitar el bloqueo de versión de Django
            con_old = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
            cursor = con_old.cursor()

            with transaction.atomic():
                # 0. CONFIGURAR NIVELES ORGANIZACIONALES (En la BD Nueva)
                self.stdout.write("Configurando Niveles Organizacionales...")
                lvl_inst, _ = OrganizationalLevel.objects.get_or_create(name="Institución", defaults={'level_order': 1})
                lvl_dir, _ = OrganizationalLevel.objects.get_or_create(name="Nivel Directivo",
                                                                       defaults={'level_order': 2})
                lvl_direccion, _ = OrganizationalLevel.objects.get_or_create(name="Dirección",
                                                                             defaults={'level_order': 3})
                lvl_jef, _ = OrganizationalLevel.objects.get_or_create(name="Jefatura / Coordinación",
                                                                       defaults={'level_order': 4})
                lvl_depto, _ = OrganizationalLevel.objects.get_or_create(name="Departamento",
                                                                         defaults={'level_order': 5})

                # 1. MIGRAR INSTITUCIÓN (Nivel 1)
                cursor.execute("SELECT id, ruc, nombre, locacion, telefono FROM institution_institucion")
                for row in cursor.fetchall():
                    old_id, ruc, nombre, locacion, telefono = row
                    nueva_unidad = AdministrativeUnit.objects.create(
                        name=nombre, ruc=ruc, address=locacion, phone=telefono,
                        is_active=False, level=lvl_inst
                    )
                    map_institucion[old_id] = nueva_unidad
                    stats[1] += 1

                # 2. MIGRAR DIRECTIVO (Nivel 2)
                cursor.execute("SELECT id, institucion_id, nombre, locacion, telefono FROM institution_directivo")
                for row in cursor.fetchall():
                    old_id, inst_id, nombre, loc, tel = row
                    nueva_unidad = AdministrativeUnit.objects.create(
                        name=nombre, address=loc, phone=tel, parent=map_institucion.get(inst_id),
                        is_active=False, level=lvl_dir
                    )
                    map_directivo[old_id] = nueva_unidad
                    stats[2] += 1

                # 3. MIGRAR DIRECCIÓN (Nivel 3)
                cursor.execute("SELECT id, directivo_id, nombre, locacion, codigo FROM institution_direccion")
                for row in cursor.fetchall():
                    old_id, dir_id, nombre, loc, cod = row
                    nueva_unidad = AdministrativeUnit.objects.create(
                        name=nombre, code=cod, address=loc, parent=map_directivo.get(dir_id),
                        is_active=False, level=lvl_direccion
                    )
                    map_direccion[old_id] = nueva_unidad
                    stats[3] += 1

                # 4. MIGRAR JEFATURA / COORDINACIÓN (Nivel 4)
                cursor.execute("SELECT id, direccion_id, nombre, codigo FROM institution_jefaturacoordinacion")
                for row in cursor.fetchall():
                    old_id, dirc_id, nombre, cod = row
                    nueva_unidad = AdministrativeUnit.objects.create(
                        name=nombre, code=cod, parent=map_direccion.get(dirc_id),
                        is_active=False, level=lvl_jef
                    )
                    map_jefatura[old_id] = nueva_unidad
                    stats[4] += 1

                # 5. MIGRAR DEPARTAMENTO (Nivel 5)
                cursor.execute("SELECT id, jefatura_id, nombre, locacion, codigo FROM institution_departamento")
                for row in cursor.fetchall():
                    old_id, jef_id, nombre, loc, cod = row
                    AdministrativeUnit.objects.create(
                        name=nombre, code=cod, address=loc, parent=map_jefatura.get(jef_id),
                        is_active=False, level=lvl_depto
                    )
                    stats[5] += 1

            # RESUMEN DETALLADO
            self.stdout.write(self.style.SUCCESS("\n" + "=" * 40))
            self.stdout.write(self.style.SUCCESS("   RESUMEN DE UNIDADES CREADAS (INACTIVAS)"))
            self.stdout.write(self.style.SUCCESS("=" * 40))
            self.stdout.write(f"Nivel 1 (Institución):   {stats[1]}")
            self.stdout.write(f"Nivel 2 (Directivo):     {stats[2]}")
            self.stdout.write(f"Nivel 3 (Dirección):     {stats[3]}")
            self.stdout.write(f"Nivel 4 (Jefatura):      {stats[4]}")
            self.stdout.write(f"Nivel 5 (Departamento):  {stats[5]}")
            self.stdout.write(self.style.SUCCESS("=" * 40))
            self.stdout.write(self.style.SUCCESS(f"TOTAL UNIDADES: {sum(stats.values())}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error crítico: {str(e)}"))
        finally:
            # Cerramos la conexión manual
            if con_old:
                cursor.close()
                con_old.close()
