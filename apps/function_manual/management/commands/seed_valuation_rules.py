# apps/function_manual/management/commands/seed_valuation_rules.py
from django.core.management.base import BaseCommand
from django.db import transaction
from function_manual.models import OccupationalMatrix, ValuationNode


class Command(BaseCommand):
    help = 'Puebla la estructura jerárquica de valoración basada en la Matriz Ocupacional 2025'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando Construcción de Árbol Jerárquico 2025 ---'))

        try:
            with transaction.atomic():
                # 1. Limpieza total para reconstruir la estructura exacta
                ValuationNode.objects.all().delete()

                # 2. Obtener la Matriz Ocupacional
                matrix_entries = OccupationalMatrix.objects.all()

                if not matrix_entries.exists():
                    self.stdout.write(
                        self.style.ERROR('Error: No hay datos en OccupationalMatrix. Cargue la matriz primero.'))
                    return

                count = 0
                for entry in matrix_entries:
                    # NIVEL 1: ROL
                    role_node, _ = ValuationNode.objects.get_or_create(
                        parent=None,
                        node_type='ROLE',
                        catalog_item=entry.required_role
                    )

                    # NIVEL 2: INSTRUCCIÓN
                    instruction_node, _ = ValuationNode.objects.get_or_create(
                        parent=role_node,
                        node_type='INSTRUCTION',
                        catalog_item=entry.minimum_instruction
                    )

                    # NIVEL 3: EXPERIENCIA
                    experience_node, _ = ValuationNode.objects.get_or_create(
                        parent=instruction_node,
                        node_type='EXPERIENCE',
                        name_extra=f"Mínimo {entry.minimum_experience_months} meses"
                    )

                    # NIVEL 4: DECISIÓN
                    decision_node, _ = ValuationNode.objects.get_or_create(
                        parent=experience_node,
                        node_type='DECISION',
                        catalog_item=entry.required_decision
                    )

                    # NIVEL 5: IMPACTO
                    impact_node, _ = ValuationNode.objects.get_or_create(
                        parent=decision_node,
                        node_type='IMPACT',
                        catalog_item=entry.required_impact
                    )

                    # NIVEL 6: COMPLEJIDAD
                    complexity_node, _ = ValuationNode.objects.get_or_create(
                        parent=impact_node,
                        node_type='COMPLEXITY',
                        catalog_item=entry.complexity_level
                    )

                    # NIVEL 7: RESULTADO (GRUPO OCUPACIONAL)
                    result_node, created = ValuationNode.objects.get_or_create(
                        parent=complexity_node,
                        node_type='RESULT',
                        occupational_classification=entry,
                        name_extra=f"{entry.occupational_group} (${entry.remuneration})"
                    )

                    if created:
                        count += 1

                self.stdout.write(self.style.SUCCESS(f'Éxito: Se han generado {count} rutas finales de clasificación.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error Crítico: {str(e)}'))