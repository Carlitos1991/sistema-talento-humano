"""
Capa de Servicios para el Módulo Institucional (SIGETH).
Encapsula cálculos jerárquicos, estadísticas consolidadas y exportación de reportes.
"""

from collections import deque
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from django.db.models import Q, F, Count, Case, When, IntegerField
from employee.models import Employee
from .models import AdministrativeUnit


def get_descendant_unit_ids(unit):
    """
    Obtiene iterativamente los IDs de una unidad y todas sus dependencias subordinadas.
    Previene bucles infinitos mediante control de nodos visitados.
    """
    descendants = [unit.pk]
    visited = {unit.pk}
    queue = deque(
        AdministrativeUnit.objects.filter(parent=unit, is_active=True)
        .values_list('id', flat=True)
    )

    while queue:
        current_id = queue.popleft()
        if current_id not in visited:
            visited.add(current_id)
            descendants.append(current_id)
            children_ids = AdministrativeUnit.objects.filter(
                parent_id=current_id, is_active=True
            ).values_list('id', flat=True)
            queue.extend(children_ids)

    return descendants


def get_consolidated_unit_employee_stats(unit):
    """Calcula estadísticas consolidadas de personal de la unidad y sus subdependencias."""
    all_unit_ids = get_descendant_unit_ids(unit)
    all_employees = Employee.objects.filter(
        area_id__in=all_unit_ids, is_active=True
    ).exclude(employment_status__name__icontains='EX ')

    own_cond = (
            Q(institutional_data__original_dependency=unit.pk) |
            Q(institutional_data__original_dependency__isnull=True, area_id=unit.pk)
    )
    relocated_cond = (
            Q(institutional_data__original_dependency__isnull=False) &
            ~Q(institutional_data__original_dependency=F('area'))
    )

    stats = all_employees.aggregate(
        total=Count('id'),
        empleados=Count(Case(When(employment_status__code='EMPLEADO', then=1), output_field=IntegerField())),
        trabajadores=Count(Case(When(employment_status__code='TRABAJADOR', then=1), output_field=IntegerField())),
        contratados=Count(Case(When(employment_status__code='CONTRATADO', then=1), output_field=IntegerField())),
        propios=Count(Case(When(own_cond, then=1), output_field=IntegerField())),
        reubicados=Count(Case(When(relocated_cond, then=1), output_field=IntegerField())),
    )

    return {
        'total': stats['total'] or 0,
        'empleado': stats['empleados'] or 0,
        'trabajador': stats['trabajadores'] or 0,
        'contratado': stats['contratados'] or 0,
        'propios': stats['propios'] or 0,
        'reubicados': stats['reubicados'] or 0,
    }


def build_unit_employees_workbook(unit, status_code='TOTAL'):
    """Construye el libro Excel con la nómina filtrada de una unidad y sus descendientes."""
    all_unit_ids = get_descendant_unit_ids(unit)

    employees = Employee.objects.filter(
        area_id__in=all_unit_ids, is_active=True
    ).exclude(
        employment_status__name__icontains='EX '
    ).select_related(
        'person',
        'employment_status',
        'area',
        'institutional_data__original_dependency'
    ).prefetch_related(
        'current_budget_line__position_item'
    ).order_by('area__name', 'person__last_name')

    own_cond = (
            Q(institutional_data__original_dependency=unit.pk) |
            Q(institutional_data__original_dependency__isnull=True, area_id=unit.pk)
    )

    if status_code == 'PROPIOS':
        employees = employees.filter(own_cond)
    elif status_code == 'REUBICADOS':
        employees = employees.exclude(own_cond)
    elif status_code != 'TOTAL':
        employees = employees.filter(employment_status__code=status_code)

    wb = Workbook()
    ws = wb.active
    ws.title = status_code if status_code != 'TOTAL' else "Todos"

    headers = [
        'N°', 'Apellidos y Nombres', 'Cédula/Documento', 'Dependencia Actual',
        'Dependencia Original', 'Cargo', 'Remuneración'
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color="198754", end_color="198754", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_align = Alignment(horizontal="center", vertical="center")

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align

    for idx, emp in enumerate(employees, start=1):
        full_name = f"{emp.person.last_name} {emp.person.first_name}"
        document = emp.person.document_number or '-'
        current_area = emp.area.name if emp.area else '-'

        orig_area = current_area
        if getattr(emp, 'institutional_data', None) and emp.institutional_data.original_dependency:
            orig_area = emp.institutional_data.original_dependency.name

        cargo = '-'
        remuneracion = '-'
        budget_line = emp.current_budget_line.first()
        if budget_line:
            if budget_line.position_item:
                cargo = budget_line.position_item.name
            if getattr(budget_line, 'remuneration', None):
                remuneracion = f"${budget_line.remuneration:,.2f}"

        ws.append([idx, full_name, document, current_area, orig_area, cargo, remuneracion])

    column_widths = [8, 40, 18, 35, 35, 35, 15]
    for i, width in enumerate(column_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    return wb
