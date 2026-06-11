"""
schedule_prefetch.py
────────────────────
Helper para cargar TODOS los horarios de una lista de empleados en
2 queries planas

USO EN generate_department_report_pdf (biometric/views.py):
------------------------------------------------------------

    from .schedule_prefetch import build_schedule_cache, get_schedule_from_cache

    # — justo después de construir emp_ids y antes del bucle —
    schedule_cache = build_schedule_cache(emp_ids, month_start, month_end)
"""

from __future__ import annotations
from collections import defaultdict
from datetime import date
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

from django.db.models import Q


# ──────────────────────────────────────────────────────────────────────────────
# PASO 1 — Construcción del caché (llamar UNA sola vez antes del bucle)
# ──────────────────────────────────────────────────────────────────────────────

def build_schedule_cache(
    emp_ids: List[int],
    month_start: date,
    month_end: date,
) -> Dict[int, list]:
    """
    Devuelve un dict  {employee_id: [EmployeeScheduleHistory ordenados desc por start_date]}
    con todos los registros de historial que solapan el mes pedido.

    Solo hace 2 queries a la BD, independientemente de cuántos empleados haya.

    Args:
        emp_ids:     lista de employee_id que participan en el reporte.
        month_start: primer día del mes (date).
        month_end:   último día del mes (date).

    Returns:
        schedule_cache — dict que se pasa a get_schedule_from_cache().
    """
    from schedule.models import EmployeeScheduleHistory, ScheduleChangeHistory

    # ── Query 1: EmployeeScheduleHistory del mes ──────────────────────────────
    # Traemos todos los registros cuyo rango [start_date, end_date] se solapa
    # con [month_start, month_end], incluyendo asignaciones sin end_date.
    histories = (
        EmployeeScheduleHistory.objects
        .filter(
            employee_id__in=emp_ids,
            start_date__lte=month_end,          # empieza antes de que acabe el mes
        )
        .filter(
            Q(end_date__isnull=True) |
            Q(end_date__gte=month_start)         # termina después de que empiece el mes
        )
        .select_related('schedule')
        .order_by('employee_id', '-start_date')  # más reciente primero por empleado
    )

    # Indexar por employee_id
    cache: Dict[int, list] = defaultdict(list)
    schedule_ids_needed: set = set()

    for h in histories:
        cache[h.employee_id].append(h)
        if h.schedule_id:
            schedule_ids_needed.add(h.schedule_id)

    # ── Query 2: ScheduleChangeHistory para todos los Schedule involucrados ───
    # Traemos únicamente los cambios con effective_from <= month_end
    # (el más reciente aplicable a cada fecha lo resolvemos en memoria).
    change_hist_map: Dict[int, list] = defaultdict(list)

    if schedule_ids_needed:
        changes = (
            ScheduleChangeHistory.objects
            .filter(
                schedule_id__in=schedule_ids_needed,
                effective_from__lte=month_end,
            )
            .order_by('schedule_id', '-effective_from')
        )
        for ch in changes:
            change_hist_map[ch.schedule_id].append(ch)

    # Guardar el mapa de cambios dentro del cache para uso posterior
    # (lo almacenamos con clave especial para no mezclarlo con emp_ids)
    cache['__change_hist__'] = change_hist_map  # type: ignore[assignment]

    return dict(cache)


# ──────────────────────────────────────────────────────────────────────────────
# PASO 2 — Consulta por (employee_id, fecha) usando el caché en memoria
# ──────────────────────────────────────────────────────────────────────────────

def get_schedule_from_cache(
    schedule_cache: Dict,
    employee_id: int,
    target_date: date,
) -> Optional[SimpleNamespace]:
    """
    Equivalente exacto a get_employee_schedule_for_date() pero usando el caché
    construido por build_schedule_cache(). Cero queries adicionales a la BD.

    Args:
        schedule_cache: dict devuelto por build_schedule_cache().
        employee_id:    pk del empleado.
        target_date:    fecha para la que se quiere el horario.

    Returns:
        SimpleNamespace con los mismos atributos que devuelve
        get_employee_schedule_for_date(), o None si no hay asignación.
    """
    change_hist_map = schedule_cache.get('__change_hist__', {})
    histories: list = schedule_cache.get(employee_id, [])

    if not histories:
        return None

    # Buscar la asignación más reciente válida para target_date
    # (ya vienen ordenadas por -start_date)
    row = None
    for h in histories:
        if h.start_date > target_date:
            continue
        if h.end_date is not None and h.end_date < target_date:
            continue
        row = h
        break

    if row is None or row.schedule is None:
        return None

    sched = row.schedule

    # Buscar ScheduleChangeHistory aplicable a target_date
    changes_for_sched: list = change_hist_map.get(sched.pk, [])
    # Ya vienen ordenadas por -effective_from; el primero <= target_date es el correcto
    hist = None
    for ch in changes_for_sched:
        if ch.effective_from <= target_date:
            hist = ch
            break

    if hist:
        # Construir SimpleNamespace igual que la función original
        obj = SimpleNamespace()
        obj.id = sched.id
        obj.name = sched.name
        obj.morning_start = hist.morning_start
        obj.morning_end = hist.morning_end
        obj.morning_crosses_midnight = hist.morning_crosses_midnight
        obj.afternoon_start = hist.afternoon_start
        obj.afternoon_end = hist.afternoon_end
        obj.afternoon_crosses_midnight = hist.afternoon_crosses_midnight
        obj.monday = hist.monday
        obj.tuesday = hist.tuesday
        obj.wednesday = hist.wednesday
        obj.thursday = hist.thursday
        obj.friday = hist.friday
        obj.saturday = hist.saturday
        obj.sunday = hist.sunday
        obj.late_tolerance_minutes = hist.late_tolerance_minutes
        obj.daily_hours = hist.daily_hours
        obj.is_continuous = (obj.afternoon_start is None)
        return obj

    # Sin ScheduleChangeHistory: devolver el Schedule base directamente
    return sched