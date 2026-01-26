import calendar
import logging
from datetime import datetime, timezone

from django.utils.timezone import make_aware
from django.views.generic import ListView, View
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string, get_template
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, models
from django.shortcuts import get_object_or_404

from xhtml2pdf import pisa
from .models import BiometricDevice, BiometricLoad, AttendanceRegistry
from .utils import test_connection, BiometricConnection
from employee.models import InstitutionalData

logger = logging.getLogger(__name__)


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
            'updated_by': request.user
        }
        if device_id and device_id != 'null':
            BiometricDevice.objects.filter(id=device_id).update(**data)
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
                    clean_date = rec.timestamp.replace(tzinfo=None)

                    if not AttendanceRegistry.objects.filter(employee=inst.employee, registry_date=clean_date).exists():
                        AttendanceRegistry.objects.create(
                            employee=inst.employee,
                            biometric_load=load_entry,
                            employee_id_bio=user_id,
                            registry_date=clean_date
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
            'id': device.id, 'name': device.name, 'ip_address': device.ip_address,
            'port': device.port, 'location': device.location, 'is_active': device.is_active,
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
    server_time = timezone.localtime()
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
        target_time = timezone.localtime().replace(tzinfo=None)  # pyzk prefiere naive local
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
    template = get_template('biometric/reports/pdf_attendance_calendar.html')
    html = template.render({
        'emp': inst_data.employee, 'month_name': months_es[month], 'year': year,
        'calendar': calendar_data, 'today': datetime.now()  # Naive
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
    paginate_by = 15

    def get_queryset(self):
        # Solo empleados con ID biométrico
        qs = InstitutionalData.objects.select_related('employee__person').filter(
            biometric_id__isnull=False
        ).exclude(biometric_id='')

        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                models.Q(employee__person__first_name__icontains=q) |
                models.Q(employee__person__last_name__icontains=q) |
                models.Q(employee__person__document_number__icontains=q)
            )
        return qs

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            html = render_to_string('biometric/partials/partial_report_employee_table.html', {
                'employees': self.object_list
            }, request=request)
            return JsonResponse({'html': html})
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

    template = get_template('biometric/modals/modal_report_specific.html')
    html_content = template.render({
        'emp': institutional_info.employee,
        'start_date': start_date,
        'end_date': end_date,
        'punches': punches,
        'today': datetime.now(),
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f"Reporte_Específico_{institutional_info.biometric_id}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    pisa_status = pisa.CreatePDF(html_content, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response