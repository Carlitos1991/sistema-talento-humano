# apps/function_manual/management/commands/init_occupational_matrix.py
from django.core.management.base import BaseCommand
from django.db import transaction
from function_manual.models import ManualCatalog, ManualCatalogItem, OccupationalMatrix
from decimal import Decimal

class Command(BaseCommand):
    help = 'Carga los catálogos base y la Matriz Ocupacional MDT 2025'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando Carga de Base Normativa 2025 ---'))

        try:
            with transaction.atomic():
                # --- ASEGURAR CATÁLOGOS ---
                cat_roles, _ = ManualCatalog.objects.get_or_create(code='JOB_ROLES', defaults={'name': 'Roles de Puestos'})
                role_apoyo, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_roles, code='EJE_APOYO', defaults={'name': 'Ejecución de Procesos de Apoyo'})
                role_ejec, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_roles, code='EJECUCION', defaults={'name': 'Ejecución de Procesos'})
                role_coord, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_roles, code='COORD', defaults={'name': 'Ejecución y Coordinación de Procesos'})

                cat_comp, _ = ManualCatalog.objects.get_or_create(code='COMPLEXITY_LEVELS', defaults={'name': 'Niveles de Complejidad'})
                comp_bajo, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_comp, code='BAJO', defaults={'name': 'Nivel Bajo'})
                comp_medio, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_comp, code='MEDIO', defaults={'name': 'Nivel Medio'})
                comp_alto, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_comp, code='ALTO', defaults={'name': 'Nivel Alto'})

                cat_inst, _ = ManualCatalog.objects.get_or_create(code='INSTRUCTION_LEVELS', defaults={'name': 'Niveles de Instrucción'})
                inst_tec, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_inst, code='TECNICO', defaults={'name': 'Técnico / Superior'})
                inst_univ, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_inst, code='TERCER_NIVEL', defaults={'name': 'Tercer Nivel (Grado)'})
                inst_post, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_inst, code='CUARTO_NIVEL', defaults={'name': 'Cuarto Nivel (Postgrado)'})

                cat_dec, _ = ManualCatalog.objects.get_or_create(code='DECISION_LEVELS', defaults={'name': 'Niveles de Toma de Decisiones'})
                dec_1, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_dec, code='DEC_1', defaults={'name': 'Nivel 1: Decisiones rutinarias'})
                dec_2, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_dec, code='DEC_2', defaults={'name': 'Nivel 2: Decisiones de baja incidencia'})

                cat_imp, _ = ManualCatalog.objects.get_or_create(code='IMPACT_LEVELS', defaults={'name': 'Niveles de Impacto de Gestión'})
                imp_1, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_imp, code='IMP_1', defaults={'name': 'Nivel 1: Impacto local'})
                imp_2, _ = ManualCatalogItem.objects.get_or_create(catalog=cat_imp, code='IMP_2', defaults={'name': 'Nivel 2: Impacto por unidad'})

                # --- DATOS COMPLETOS DE 7 NIVELES ---
                # Formato: (Grupo, Grado, RMU, Rol, Inst, Exp, Dec, Imp, Comp)
                full_matrix = [
                    ('SP1', 1, 817.00, role_apoyo, inst_tec, 12, dec_1, imp_1, comp_bajo),
                    ('SP2', 2, 901.00, role_apoyo, inst_tec, 24, dec_1, imp_1, comp_bajo),
                    ('SP3', 3, 986.00, role_ejec, inst_univ, 12, dec_2, imp_2, comp_medio),
                    ('SP4', 4, 1086.00, role_ejec, inst_univ, 24, dec_2, imp_2, comp_medio),
                    ('SP5', 5, 1212.00, role_coord, inst_univ, 36, dec_2, imp_2, comp_medio),
                    ('SP6', 6, 1412.00, role_coord, inst_univ, 48, dec_2, imp_2, comp_alto),
                    ('SP7', 7, 1676.00, role_coord, inst_post, 60, dec_2, imp_2, comp_alto),
                ]

                for row in full_matrix:
                    OccupationalMatrix.objects.update_or_create(
                        occupational_group=row[0],
                        grade=row[1],
                        defaults={
                            'remuneration': Decimal(row[2]),
                            'required_role': row[3],
                            'minimum_instruction': row[4],
                            'minimum_experience_months': row[5],
                            'required_decision': row[6],
                            'required_impact': row[7],
                            'complexity_level': row[8],
                        }
                    )

                self.stdout.write(self.style.SUCCESS(f'Éxito: Matriz Ocupacional cargada correctamente.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error Crítico: {str(e)}'))