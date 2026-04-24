import calendar
import json
import logging
from datetime import datetime, date, timedelta
import base64
import mimetypes
import os
from decimal import Decimal
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string, get_template
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import ListView, TemplateView, View
from django.db import transaction, models
from django.shortcuts import get_object_or_404

from xhtml2pdf import pisa
from .models import BiometricDevice, BiometricLoad, AttendanceRegistry, BiometricCommand, OfflineAttendanceRegistry
from .utils import test_connection, BiometricConnection
from permitrequest.models import PermitRequest
from schedule.models import ScheduleObservation
from core.models import SystemConfiguration
from django.db.models import Q
from employee.models import InstitutionalData
from employee.models import Employee

logger = logging.getLogger(__name__)


def _resolve_user_employee(user):
    if not user or not user.is_authenticated:
        return None

    user_person = getattr(user, 'person', None)
    if user_person:
        user_employee = getattr(user_person, 'employee_profile', None)
        if user_employee:
            return user_employee

    if user.email:
        user_employee = Employee.objects.filter(
            person__email__iexact=user.email,
            is_active=True,
        ).first()
        if user_employee:
            return user_employee

    if user.username:
        return Employee.objects.filter(
            person__document_number=user.username,
            is_active=True,
        ).first()

    return None


@method_decorator(login_required, name='dispatch')
@method_decorator(ensure_csrf_cookie, name='dispatch')
class OfflineAttendanceView(TemplateView):
    template_name = 'biometric/offline_attendance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = _resolve_user_employee(self.request.user)
        inst_data = InstitutionalData.objects.filter(employee=employee).select_related('employee__person').first() if employee else None
        context.update({
            'offline_employee': employee,
            'offline_institutional_data': inst_data,
            'offline_employee_name': employee.person.full_name if employee and getattr(employee, 'person', None) else self.request.user.get_full_name() or self.request.user.username,
            'offline_employee_document': employee.person.document_number if employee and getattr(employee, 'person', None) else '',
            'offline_sync_url': '/biometric/offline-attendance/sync/',
            'offline_manifest_url': '/biometric/offline-attendance/manifest.webmanifest',
            'offline_sw_url': '/biometric/offline-attendance/sw.js',
            'offline_page_url': '/biometric/offline-attendance/',
            'offline_access_url': '/biometric/offline-access/',
            'offline_can_sync': bool(employee),
        })
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(ensure_csrf_cookie, name='dispatch')
class OfflineAttendanceAccessView(TemplateView):
    template_name = 'biometric/offline_access.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = _resolve_user_employee(self.request.user)
        context.update({
            'offline_employee': employee,
            'offline_employee_name': employee.person.full_name if employee and getattr(employee, 'person', None) else self.request.user.get_full_name() or self.request.user.username,
            'offline_employee_document': employee.person.document_number if employee and getattr(employee, 'person', None) else '',
            'offline_redirect_url': '/biometric/offline-attendance/',
            'offline_can_sync': bool(employee),
        })
        return context


@login_required
@require_GET
def offline_attendance_manifest(request):
    return JsonResponse({
        'name': 'Asistencia Offline',
        'short_name': 'Asistencia',
        'start_url': '/biometric/offline-attendance/',
        'scope': '/biometric/offline-attendance/',
        'display': 'standalone',
        'background_color': '#08121f',
        'theme_color': '#0f766e',
        'description': 'Marcación de ingreso y salida con GPS y sincronización offline.',
        'icons': [
            {
                'src': '/static/img/logo.png',
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'any maskable'
            },
            {
                'src': '/static/img/favicon.png',
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'any maskable'
            }
        ]
    })


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
        return JsonResponse({'status': 'error', 'message': 'No se pudo identificar al empleado asociado al usuario.'}, status=400)

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

    # Query de marcaciones (Naive)
    punches = AttendanceRegistry.objects.filter(
        employee_id=emp_id, registry_date__year=year, registry_date__month=month
    ).order_by('registry_date')

    punches_map = {}
    for p in punches:
        day = p.registry_date.day
        if day not in punches_map: punches_map[day] = []
        punches_map[day].append({
            'time': p.registry_date.strftime('%H:%M'),
            'device': p.biometric_load.biometric.name[:10]
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
            permits_map[d].append({'type': pr.permit_type.name, 'note': pr.response_note or ''})
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
        months_es = ["", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE",
                     "NOVIEMBRE", "DICIEMBRE"]
        disp = f"{disp_date.day} de {months_es[disp_date.month].capitalize()} de {disp_date.year} - {obs.name.upper()}"
        observations_list.append(disp)

    # Añadir flags de permisos y feriados por día (facilita el template)
    for widx, week in enumerate(calendar_data):
        for didx, day_obj in enumerate(week):
            d = day_obj.get('day')
            if not d:
                day_obj['is_holiday'] = False
                day_obj['holi_name'] = ''
                day_obj['permits'] = []
            else:
                day_obj['is_holiday'] = d in holidays_map
                day_obj['holi_name'] = holidays_map.get(d, '')
                day_obj['permits'] = permits_map.get(d, [])
                # Etiqueta de fecha: 01 de enero
                try:
                    months_es_local = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
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
    html = template.render({
        'emp': inst_data.employee,
        'month_name': months_es[month],
        'year': year,
        'calendar': calendar_data,
        'today': datetime.now(),
        'permits_map': permits_map,
        'holidays_map': holidays_map,
        'configuration': config,
        'letterhead_data': letterhead_data,
        'observations_list': observations_list,
    })
    response = HttpResponse(content_type='application/pdf')
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

    response = HttpResponse(content_type='application/pdf')
    filename = f"Reporte_Especifico_{institutional_info.employee.person.document_number}_{start_str}_al_{end_str}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    pisa_status = pisa.CreatePDF(html_content, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response
