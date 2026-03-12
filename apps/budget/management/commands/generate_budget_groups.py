from django.core.management.base import BaseCommand
from django.db import transaction
from budget.models import BudgetLine, BudgetGroup


class Command(BaseCommand):
    help = 'Genera y asigna grupos presupuestarios masivamente a las partidas existentes.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando escaneo de 5000+ partidas... por favor espera.")

        # Traemos todas las partidas optimizando las consultas foráneas
        lines = BudgetLine.objects.select_related(
            'activity__project__subprogram__program',
            'spending_type_item',
            'regime_item'
        ).all()

        grupos_creados = 0
        partidas_actualizadas = 0

        with transaction.atomic():  # Hace todo en un solo bloque para ser ultrarrápido
            for line in lines:
                if not line.code:
                    continue

                parts = line.code.split('.')
                if len(parts) >= 9:
                    try:
                        # 1. Matemática de códigos
                        p1, p2, p3, p4, p5 = str(int(parts[0])), str(int(parts[1])), str(int(parts[2])), str(
                            int(parts[3])), str(int(parts[4]))
                        numeric_base = f"{p1}{p2}{p3}{p4}{p5}"

                        gasto = f"{parts[5]}.{parts[6]}"
                        letter1 = 'C' if gasto == '5.1' else 'P' if gasto == '6.1' else 'I' if gasto == '7.1' else 'X'

                        item = f"{parts[7]}.{parts[8]}"
                        letter2 = 'E' if item == '01.05' else 'T' if item == '01.06' else 'C' if item == '05.10' else 'X'

                        short_code = f"{numeric_base}{letter1}{letter2}"
                        base_code = ".".join(parts[:9])

                        # 2. Nombres descriptivos
                        prog_name = line.activity.project.subprogram.program.name if line.activity else "S/P"
                        spend_name = line.spending_type_item.name if line.spending_type_item else "S/G"
                        regime_name = line.regime_item.name if line.regime_item else "S/R"
                        desc_name = f"Agrupación {prog_name} - {spend_name} - {regime_name}"[:255]

                        # 3. Creación del grupo
                        group, created = BudgetGroup.objects.get_or_create(
                            base_code=base_code,
                            defaults={'short_code': short_code, 'name': desc_name}
                        )

                        if created:
                            grupos_creados += 1

                        # 4. Asignación a la partida
                        if line.budget_group_id != group.id:
                            line.budget_group = group
                            line.save(update_fields=[
                                'budget_group'])  # Solo actualizamos este campo para no activar historiales
                            partidas_actualizadas += 1

                    except Exception as e:
                        self.stderr.write(f"Error procesando la partida {line.code}: {e}")

        self.stdout.write(self.style.SUCCESS(f"¡Proceso Terminado!"))
        self.stdout.write(self.style.SUCCESS(f"Nuevos grupos creados: {grupos_creados}"))
        self.stdout.write(self.style.SUCCESS(f"Partidas actualizadas y enlazadas: {partidas_actualizadas}"))