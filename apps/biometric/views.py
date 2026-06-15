import calendar
import json
import logging
from datetime import datetime, date, timedelta
from datetime import time as dtime
from django.utils import timezone
import base64
import mimetypes
import os
from decimal import Decimal
from uuid import UUID
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import TemplateView, View, ListView
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string, get_template
from django.db import transaction, models

logger = logging.getLogger(__name__)
ENABLE_SHIFT_COLLAPSE = False  # desactivar colapso automático hasta afinar reglas
# Configurables para el emparejador (ajustables según pruebas)
DEDUPE_WINDOW_MINUTES = 3  # 3 minutos no acepta duplicados dentro de los primeros 3 minutos
IN_TOLERANCE_SECONDS = 60  # 1 minuto de tolerancia para in
OUT_MAX_SECONDS = 90 * 60  # 30 minutos para aceptar out antes del evento si no hay after
IN_MAX_SECONDS = 60 * 60 * 2  # 2 horas máximo para emparejar despues en in
CROSS_SHIFT_THRESHOLD = 60  # umbral en segundos para decidir entre salida vs ingreso cercano


def _p_dt(p):
    return p.get('dt_norm') or p.get('dt')


def select_in_candidate(candidates, ev_dt, prev_ev_dt=None, next_ev_dt=None):
    """Selecciona candidato para evento 'in'.
    Preferir el candidato más cercano ANTES de ev_dt. Si no existe, elegir el más cercano DESPUÉS
    sólo si está dentro de IN_MAX_SECONDS. Además, si el candidato posterior está claramente
    más cercano al siguiente evento (next_ev_dt) y dentro de CROSS_SHIFT_THRESHOLD, se evita.
    """
    if not candidates:
        return None
    before = [p for p in candidates if _p_dt(p) <= ev_dt]
    if before:
        # elegir el anterior más cercano (máxima dt)
        return max(before, key=lambda p: (_p_dt(p) - ev_dt).total_seconds())
    after = [p for p in candidates if _p_dt(p) > ev_dt]
    if not after:
        return None
    # elegir el posterior más cercano si está dentro del máximo
    best_after = min(after, key=lambda p: (_p_dt(p) - ev_dt).total_seconds())
    diff = (_p_dt(best_after) - ev_dt).total_seconds()
    if diff <= IN_MAX_SECONDS:
        # comprobar regla literal cross-shift: si el punch está claramente
        # más cercano al evento previo (prev_ev_dt) según umbral, no tomarlo.
        if prev_ev_dt:
            res = resolve_cross_shift(best_after, prev_ev_dt=prev_ev_dt, next_ev_dt=next_ev_dt)
            if res == 'prev':
                return None
        # si está claramente más cercano al siguiente evento, permitirlo
        return best_after
    return None


def select_out_candidate(candidates, ev_dt, prev_ev_dt=None, next_ev_dt=None):
    """Selecciona candidato para evento 'out'.
    Preferir el candidato más cercano DESPUÉS de ev_dt. Si no existe, elegir el más cercano ANTES
    sólo si está dentro de OUT_MAX_SECONDS.
    """
    if not candidates:
        return None
    after = [p for p in candidates if _p_dt(p) >= ev_dt]
    if after:
        # elegir el posterior más cercano (mínima dt)
        best_after = min(after, key=lambda p: (_p_dt(p) - ev_dt).total_seconds())
        # evitar robar un punch que sea claramente más cercano al siguiente evento
        try:
            res = resolve_cross_shift(best_after, prev_ev_dt=ev_dt, next_ev_dt=next_ev_dt)
            if res == 'next':
                return None
        except Exception:
            pass
        return best_after
    before = [p for p in candidates if _p_dt(p) < ev_dt]
    if not before:
        return None
    best_before = max(before, key=lambda p: (_p_dt(p) - ev_dt).total_seconds())
    diff = abs((_p_dt(best_before) - ev_dt).total_seconds())
    if diff <= OUT_MAX_SECONDS:
        # si este punch es muy cercano al evento anterior, y prev_ev_dt existe, evitar robarlo
        if prev_ev_dt:
            diff_prev = abs((_p_dt(best_before) - prev_ev_dt).total_seconds())
            if diff_prev <= CROSS_SHIFT_THRESHOLD and diff_prev < diff:
                return None
        return best_before
    return None


def resolve_cross_shift(punch, prev_ev_dt=None, next_ev_dt=None):
    """Decide si un `punch` que cae entre dos eventos pertenece al evento previo o al siguiente
    según la cercanía y el umbral `CROSS_SHIFT_THRESHOLD`. Devuelve 'prev', 'next' o None.
    """
    try:
        p_dt = _p_dt(punch)
    except Exception:
        return None
    if prev_ev_dt and next_ev_dt:
        diff_prev = abs((p_dt - prev_ev_dt).total_seconds())
        diff_next = abs((p_dt - next_ev_dt).total_seconds())
        if diff_prev <= CROSS_SHIFT_THRESHOLD and diff_prev < diff_next:
            return 'prev'
        if diff_next <= CROSS_SHIFT_THRESHOLD and diff_next < diff_prev:
            return 'next'
        # si ninguno está dentro del umbral, devolver None para que la selección use otras reglas
    return None


def build_attendance_summary_for_employee(calendar_data_local, year_local, month_local, employee_obj, debug_flag=False):
    """Helper reutilizable para calcular inconsistencias, dias sin marcar y minutos de atraso
    a partir de una estructura `calendar_data` preparada previamente por los reportes.
    """
    inconsistencias = 0
    dias_sin_marcar = 0
    minutos_atraso = 0
    for week_local in calendar_data_local:
        for day_obj_local in week_local:
            d = day_obj_local.get('day')
            if not d:
                continue

            events = day_obj_local.get('events', []) or []
            events_skipped = day_obj_local.get('events_skipped', [])

            expected = sum(1 for ev in events if ev.get('label') not in events_skipped)
            # Usar set de labels para evitar doble conteo si el mismo punch aparece duplicado
            matched_labels = set()
            for p in day_obj_local.get('punches', []):
                if p.get('assigned') and p.get('matched_event'):
                    ev_label = p.get('matched_event')
                    if ev_label not in events_skipped:
                        matched_labels.add(ev_label)
            matched = len(matched_labels)

            is_holiday = day_obj_local.get('is_holiday', False)
            raw_cnt = day_obj_local.get('raw_punches_count', 0)

            try:
                cur_date = date(year_local, month_local, int(d))
                wd = cur_date.weekday()
                is_workday = wd < 5
            except Exception:
                is_workday = True

            if is_workday and not is_holiday:
                if raw_cnt == 0 and expected > 0:
                    dias_sin_marcar += 1
                elif expected > matched:
                    inconsistencias += (expected - matched)

                events_map = {ev['label']: ev for ev in events}
                for p in day_obj_local.get('punches', []):
                    if not p.get('matched_event'):
                        continue
                    ev_label = p.get('matched_event')

                    if ev_label in events_skipped:
                        continue

                    ev = events_map.get(ev_label)
                    if not ev:
                        continue
                    try:
                        p_dt = p.get('dt_norm') or p.get('dt')
                        ev_dt = ev.get('dt')
                    except Exception:
                        continue

                    # El desplazamiento por permiso ya está aplicado en ev_dt gracias al anotador
                    if ev.get('type') == 'in':
                        # Entrada tardía: punch llegó después de la hora esperada
                        diff = (p_dt - ev_dt).total_seconds()
                        if diff >= 60:
                            minutos_atraso += int(diff // 60)
                    elif ev.get('type') == 'out':
                        # Early departure: only penalize if the mark is BEFORE the (adjusted) expected time
                        diff_seconds = (ev_dt - p_dt).total_seconds()
                        if diff_seconds >= 60:
                            # Check if the punch itself fell inside any permit window to avoid unfair penalties
                            is_inside_permit = False
                            for perm in day_obj_local.get('permits', []):
                                ps = perm.get('start_time')
                                pe = perm.get('end_time')
                                if ps and pe and ps <= p_dt.time() <= pe:
                                    is_inside_permit = True
                                    break

                            if not is_inside_permit:
                                minutos_atraso += int(diff_seconds // 60)

    return {'inconsistencias': inconsistencias, 'dias_sin_marcar': dias_sin_marcar,
            'minutos_atraso': minutos_atraso}


def annotate_attendance_calendar_for_employee(calendar_data_local, year_local, month_local, employee_obj,
                                              debug_flag=False, schedule_lookup_fn=None):
    """Anota calendar_data con eventos esperados y empareja marcaciones usando la misma heurística del reporte mensual."""
    try:
        from schedule.models import get_employee_schedule_for_date
    except Exception:
        get_employee_schedule_for_date = None

    # Usar función de lookup inyectada (caché bulk) o la original por defecto
    _lookup = schedule_lookup_fn or get_employee_schedule_for_date

    for week_local in calendar_data_local:
        for day_obj_local in week_local:
            d = day_obj_local.get('day')
            if not d:
                day_obj_local['events'] = []
                day_obj_local['events_skipped'] = []
                continue

            cur_date = date(year_local, month_local, int(d))
            is_workday = cur_date.weekday() < 5
            is_holiday = day_obj_local.get('is_holiday', False)
            schedule = None
            if _lookup:
                try:
                    schedule = _lookup(employee_obj, cur_date)
                except Exception:
                    schedule = None

            events = []
            if schedule:
                if getattr(schedule, 'morning_start', None):
                    ev_dt = datetime.combine(cur_date, schedule.morning_start)
                    events.append({'label': 'J1_in', 'type': 'in', 'dt': ev_dt})
                if getattr(schedule, 'morning_end', None):
                    ev_dt = datetime.combine(cur_date, schedule.morning_end)
                    if getattr(schedule, 'morning_crosses_midnight',
                               False) and schedule.morning_end <= schedule.morning_start:
                        ev_dt = ev_dt + timedelta(days=1)
                    events.append({'label': 'J1_out', 'type': 'out', 'dt': ev_dt})
                if getattr(schedule, 'afternoon_start', None):
                    ev_dt = datetime.combine(cur_date, schedule.afternoon_start)
                    events.append({'label': 'J2_in', 'type': 'in', 'dt': ev_dt})
                if getattr(schedule, 'afternoon_end', None):
                    ev_dt = datetime.combine(cur_date, schedule.afternoon_end)
                    if getattr(schedule, 'afternoon_crosses_midnight', False) and schedule.afternoon_end <= (
                            getattr(schedule, 'afternoon_start', None) or getattr(schedule, 'morning_start', None)):
                        ev_dt = ev_dt + timedelta(days=1)
                    events.append({'label': 'J2_out', 'type': 'out', 'dt': ev_dt})

            permits_day = day_obj_local.get('permits', []) or []

            events_active = []
            events_skipped = []

            for ev in events:
                is_covered = False
                try:
                    ev_time = ev['dt'].time()
                except Exception:
                    events_active.append(ev)
                    continue

                for perm in permits_day:
                    ps = perm.get('start_time')
                    pe = perm.get('end_time')

                    if not ps and not pe:  # Permiso de día completo
                        is_covered = True
                        break

                    if ev['type'] == 'in':
                        if ps and pe and ps <= ev_time <= pe:
                            ev['dt'] = datetime.combine(ev['dt'].date(), pe)
                        elif ps and not pe and ev_time >= ps:
                            is_covered = True
                        elif pe and not ps and ev_time <= pe:
                            ev['dt'] = datetime.combine(ev['dt'].date(), pe)
                    elif ev['type'] == 'out':
                        valid_permits = [p for p in permits_day if p.get('start_time') and p.get('end_time')]
                        valid_permits.sort(key=lambda x: x['start_time'], reverse=True)

                        adjusted_time = ev['dt']

                        for perm in valid_permits:
                            ps = perm.get('start_time')
                            pe = perm.get('end_time')
                            current_out_time = adjusted_time.time()

                            if (ps <= current_out_time <= pe) or (pe == current_out_time):
                                adjusted_time = datetime.combine(adjusted_time.date(), ps)

                        ev['dt'] = adjusted_time

                        for perm in permits_day:
                            ps = perm.get('start_time')
                            pe = perm.get('end_time')
                            if not ps and not pe:
                                is_covered = True
                            if pe and not ps and ev['dt'].time() <= pe:
                                is_covered = True

                # Solución Punto 1: El evento SIEMPRE queda activo para permitir emparejar marcas reales
                events_active.append(ev)
                if is_covered:
                    events_skipped.append(ev['label'])

            to_remove = []
            for in_lbl, out_lbl in [('J1_in', 'J1_out'), ('J2_in', 'J2_out')]:
                ev_in = next((e for e in events_active if e['label'] == in_lbl), None)
                ev_out = next((e for e in events_active if e['label'] == out_lbl), None)
                if ev_in and ev_out and ev_in['dt'] >= ev_out['dt']:
                    to_remove.extend([in_lbl, out_lbl])

            events_skipped.extend(to_remove)
            events_active = [e for e in events_active if e['label'] not in to_remove]

            day_obj_local['events'] = events
            day_obj_local['events_skipped'] = events_skipped

            punches_sorted = [p.copy() for p in sorted(
                day_obj_local.get('punches', []),
                key=lambda x: x.get('dt_norm') or x.get('dt')
            )]

            # Deduplicar marcaciones cercanas
            last_p_dt = datetime.min
            for p in punches_sorted:
                try:
                    p_dt = p.get('dt_norm') or p.get('dt')
                    if (p_dt - last_p_dt).total_seconds() <= DEDUPE_WINDOW_MINUTES * 60:
                        p['is_duplicate'] = True
                    else:
                        last_p_dt = p_dt
                except Exception:
                    pass

            def get_dt(p):
                return p.get('dt_norm') or p.get('dt')

            annotated = []
            prev_assigned_dt = datetime.min
            max_match_seconds = 60 * 60 * 7

            for ev in events_active:
                candidates = [p for p in punches_sorted if not p.get('assigned') and not p.get('is_duplicate')]
                ordered_candidates = [p for p in candidates if get_dt(p) >= prev_assigned_dt]
                if ordered_candidates:
                    candidates = ordered_candidates
                if not candidates:
                    continue

                try:
                    idx = events.index(ev)
                    prev_ev_dt = events[idx - 1]['dt'] if idx > 0 else ev['dt'] - timedelta(hours=24)
                    next_ev_dt = events[idx + 1]['dt'] if idx + 1 < len(events) else ev['dt'] + timedelta(hours=24)
                except Exception:
                    prev_ev_dt = ev['dt'] - timedelta(hours=24)
                    next_ev_dt = ev['dt'] + timedelta(hours=24)

                windowed = [p for p in candidates if get_dt(p) >= prev_ev_dt and get_dt(p) <= next_ev_dt]
                if windowed:
                    candidates = windowed

                candidates = [p for p in candidates if abs((get_dt(p) - ev['dt']).total_seconds()) <= max_match_seconds]
                if not candidates:
                    continue

                if ev['type'] == 'in':
                    best = select_in_candidate(candidates, ev['dt'], prev_ev_dt=prev_ev_dt, next_ev_dt=next_ev_dt)
                else:
                    best = select_out_candidate(candidates, ev['dt'], prev_ev_dt=prev_ev_dt, next_ev_dt=next_ev_dt)
                if not best and ev['type'] == 'out':
                    before_all = [p for p in candidates if _p_dt(p) < ev['dt']]
                    if before_all:
                        best = max(before_all, key=lambda p: _p_dt(p))

                if not best:
                    continue

                try:
                    prev_assigned_dt = get_dt(best)
                except Exception:
                    pass
                best['matched_event'] = ev['label']
                best['matched_event_dt'] = ev['dt']
                best['assigned'] = True

                row_class = ''
                if is_workday and not is_holiday:
                    try:
                        best_dt = best.get('dt_norm') or best.get('dt')
                        if ev['type'] == 'in' and best_dt:
                            cutoff = ev['dt'].replace(second=0, microsecond=0)
                            best_min = best_dt.replace(second=0, microsecond=0)
                            if best_min > cutoff:
                                row_class = 'late'
                        if ev['type'] == 'out' and best_dt:
                            cutoff = ev['dt'].replace(second=0, microsecond=0)
                            best_min = best_dt.replace(second=0, microsecond=0)
                            if best_min < cutoff:
                                row_class = 'late'
                    except Exception:
                        row_class = ''

                newp = best.copy()
                newp['row_class'] = row_class
                annotated.append(newp)

            remaining = [p for p in punches_sorted if not p.get('assigned')]
            for r in remaining:
                r_new = r.copy()
                r_new['row_class'] = r_new.get('row_class', '')
                annotated.append(r_new)

            raw_cnt = day_obj_local.get('raw_punches_count', len(punches_sorted))
            skipped_labels = set(events_skipped)
            expected_slots = sum(1 for ev in events if ev.get('label') not in skipped_labels)
            assigned_slots = sum(
                1 for p in annotated if p.get('assigned') and p.get('matched_event') not in skipped_labels)
            is_holiday = day_obj_local.get('is_holiday', False)
            no_marks = raw_cnt == 0 and not is_holiday and cur_date.weekday() < 5 and expected_slots > 0
            missing_slots = expected_slots > assigned_slots
            day_obj_local['expected_cnt'] = expected_slots
            day_obj_local['matched_cnt'] = assigned_slots
            day_obj_local['extra_cnt'] = max(0, raw_cnt - expected_slots)
            day_obj_local['no_marks_all_day'] = no_marks
            day_obj_local[
                'has_inconsistency'] = missing_slots and cur_date.weekday() < 5 and not is_holiday and not no_marks

            day_obj_local['punches'] = sorted(annotated, key=lambda x: x.get('dt') or x.get('dt_norm'))

    return calendar_data_local


from django.urls import reverse
from django.views.generic import TemplateView

try:
    from weasyprint import HTML, CSS
except Exception:
    HTML = None
    CSS = None
from .models import BiometricDevice, BiometricLoad, AttendanceRegistry, BiometricCommand, OfflineAttendanceRegistry
from .utils import test_connection, BiometricConnection
from permitrequest.models import PermitRequest
from schedule.models import ScheduleObservation
from core.models import SystemConfiguration
from django.db.models import Q
from employee.models import InstitutionalData


class OfflineAttendanceAccessView(View):
    """Simple redirector to the offline attendance page."""

    def get(self, request, *args, **kwargs):
        try:
            url = reverse('biometric:offline_attendance')
        except Exception:
            url = '/biometric/offline-attendance/'
        return HttpResponse(status=302, headers={'Location': url})


class OfflineAttendanceView(TemplateView):
    template_name = 'biometric/offline_attendance.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        try:
            ctx['offline_manifest_url'] = reverse('biometric:offline_attendance_manifest')
        except Exception:
            ctx['offline_manifest_url'] = '/biometric/offline-attendance/manifest.webmanifest'
        try:
            ctx['offline_sw_url'] = reverse('biometric:offline_attendance_sw')
        except Exception:
            ctx['offline_sw_url'] = '/biometric/offline-attendance/sw.js'
        try:
            ctx['offline_sync_url'] = reverse('biometric:offline_attendance_sync')
        except Exception:
            ctx['offline_sync_url'] = '/biometric/offline-attendance/sync/'
        try:
            ctx['offline_page_url'] = reverse('biometric:offline_attendance')
        except Exception:
            ctx['offline_page_url'] = '/biometric/offline-attendance/'
        # Employee info fallbacks
        try:
            name = request.user.get_full_name() or request.user.username
        except Exception:
            name = ''
        ctx['offline_employee_name'] = name
        try:
            doc = getattr(request.user, 'identification_number', '')
        except Exception:
            doc = ''
        ctx['offline_employee_document'] = doc
        # permission to sync depends on authentication
        ctx['offline_can_sync'] = request.user.is_authenticated
        return ctx


def offline_attendance_manifest(request):
    manifest = {
        'name': 'SIGETH - Asistencia Offline',
        'short_name': 'Asistencia',
        'start_url': '/biometric/offline-attendance/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': '#0f766e',
        'icons': [
            {'src': '/static/img/logo.png', 'sizes': '192x192', 'type': 'image/png'},
            {'src': '/static/img/favicon.png', 'sizes': '512x512', 'type': 'image/png'},
        ]
    }
    return JsonResponse(manifest, safe=False)


@login_required
@require_GET
def offline_attendance_service_worker(request):
    script = """
const CACHE_NAME = 'sigeth-offline-attendance-v1';
const PRECACHE_URLS = [
  '/biometric/offline-attendance/',
  '/biometric/offline-attendance/manifest.webmanifest',
    '/static/js/biometric/offline_attendance.js',
    '/static/css/biometric_offline_attendance.css',
  '/static/img/logo.png',
  '/static/img/favicon.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put('/biometric/offline-attendance/', clone));
          return response;
        })
        .catch(() => caches.match('/biometric/offline-attendance/'))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }

      return fetch(request).then((response) => {
        if (request.url.startsWith(self.location.origin)) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      });
    })
  );
});
""".strip()
    return HttpResponse(script, content_type='application/javascript')


@login_required
@require_http_methods(["POST"])
def offline_attendance_sync(request):
    employee = _resolve_user_employee(request.user)
    if not employee:
        return JsonResponse({'status': 'error', 'message': 'No se pudo identificar al empleado asociado al usuario.'},
                            status=400)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    records = payload.get('records') if isinstance(payload, dict) else None
    if not isinstance(records, list) or not records:
        return JsonResponse({'status': 'error', 'message': 'No hay marcaciones para sincronizar.'}, status=400)

    created_count = 0
    updated_count = 0
    skipped_count = 0
    synced_uuids = []
    failed_records = []

    with transaction.atomic():
        for item in records:
            try:
                offline_uuid_raw = item.get('offline_uuid')
                punch_type = (item.get('punch_type') or '').upper().strip()
                captured_at_raw = item.get('captured_at')
                latitude_raw = item.get('latitude')
                longitude_raw = item.get('longitude')
                accuracy_raw = item.get('accuracy_m')
                location_text = (item.get('location_text') or '').strip() or None
                source = (item.get('source') or OfflineAttendanceRegistry.SourceType.PWA).upper().strip()

                if not offline_uuid_raw or not captured_at_raw:
                    skipped_count += 1
                    continue

                try:
                    offline_uuid = UUID(str(offline_uuid_raw))
                except ValueError:
                    skipped_count += 1
                    continue

                if punch_type not in OfflineAttendanceRegistry.PunchType.values:
                    skipped_count += 1
                    continue

                captured_at = parse_datetime(str(captured_at_raw))
                if captured_at is None:
                    skipped_count += 1
                    continue
                if timezone.is_aware(captured_at):
                    captured_at = captured_at.replace(tzinfo=None)

                latitude = Decimal(str(latitude_raw))
                longitude = Decimal(str(longitude_raw))
                accuracy = None if accuracy_raw in (None, '') else float(accuracy_raw)

                defaults = {
                    'employee': employee,
                    'punch_type': punch_type,
                    'captured_at': captured_at,
                    'latitude': latitude,
                    'longitude': longitude,
                    'accuracy_m': accuracy,
                    'location_text': location_text,
                    'sync_status': OfflineAttendanceRegistry.SyncStatus.SYNCED,
                    'synced_at': timezone.now(),
                    'sync_error': '',
                    'source': source if source in OfflineAttendanceRegistry.SourceType.values else OfflineAttendanceRegistry.SourceType.PWA,
                    'updated_by': request.user,
                }

                obj, created = OfflineAttendanceRegistry.objects.update_or_create(
                    offline_uuid=offline_uuid,
                    defaults=defaults,
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                synced_uuids.append(str(offline_uuid))
            except Exception as exc:
                failed_records.append({
                    'offline_uuid': str(item.get('offline_uuid') or ''),
                    'error': str(exc),
                })

    status = 'success' if not failed_records else 'partial'
    http_status = 200 if not failed_records else 207
    return JsonResponse({
        'status': status,
        'message': 'Sincronización procesada.',
        'created': created_count,
        'updated': updated_count,
        'skipped': skipped_count,
        'synced_uuids': synced_uuids,
        'failed_records': failed_records[:10],
    }, status=http_status)


class BiometricListView(ListView):
    model = BiometricDevice
    template_name = 'biometric/biometric_list.html'
    context_object_name = 'devices'
    paginate_by = 10

    def get_queryset(self):
        qs = BiometricDevice.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(models.Q(name__icontains=q) | models.Q(ip_address__icontains=q))

        status = self.request.GET.get('status')
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)
        # Ordenamiento via GET params similar a PersonListView
        sort_field = self.request.GET.get('sort_field')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        allowed = {
            'name': 'name',
            'ip_address': 'ip_address',
            'serial_number': 'serial_number',
            'model_name': 'model_name',
            'location': 'location',
            'is_active': 'is_active'
        }
        if sort_field in allowed:
            field = allowed[sort_field]
            if sort_dir == 'desc':
                field = '-' + field
            qs = qs.order_by(field)
        return qs

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            qs = self.get_queryset()
            # paginar resultados para AJAX
            from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
            page = request.GET.get('page', 1)
            paginator = Paginator(qs, self.paginate_by)
            try:
                page_obj = paginator.page(page)
            except PageNotAnInteger:
                page_obj = paginator.page(1)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)

            html = render_to_string('biometric/partials/partial_biometric_table.html', {
                'devices': page_obj.object_list
            }, request=request)

            all_devs = BiometricDevice.objects.all()
            return JsonResponse({
                'html': html,
                'stats': {
                    'total': all_devs.count(),
                    'active': all_devs.filter(is_active=True).count(),
                    'inactive': all_devs.filter(is_active=False).count()
                },
                'pagination': {
                    'label': f"Mostrando {page_obj.start_index()}-{page_obj.end_index()} de {paginator.count}" if paginator.count > 0 else "Mostrando 0-0 de 0",
                    'current_page': page_obj.number,
                    'num_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                }
            })
        return super().get(request, *args, **kwargs)


@csrf_exempt
def save_biometric_ajax(request):
    """Crea o actualiza biométricos"""
    try:
        device_id = request.POST.get('id')
        is_active = request.POST.get('is_active') == 'true'
        data = {
            'name': request.POST.get('name'),
            'ip_address': request.POST.get('ip_address'),
            'port': request.POST.get('port', 4370),
            'is_active': is_active,
            'location': request.POST.get('location'),
            'serial_number': request.POST.get('serial_number', ''),
            'model_name': request.POST.get('model_name', ''),
            'updated_by': request.user
        }
        if device_id and device_id != 'null':
            # 👇 Cambiamos update por obtención y guardado manual
            device = BiometricDevice.objects.get(id=device_id)
            device.name = request.POST.get('name')
            device.ip_address = request.POST.get('ip_address')
            device.serial_number = request.POST.get('serial_number')
            device.model_name = request.POST.get('model_name')
            device.location = request.POST.get('location')
            device.is_active = request.POST.get('is_active') == 'true'
            device.save()
            msg = "Dispositivo actualizado."
        else:
            data['created_by'] = request.user
            BiometricDevice.objects.create(**data)
            msg = "Dispositivo registrado."
        return JsonResponse({'status': 'success', 'message': msg})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
def load_attendance_ajax(request, pk):
    device = get_object_or_404(BiometricDevice, pk=pk)
    connection = BiometricConnection(device.ip_address, device.port)
    if not connection.connect():
        return JsonResponse({'status': 'error', 'message': 'Fallo de conexión'}, status=400)

    try:
        raw_records = connection.get_attendance()
        saved_count = 0
        with transaction.atomic():
            load_entry = BiometricLoad.objects.create(biometric=device, load_type="DIRECT_SYNC")
            for rec in raw_records:
                user_id = str(rec.user_id).strip().lstrip('0')
                inst = InstitutionalData.objects.filter(biometric_id=user_id).first()
                if inst:
                    # El dispositivo devuelve hora local naive, usarla directamente sin conversiones
                    registry_datetime = rec.timestamp

                    # Si por alguna razón viene con tzinfo, removerlo para mantener la hora local
                    if hasattr(registry_datetime, 'tzinfo') and registry_datetime.tzinfo is not None:
                        registry_datetime = registry_datetime.replace(tzinfo=None)

                    if not AttendanceRegistry.objects.filter(employee=inst.employee,
                                                             registry_date=registry_datetime).exists():
                        AttendanceRegistry.objects.create(
                            employee=inst.employee,
                            biometric_load=load_entry,
                            employee_id_bio=user_id,
                            registry_date=registry_datetime
                        )
                        saved_count += 1
            load_entry.num_records = saved_count
            load_entry.save()
        connection.disconnect()
        return JsonResponse({'status': 'success', 'message': f'Sincronizados {saved_count} registros.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def get_biometric_data(request, pk):
    device = get_object_or_404(BiometricDevice, pk=pk)
    return JsonResponse({
        'success': True,
        'biometric': {
            'id': device.id,
            'name': device.name,
            'ip_address': device.ip_address,
            'port': device.port,
            'location': device.location,
            'is_active': device.is_active,
            'serial_number': device.serial_number or '',
            'model_name': device.model_name or '',
        }
    })


@csrf_exempt
def test_connection_ajax(request, pk):
    device = get_object_or_404(BiometricDevice, pk=pk)
    result = test_connection(device.ip_address, int(device.port))
    if result.get('success') and result.get('device_info'):
        info = result['device_info']
        device.serial_number = info.get('serialNumber', device.serial_number)
        device.model_name = info.get('deviceName', device.model_name)
        device.save()
    return JsonResponse(result)


@csrf_exempt
def get_biometric_time_ajax(request, pk):
    device = get_object_or_404(BiometricDevice, pk=pk)
    server_time = datetime.now()  # USE_TZ=False, usar datetime.now() para hora local
    device_time_str = "Error: No se pudo conectar"

    bio = BiometricConnection(device.ip_address, device.port)
    if bio.connect():
        d_time = bio.get_time()
        if d_time:
            device_time_str = d_time.strftime('%Y-%m-%d %H:%M:%S')
        bio.disconnect()

    return JsonResponse({
        'success': True, 'device_name': device.name,
        'server_time': server_time.strftime('%Y-%m-%d %H:%M:%S'),
        'device_time': device_time_str
    })


@csrf_exempt
def update_biometric_time_ajax(request, pk):
    if request.method != 'POST': return JsonResponse({'status': 'error'}, status=405)
    device = get_object_or_404(BiometricDevice, pk=pk)
    mode = request.POST.get('mode')
    new_time_str = request.POST.get('new_time')

    if mode == 'server':
        target_time = datetime.now()  # USE_TZ=False, hora local naive directa
    else:
        target_time = datetime.strptime(new_time_str, '%Y-%m-%dT%H:%M')

    bio = BiometricConnection(device.ip_address, device.port)
    if bio.connect():
        success = bio.set_time(target_time)
        bio.disconnect()
        if success:
            return JsonResponse({'status': 'success', 'message': 'Hora actualizada.'})
    return JsonResponse({'status': 'error', 'message': 'Fallo al establecer hora.'}, status=400)


@csrf_exempt
def upload_biometric_file_ajax(request, pk):
    if request.method == 'POST' and request.FILES.get('file'):
        device = get_object_or_404(BiometricDevice, pk=pk)
        file = request.FILES['file']
        try:
            content = file.read().decode('utf-8', errors='ignore').strip()
            lines = content.splitlines()
            saved_count = 0
            with transaction.atomic():
                manual_load = BiometricLoad.objects.create(
                    biometric=device, load_type="MANUAL_USB",
                    reason=f"Archivo: {file.name}", created_by=request.user
                )
                for line in lines:
                    parts = line.strip().split('\t')
                    if len(parts) < 2: continue
                    user_pin = parts[0].strip().lstrip('0')
                    try:
                        naive_date = datetime.strptime(parts[1].strip(), '%Y-%m-%d %H:%M:%S')
                        reg_date = make_aware(naive_date)
                        inst_data = InstitutionalData.objects.filter(biometric_id=user_pin).first()
                        if inst_data and not AttendanceRegistry.objects.filter(employee=inst_data.employee,
                                                                               registry_date=reg_date).exists():
                            AttendanceRegistry.objects.create(
                                employee=inst_data.employee, biometric_load=manual_load,
                                employee_id_bio=user_pin, registry_date=reg_date
                            )
                            saved_count += 1
                    except:
                        continue
                manual_load.num_records = saved_count
                manual_load.save()
            return JsonResponse({'status': 'success', 'message': f'Cargados {saved_count} registros.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Archivo requerido.'}, status=400)


def generate_monthly_report_pdf(request):
    emp_id = request.GET.get('emp_id')
    month = int(request.GET.get('month', 1))
    year = int(request.GET.get('year', 2026))
    inst_data = get_object_or_404(InstitutionalData, employee_id=emp_id)
    debug_punches = request.GET.get('debug_punches') == '1'

    punches = AttendanceRegistry.objects.filter(
        employee_id=emp_id, registry_date__year=year, registry_date__month=month
    ).order_by('registry_date')

    punches_map = {}
    for p in punches:
        try:
            if timezone.is_aware(p.registry_date):
                dt_norm = timezone.localtime(p.registry_date).replace(tzinfo=None)
            else:
                dt_norm = p.registry_date
        except Exception:
            dt_norm = p.registry_date

        day = dt_norm.day
        if day not in punches_map:
            punches_map[day] = []

        punches_map[day].append({
            'time': dt_norm.strftime('%H:%M'),
            'device': p.biometric_load.biometric.name[:10],
            'dt': p.registry_date,
            'dt_norm': dt_norm,
        })

    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    calendar_data = []
    for week in weeks:
        week_list = []
        for day in week:
            week_list.append({'day': day if day != 0 else '', 'punches': punches_map.get(day, [])})
        calendar_data.append(week_list)

    months_es = ["", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE",
                 "NOVIEMBRE", "DICIEMBRE"]
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    # Carga de Permisos Aprobados
    permits_qs = PermitRequest.objects.filter(employee_id=emp_id, status='APPROVED').filter(
        Q(start_date__lte=month_end, end_date__gte=month_start) |
        Q(start_date__range=(month_start, month_end)) |
        Q(end_date__range=(month_start, month_end))
    )
    permits_map = {}
    for pr in permits_qs:
        start_date = pr.start_date if pr.start_date >= month_start else month_start
        end_date = (pr.end_date or pr.start_date)
        if end_date > month_end:
            end_date = month_end

        crosses_midnight = False
        try:
            if pr.start_time and pr.end_time and pr.end_time <= pr.start_time:
                crosses_midnight = True
        except Exception:
            crosses_midnight = False

        cur = start_date
        while cur <= end_date:
            d = cur.day
            if d not in permits_map:
                permits_map[d] = []

            entry = {'type': pr.permit_type.name, 'note': pr.response_note or ''}
            if not pr.start_time and not pr.end_time:
                entry['start_time'] = None
                entry['end_time'] = None
            else:
                if (pr.start_date == (pr.end_date or pr.start_date)) and not crosses_midnight:
                    entry['start_time'] = pr.start_time
                    entry['end_time'] = pr.end_time
                else:
                    if crosses_midnight:
                        if cur == pr.start_date:
                            entry['start_time'] = pr.start_time
                            entry['end_time'] = dtime(0, 0)
                        elif cur == (pr.end_date or pr.start_date):
                            entry['start_time'] = dtime(0, 0)
                            entry['end_time'] = pr.end_time
                        else:
                            entry['start_time'] = dtime(0, 0)
                            entry['end_time'] = dtime(23, 59)
                    else:
                        if cur == pr.start_date:
                            entry['start_time'] = pr.start_time
                            entry['end_time'] = dtime(23, 59)
                        elif cur == (pr.end_date or pr.start_date):
                            entry['start_time'] = dtime(0, 0)
                            entry['end_time'] = pr.end_time
                        else:
                            entry['start_time'] = dtime(0, 0)
                            entry['end_time'] = dtime(23, 59)

            permits_map[d].append(entry)
            cur = cur + timedelta(days=1)

    # Carga de Feriados y Observaciones
    holidays_qs = ScheduleObservation.objects.filter(is_active=True, is_holiday=True, start_date__lte=month_end,
                                                     end_date__gte=month_start)
    holidays_map = {}
    for obs in holidays_qs:
        start = obs.start_date if obs.start_date >= month_start else month_start
        end = obs.end_date if obs.end_date <= month_end else month_end
        cur = start
        while cur <= end:
            holidays_map[cur.day] = obs.name
            cur = cur + timedelta(days=1)

    notes_qs = ScheduleObservation.objects.filter(is_active=True, is_holiday=False, start_date__lte=month_end,
                                                  end_date__gte=month_start)
    observations_list = []
    for obs in notes_qs:
        disp_date = obs.start_date if (month_start <= obs.start_date <= month_end) else obs.start_date
        disp = f"{disp_date.day} de {months_es[disp_date.month].capitalize()} de {disp_date.year} - {obs.name.upper()}"
        observations_list.append(disp)

    # Inyectar metadatos base iniciales por día
    for week in calendar_data:
        for day_obj in week:
            d = day_obj.get('day')
            day_obj['raw_punches_count'] = len(day_obj.get('punches', []))
            if not d:
                day_obj['is_holiday'] = False
                day_obj['holi_name'] = ''
                day_obj['permits'] = []
            else:
                day_obj['is_holiday'] = d in holidays_map
                day_obj['holi_name'] = holidays_map.get(d, '')
                day_obj['permits'] = permits_map.get(d, [])

    # Solución Punto 2: Ejecutamos el anotador centralizado común para blindar consistencia total de datos
    annotate_attendance_calendar_for_employee(calendar_data, year, month, inst_data.employee, debug_punches)

    # Segundo recorrido para procesar la visualización y Máquina de Estados G1..G4 en el reporte individual
    for week in calendar_data:
        for day_obj in week:
            d = day_obj.get('day')
            if not d:
                continue

            cur_date = date(year, month, int(d))
            is_workday = cur_date.weekday() < 5

            g_regs = {'G1': None, 'G2': None, 'G3': None, 'G4': None}
            g_atr = {'G1': 0, 'G2': 0, 'G3': 0, 'G4': 0}

            events_list = day_obj.get('events', []) or []
            events_map = {ev.get('label'): ev for ev in events_list}
            E1 = events_map.get('J1_in', {}).get('dt')
            S1 = events_map.get('J1_out', {}).get('dt')
            E2 = events_map.get('J2_in', {}).get('dt')
            S2 = events_map.get('J2_out', {}).get('dt')

            day_punches = [p for p in day_obj.get('punches', []) if not p.get('is_duplicate')]
            TEMP = 0
            ATR = 0
            is_4_jornadas = (E2 is not None and S2 is not None)

            if is_workday and not day_obj.get('is_holiday', False):
                for p in day_punches:
                    try:
                        M = p.get('dt_norm') or p.get('dt')
                    except Exception:
                        continue
                    if M is None:
                        continue

                    if not is_4_jornadas:
                        if g_regs['G1'] is None:
                            g_regs['G1'] = M
                            if E1 and M > E1:
                                mins = int((M - E1).total_seconds() // 60)
                                ATR += max(0, mins)
                                g_atr['G1'] = max(0, mins)
                            continue
                        if g_regs['G2'] is None:
                            g_regs['G2'] = M
                            if S1 and M < S1:
                                mins = int((S1 - M).total_seconds() // 60)
                                ATR += max(0, mins)
                                g_atr['G2'] = max(0, mins)
                            continue
                        continue

                    if g_regs['G1'] is None:
                        if E1 and M > E1:
                            g_regs['G1'] = M
                            mins = int((M - E1).total_seconds() // 60)
                            ATR += max(0, mins)
                            g_atr['G1'] = max(0, mins)
                        continue

                    if g_regs['G2'] is None:
                        g_regs['G2'] = M
                        if S1 and M >= S1:
                            pass
                        elif S1 and M < S1:
                            TEMP = int((S1 - M).total_seconds() // 60)
                            ATR += max(0, TEMP)
                            g_atr['G2'] = max(0, TEMP)
                        continue

                    if g_regs['G3'] is None:
                        if S1 and g_regs['G2'] >= S1 and E2 and M <= E2:
                            continue
                        if E2 and M > E2:
                            g_regs['G3'] = M
                            ATR = max(0, ATR - TEMP)
                            TEMP = 0
                            mins = int((M - E2).total_seconds() // 60)
                            if mins > 0:
                                ATR += mins
                                g_atr['G3'] = mins
                        continue

                    if g_regs['G4'] is None:
                        g_regs['G4'] = M
                        if S2 and M >= S2:
                            pass
                        elif S2 and M < S2:
                            TEMP = int((S2 - M).total_seconds() // 60)
                            ATR += max(0, TEMP)
                            g_atr['G4'] = max(0, TEMP)
                        continue

            day_obj['g_regs'] = g_regs
            day_obj['g_atr'] = g_atr
            day_obj['atr_dia'] = ATR
            day_obj['temp'] = TEMP

            # Mapear visibilidad en base al emparejamiento unificado
            try:
                event_to_punch = {}
                for p in day_obj.get('punches', []):
                    ev_label = p.get('matched_event')
                    if p.get('assigned') and ev_label:
                        if ev_label not in event_to_punch:
                            event_to_punch[ev_label] = p

                visible_ids = {id(p) for p in event_to_punch.values()}

                for p in day_obj.get('punches', []):
                    if 'selected_slot' in p:
                        del p['selected_slot']
                    if id(p) in visible_ids:
                        p['filtered'] = False
                        ev_label = p.get('matched_event', '')
                        slot_map = {'J1_in': 'G1', 'J1_out': 'G2', 'J2_in': 'G3', 'J2_out': 'G4'}
                        p['selected_slot'] = slot_map.get(ev_label, '')
                    else:
                        p['filtered'] = True

                day_obj['punches'] = sorted(day_obj.get('punches', []), key=lambda x: x.get('dt') or x.get('dt_norm'))
            except Exception:
                pass

            try:
                months_es_local = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                   "septiembre", "octubre", "noviembre", "diciembre"]
                day_obj['day_label'] = f"{int(d):02d} de {months_es_local[month]}"
            except Exception:
                day_obj['day_label'] = str(d)

    config = SystemConfiguration.get_current()
    letterhead_data = None
    no_letterhead = request.GET.get('no_letterhead') == '1'
    if not no_letterhead and config and getattr(config, 'letterhead', None):
        try:
            try:
                letterhead_data = request.build_absolute_uri(config.letterhead.url)
            except Exception:
                letterhead_data = config.letterhead.url
            if not letterhead_data:
                file_path = getattr(config.letterhead, 'path', None)
                if file_path and os.path.exists(file_path):
                    mime, _ = mimetypes.guess_type(file_path)
                    with open(file_path, 'rb') as f:
                        encoded = base64.b64encode(f.read()).decode('ascii')
                        letterhead_data = f"data:{mime};base64,{encoded}"
        except Exception:
            letterhead_data = None

    template = get_template('biometric/reports/pdf_attendance_calendar.html')
    summary = build_attendance_summary_for_employee(calendar_data, year, month, inst_data.employee, debug_punches)

    html = template.render({
        'emp': inst_data.employee,
        'month_name': months_es[month],
        'year': year,
        'calendar': calendar_data,
        'today': datetime.now(),
        'permits_map': permits_map,
        'holidays_map': holidays_map,
        'configuration': config,
        'summary': summary,
        'letterhead_data': letterhead_data,
        'observations_list': observations_list,
    })

    if HTML:
        base_url = request.build_absolute_uri('/')
        pdf = HTML(string=html, base_url=base_url).write_pdf(
            stylesheets=[CSS(string='@page { size: A4; margin: 0.8cm }')])
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="reporte_mensual.pdf"'
        return response
    else:
        response = HttpResponse(content_type='application/pdf')
        from xhtml2pdf import pisa
        pisa.CreatePDF(html, dest=response)
        return response


# Receptor ADMS unificado
@method_decorator(csrf_exempt, name='dispatch')
class ADMSReceiverView(View):
    def get(self, request):
        return HttpResponse("OK\nC:99:ATTLOG", content_type="text/plain")

    def post(self, request):
        # Esta lógica se delegó a adms_views.py para mantener limpieza
        from .adms_views import adms_receive_attendance
        return adms_receive_attendance(request)


class EmployeeReportListView(ListView):
    model = InstitutionalData
    template_name = 'biometric/employee_report_list.html'
    context_object_name = 'employees'
    paginate_by = 10

    def get_queryset(self):
        # Solo empleados con ID biométrico y que sean empleados activos
        qs = InstitutionalData.objects.select_related('employee__person').filter(
            biometric_id__isnull=False,
            employee__is_active=True
        )
        # Capturamos los parámetros del nuevo buscador
        name_query = self.request.GET.get('name', '').strip()
        dni_query = self.request.GET.get('dni', '').strip()
        if name_query or dni_query:
            if name_query:
                qs = qs.filter(
                    models.Q(employee__person__first_name__icontains=name_query) |
                    models.Q(employee__person__last_name__icontains=name_query)
                )
            if dni_query:
                qs = qs.filter(employee__person__document_number__icontains=dni_query)
        else:
            qs = qs.order_by('-id')[:100]

        return qs

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            html = render_to_string('biometric/partials/partial_report_employee_table.html', {
                'employees': self.object_list
            }, request=request)
            # Retornamos también el conteo para validación visual
            return JsonResponse({'html': html, 'count': len(self.object_list)})
        return super().get(request, *args, **kwargs)


def generate_specific_report_pdf(request):
    """Genera un reporte PDF basado en un rango de fechas personalizado."""
    employee_id = request.GET.get('emp_id')
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    if not all([employee_id, start_str, end_str]):
        return HttpResponse("Parámetros incompletos", status=400)

    # Convertir strings a objetos date
    start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_str, '%Y-%m-%d').date()

    institutional_info = get_object_or_404(InstitutionalData, employee_id=employee_id)

    # Obtener marcaciones en el rango (usando __date para comparar solo la parte de fecha)
    punches = AttendanceRegistry.objects.filter(
        employee_id=employee_id,
        registry_date__date__range=[start_date, end_date]
    ).select_related('biometric_load__biometric').order_by('registry_date')

    template = get_template('biometric/reports/pdf_attendance_specific.html')
    html_content = template.render({
        'emp': institutional_info.employee,
        'start_date': start_date,
        'end_date': end_date,
        'punches': punches,
        'today': datetime.now(),
    })

    filename = f"Reporte_Especifico_{institutional_info.employee.person.document_number}_{start_str}_al_{end_str}.pdf"

    if HTML:
        base_url = request.build_absolute_uri('/')
        pdf = HTML(string=html_content, base_url=base_url).write_pdf(
            stylesheets=[CSS(string='@page { size: A4; margin: 0.8cm }')])
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    else:
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        from xhtml2pdf import pisa
        pisa_status = pisa.CreatePDF(html_content, dest=response)
        if pisa_status.err:
            return HttpResponse('Error al generar PDF', status=500)
        return response


from collections import defaultdict


def generate_department_report_pdf(request):
    unit_id = request.GET.get('unit_id')
    month = int(request.GET.get('month', 1))
    year = int(request.GET.get('year', datetime.now().year))
    debug_punches = request.GET.get('debug_punches') == '1'
    if not unit_id:
        return HttpResponse('unit_id requerido', status=400)

    from institution.models import AdministrativeUnit

    def collect_unit_ids(root_id):
        ids = set()
        stack = [int(root_id)]
        while stack:
            cur = stack.pop()
            ids.add(cur)
            children = AdministrativeUnit.objects.filter(parent_id=cur, is_active=True).values_list('id', flat=True)
            for c in children:
                if c not in ids: stack.append(c)
        return list(ids)

    try:
        unit = AdministrativeUnit.objects.get(pk=unit_id, is_active=True)
    except AdministrativeUnit.DoesNotExist:
        return HttpResponse('Unidad no encontrada', status=404)

    unit_ids = collect_unit_ids(unit_id)

    # 1. Traer empleados
    inst_qs = InstitutionalData.objects.select_related(
        'employee__person', 'employee__area'
    ).prefetch_related(
        'employee__management_periods__contract_type__labor_regime',
        'employee__management_periods__status'
    ).filter(
        employee__area_id__in=unit_ids,
        employee__is_active=True,
        biometric_id__isnull=False
    ).order_by('employee__person__last_name', 'employee__person__first_name')

    emp_ids = [inst.employee_id for inst in inst_qs]
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    # 2. MEGA OPTIMIZACIÓN: Diccionarios con llaves NORMALIZADAS (string)
    all_punches = AttendanceRegistry.objects.filter(
        employee_id__in=emp_ids, registry_date__year=year, registry_date__month=month
    ).select_related('biometric_load__biometric')

    punches_by_emp = defaultdict(lambda: defaultdict(list))
    for p in all_punches:
        emp_key = str(p.employee_id)
        dt = timezone.localtime(p.registry_date).replace(tzinfo=None) if timezone.is_aware(
            p.registry_date) else p.registry_date
        punches_by_emp[emp_key][dt.day].append({
            'time': dt.strftime('%H:%M'),
            'device': p.biometric_load.biometric.name[:10] if p.biometric_load and p.biometric_load.biometric else '',
            'dt': p.registry_date,
            'dt_norm': dt,
        })

    all_permits = PermitRequest.objects.filter(employee_id__in=emp_ids, status='APPROVED').filter(
        models.Q(start_date__lte=month_end, end_date__gte=month_start) |
        models.Q(start_date__range=(month_start, month_end)) |
        models.Q(end_date__range=(month_start, month_end))
    ).select_related('permit_type')

    permits_by_emp = defaultdict(lambda: defaultdict(list))
    for pr in all_permits:
        emp_key = str(pr.employee_id)
        p_start = pr.start_date if pr.start_date >= month_start else month_start
        p_end = pr.end_date or pr.start_date
        if p_end > month_end:
            p_end = month_end

        crosses_midnight = False
        try:
            if pr.start_time and pr.end_time and pr.end_time <= pr.start_time:
                crosses_midnight = True
        except Exception:
            crosses_midnight = False

        cur = p_start
        while cur <= p_end:
            entry = {'type': pr.permit_type.name if pr.permit_type else '', 'note': pr.response_note or ''}
            if not pr.start_time and not pr.end_time:
                entry['start_time'] = None
                entry['end_time'] = None
            else:
                if (pr.start_date == (pr.end_date or pr.start_date)) and not crosses_midnight:
                    entry['start_time'] = pr.start_time
                    entry['end_time'] = pr.end_time
                else:
                    if crosses_midnight:
                        if cur == pr.start_date:
                            entry['start_time'] = pr.start_time
                            entry['end_time'] = dtime(0, 0)
                        elif cur == (pr.end_date or pr.start_date):
                            entry['start_time'] = dtime(0, 0)
                            entry['end_time'] = pr.end_time
                        else:
                            entry['start_time'] = dtime(0, 0)
                            entry['end_time'] = dtime(23, 59)
                    else:
                        if cur == pr.start_date:
                            entry['start_time'] = pr.start_time
                            entry['end_time'] = dtime(23, 59)
                        elif cur == (pr.end_date or pr.start_date):
                            entry['start_time'] = dtime(0, 0)
                            entry['end_time'] = pr.end_time
                        else:
                            entry['start_time'] = dtime(0, 0)
                            entry['end_time'] = dtime(23, 59)

            permits_by_emp[emp_key][cur.day].append(entry)
            cur += timedelta(days=1)

    holidays_qs = ScheduleObservation.objects.filter(is_active=True, is_holiday=True, start_date__lte=month_end,
                                                     end_date__gte=month_start)
    holidays_map = {}
    for obs in holidays_qs:
        h_cur, h_last = max(obs.start_date, month_start), min(obs.end_date, month_end)
        while h_cur <= h_last:
            holidays_map[h_cur.day] = obs.name
            h_cur += timedelta(days=1)

    try:
        from schedule.models import get_employee_schedule_for_date
    except Exception:
        get_employee_schedule_for_date = None

    results_by_unit = {}
    for inst in inst_qs:
        emp_id_str = str(inst.employee_id)

        # Régimen laboral
        periods = list(inst.employee.management_periods.all())
        active_period = next((p for p in periods if p.status.code.upper() in ['ACTIVO', 'ACT']),
                             periods[0] if periods else None)
        regimen_name = active_period.contract_type.labor_regime.name if active_period and active_period.contract_type and active_period.contract_type.labor_regime else "N/A"

        # Construir calendario del mes para este empleado
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
        calendar_data = []
        emp_punches = punches_by_emp.get(emp_id_str, {})
        emp_permits = permits_by_emp.get(emp_id_str, {})

        for week in weeks:
            week_list = []
            for day in week:
                day_data = {'day': day if day != 0 else '', 'punches': emp_punches.get(day, [])}
                day_data['raw_punches_count'] = len(day_data['punches'])
                day_data['is_holiday'] = day in holidays_map
                day_data['permits'] = emp_permits.get(day, [])
                week_list.append(day_data)
            calendar_data.append(week_list)

        # Anotar y calcular
        annotate_attendance_calendar_for_employee(
            calendar_data, year, month, inst.employee, debug_punches,
            schedule_lookup_fn=get_employee_schedule_for_date,
        )
        summary_emp = build_attendance_summary_for_employee(calendar_data, year, month, inst.employee, debug_punches)

        # Tolerancia del horario (tomamos el del día 1 como referencia)
        sched_ref = get_employee_schedule_for_date(inst.employee,
                                                   month_start) if get_employee_schedule_for_date else None
        tolerance = sched_ref.late_tolerance_minutes if sched_ref else 0

        minutos_atraso = summary_emp.get('minutos_atraso', 0)
        inconsistencias = summary_emp.get('inconsistencias', 0)
        dias_sin_marcar = summary_emp.get('dias_sin_marcar', 0)

        # --- FILTRO DE EXCEPCIONES ---
        if inconsistencias > 0 or dias_sin_marcar > 0 or minutos_atraso > tolerance:
            unit_name = inst.employee.area.name if inst.employee.area else 'Sin Unidad'
            results_by_unit.setdefault(unit_name, []).append({
                'employee': inst.employee,
                'regimen': regimen_name,
                'inconsistencias': inconsistencias,
                'dias_sin_marcar': dias_sin_marcar,
                'minutos_atraso': minutos_atraso,
                'tolerancia': tolerance,
            })

    # Ordenar y Generar PDF
    grouped_results = sorted(list(results_by_unit.items()), key=lambda x: x[0].lower())
    template = get_template('biometric/reports/pdf_attendance_by_unit.html')
    html = template.render(
        {'unit': unit, 'year': year, 'month': month, 'grouped_results': grouped_results, 'today': datetime.now()})

    filename = f"Reporte_Dep_{unit.name.replace(' ', '_')}_{year}_{month}.pdf"
    if HTML:
        pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf(
            stylesheets=[CSS(string='@page { size: A4; margin: 0.8cm }')])
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    else:
        response = HttpResponse(content_type='application/pdf')
        from xhtml2pdf import pisa
        pisa.CreatePDF(html, dest=response)
        return response
