import logging
from datetime import datetime

from django.views.generic import ListView, View
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import BiometricDevice, BiometricLoad, AttendanceRegistry
from employee.models import InstitutionalData

logger = logging.getLogger(__name__)


class BiometricListView(ListView):
    model = BiometricDevice
    template_name = 'biometric/biometric_list.html'
    context_object_name = 'devices'
    paginate_by = 10

    def get_queryset(self):
        qs = BiometricDevice.objects.all()

        # 1. Filtro por búsqueda de texto
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(ip_address__icontains=q)

        # 2. Filtro por Estado (Nuevo)
        status = self.request.GET.get('status')
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)

        return qs

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()

            # 1. Renderizar la tabla parcial
            html = render_to_string('biometric/partials/partial_biometric_table.html', {
                'devices': self.object_list
            }, request=request)
            total_qs = BiometricDevice.objects.all()
            # 2. Calcular estadísticas reales
            total = self.object_list.count()
            active = self.object_list.filter(is_active=True).count()
            inactive = total - active

            # 3. Devolver HTML + Estadísticas + Paginación
            return JsonResponse({
                'html': html,
                'stats': {
                    'total': total_qs.count(),
                    'active': total_qs.filter(is_active=True).count(),
                    'inactive': total_qs.filter(is_active=False).count()
                },
                'pagination': {
                    'label': f"Mostrando 1-{self.object_list.count()} de {self.object_list.count()}" if self.object_list.count() > 0 else "Mostrando 0-0 de 0"
                }
            })
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        context['stats_total'] = qs.count()
        context['stats_active'] = qs.filter(is_active=True).count()
        context['stats_inactive'] = qs.filter(is_active=False).count()
        return context


@csrf_exempt
def create_biometric_ajax(request):
    """Crea o actualiza biométricos vía AJAX"""
    if request.method == 'POST':
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

            if device_id:
                BiometricDevice.objects.filter(id=device_id).update(**data)
                msg = "Dispositivo actualizado."
            else:
                data['created_by'] = request.user
                BiometricDevice.objects.create(**data)
                msg = "Dispositivo registrado."

            return JsonResponse({'status': 'success', 'message': msg})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return None


@method_decorator(csrf_exempt, name='dispatch')
class ADMSReceiverView(View):
    """Receptor Push Mode de ZKTeco"""

    def get(self, request):
        sn = request.GET.get('SN')
        return HttpResponse("OK\nC:99:ATTLOG", content_type="text/plain")

    def post(self, request):
        sn = request.GET.get('SN')
        table = request.GET.get('table')

        if table == 'ATTLOG':
            datos_crudos = request.body.decode('utf-8').strip()
            if not datos_crudos:
                return HttpResponse("OK", content_type="text/plain")

            try:
                # 1. Identificar el dispositivo
                device = BiometricDevice.objects.get(serial_number=sn, is_active=True)

                with transaction.atomic():
                    # 2. Crear un registro de carga para este lote
                    batch_load = BiometricLoad.objects.create(
                        biometric=device,
                        load_type="ADMS_PUSH",
                        reason=f"Recepción automática SN: {sn}"
                    )

                    count = 0
                    for linea in datos_crudos.splitlines():
                        campos = linea.split('\t')
                        if len(campos) < 2: continue

                        user_pin = campos[0].strip()
                        timestamp_str = campos[1].strip()

                        # 3. Buscar al empleado por su biometric_id (InstitutionalData)
                        # Usamos select_related para no saturar la base de datos
                        inst_data = InstitutionalData.objects.select_related('employee').filter(
                            biometric_id=user_pin
                        ).first()

                        if inst_data:
                            # 4. Evitar duplicados exactos (Mismo empleado, misma hora)
                            reg_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                            exists = AttendanceRegistry.objects.filter(
                                employee=inst_data.employee,
                                registry_date=reg_time
                            ).exists()

                            if not exists:
                                AttendanceRegistry.objects.create(
                                    employee=inst_data.employee,
                                    biometric_load=batch_load,
                                    employee_id_bio=user_pin,
                                    registry_date=reg_time
                                )
                                count += 1

                    # 5. Actualizar total de la carga
                    batch_load.num_records = count
                    batch_load.save()

                logger.info(f"ADMS: {count} marcaciones procesadas de {sn}")
                return HttpResponse("OK", content_type="text/plain")

            except BiometricDevice.DoesNotExist:
                logger.error(f"ADMS Error: Dispositivo SN {sn} no registrado.")
                return HttpResponse("OK", content_type="text/plain")

        return HttpResponse("OK", content_type="text/plain")


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
        }
    })
