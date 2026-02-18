# apps/biometric/adms_views.py

import logging
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from .models import BiometricDevice, AttendanceRegistry, BiometricLoad
from employee.models import InstitutionalData
from .models import BiometricCommand

logger = logging.getLogger(__name__)


@csrf_exempt
def iclock_registry(request):
    sn = request.GET.get('SN') or request.GET.get('sn')
    return HttpResponse(f"RegistryCode={sn}", content_type="text/plain")


@csrf_exempt
def iclock_getrequest(request):
    sn = request.GET.get('SN') or request.GET.get('sn')

    device = BiometricDevice.objects.filter(serial_number=sn, is_active=True).first()
    if not device:
        return HttpResponse("OK", content_type="text/plain")

    # Buscar el comando más antiguo pendiente (FIFO)
    cmd = BiometricCommand.objects.filter(device=device, status='PENDING').order_by('created_at').first()

    if cmd:
        # Formato ADMS: C:ID_UNICO:COMANDO
        response_str = f"C:{cmd.id}:{cmd.command}"

        # Marcar como enviado para no enviarlo doble
        cmd.status = 'SENT'
        cmd.save()

        print(f"📤 [ADMS] Enviando comando a {sn}: {cmd.command}")
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
            print(f"📩 [ADMS] Respuesta de comando: {raw_body}")

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
                    print(f"✅ Comando {cmd_id} ejecutado con código {ret_val}")

        except Exception as e:
            print(f"❌ Error procesando devicecmd: {e}")

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

            if (table == 'ATTLOG' or table == 'rtlog') and raw_body:

                device = BiometricDevice.objects.filter(serial_number=sn, is_active=True).first()
                if not device:
                    print(f"⚠️ Dispositivo desconocido: {sn}")
                    return HttpResponse("OK", content_type="text/plain")

                lines = raw_body.splitlines()
                saved_count = 0

                with transaction.atomic():
                    load_log = BiometricLoad.objects.create(
                        biometric=device,
                        load_type="REAL_TIME" if table == 'rtlog' else "ADMS_SYNC",
                        reason=f"Push automático ({table})"
                    )

                    for line in lines:
                        if not line.strip(): continue

                        user_pin = None
                        time_str = None

                        # --- DETECCIÓN DE FORMATO ---

                        # 1. FORMATO NUEVO (Clave=Valor)
                        # Ejemplo: time=2026-02-13... pin=2...
                        if 'pin=' in line and 'time=' in line:
                            data_dict = {}
                            # Separar por tabuladores y luego por signo igual
                            pairs = line.split('\t')
                            for p in pairs:
                                if '=' in p:
                                    key, val = p.split('=', 1)
                                    data_dict[key] = val

                            user_pin = data_dict.get('pin')
                            time_str = data_dict.get('time')

                        # 2. FORMATO ANTIGUO (Solo valores)
                        # Ejemplo: 2 \t 2026-02-13... \t 0 \t 1
                        else:
                            parts = line.split('\t')
                            if len(parts) >= 2:
                                user_pin = parts[0]
                                time_str = parts[1]

                        # --- PROCESAMIENTO ---

                        if user_pin and time_str:
                            # Limpieza de ID (quitar ceros a la izquierda y espacios)
                            clean_pin = user_pin.strip().lstrip('0')

                            # DEBUG VISUAL
                            print(f"📥 Marcación: ID Reloj='{user_pin}' -> ID BD='{clean_pin}' | Hora={time_str}")

                            # Buscar empleado
                            inst_data = InstitutionalData.objects.filter(biometric_id=clean_pin).first()

                            if inst_data:
                                try:
                                    reg_date = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')

                                    if not AttendanceRegistry.objects.filter(
                                            employee=inst_data.employee,
                                            registry_date=reg_date
                                    ).exists():
                                        AttendanceRegistry.objects.create(
                                            employee=inst_data.employee,
                                            biometric_load=load_log,
                                            employee_id_bio=clean_pin,
                                            registry_date=reg_date
                                        )
                                        saved_count += 1
                                        print(f"   ✅ GUARDADO: {inst_data.employee}")
                                    else:
                                        print(f"   ⚠️ Duplicado ignorado.")
                                except ValueError:
                                    print(f"   ❌ Error formato fecha: {time_str}")
                            else:
                                print(f"   ❌ Empleado no encontrado en BD (ID: {clean_pin})")

                    load_log.num_records = saved_count
                    load_log.save()

            return HttpResponse("OK", content_type="text/plain")

        except Exception as e:
            print(f"❌ Error ADMS: {e}")
            return HttpResponse("OK", content_type="text/plain")

    return HttpResponse("OK", content_type="text/plain")


@csrf_exempt
def adms_stats(request):
    return JsonResponse({'success': True})
