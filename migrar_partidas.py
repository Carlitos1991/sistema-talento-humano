import os
import sys
from pathlib import Path

# Configuración del entorno de Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talento_humano.settings')

import django

django.setup()

from django.db import connection, transaction
from employee.models import Employee, InstitutionalData
from budget.models import BudgetLine, BudgetAssignmentHistory

# Obtener el nombre real de la tabla configurada en el modelo
table_name = BudgetAssignmentHistory._meta.db_table
print(f"Nombre real de la tabla de asignaciones: {table_name}")

print("\n1. Reparando fechas corruptas en la base de datos...")
with connection.cursor() as cursor:
    cursor.execute(f"""
        UPDATE "{table_name}"
        SET start_date = (start_date - INTERVAL '18100 years')::date 
        WHERE EXTRACT(YEAR FROM start_date) = 20123;
    """)
    cursor.execute(f"""
        UPDATE "{table_name}"
        SET end_date = (end_date - INTERVAL '18100 years')::date 
        WHERE EXTRACT(YEAR FROM end_date) = 20123;
    """)
print("Fechas reparadas exitosamente.")

print("\n2. Asignando partida original a los empleados...")
employees = list(Employee.objects.all())
print(f"Total empleados encontrados: {len(employees)}")

actualizados = 0
ya_configurados = 0
sin_partida = 0

with transaction.atomic():
    for emp in employees:
        inst_data, _ = InstitutionalData.objects.get_or_create(employee=emp)

        # Si ya tiene partida original, se conserva
        if inst_data.original_budget_line_id:
            ya_configurados += 1
            continue

        # 1. Buscar en la partida activa actual (current_employee)
        bl = BudgetLine.objects.filter(current_employee=emp).first()

        # 2. Si no tiene, buscar la última asignación en el historial
        if not bl:
            hist = (
                BudgetAssignmentHistory.objects
                .filter(employee=emp)
                .exclude(start_date__year__gt=2100)
                .select_related('budget_line')
                .order_by('-start_date')
                .first()
            )
            if hist:
                bl = hist.budget_line

        # 3. Guardar en InstitutionalData
        if bl:
            inst_data.original_budget_line = bl
            inst_data.save(update_fields=['original_budget_line'])
            actualizados += 1
        else:
            sin_partida += 1

print("\n--- Resultado Final ---")
print(f"Actualizados exitosamente: {actualizados}")
print(f"Ya tenían partida previa: {ya_configurados}")
print(f"Sin partida encontrada: {sin_partida}")