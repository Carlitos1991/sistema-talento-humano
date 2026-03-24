import psycopg2
import re
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from employee.models import Employee
from core.models import CatalogItem
from institution.models import AdministrativeUnit
from schedule.models import Schedule
from budget.models import BudgetLine
from contract.models import ManagementPeriod, LaborRegime, ContractType, History


class Command(BaseCommand):
    help = 'Migración Total: Unidades estrictas usando departamento_id y direccion_id reales'

    def handle(self, *args, **options):
        log_file = "log_migracion_contratos.txt"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"--- MIGRACIÓN DE UNIDADES EXACTAS: {datetime.now()} ---\n\n")

        def escribir_log(mensaje):
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{mensaje}\n")

        MAPEO_REGIMEN = {
            'CODIGO DE TRABAJO': 'CT',
            'CÓDIGO DE TRABAJO': 'CT',
            'CODIGO_DE_TRABAJO': 'CT',
            'LOSEP': 'LOSEP',
            'LEY ORGANICA DE SERVICIO CIVIL Y CARRERA ADMINISTRATIVA': 'LOSEP'
        }

        stats = {
            'exitosos': 0,
            'error_cedula': 0,
            'unidades_no_encontradas': 0
        }

        DB_PASS = r"Talento2023**"

        try:
            con_old = psycopg2.connect(host="192.168.1.253", dbname="db_talento_2020", user="postgres",
                                       password=DB_PASS)
            cursor = con_old.cursor()

            # 🟢 Tablas actualizadas según tu captura de pgAdmin
            cursor.execute("""
                           SELECT p.cedula,
                                  c.regimen,
                                  c.tipo_contrato,
                                  c.funciones,
                                  c.lugar_trabajo,
                                  c.certificacion_presupuestaria,
                                  c.partida,
                                  c.cargo,
                                  c.remuneracion,
                                  c.fecha_inicio,
                                  c.fecha_fin,
                                  c.estado,
                                  c.codigo,
                                  dep.nombre AS depto_nombre,
                                  dir.nombre AS dir_nombre
                           FROM contrato_contrato c
                                    JOIN employee_employee e ON c.empleado_id = e.id
                                    JOIN person_person p ON e.person_id = p.id
                                    LEFT JOIN institution_departamento dep ON c.departamento_id = dep.id
                                    LEFT JOIN institution_direccion dir ON c.direccion_id = dir.id
                           """)
            registros = cursor.fetchall()

            status_firmado = CatalogItem.objects.filter(catalog__code='STATUS_CONTRACT',
                                                        name__icontains='FIRMADO').first()
            status_finalizado = CatalogItem.objects.filter(catalog__code='STATUS_CONTRACT',
                                                           name__icontains='FINALIZADO').first()
            default_schedule = Schedule.objects.first()
            default_unit = AdministrativeUnit.objects.first()  # Unidad comodín si no existe

            for row in registros:
                # Recibimos depto_nombre y dir_nombre de la consulta
                (cedula, reg, tipo, func, lugar, cert, part_old, cargo_old, rem_old, f_ini, f_fin, est, cod,
                 depto_nombre, dir_nombre) = row

                empleado = Employee.objects.filter(person__document_number=cedula).first()
                if not empleado:
                    stats['error_cedula'] += 1
                    continue

                # Normalización de Cargo y Partida
                cargo_str = str(cargo_old).upper().strip() if cargo_old else "SIN CARGO"
                cargo_base = re.sub(r'/\s*[AO]\b', '', cargo_str).replace('(A)', '').replace('(O)', '')
                cargo_base = re.sub(r'\s+', ' ', cargo_base).strip()

                budget_line = BudgetLine.objects.filter(number_individual=part_old).first()
                if not budget_line:
                    budget_line = BudgetLine.objects.filter(position_item__name__iexact=cargo_base).first()

                # 🟢 BÚSQUEDA DE LA UNIDAD REAL:
                # Damos prioridad al departamento (nivel más bajo). Si es nulo, usamos la dirección.
                unidad_antigua_str = str(depto_nombre or dir_nombre or '').strip().upper()

                unidad_obj = None
                if unidad_antigua_str and unidad_antigua_str != 'NONE':
                    # 1. Búsqueda exacta
                    unidad_obj = AdministrativeUnit.objects.filter(name__iexact=unidad_antigua_str).first()
                    # 2. Si no encuentra exacta, busca coincidencia parcial
                    if not unidad_obj:
                        unidad_obj = AdministrativeUnit.objects.filter(name__icontains=unidad_antigua_str).first()

                # Respaldo en Historial si la unidad no existe en el sistema nuevo
                texto_historial = cargo_str
                if unidad_obj:
                    unidad_final = unidad_obj
                else:
                    unidad_final = default_unit
                    if unidad_antigua_str and unidad_antigua_str != 'NONE':
                        stats['unidades_no_encontradas'] += 1
                        texto_historial = f"{cargo_str} | Unidad Orig: {unidad_antigua_str}"

                try:
                    with transaction.atomic():
                        nuevo_estado = status_firmado if est == 'Firmado' else status_finalizado
                        reg_original = str(reg or '').upper().strip()
                        reg_codigo = MAPEO_REGIMEN.get(reg_original, reg_original.replace(" ", "_")[:10])
                        reg_obj, _ = LaborRegime.objects.get_or_create(code=reg_codigo,
                                                                       defaults={'name': reg_original or 'SIN REGIMEN'})

                        tip_name = str(tipo or 'SIN TIPO').upper().strip()
                        tip_obj, _ = ContractType.objects.get_or_create(
                            code=tip_name[:50].replace(" ", "_"), labor_regime=reg_obj, defaults={'name': tip_name}
                        )

                        doc_cod = cod if cod else f"MIG-{cedula}-{f_ini}"

                        nuevo_contrato = ManagementPeriod.objects.create(
                            document_number=doc_cod,
                            employee=empleado,
                            budget_line=budget_line,
                            contract_type=tip_obj,
                            status=nuevo_estado,
                            schedule=default_schedule,
                            administrative_unit=unidad_final,
                            job_functions=func or 'Migrado',
                            workplace=lugar or 'Loja',
                            start_date=f_ini,
                            end_date=f_fin if f_fin and f_fin >= f_ini else None,
                        )

                        History.objects.create(
                            employee=empleado,
                            contract=nuevo_contrato,
                            type="MIGRACION",
                            user_register="SISTEMA",
                            historical_position=texto_historial,
                            historical_salary=Decimal(str(rem_old)) if rem_old else Decimal('0.00')
                        )
                        stats['exitosos'] += 1

                except Exception as e:
                    escribir_log(f"[ERROR] {cedula} | {str(e)}")

            self.stdout.write(self.style.SUCCESS(f"\n✅ MIGRACIÓN FINALIZADA"))
            self.stdout.write(f"Total Migrados:          {stats['exitosos']}")
            self.stdout.write(self.style.WARNING(f"Deptos no enlazados (Texto): {stats['unidades_no_encontradas']}"))
            self.stdout.write(self.style.ERROR(f"Cédulas faltantes:       {stats['error_cedula']}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error Crítico: {str(e)}"))
        finally:
            if 'con_old' in locals(): con_old.close()