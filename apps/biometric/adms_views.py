import logging
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from .models import BiometricDevice, AttendanceRegistry, BiometricLoad
from employee.models import InstitutionalData

logger = logging.getLogger(__name__)


@csrf_exempt
def adms_receive_attendance(request):
    """
    Main endpoint for ZKTeco ADMS (Push Mode).
    GET: Handshake / POST: Real-time data reception.
    """
    # 1. Identify the device by Serial Number
    sn = request.GET.get('SN') or request.GET.get('sn')
    table = request.GET.get('table')

    # HANDSHAKE (Handing GET request from the device)
    if request.method == 'GET':
        logger.info(f"[ADMS] Handshake GET - Device SN: {sn}")
        return HttpResponse("OK\nC:99:ATTLOG", content_type="text/plain")

    # DATA RECEPTION (Handling POST request from the device)
    try:
        # Ignore system tables that don't contain attendance
        if table in ['options', 'INFO', 'OPERLOG']:
            return HttpResponse("OK", content_type="text/plain")

        if table == 'ATTLOG':
            raw_body = request.body.decode('utf-8').strip()
            if not raw_body:
                return HttpResponse("OK", content_type="text/plain")

            # Check if device exists and is active
            device = BiometricDevice.objects.filter(serial_number=sn, is_active=True).first()
            if not device:
                logger.warning(f"[ADMS] Received data from unregistered SN: {sn}")
                return HttpResponse("OK", content_type="text/plain")

            lines = raw_body.splitlines()
            saved_count = 0

            with transaction.atomic():
                # Create a load record for this batch
                load_log = BiometricLoad.objects.create(
                    biometric=device,
                    load_type="ADMS_PUSH",
                    reason=f"Automatic Push from SN: {sn}"
                )

                for line in lines:
                    # ZKTeco sends fields separated by tabs
                    fields = line.strip().split('\t')
                    if len(fields) < 2:
                        continue

                    # Extract data: User ID and Timestamp
                    user_id_bio = fields[0].strip().lstrip('0')
                    time_str = fields[1].strip()  # Format: YYYY-MM-DD HH:MM:SS

                    # FIND EMPLOYEE
                    employee_info = InstitutionalData.objects.filter(biometric_id=user_id_bio).first()

                    if employee_info:
                        try:
                            # --- FIX FOR AUDIT / DATABASE TIME OFFSET ---
                            # 1. Convert string to datetime object
                            parsed_date = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')

                            # 2. FORCE NAIVE: Remove any timezone metadata (tzinfo=None)
                            # This ensures PostgreSQL saves EXACTLY what's in the clock
                            clean_registry_date = parsed_date.replace(tzinfo=None)

                            # 3. Avoid exact duplicates
                            if not AttendanceRegistry.objects.filter(
                                    employee=employee_info.employee,
                                    registry_date=clean_registry_date
                            ).exists():
                                AttendanceRegistry.objects.create(
                                    employee=employee_info.employee,
                                    biometric_load=load_log,
                                    employee_id_bio=user_id_bio,
                                    registry_date=clean_registry_date
                                )
                                saved_count += 1
                        except ValueError:
                            continue

                # Finalize load log
                load_log.num_records = saved_count
                load_log.save()

            logger.info(f"[ADMS] SN:{sn} - Saved {saved_count} records.")
            return HttpResponse("OK", content_type="text/plain")

        return HttpResponse("OK", content_type="text/plain")

    except Exception as e:
        logger.error(f"[ADMS] Critical Error: {str(e)}", exc_info=True)
        return HttpResponse("Error", status=500)


@csrf_exempt
def adms_stats(request):
    """Real-time stats for the ADMS Dashboard."""
    from datetime import date
    today_date = date.today()
    return JsonResponse({
        'success': True,
        'stats': {
            'records_today': AttendanceRegistry.objects.filter(registry_date__date=today_date).count(),
            'active_devices': BiometricDevice.objects.filter(is_active=True).count(),
        }
    })