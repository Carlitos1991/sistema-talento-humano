import logging
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.conf import settings

from .models import BiometricDevice, AttendanceRegistry, BiometricLoad
from employee.models import InstitutionalData

logger = logging.getLogger(__name__)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')


@csrf_exempt
def adms_receive_attendance(request):
    client_ip = get_client_ip(request)
    sn = request.GET.get('SN') or request.GET.get('sn')
    table_name = request.GET.get('table')

    if request.method == 'GET':
        logger.info(f"[ADMS] 🤝 Handshake GET desde {client_ip} - SN: {sn}")
        return HttpResponse("OK\nC:99:ATTLOG", content_type="text/plain")

    # POST processing
    try:
        # --- AJUSTE 1: Manejar tablas de sistema ---
        if table_name in ['options', 'INFO', 'OPERLOG']:
            return HttpResponse("OK", content_type="text/plain")

        if table_name == 'ATTLOG':
            datos_crudos = request.body.decode('utf-8').strip()
            if not datos_crudos:
                return HttpResponse("OK", content_type="text/plain")

            try:
                device = BiometricDevice.objects.get(serial_number=sn, is_active=True)
            except BiometricDevice.DoesNotExist:
                logger.warning(f"[ADMS] ⚠️ Equipo SN:{sn} no registrado.")
                return HttpResponse("OK", content_type="text/plain")

            lineas = datos_crudos.splitlines()
            count_saved = 0

            with transaction.atomic():
                batch_load = BiometricLoad.objects.create(
                    biometric=device,
                    load_type="ADMS_PUSH",
                    reason=f"Carga automática via Push Protocol",
                )

                for linea in lineas:
                    campos = linea.strip().split('\t')
                    if len(campos) < 2: continue

                    # --- AJUSTE 3: Normalizar PIN (Quitar ceros a la izquierda) ---
                    user_pin = campos[0].strip().lstrip('0')
                    timestamp_str = campos[1].strip()

                    inst_data = InstitutionalData.objects.select_related('employee').filter(
                        biometric_id=user_pin
                    ).first()

                    if not inst_data:
                        continue

                    # --- AJUSTE 2: Hacer la fecha aware de la zona horaria ---
                    try:
                        naive_date = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        # Usamos el timezone definido en settings.py (America/Guayaquil)
                        registry_date = make_aware(naive_date)
                    except (ValueError, pytz.exceptions.UnknownTimeZoneError):
                        continue

                    exists = AttendanceRegistry.objects.filter(
                        employee=inst_data.employee,
                        registry_date=registry_date
                    ).exists()

                    if not exists:
                        AttendanceRegistry.objects.create(
                            employee=inst_data.employee,
                            biometric_load=batch_load,
                            employee_id_bio=user_pin,
                            registry_date=registry_date
                        )
                        count_saved += 1

                batch_load.num_records = count_saved
                batch_load.save()

            return HttpResponse("OK", content_type="text/plain")

        return HttpResponse("OK", content_type="text/plain")

    except Exception as e:
        logger.error(f"[ADMS] ❌ Error crítico: {str(e)}", exc_info=True)
        return HttpResponse("Error", status=500)


@csrf_exempt
def adms_stats(request):
    """Estadísticas rápidas para el dashboard de ADMS"""
    from datetime import date
    today = date.today()

    return JsonResponse({
        'success': True,
        'stats': {
            'records_today': AttendanceRegistry.objects.filter(created_at__date=today).count(),
            'active_devices': BiometricDevice.objects.filter(is_active=True).count(),
            'last_sync': BiometricLoad.objects.order_by('-created_at').first().created_at.strftime(
                '%Y-%m-%d %H:%M:%S') if BiometricLoad.objects.exists() else 'N/A'
        }
    })
