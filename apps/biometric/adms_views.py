# apps/biometric/adms_views.py
import json
import logging
import time
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from .models import BiometricDevice, AttendanceRegistry, BiometricLoad
from employee.models import InstitutionalData
from .models import BiometricCommand

logger = logging.getLogger(__name__)

_HEARTBEAT_LOG_WINDOW_SECONDS = 60
_last_heartbeat_log_by_sn = {}


def _should_log_heartbeat(sn):
    now = time.time()
    key = sn or 'UNKNOWN'
    last = _last_heartbeat_log_by_sn.get(key, 0)
    if now - last >= _HEARTBEAT_LOG_WINDOW_SECONDS:
        _last_heartbeat_log_by_sn[key] = now
        return True
    return False


@csrf_exempt
def iclock_registry(request):
    sn = request.GET.get('SN') or request.GET.get('sn')
    return HttpResponse(f"RegistryCode={sn}", content_type="text/plain")


@csrf_exempt
def iclock_getrequest(request):
    sn = request.GET.get('SN') or request.GET.get('sn')
    if _should_log_heartbeat(sn):
        logger.info("[ADMS] Heartbeat SN='%s'", sn)

    device = BiometricDevice.objects.filter(serial_number=sn, is_active=True).first()
    if not device:
        logger.warning("[ADMS] Rechazado SN='%s' (no existe o inactivo)", sn)
        return HttpResponse("OK", content_type="text/plain")

    # Buscar el comando más antiguo pendiente (FIFO)
    cmd = BiometricCommand.objects.filter(device=device, status='PENDING').order_by('created_at').first()

    if cmd:
        # Formato ADMS: C:ID_UNICO:COMANDO
        response_str = f"C:{cmd.id}:{cmd.command}"

        # Marcar como enviado para no enviarlo doble
        cmd.status = 'SENT'
        cmd.save()

        logger.info("[ADMS] Enviando comando a SN='%s': %s", sn, cmd.command)
        return HttpResponse(response_str, content_type="text/plain")

    return HttpResponse("OK", content_type="text/plain")


@csrf_exempt
def iclock_devicecmd(request):
    """
    Endpoint donde el dispositivo reporta el resultado de un comando.
    El reloj envía POST con: ID=123&Return=0&CMD=DATA...
    """
    if request.method == 'POST':
        try:
            # Los datos suelen venir en el body como texto plano: ID=1&Return=0
            raw_body = request.body.decode('utf-8', errors='ignore')
            logger.info("[ADMS] Respuesta de comando: %s", raw_body)

            # Parsear respuesta
            data = {}
            parts = raw_body.split('&')
            for p in parts:
                if '=' in p:
                    k, v = p.split('=', 1)
                    data[k] = v

            cmd_id = data.get('ID')
            ret_val = data.get('Return')  # 0 = Éxito, otros valores = Error

            if cmd_id:
                cmd = BiometricCommand.objects.filter(id=cmd_id).first()
                if cmd:
                    cmd.status = 'SUCCESS' if ret_val == '0' else 'ERROR'
                    cmd.return_value = ret_val
                    cmd.execution_time = datetime.now()
                    cmd.save()
                    logger.info("[ADMS] Comando %s ejecutado con codigo %s", cmd_id, ret_val)

        except Exception as e:
            logger.error("[ADMS] Error procesando devicecmd: %s", e)

    return HttpResponse("OK", content_type="text/plain")


@csrf_exempt
def iclock_ping(request):
    return HttpResponse("OK", content_type="text/plain")


@csrf_exempt
def adms_receive_attendance(request):
    sn = request.GET.get('SN') or request.GET.get('sn')
    table = request.GET.get('table')

    if request.method == 'GET':
        return HttpResponse("OK\nC:99:ATTLOG", content_type="text/plain")

    if request.method == 'POST':
        try:
            if table == 'rtstate':
                return HttpResponse("OK", content_type="text/plain")

            raw_body = request.body.decode('utf-8', errors='ignore').strip()
            if (table in ['ATTLOG', 'rtlog']) and raw_body:
                device = BiometricDevice.objects.filter(serial_number=sn, is_active=True).first()
                if not device:
                    return HttpResponse("OK", content_type="text/plain")

                lines = raw_body.splitlines()

                # 1. Pre-cargar empleados en un diccionario para evitar queries en el loop
                # Solo traemos los que tienen biometric_id
                emps_map = {
                    e.biometric_id: e
                    for e in InstitutionalData.objects.filter(biometric_id__isnull=False).select_related('employee')
                }

                new_registries = []
                load_log = BiometricLoad.objects.create(
                    biometric=device,
                    load_type="REAL_TIME" if table == 'rtlog' else "ADMS_SYNC",
                    reason=f"Push automático optimizado ({table})"
                )

                for line in lines:
                    if not line.strip(): continue
                    user_pin, time_str = None, None

                    # Parseo de formatos (Nuevo y Antiguo)
                    if 'pin=' in line and 'time=' in line:
                        pairs = {p.split('=')[0]: p.split('=')[1] for p in line.split('\t') if '=' in p}
                        user_pin, time_str = pairs.get('pin'), pairs.get('time')
                    else:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            user_pin, time_str = parts[0], parts[1]

                    if user_pin and time_str:
                        clean_pin = user_pin.strip().lstrip('0')
                        inst_data = emps_map.get(clean_pin)

                        if inst_data:
                            try:
                                reg_date = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                                # Agregamos a la lista para procesar en lote
                                new_registries.append(AttendanceRegistry(
                                    employee=inst_data.employee,
                                    biometric_load=load_log,
                                    employee_id_bio=clean_pin,
                                    registry_date=reg_date
                                ))
                            except ValueError:
                                continue

                # 2. Inserción masiva ignorando duplicados (Eficiencia máxima)
                if new_registries:
                    # ignore_conflicts=True evita que el proceso falle si una marcación ya existe
                    created_objs = AttendanceRegistry.objects.bulk_create(
                        new_registries,
                        ignore_conflicts=True
                    )
                    load_log.num_records = len(created_objs)
                    load_log.save()

            return HttpResponse("OK", content_type="text/plain")
        except Exception as e:
            logger.error(f"❌ Error crítico ADMS: {e}")
            return HttpResponse("OK", content_type="text/plain")

    return HttpResponse("OK", content_type="text/plain")


@csrf_exempt
def adms_stats(request):
    return JsonResponse({'success': True})


@csrf_exempt
def adms_download_command(request, pk):
    if request.method == 'POST':
        try:
            device = get_object_or_404(BiometricDevice, pk=pk)
            data = json.loads(request.body)
            start_time = data.get('start_time')
            end_time = data.get('end_time')

            # Creamos el comando ADMS para que el reloj lo lea en su próximo Heartbeat
            # Formato: DATA QUERY ATTLOG StartTime=... EndTime=...
            command_text = f"DATA QUERY ATTLOG StartTime={start_time} EndTime={end_time}"

            BiometricCommand.objects.create(
                device=device,
                command=command_text,
                status='PENDING'
            )

            return JsonResponse({
                'status': 'success',
                'message': f'Comando de descarga enviado al equipo {device.name}. Se procesará en el próximo latido (Heartbeat).'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
