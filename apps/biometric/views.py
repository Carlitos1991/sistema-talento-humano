import calendar
import json
import logging
from datetime import datetime, date, timedelta
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
DEDUPE_WINDOW_MINUTES = 3
IN_TOLERANCE_SECONDS = 60  # 1 minuto de tolerancia para in
OUT_MAX_SECONDS = 30 * 60  # 30 minutos para aceptar out antes del evento si no hay after
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


def select_out_candidate(candidates, ev_dt, prev_ev_dt=None):
    """Selecciona candidato para evento 'out'.
    Preferir el candidato más cercano DESPUÉS de ev_dt. Si no existe, elegir el más cercano ANTES
    sólo si está dentro de OUT_MAX_SECONDS.
    """
    if not candidates:
        return None
    after = [p for p in candidates if _p_dt(p) >= ev_dt]
    if after:
        # elegir el posterior más cercano (mínima dt)
        return min(after, key=lambda p: (_p_dt(p) - ev_dt).total_seconds())
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
        return qs

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            html = render_to_string('biometric/partials/partial_biometric_table.html', {
                'devices': self.object_list
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
                    'label': f"Mostrando 1-{self.object_list.count()} de {self.object_list.count()}" if self.object_list.count() > 0 else "Mostrando 0-0 de 0"
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
    if debug_punches:
        try:
            emp_obj = inst_data.employee
            msg = f"[punch-debug] emp_obj pk={getattr(emp_obj, 'pk', None)} repr={repr(emp_obj)}"
            print(msg);
            logger.debug(msg)
            try:
                from schedule.models import EmployeeScheduleHistory
                rows = list(
                    EmployeeScheduleHistory.objects.filter(employee=emp_obj).values('pk', 'start_date', 'end_date',
                                                                                    'is_current', 'schedule_id'))
                msg2 = f"[punch-debug] schedule_history rows={rows}"
                print(msg2);
                logger.debug(msg2)
            except Exception as e:
                print(f"[punch-debug] schedule_history lookup failed: {e}")
        except Exception as e:
            print(f"[punch-debug] inst_data.employee access failed: {e}")

    # Query de marcaciones (Naive)
    punches = AttendanceRegistry.objects.filter(
        employee_id=emp_id, registry_date__year=year, registry_date__month=month
    ).order_by('registry_date')

    punches_map = {}
    for p in punches:
        # Normalizar datetime a hora local sin tz para comparaciones fiables
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
    # --- Permits (aprobados) ---
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    permits_qs = PermitRequest.objects.filter(employee_id=emp_id, status='APPROVED').filter(
        Q(start_date__lte=month_end, end_date__gte=month_start) |
        Q(start_date__range=(month_start, month_end)) |
        Q(end_date__range=(month_start, month_end))
    )
    permits_map = {}
    for pr in permits_qs:
        start = pr.start_date if pr.start_date >= month_start else month_start
        end = (pr.end_date or pr.start_date)
        if end > month_end:
            end = month_end
        cur = start
        while cur <= end:
            d = cur.day
            if d not in permits_map:
                permits_map[d] = []
            permits_map[d].append({
                'type': pr.permit_type.name,
                'note': pr.response_note or '',
                'start_time': pr.start_time,
                'end_time': pr.end_time,
            })
            cur = cur + timedelta(days=1)

    # --- Feriados (is_holiday=True y activos) y Observaciones (is_holiday=False y activos) ---
    holidays_qs = ScheduleObservation.objects.filter(is_active=True, is_holiday=True,
                                                     start_date__lte=month_end, end_date__gte=month_start)
    holidays_map = {}
    for obs in holidays_qs:
        start = obs.start_date if obs.start_date >= month_start else month_start
        end = obs.end_date if obs.end_date <= month_end else month_end
        cur = start
        while cur <= end:
            holidays_map[cur.day] = obs.name
            cur = cur + timedelta(days=1)

    notes_qs = ScheduleObservation.objects.filter(is_active=True, is_holiday=False,
                                                  start_date__lte=month_end, end_date__gte=month_start)
    observations_list = []
    for obs in notes_qs:
        # Mostrar la fecha inicial de la observación (si está dentro del mes)
        disp_date = obs.start_date if (month_start <= obs.start_date <= month_end) else obs.start_date
        # Formatear: "13 de Marzo de 2026 - NOMBRE"
        months_es = ["", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE",
                     "OCTUBRE",
                     "NOVIEMBRE", "DICIEMBRE"]
        disp = f"{disp_date.day} de {months_es[disp_date.month].capitalize()} de {disp_date.year} - {obs.name.upper()}"
        observations_list.append(disp)

    # Añadir flags de permisos y feriados por día (facilita el template)
    for widx, week in enumerate(calendar_data):
        for didx, day_obj in enumerate(week):
            d = day_obj.get('day')
            # conservar conteo inicial de marcaciones crudas para métricas
            day_obj['raw_punches_count'] = len(day_obj.get('punches', []))
            if not d:
                day_obj['is_holiday'] = False
                day_obj['holi_name'] = ''
                day_obj['permits'] = []
            else:
                day_obj['is_holiday'] = d in holidays_map
                day_obj['holi_name'] = holidays_map.get(d, '')
                day_obj['permits'] = permits_map.get(d, [])
                # Evaluar tardanzas / salidas anticipadas según horario asignado
                try:
                    from schedule.models import get_employee_schedule_for_date
                    cur_date = date(year, month, int(d))
                    schedule = get_employee_schedule_for_date(inst_data.employee, cur_date)
                    if debug_punches:
                        msg = f"[punch-debug] emp={emp_id} day={d} schedule={getattr(schedule, 'name', None)}"
                        logger.debug(msg)
                        print(msg)
                        try:
                            with open(os.path.join(os.getcwd(), 'punch_debug.log'), 'a', encoding='utf-8') as _f:
                                _f.write(msg + '\n')
                        except Exception:
                            pass
                except Exception:
                    schedule = None
                    if debug_punches:
                        logger.debug("[punch-debug] emp=%s day=%s schedule lookup failed", emp_id, d)

                punches = day_obj.get('punches', [])
                # Ordenar copias de marcaciones (asegurarnos que están ordenadas) usando 'dt_norm'
                punches_sorted = sorted(punches, key=lambda x: x.get('dt_norm') or x.get('dt'))

                annotated = []
                if schedule and punches_sorted:
                    # Construir eventos esperados en datetime, respetando cruces de medianoche
                    try:
                        cur_date = date(year, month, int(d))
                        events = []
                        if schedule.morning_start:
                            ev_dt = datetime.combine(cur_date, schedule.morning_start)
                            events.append({'label': 'J1_in', 'type': 'in', 'dt': ev_dt})
                        if schedule.morning_end:
                            ev_dt = datetime.combine(cur_date, schedule.morning_end)
                            if schedule.morning_crosses_midnight and schedule.morning_end <= schedule.morning_start:
                                ev_dt = ev_dt + timedelta(days=1)
                            events.append({'label': 'J1_out', 'type': 'out', 'dt': ev_dt})
                        if schedule.afternoon_start:
                            ev_dt = datetime.combine(cur_date, schedule.afternoon_start)
                            events.append({'label': 'J2_in', 'type': 'in', 'dt': ev_dt})
                        if schedule.afternoon_end:
                            ev_dt = datetime.combine(cur_date, schedule.afternoon_end)
                            if schedule.afternoon_crosses_midnight and schedule.afternoon_end <= (
                                    schedule.afternoon_start or schedule.morning_start):
                                ev_dt = ev_dt + timedelta(days=1)
                            events.append({'label': 'J2_out', 'type': 'out', 'dt': ev_dt})

                        # Guardar los eventos esperados para uso en el resumen
                        day_obj['events'] = events

                        # Emparejamiento greedy por proximidad manteniendo orden
                        prev_assigned_dt = datetime.min
                        # No emparejar con marcas extremadamente lejanas: umbral en segundos
                        MAX_MATCH_SECONDS = 60 * 60 * 2  # 2 horas
                        for ev in events:
                            # candidatos sin asignar
                            candidates = [p for p in punches_sorted if not p.get('assigned')]

                            # Preferir candidatos que mantengan orden cronológico respecto a la última asignación
                            def get_dt(p):
                                return p.get('dt_norm') or p.get('dt')

                            ordered_candidates = [p for p in candidates if get_dt(p) >= prev_assigned_dt]
                            if ordered_candidates:
                                candidates = ordered_candidates
                            if not candidates:
                                break
                            # Ventana del evento: entre evento anterior y siguiente (si existen)
                            try:
                                idx = events.index(ev)
                                prev_ev_dt = events[idx - 1]['dt'] if idx > 0 else ev['dt'] - timedelta(hours=24)
                                next_ev_dt = events[idx + 1]['dt'] if idx + 1 < len(events) else ev['dt'] + timedelta(
                                    hours=24)
                            except Exception:
                                prev_ev_dt = ev['dt'] - timedelta(hours=24)
                                next_ev_dt = ev['dt'] + timedelta(hours=24)
                            windowed = [p for p in candidates if (get_dt(p) >= prev_ev_dt and get_dt(p) <= next_ev_dt)]
                            if windowed:
                                candidates = windowed
                            # limitar candidatos a una distancia razonable del evento
                            MAX_MATCH_SECONDS = 60 * 60 * 4  # 2 horas

                            def get_dt(p):
                                return p.get('dt_norm') or p.get('dt')

                            candidates = [p for p in candidates if
                                          abs((get_dt(p) - ev['dt']).total_seconds()) <= MAX_MATCH_SECONDS]
                            if not candidates:
                                # no hay candidatos cercanos -> no asignar este evento
                                continue

                            # filtrar candidatos extremadamente lejanos respecto al evento
                            def get_dt(p):
                                return p.get('dt_norm') or p.get('dt')

                            candidates = [p for p in candidates if
                                          abs((get_dt(p) - ev['dt']).total_seconds()) <= MAX_MATCH_SECONDS]
                            if not candidates:
                                # si no quedan candidatos cercanos, no asignar este evento
                                continue
                            # Selección preferente usando helpers configurables
                            ev_dt = ev['dt']
                            try:
                                idx = events.index(ev)
                                prev_ev_dt = events[idx - 1]['dt'] if idx > 0 else None
                                next_ev_dt = events[idx + 1]['dt'] if idx + 1 < len(events) else None
                            except Exception:
                                prev_ev_dt = None
                                next_ev_dt = None
                            if ev['type'] == 'in':
                                best = select_in_candidate(candidates, ev_dt, prev_ev_dt=prev_ev_dt,
                                                           next_ev_dt=next_ev_dt)
                            else:
                                best = select_out_candidate(candidates, ev_dt, prev_ev_dt=prev_ev_dt)
                            if not best:
                                # no hubo candidato válido según las reglas
                                continue
                            # marcar la asignación y etiquetar qué evento cubre
                            try:
                                prev_assigned_dt = _p_dt(best)
                            except Exception:
                                pass
                            # registrar evento emparejado en la marcación
                            try:
                                best['matched_event'] = ev['label']
                                best['matched_event_dt'] = ev_dt
                            except Exception:
                                pass
                            best['assigned'] = True
                            # añadir motivo de emparejamiento para debugging
                            try:
                                best_dt = best.get('dt_norm') or best.get('dt')
                                try:
                                    diff = (best_dt - ev['dt']).total_seconds()
                                except Exception:
                                    diff = None
                            except Exception:
                                best_dt = None
                                diff = None
                            reason = []
                            try:
                                if _p_dt(best) < ev_dt:
                                    reason.append('before')
                                elif _p_dt(best) > ev_dt:
                                    reason.append('after')
                                if diff is None:
                                    reason.append('no-diff')
                                else:
                                    if abs(diff) > IN_MAX_SECONDS:
                                        reason.append('far')
                            except Exception:
                                pass
                            best['match_reason'] = ','.join(reason)
                            if debug_punches:
                                msg = f"[punch-debug] emp={emp_id} day={d} ev={ev['label']} ev_dt={ev['dt']} best_dt={best_dt} diff_s={diff} reason={best.get('match_reason')} best_raw={best}"
                                logger.debug(msg)
                                print(msg)
                                try:
                                    with open(os.path.join(os.getcwd(), 'punch_debug.log'), 'a',
                                              encoding='utf-8') as _f:
                                        _f.write(msg + '\n')
                                except Exception:
                                    pass
                            # determinar si es tardanza/anticipada
                            row_class = ''
                            try:
                                best_dt = best.get('dt_norm') or best.get('dt')
                                # Comparar truncando segundos: 08:00:30 NO es tardanza,
                                # solo se marca 'late' si el MINUTO es posterior al esperado.
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
                            if debug_punches:
                                msg = f"[punch-debug] emp={emp_id} day={d} ev={ev['label']} result_row_class={row_class}"
                                logger.debug(msg)
                                print(msg)
                                try:
                                    with open(os.path.join(os.getcwd(), 'punch_debug.log'), 'a',
                                              encoding='utf-8') as _f:
                                        _f.write(msg + '\n')
                                except Exception:
                                    pass
                            newp = best.copy()
                            newp['row_class'] = row_class
                            annotated.append(newp)

                        # añadir marcaciones no asignadas (si las hay) en orden cronológico
                        remaining = [p for p in punches_sorted if not p.get('assigned')]
                        for r in remaining:
                            r_new = r.copy()
                            r_new['row_class'] = r_new.get('row_class', '')
                            annotated.append(r_new)

                        # El filtrado de duplicados se realiza más abajo en el bloque
                        # de G-registers, que usa matched_event para decidir qué mostrar.
                        # No se aplica ningún filtro adicional aquí.

                        # Post-proceso: por cada jornada (J1, J2) colapsar múltiples marcaciones
                        if ENABLE_SHIFT_COLLAPSE:
                            try:
                                def dt_of(p):
                                    return p.get('dt_norm') or p.get('dt')

                                # pares de jornadas esperadas: (J1_in,J1_out), (J2_in,J2_out)
                                for in_label, out_label in [('J1_in', 'J1_out'), ('J2_in', 'J2_out')]:
                                    ev_in = next((e for e in events if e.get('label') == in_label), None)
                                    ev_out = next((e for e in events if e.get('label') == out_label), None)
                                    if not ev_in or not ev_out:
                                        continue
                                    start_window = ev_in['dt'] - timedelta(hours=2)
                                    end_window = ev_out['dt'] + timedelta(hours=2)
                                    in_shift = [p for p in annotated if
                                                dt_of(p) >= start_window and dt_of(p) <= end_window]
                                    if len(in_shift) > 1:
                                        earliest = min(in_shift, key=dt_of)
                                        latest = max(in_shift, key=dt_of)
                                        # mantener el resto fuera del shift
                                        new_annot = [p for p in annotated if p not in in_shift]
                                        e_copy = earliest.copy();
                                        e_copy['matched_event'] = in_label;
                                        e_copy['assigned'] = True
                                        l_copy = latest.copy();
                                        l_copy['matched_event'] = out_label;
                                        l_copy['assigned'] = True
                                        new_annot.extend([e_copy, l_copy])
                                        annotated = sorted(new_annot, key=lambda x: x.get('dt'))
                            except Exception:
                                pass
                        # Antes: eliminábamos marcaciones no asignadas cuando había más
                        # marcaciones crudas que eventos esperados. Eso ocultaba
                        # marcaciones válidas en casos ruidosos. Ahora conservamos
                        # todas las marcaciones y añadimos flags por día para que
                        # la plantilla decida cómo resaltarlas.
                        try:
                            raw_cnt = day_obj.get('raw_punches_count', len(punches_sorted))
                            expected_cnt = len(events)
                            # contar asignadas (matched)
                            matched_cnt = sum(1 for p in annotated if p.get('assigned') and p.get('matched_event'))
                            day_obj['expected_cnt'] = expected_cnt
                            day_obj['matched_cnt'] = matched_cnt
                            day_obj['extra_cnt'] = max(0, raw_cnt - expected_cnt)
                            # flag: si no hubo marcaciones crudas y no hay permisos/feriado
                            no_marks = (raw_cnt == 0 and not day_obj.get('permits') and not day_obj.get('is_holiday',
                                                                                                        False))
                            day_obj['no_marks_all_day'] = no_marks
                            # flag: si hay menos marcaciones asignadas que eventos esperados
                            day_obj['has_inconsistency'] = (expected_cnt > matched_cnt)
                        except Exception:
                            day_obj['expected_cnt'] = 0
                            day_obj['matched_cnt'] = 0
                            day_obj['extra_cnt'] = 0
                            day_obj['no_marks_all_day'] = False
                            day_obj['has_inconsistency'] = False
                    except Exception:
                        # si algo falla, fallback: no marcar
                        annotated = []
                        for p in punches_sorted:
                            np = p.copy()
                            np['row_class'] = ''
                            annotated.append(np)
                else:
                    # Sin horario o sin marcaciones: devolver tal cual
                    for p in punches_sorted:
                        np = p.copy()
                        np['row_class'] = ''
                        annotated.append(np)

                # ordenar por fecha para la presentación
                annotated = sorted(annotated, key=lambda x: x.get('dt'))

                # ---------------------------------------------------------------
                # MÁQUINA DE ESTADOS DE MARCACIONES  (fiel al diagrama de flujo)
                # Variables del diagrama:
                #   G1..G4  = datetime de cada marcación guardada (None = vacío)
                #   E1,S1   = Hora entrada / salida Jornada 1
                #   E2,S2   = Hora entrada / salida Jornada 2  (None si no aplica)
                #   ATR     = acumulador de minutos de atraso
                #   TEMP    = atraso temporal (salida anticipada J1 pendiente de confirmar)
                #   INC     = contador de inconsistencias (marcas sin slot válido)
                #   DIAS    = contador días sin marcar (se lleva a nivel superior)
                # ---------------------------------------------------------------
                g_regs = {'G1': None, 'G2': None, 'G3': None, 'G4': None}
                g_atr = {'G1': 0, 'G2': 0, 'G3': 0, 'G4': 0}

                # Mapear eventos del horario del día
                events_list = day_obj.get('events', []) or []
                events_map = {ev.get('label'): ev for ev in events_list}
                E1 = events_map.get('J1_in', {}).get('dt')
                S1 = events_map.get('J1_out', {}).get('dt')
                E2 = events_map.get('J2_in', {}).get('dt')
                S2 = events_map.get('J2_out', {}).get('dt')

                day_punches = punches_sorted  # lista cronológica de marcas del día

                # Contadores del diagrama
                TEMP = 0
                ATR = 0
                INC = 0

                # ── Decisión raíz: ¿HORARIO 4 JORNADAS? ─────────────────────
                is_4_jornadas = (E2 is not None and S2 is not None)

                for p in day_punches:
                    try:
                        M = p.get('dt_norm') or p.get('dt')
                    except Exception:
                        continue
                    if M is None:
                        continue

                    # ════════════════════════════════════════════════════════
                    # RAMA NO  → 2 GUARDADOS (horario de una sola jornada)
                    # Nodos según diagrama: SI G1 → M>E1 → M=G1 → ATR=M-E1
                    #                                      ↓ NO
                    #                       SI G2 → G2≥S2 → FIN
                    # ════════════════════════════════════════════════════════
                    if not is_4_jornadas:

                        # ── Slot G1 vacío → primera marca del día ──────────
                        if g_regs['G1'] is None:
                            g_regs['G1'] = M
                            # Diagrama: M > E1  →  ATR = M - E1
                            if E1 and M > E1:
                                mins = int((M - E1).total_seconds() // 60)
                                ATR += max(0, mins)
                                g_atr['G1'] = max(0, mins)
                            # M <= E1 → llegó a tiempo, ATR no cambia
                            continue

                        # ── G1 lleno, G2 vacío → segunda marca (salida) ────
                        if g_regs['G2'] is None:
                            g_regs['G2'] = M
                            # Diagrama: G2 ≥ S2 → FIN (salida ok)
                            #           G2 < S2 → salida anticipada → ATR = ATR + (S1 - G2)
                            if S1 and M < S1:
                                mins = int((S1 - M).total_seconds() // 60)
                                ATR += max(0, mins)
                                g_atr['G2'] = max(0, mins)
                            continue

                        # G1 y G2 ya llenos → marcas extra ignoradas en ruta 2
                        continue

                    # ════════════════════════════════════════════════════════
                    # RAMA SÍ  → 4 GUARDADOS (horario con dos jornadas)
                    # El diagrama sigue este orden para cada marcación M:
                    #
                    #  SI G1 vacío:
                    #      M > E1? SÍ → M = G1 ;  ATR = M - E1
                    #              NO → (marca antes de E1, no asignar G1)
                    #
                    #  SI G1 lleno, G2 vacío:
                    #      M ≥ S1? SÍ → G2 = M  (salida a tiempo, sin TEMP)
                    #              NO → G2 = M ; TEMP = S1 - G2 ; ATR = ATR + TEMP
                    #
                    #  SI G2 lleno, G3 vacío:
                    #      G2 ≥ S2?  SÍ → [nunca ocurre si hay J2, rama de seguridad → FIN]
                    #      SI G3:
                    #          M > E2? SÍ → G3 = M
                    #                       ATR = ATR - TEMP ; TEMP = 0
                    #                       M > E2? → ATR = ATR + (M - E2)
                    #                  NO → (antes de E2, ignorar o marcar INC)
                    #
                    #  SI G3 lleno, G4 vacío:
                    #      M ≥ S2? SÍ → G4 = M  (salida a tiempo, TEMP ya = 0)
                    #              NO → G4 = M ; TEMP = S2 - G4 ; ATR = ATR + TEMP
                    # ════════════════════════════════════════════════════════

                    # ── Slot G1 ─────────────────────────────────────────────
                    if g_regs['G1'] is None:
                        # Diagrama: M > E1 → asignar G1 y calcular ATR
                        if E1 and M > E1:
                            g_regs['G1'] = M
                            mins = int((M - E1).total_seconds() // 60)
                            ATR += max(0, mins)
                            g_atr['G1'] = max(0, mins)
                        # M <= E1: llegó antes de la entrada esperada → no asignar todavía
                        # (el diagrama muestra "NO" volviendo al inicio del loop)
                        continue

                    # ── Slot G2 ─────────────────────────────────────────────
                    if g_regs['G2'] is None:
                        g_regs['G2'] = M
                        if S1 and M >= S1:
                            # Salida a tiempo o tardía → sin penalidad por salida anticipada
                            # (TEMP permanece en 0)
                            pass
                        elif S1 and M < S1:
                            # Salida anticipada J1: TEMP = S1 - G2 ; ATR += TEMP
                            TEMP = int((S1 - M).total_seconds() // 60)
                            ATR += max(0, TEMP)
                            g_atr['G2'] = max(0, TEMP)
                        continue

                    # ── Slot G3 ─────────────────────────────────────────────
                    if g_regs['G3'] is None:
                        # Diagrama: G2 ≥ S2 → rama de cortocircuito (no debería llegar
                        # aquí si la segunda jornada arrancó antes de S1; protección)
                        if S1 and g_regs['G2'] >= S1 and E2 and M <= E2:
                            # marca entre S1 y E2 → no es entrada J2 todavía; ignorar
                            continue
                        if E2 and M > E2:
                            g_regs['G3'] = M
                            # Revertir TEMP (salida anticipada J1 quedó cubierta por llegada J2)
                            ATR = max(0, ATR - TEMP)
                            TEMP = 0
                            # Nuevo atraso: llegada J2 después de E2
                            mins = int((M - E2).total_seconds() // 60)
                            if mins > 0:
                                ATR += mins
                                g_atr['G3'] = mins
                        # M <= E2 → antes de la entrada J2 → ignorar (diagrama "NO")
                        continue

                    # ── Slot G4 ─────────────────────────────────────────────
                    if g_regs['G4'] is None:
                        g_regs['G4'] = M
                        if S2 and M >= S2:
                            # Salida J2 a tiempo o tardía → sin penalidad adicional
                            pass
                        elif S2 and M < S2:
                            # Salida anticipada J2: TEMP = S2 - G4 ; ATR += TEMP
                            TEMP = int((S2 - M).total_seconds() // 60)
                            ATR += max(0, TEMP)
                            g_atr['G4'] = max(0, TEMP)
                        continue

                    # G1..G4 ya llenos → marcas extra se ignoran
                    continue

                # ── Exponer resultados del día ───────────────────────────────
                day_obj['g_regs'] = g_regs
                day_obj['g_atr'] = g_atr
                day_obj['atr_dia'] = ATR
                day_obj['temp'] = TEMP

                # ── Filtrado final: mostrar solo las marcaciones que cubren un evento ──
                #
                # CRITERIO: una marcación es visible si tiene matched_event asignado
                # por el emparejador (assigned=True + matched_event != None).
                # Las marcaciones extra sin evento emparejado se marcan filtered=True.
                #
                # Esto reemplaza el bloque anterior que buscaba por proximidad ciega
                # a los G-registers, lo que causaba que marcaciones correctamente
                # emparejadas (ej. 07:59 → J1_in) quedaran ocultas porque la
                # máquina de estados G asignaba su slot a una marca posterior.
                try:
                    def dt_of(p):
                        return p.get('dt_norm') or p.get('dt')

                    # Mapeo inverso: evento → marcación asignada
                    # (un evento solo puede tener UNA marcación asignada)
                    event_to_punch = {}
                    for p in annotated:
                        ev_label = p.get('matched_event')
                        if p.get('assigned') and ev_label:
                            # Si hay duplicados para el mismo evento, quedarse
                            # con la cronológicamente más cercana al horario esperado
                            if ev_label not in event_to_punch:
                                event_to_punch[ev_label] = p
                            else:
                                # Resolver conflicto: preferir la ya registrada
                                # (el emparejador greedy ya eligió la mejor)
                                pass

                    # Construir el set de ids visibles
                    visible_ids = {id(p) for p in event_to_punch.values()}

                    for p in annotated:
                        if 'selected_slot' in p:
                            del p['selected_slot']
                        if id(p) in visible_ids:
                            p['filtered'] = False
                            # Anotar qué slot cubre para el template
                            ev_label = p.get('matched_event', '')
                            slot_map = {
                                'J1_in': 'G1', 'J1_out': 'G2',
                                'J2_in': 'G3', 'J2_out': 'G4',
                            }
                            p['selected_slot'] = slot_map.get(ev_label, '')
                        else:
                            # Marcación extra sin evento: ocultar
                            p['filtered'] = True

                    # mantener orden cronológico
                    annotated = sorted(annotated, key=lambda x: x.get('dt') or x.get('dt_norm'))
                except Exception:
                    pass

                # Flags de resumen: falta algun slot esperado y hay marcaciones
                try:
                    expected_slots = len(events_list)
                    assigned_slots = sum(1 for v in g_regs.values() if v is not None)
                    raw_cnt = day_obj.get('raw_punches_count', len(day_punches))
                    is_holiday = day_obj.get('is_holiday', False)
                    has_permits = bool(day_obj.get('permits'))
                    cur_date_tmp = date(year, month, int(d))
                    is_workday_tmp = cur_date_tmp.weekday() < 5
                    # Inconsistencia = falta al menos una marcación esperada en un día laborable:
                    #   · Tiene marcaciones pero no alcanzó todos los slots (ej. falta salida)
                    #   · No tiene ninguna marcación en un día laborable sin permiso ni feriado
                    missing_slots = expected_slots > assigned_slots
                    no_marks = (raw_cnt == 0 and not is_holiday and not has_permits and is_workday_tmp)
                    day_obj['has_inconsistency'] = (missing_slots or no_marks) and is_workday_tmp and not is_holiday
                    day_obj['no_marks_all_day'] = no_marks
                except Exception:
                    day_obj['has_inconsistency'] = day_obj.get('has_inconsistency', False)
                    day_obj['no_marks_all_day'] = day_obj.get('no_marks_all_day', False)

                day_obj['punches'] = annotated
                # Etiqueta de fecha: 01 de enero
                try:
                    months_es_local = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                       "septiembre", "octubre", "noviembre", "diciembre"]
                    day_obj['day_label'] = f"{int(d):02d} de {months_es_local[month]}"
                except Exception:
                    day_obj['day_label'] = str(d)

    # --- Membrete (configuración del sistema) embebido como data URI para xhtml2pdf ---
    config = SystemConfiguration.get_current()
    letterhead_data = None
    # Permitir desactivar membrete vía parámetro para pruebas
    no_letterhead = request.GET.get('no_letterhead') == '1'
    if not no_letterhead and config and getattr(config, 'letterhead', None):
        try:
            # Preferir siempre la URL pública del archivo (funciona mejor con xhtml2pdf)
            try:
                letterhead_data = request.build_absolute_uri(config.letterhead.url)
            except Exception:
                letterhead_data = config.letterhead.url
            # Si no hay URL válida y existe en disco, usar data URI como fallback
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

    # Construir resumen de asistencia: inconsistencias, dias sin marcar, minutos de atraso
    def build_attendance_summary(calendar_data, year, month):
        inconsistencias = 0
        dias_sin_marcar = 0
        minutos_atraso = 0
        # compute schedule per day using history lookup
        schedule_obj = None
        for week in calendar_data:
            for day_obj in week:
                d = day_obj.get('day')
                if not d:
                    continue
                # excluir feriados o permisos totales del conteo de dias sin marcar
                is_holiday = day_obj.get('is_holiday', False)
                has_permits = bool(day_obj.get('permits'))
                raw_cnt = day_obj.get('raw_punches_count', 0)

                # determinar si es día laborable según el horario (por defecto Lun-Vie)
                try:
                    cur_date = date(year, month, int(d))
                    wd = cur_date.weekday()  # 0=Lun .. 6=Dom
                    try:
                        from schedule.models import get_employee_schedule_for_date
                        schedule_obj = get_employee_schedule_for_date(inst_data.employee, cur_date)
                    except Exception:
                        schedule_obj = None

                    if schedule_obj:
                        if wd == 0:
                            is_workday = bool(getattr(schedule_obj, 'monday', True))
                        elif wd == 1:
                            is_workday = bool(getattr(schedule_obj, 'tuesday', True))
                        elif wd == 2:
                            is_workday = bool(getattr(schedule_obj, 'wednesday', True))
                        elif wd == 3:
                            is_workday = bool(getattr(schedule_obj, 'thursday', True))
                        elif wd == 4:
                            is_workday = bool(getattr(schedule_obj, 'friday', True))
                        elif wd == 5:
                            is_workday = bool(getattr(schedule_obj, 'saturday', False))
                        else:
                            is_workday = bool(getattr(schedule_obj, 'sunday', False))
                    else:
                        # por defecto considerar Lun-Vie como laborables
                        is_workday = wd < 5
                except Exception:
                    is_workday = True

                if raw_cnt == 0 and not is_holiday and not has_permits and is_workday:
                    dias_sin_marcar += 1

                # calcular expected como eventos no cubiertos por permisos
                events = day_obj.get('events', []) or []

                def event_covered_by_permit(ev, permits):
                    for perm in permits:
                        ps = perm.get('start_time')
                        pe = perm.get('end_time')
                        # si no hay horarios en el permiso, se considera permiso todo el día
                        if not ps and not pe:
                            return True
                        try:
                            ev_time = ev.get('dt').time()
                        except Exception:
                            continue
                        # si sólo existe start_time, asumir que cubre desde ese momento hasta fin de jornada
                        if ps and not pe:
                            if ev_time >= ps:
                                return True
                            continue
                        # si sólo existe end_time, asumir que cubre desde inicio de jornada hasta end_time
                        if pe and not ps:
                            if ev_time <= pe:
                                return True
                            continue
                        # si existen ambos, verificar inclusión
                        if ps and pe:
                            try:
                                if ps <= ev_time <= pe:
                                    return True
                            except Exception:
                                continue
                    return False

                permits = day_obj.get('permits', [])
                expected = sum(1 for ev in events if not event_covered_by_permit(ev, permits))
                # matched events that are not covered by permit
                matched = 0
                for p in day_obj.get('punches', []):
                    if p.get('assigned') and p.get('matched_event'):
                        # si evento existe y no está cubierto por permit, contarlo
                        ev_label = p.get('matched_event')
                        ev = next((e for e in events if e.get('label') == ev_label), None)
                        if ev and not event_covered_by_permit(ev, permits):
                            matched += 1

                if is_workday and expected > matched:
                    inconsistencias += (expected - matched)

                # Mapear eventos por etiqueta para comparar tiempos
                events_map = {ev['label']: ev for ev in day_obj.get('events', [])}
                cur_date = date(year, month, int(d))
                for p in day_obj.get('punches', []):
                    if not p.get('matched_event'):
                        continue
                    ev_label = p.get('matched_event')
                    ev = events_map.get(ev_label)
                    if not ev:
                        continue
                    # solo calcular atraso para eventos de tipo 'in'
                    if ev.get('type') != 'in':
                        continue
                    try:
                        p_dt = p.get('dt_norm') or p.get('dt')
                        ev_dt = ev.get('dt')
                    except Exception:
                        continue
                    # revisar si hay permiso que cubra este evento; si lo hay, usar end_time como corte
                    # El conteo de minutos empieza desde el minuto 1 (08:01 -> 1 min)
                    cutoff = ev_dt
                    for perm in day_obj.get('permits', []):
                        try:
                            ps = perm.get('start_time')
                            pe = perm.get('end_time')
                            if ps and pe:
                                # si el evento cae dentro del permiso, ajustar cutoff al final del permiso
                                if ps <= ev_dt.time() <= pe:
                                    cutoff = datetime.combine(cur_date, pe)
                                    break
                        except Exception:
                            continue

                    diff = (p_dt - cutoff).total_seconds()
                    if diff >= 60:
                        minutos_atraso += int(diff // 60)

        return {'inconsistencias': inconsistencias, 'dias_sin_marcar': dias_sin_marcar,
                'minutos_atraso': minutos_atraso}

    summary = build_attendance_summary(calendar_data, year, month)

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

    # Usar WeasyPrint si está disponible, si no, intentar pisa como fallback
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


def generate_department_report_pdf(request):
    unit_id = request.GET.get('unit_id')
    month = int(request.GET.get('month', 1))
    year = int(request.GET.get('year', datetime.now().year))
    if not unit_id:
        return HttpResponse('unit_id requerido', status=400)

    # Recolectar unidad y sus descendientes
    from institution.models import AdministrativeUnit

    def collect_unit_ids(root_id):
        ids = set()
        stack = [int(root_id)]
        while stack:
            cur = stack.pop()
            ids.add(cur)
            children = AdministrativeUnit.objects.filter(parent_id=cur, is_active=True).values_list('id', flat=True)
            for c in children:
                if c not in ids:
                    stack.append(c)
        return list(ids)

    try:
        unit = AdministrativeUnit.objects.get(pk=unit_id, is_active=True)
    except AdministrativeUnit.DoesNotExist:
        return HttpResponse('Unidad no encontrada', status=404)

    unit_ids = collect_unit_ids(unit_id)

    # Empleados con datos biométricos en la unidad
    inst_qs = InstitutionalData.objects.select_related('employee__person').filter(
        employee__area_id__in=unit_ids,
        employee__is_active=True,
        biometric_id__isnull=False
    )

    results_by_unit = {}
    for inst in inst_qs:
        emp_id = inst.employee_id
        # Marcaciones del mes
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
            punches_map.setdefault(day, []).append(
                {'time': dt_norm.strftime('%H:%M'), 'dt': p.registry_date, 'dt_norm': dt_norm})

        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
        calendar_data = []
        for week in weeks:
            week_list = []
            for day in week:
                week_list.append({'day': day if day != 0 else '', 'punches': punches_map.get(day, [])})
            calendar_data.append(week_list)

        # Permits y feriados (solo se necesitan para el resumen)
        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        permits_qs = PermitRequest.objects.filter(employee_id=emp_id, status='APPROVED').filter(
            Q(start_date__lte=month_end, end_date__gte=month_start) |
            Q(start_date__range=(month_start, month_end)) |
            Q(end_date__range=(month_start, month_end))
        )
        permits_map = {}
        for pr in permits_qs:
            start = pr.start_date if pr.start_date >= month_start else month_start
            end = (pr.end_date or pr.start_date)
            if end > month_end:
                end = month_end
            cur = start
            while cur <= end:
                d = cur.day
                permits_map.setdefault(d, []).append({'start_time': pr.start_time, 'end_time': pr.end_time})
                cur = cur + timedelta(days=1)

        holidays_qs = ScheduleObservation.objects.filter(is_active=True, is_holiday=True,
                                                         start_date__lte=month_end, end_date__gte=month_start)
        holidays_map = {}
        for obs in holidays_qs:
            start = obs.start_date if obs.start_date >= month_start else month_start
            end = obs.end_date if obs.end_date <= month_end else month_end
            cur = start
            while cur <= end:
                holidays_map[cur.day] = obs.name
                cur = cur + timedelta(days=1)

        # Anotar calendar_data con events, permits y punches ya emparejadas de forma simple (similar a la lógica existente)
        for widx, week in enumerate(calendar_data):
            for didx, day_obj in enumerate(week):
                d = day_obj.get('day')
                day_obj['raw_punches_count'] = len(day_obj.get('punches', []))
                if not d:
                    day_obj['is_holiday'] = False
                    day_obj['permits'] = []
                else:
                    day_obj['is_holiday'] = d in holidays_map
                    day_obj['permits'] = permits_map.get(d, [])

                    punches_sorted = sorted(day_obj.get('punches', []), key=lambda x: x.get('dt_norm') or x.get('dt'))
                    annotated = []
                    try:
                        # obtener schedule para este empleado en la fecha
                        from schedule.models import get_employee_schedule_for_date
                        cur_date = date(year, month, int(d))
                        schedule = get_employee_schedule_for_date(inst.employee, cur_date)
                    except Exception:
                        schedule = None

                    if schedule and punches_sorted:
                        cur_date = date(year, month, int(d))
                        events = []
                        if schedule.morning_start:
                            ev_dt = datetime.combine(cur_date, schedule.morning_start)
                            events.append({'label': 'J1_in', 'type': 'in', 'dt': ev_dt})
                        if schedule.morning_end:
                            ev_dt = datetime.combine(cur_date, schedule.morning_end)
                            if schedule.morning_crosses_midnight and schedule.morning_end <= schedule.morning_start:
                                ev_dt = ev_dt + timedelta(days=1)
                            events.append({'label': 'J1_out', 'type': 'out', 'dt': ev_dt})
                        if schedule.afternoon_start:
                            ev_dt = datetime.combine(cur_date, schedule.afternoon_start)
                            events.append({'label': 'J2_in', 'type': 'in', 'dt': ev_dt})
                        if schedule.afternoon_end:
                            ev_dt = datetime.combine(cur_date, schedule.afternoon_end)
                            if schedule.afternoon_crosses_midnight and schedule.afternoon_end <= (
                                    schedule.afternoon_start or schedule.morning_start):
                                ev_dt = ev_dt + timedelta(days=1)
                            events.append({'label': 'J2_out', 'type': 'out', 'dt': ev_dt})

                        day_obj['events'] = events

                        prev_assigned_dt = datetime.min

                        def get_dt(p):
                            return p.get('dt_norm') or p.get('dt')

                        # candidatos mutables: copias de punches_sorted sin asignar
                        unassigned = [p for p in punches_sorted if not p.get('assigned')]

                        # PASO 1: asignar eventos 'in' prefiriendo la marcacion mas cercana ANTES de la hora de entrada
                        for ev in events:
                            if ev.get('type') != 'in':
                                continue
                            ev_dt = ev.get('dt')
                            # preferir la ultima marcacion <= ev_dt
                            before = [p for p in unassigned if get_dt(p) <= ev_dt]
                            best = None
                            if before:
                                best = max(before, key=get_dt)
                            else:
                                # fallback: primer candidato despues de la entrada pero antes del siguiente evento
                                try:
                                    idx = events.index(ev)
                                    next_ev_dt = events[idx + 1]['dt'] if idx + 1 < len(events) else ev_dt + timedelta(
                                        hours=24)
                                except Exception:
                                    next_ev_dt = ev_dt + timedelta(hours=24)
                                after = [p for p in unassigned if get_dt(p) > ev_dt and get_dt(p) <= next_ev_dt]
                                if after:
                                    best = min(after, key=get_dt)
                            if not best:
                                continue
                            # aplicar límite de distancia
                            MAX_MATCH_SECONDS = 60 * 60 * 2
                            if abs((get_dt(best) - ev_dt).total_seconds()) > MAX_MATCH_SECONDS:
                                continue
                            best['matched_event'] = ev.get('label')
                            best['matched_event_dt'] = ev_dt
                            best['assigned'] = True
                            annotated.append(best.copy())
                            unassigned = [p for p in unassigned if p is not best]

                        # PASO 2: asignar eventos 'out' prefiriendo la marcacion mas cercana DESPUES de la hora de salida
                        for ev in events:
                            if ev.get('type') != 'out':
                                continue
                            ev_dt = ev.get('dt')
                            try:
                                idx = events.index(ev)
                                prev_ev_dt = events[idx - 1]['dt'] if idx > 0 else ev_dt - timedelta(hours=24)
                                next_ev_dt = events[idx + 1]['dt'] if idx + 1 < len(events) else ev_dt + timedelta(
                                    hours=24)
                            except Exception:
                                prev_ev_dt = ev_dt - timedelta(hours=24)
                                next_ev_dt = ev_dt + timedelta(hours=24)
                            candidates = [p for p in unassigned if get_dt(p) >= prev_ev_dt and get_dt(p) <= next_ev_dt]
                            after = [p for p in candidates if get_dt(p) >= ev_dt]
                            before = [p for p in candidates if get_dt(p) < ev_dt]
                            best = None
                            if after:
                                # preferir la ultima marcacion despues de la hora de salida (salida real)
                                best = max(after, key=get_dt)
                            elif before:
                                # si no hay despues, tomar la mas cercana antes
                                best = max(before, key=get_dt)
                            if not best:
                                continue
                            MAX_MATCH_SECONDS = 60 * 60 * 2
                            if abs((get_dt(best) - ev_dt).total_seconds()) > MAX_MATCH_SECONDS:
                                continue
                            best['matched_event'] = ev.get('label')
                            best['matched_event_dt'] = ev_dt
                            best['assigned'] = True
                            annotated.append(best.copy())
                            unassigned = [p for p in unassigned if p is not best]

                        remaining = [p for p in punches_sorted if not p.get('assigned')]
                        for r in remaining:
                            r_new = r.copy();
                            r_new['row_class'] = '';
                            annotated.append(r_new)

                        # Collapsing disabled (handled via ENABLE_SHIFT_COLLAPSE flag)
                        if ENABLE_SHIFT_COLLAPSE:
                            try:
                                def dt_of(p):
                                    return p.get('dt_norm') or p.get('dt')

                                for in_label, out_label in [('J1_in', 'J1_out'), ('J2_in', 'J2_out')]:
                                    ev_in = next((e for e in events if e.get('label') == in_label), None)
                                    ev_out = next((e for e in events if e.get('label') == out_label), None)
                                    if not ev_in or not ev_out:
                                        continue
                                    start_window = ev_in['dt'] - timedelta(hours=2)
                                    end_window = ev_out['dt'] + timedelta(hours=2)
                                    in_shift = [p for p in annotated if
                                                dt_of(p) >= start_window and dt_of(p) <= end_window]
                                    if len(in_shift) > 1:
                                        earliest = min(in_shift, key=dt_of)
                                        latest = max(in_shift, key=dt_of)
                                        new_annot = [p for p in annotated if p not in in_shift]
                                        e_copy = earliest.copy();
                                        e_copy['matched_event'] = in_label;
                                        e_copy['assigned'] = True
                                        l_copy = latest.copy();
                                        l_copy['matched_event'] = out_label;
                                        l_copy['assigned'] = True
                                        new_annot.extend([e_copy, l_copy])
                                        annotated = sorted(new_annot, key=lambda x: x.get('dt'))
                            except Exception:
                                pass

                        try:
                            raw_cnt = day_obj.get('raw_punches_count', len(punches_sorted))
                            # calcular eventos esperados excluyendo aquellos cubiertos por permisos
                            permits = day_obj.get('permits', [])

                            def event_covered_by_permit_local(ev, permits_list):
                                for perm in permits_list:
                                    ps = perm.get('start_time')
                                    pe = perm.get('end_time')
                                    # permiso de jornada completa
                                    if not ps and not pe:
                                        return True
                                    try:
                                        ev_time = ev.get('dt').time()
                                    except Exception:
                                        continue
                                    if ps and not pe:
                                        if ev_time >= ps:
                                            return True
                                        continue
                                    if pe and not ps:
                                        if ev_time <= pe:
                                            return True
                                        continue
                                    if ps and pe:
                                        try:
                                            if ps <= ev_time <= pe:
                                                return True
                                        except Exception:
                                            continue
                                return False

                            expected_cnt = sum(1 for ev in events if not event_covered_by_permit_local(ev, permits))
                            matched_cnt = sum(1 for p in annotated if p.get('assigned') and p.get(
                                'matched_event') and not event_covered_by_permit_local(
                                next((e for e in events if e.get('label') == p.get('matched_event')), {}), permits))
                            day_obj['expected_cnt'] = expected_cnt
                            day_obj['matched_cnt'] = matched_cnt
                            day_obj['extra_cnt'] = max(0, raw_cnt - expected_cnt)
                            no_marks = (raw_cnt == 0 and not permits and not day_obj.get('is_holiday', False))
                            day_obj['no_marks_all_day'] = no_marks
                            # si todos los eventos esperados están cubiertos por permisos, no marcar inconsistencia
                            day_obj['has_inconsistency'] = (expected_cnt > matched_cnt)
                        except Exception:
                            day_obj['expected_cnt'] = 0
                            day_obj['matched_cnt'] = 0
                            day_obj['extra_cnt'] = 0
                            day_obj['no_marks_all_day'] = False
                            day_obj['has_inconsistency'] = False
                    else:
                        for p in punches_sorted:
                            np = p.copy();
                            np['row_class'] = '';
                            annotated.append(np)

                    annotated = sorted(annotated, key=lambda x: x.get('dt'))
                    day_obj['punches'] = annotated
                    # debug: volcar info detallada por día cuando se solicita
                    if debug_punches:
                        try:
                            raw_list = [(p.get('dt_norm') or p.get('dt')).strftime('%Y-%m-%d %H:%M:%S') for p in
                                        punches_sorted]
                        except Exception:
                            raw_list = [str(p.get('dt_norm') or p.get('dt')) for p in punches_sorted]
                        try:
                            ann_list = []
                            for p in annotated:
                                dt = (p.get('dt_norm') or p.get('dt'))
                                dt_s = dt.strftime('%Y-%m-%d %H:%M:%S') if hasattr(dt, 'strftime') else str(dt)
                                ann_list.append({'dt': dt_s, 'assigned': bool(p.get('assigned')),
                                                 'matched_event': p.get('matched_event'),
                                                 'row_class': p.get('row_class')})
                        except Exception:
                            ann_list = [str(p) for p in annotated]
                        dbg = f"[punch-debug] emp={emp_id} day={d} raw={raw_list} events={[e.get('label') + ':' + (e.get('dt').strftime('%H:%M') if hasattr(e.get('dt'), 'strftime') else str(e.get('dt'))) for e in events]} annotated={ann_list} expected={day_obj.get('expected_cnt')} matched={day_obj.get('matched_cnt')} extra={day_obj.get('extra_cnt')} no_marks={day_obj.get('no_marks_all_day')} inconsistency={day_obj.get('has_inconsistency')}"
                        print(dbg)
                        try:
                            with open(os.path.join(os.getcwd(), 'punch_debug.log'), 'a', encoding='utf-8') as _f:
                                _f.write(dbg + '\n')
                        except Exception:
                            pass

        # Calcular resumen (duplicando la lógica de build_attendance_summary)
        inconsistencias = 0
        dias_sin_marcar = 0
        minutos_atraso = 0
        # schedule will be resolved per-day using history
        schedule_obj = None

        for week in calendar_data:
            for day_obj in week:
                d = day_obj.get('day')
                if not d:
                    continue
                is_holiday = day_obj.get('is_holiday', False)
                has_permits = bool(day_obj.get('permits'))
                raw_cnt = day_obj.get('raw_punches_count', 0)
                try:
                    cur_date = date(year, month, int(d))
                    wd = cur_date.weekday()
                    try:
                        from schedule.models import get_employee_schedule_for_date
                        schedule_obj = get_employee_schedule_for_date(inst.employee, cur_date)
                    except Exception:
                        schedule_obj = None

                    if schedule_obj:
                        if wd == 0:
                            is_workday = bool(getattr(schedule_obj, 'monday', True))
                        elif wd == 1:
                            is_workday = bool(getattr(schedule_obj, 'tuesday', True))
                        elif wd == 2:
                            is_workday = bool(getattr(schedule_obj, 'wednesday', True))
                        elif wd == 3:
                            is_workday = bool(getattr(schedule_obj, 'thursday', True))
                        elif wd == 4:
                            is_workday = bool(getattr(schedule_obj, 'friday', True))
                        elif wd == 5:
                            is_workday = bool(getattr(schedule_obj, 'saturday', False))
                        else:
                            is_workday = bool(getattr(schedule_obj, 'sunday', False))
                    else:
                        is_workday = wd < 5
                except Exception:
                    is_workday = True

                if raw_cnt == 0 and not is_holiday and not has_permits and is_workday:
                    dias_sin_marcar += 1

                events = day_obj.get('events', []) or []

                def event_covered_by_permit(ev, permits):
                    for perm in permits:
                        ps = perm.get('start_time')
                        pe = perm.get('end_time')
                        if ps and pe:
                            try:
                                ev_time = ev.get('dt').time()
                                if ps <= ev_time <= pe:
                                    return True
                            except Exception:
                                continue
                    return False

                permits = day_obj.get('permits', [])
                expected = sum(1 for ev in events if not event_covered_by_permit(ev, permits))
                matched = 0
                for p in day_obj.get('punches', []):
                    if p.get('assigned') and p.get('matched_event'):
                        ev_label = p.get('matched_event')
                        ev = next((e for e in events if e.get('label') == ev_label), None)
                        if ev and not event_covered_by_permit(ev, permits):
                            matched += 1

                if is_workday and expected > matched:
                    inconsistencias += (expected - matched)

                events_map = {ev['label']: ev for ev in day_obj.get('events', [])}
                cur_date = date(year, month, int(d))
                for p in day_obj.get('punches', []):
                    if not p.get('matched_event'):
                        continue
                    ev_label = p.get('matched_event')
                    ev = events_map.get(ev_label)
                    if not ev:
                        continue
                    if ev.get('type') != 'in':
                        continue
                    try:
                        p_dt = p.get('dt_norm') or p.get('dt')
                        ev_dt = ev.get('dt')
                    except Exception:
                        continue
                    cutoff = ev_dt
                    for perm in day_obj.get('permits', []):
                        try:
                            ps = perm.get('start_time')
                            pe = perm.get('end_time')
                            if ps and pe:
                                if ps <= ev_dt.time() <= pe:
                                    cutoff = datetime.combine(cur_date, pe)
                                    break
                        except Exception:
                            continue

                    diff = (p_dt - cutoff).total_seconds()
                    if diff >= 60:
                        minutos_atraso += int(diff // 60)

        if inconsistencias > 0 or dias_sin_marcar > 0 or minutos_atraso > 0:
            unit_name = inst.employee.area.name if inst.employee and inst.employee.area else 'Sin Unidad'
            results_by_unit.setdefault(unit_name, []).append({
                'employee': inst.employee,
                'inconsistencias': inconsistencias,
                'dias_sin_marcar': dias_sin_marcar,
                'minutos_atraso': minutos_atraso,
            })

    # Ordenar las unidades alfabéticamente y convertir a lista para el template
    grouped_results = sorted(list(results_by_unit.items()), key=lambda x: x[0].lower())

    template = get_template('biometric/reports/pdf_attendance_by_unit.html')
    html = template.render({
        'unit': unit,
        'year': year,
        'month': month,
        'grouped_results': grouped_results,
        'today': datetime.now(),
    })

    filename = f"Reporte_Dep_{unit.name.replace(' ', '_')}_{year}_{month}.pdf"
    if HTML:
        base_url = request.build_absolute_uri('/')
        pdf = HTML(string=html, base_url=base_url).write_pdf(
            stylesheets=[CSS(string='@page { size: A4; margin: 0.8cm }')])
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    else:
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        from xhtml2pdf import pisa
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse('Error al generar PDF', status=500)
        return response