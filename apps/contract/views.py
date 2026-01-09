from django.db import transaction
from django.views.generic import ListView, View
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from institution.models import AdministrativeUnit
from schedule.models import Schedule
from .models import LaborRegime, ContractType, ManagementPeriod
from .forms import LaborRegimeForm, ContractTypeForm


class LaborRegimeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LaborRegime
    template_name = 'contract/labor_regime_list.html'
    permission_required = 'contract.view_laborregime'
    context_object_name = 'regimes'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = LaborRegime.objects.all()
        context['stats_total'] = qs.count()
        context['stats_active'] = qs.filter(is_active=True).count()
        context['stats_inactive'] = qs.filter(is_active=False).count()
        return context


class LaborRegimeTablePartialView(LoginRequiredMixin, View):
    def get(self, request):
        name = request.GET.get('name', '')
        is_active = request.GET.get('is_active', '')
        queryset = LaborRegime.objects.all().order_by('code')

        if name: queryset = queryset.filter(name__icontains=name)
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)

        all_qs = LaborRegime.objects.all()
        stats = {
            'total': all_qs.count(),
            'active': all_qs.filter(is_active=True).count(),
            'inactive': all_qs.filter(is_active=False).count(),
        }

        html = render_to_string('contract/partials/partial_labor_regime_table.html', {
            'regimes': queryset
        }, request=request)
        return JsonResponse({'table_html': html, 'stats': stats})


class LaborRegimeDetailAPIView(LoginRequiredMixin, View):
    def get(self, request, pk):
        regime = get_object_or_404(LaborRegime, pk=pk)
        return JsonResponse({
            'success': True,
            'regime': {
                'id': regime.id,
                'code': regime.code,
                'name': regime.name,
                'description': regime.description or '',
                'is_active': regime.is_active
            }
        })


class ContractTypeListView(LoginRequiredMixin, View):
    """
    Retorna los tipos de contrato vinculados a un régimen laboral específico.
    """

    def get(self, request, regime_id):
        regime = get_object_or_404(LaborRegime, pk=regime_id)
        types = regime.contract_types.all().order_by('name')

        data = [{
            'id': t.id,
            'code': t.code,
            'name': t.name,
            'category': t.contract_type_category,
            'category_display': t.get_contract_type_category_display(),
            'is_active': t.is_active
        } for t in types]

        return JsonResponse({'success': True, 'contract_types': data})


class ContractTypeCreateView(LoginRequiredMixin, View):
    """
    Crea un nuevo tipo de contrato vinculado a un régimen.
    Diseñado para ser llamado vía AJAX desde SweetAlert2.
    """

    def post(self, request):
        form = ContractTypeForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    instance = form.save(commit=False)
                    instance.created_by = request.user
                    instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Modalidad laboral registrada con éxito.'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error interno: {str(e)}'
                }, status=500)

        # Enviamos los errores de validación (ej: código duplicado)
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class ContractTypeToggleStatusView(LoginRequiredMixin, View):
    """
    Alterna el estado activo/inactivo de una modalidad.
    """

    def post(self, request, pk):
        instance = get_object_or_404(ContractType, pk=pk)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save()
        return JsonResponse({
            'success': True,
            'message': f'Estado de "{instance.name}" actualizado.'
        })


class LaborRegimeCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Procesa la creación de un nuevo régimen laboral."""
    permission_required = 'contract.add_laborregime'

    def post(self, request):
        form = LaborRegimeForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    instance = form.save(commit=False)
                    instance.created_by = request.user  # Auditoría BaseModel
                    instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Régimen Laboral creado exitosamente.'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error al guardar: {str(e)}'
                }, status=500)

        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class LaborRegimeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Procesa la actualización de un régimen existente."""
    permission_required = 'contract.change_laborregime'

    def post(self, request, pk):
        instance = get_object_or_404(LaborRegime, pk=pk)
        form = LaborRegimeForm(request.POST, instance=instance)

        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_instance = form.save(commit=False)
                    updated_instance.updated_by = request.user  # Auditoría BaseModel
                    updated_instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Régimen Laboral actualizado correctamente.'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error al actualizar: {str(e)}'
                }, status=500)

        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class LaborRegimeToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Alterna el estado is_active (Alta/Baja) de un régimen."""
    permission_required = 'contract.change_laborregime'

    def post(self, request, pk):
        instance = get_object_or_404(LaborRegime, pk=pk)
        # Cambiamos el estado (Toggle logic)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save()

        message = "Régimen activado (Alta)" if instance.is_active else "Régimen desactivado (Baja)"
        return JsonResponse({
            'success': True,
            'message': message
        })


class ContractTypeUpdateView(LoginRequiredMixin, View):
    """
    Actualiza un tipo de contrato existente.
    """

    def post(self, request, pk):
        instance = get_object_or_404(ContractType, pk=pk)
        form = ContractTypeForm(request.POST, instance=instance)
        if form.is_valid():
            try:
                with transaction.atomic():
                    instance = form.save(commit=False)
                    instance.updated_by = request.user
                    instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Modalidad actualizada correctamente.'
                })
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)}, status=500)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ManagementPeriodListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ManagementPeriod
    template_name = 'contract/management_period_list.html'
    permission_required = 'contract.view_managementperiod'
    context_object_name = 'periods'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = ManagementPeriod.objects.filter(is_active=True)

        # Estadísticas dinámicas según el video
        context['total_active'] = qs.count()
        # Ejemplo de conteo por régimen (ajustar códigos según tu base)
        context['count_losep'] = qs.filter(contract_type__labor_regime__code='LOSEP').count()
        context['count_ct'] = qs.filter(contract_type__labor_regime__code='CT').count()

        # Para el modal (necesitamos cargar regímenes y sus tipos)
        context['regimes'] = LaborRegime.objects.filter(is_active=True).prefetch_related('contract_types')
        context['schedules'] = Schedule.objects.filter(is_active=True)
        context['units'] = AdministrativeUnit.objects.filter(is_active=True)

        return context


class ValidateEmployeeAPIView(LoginRequiredMixin, View):
    """Busca un empleado y verifica si tiene contratos activos."""

    def get(self, request, doc_number):
        from apps.employee.models import Employee
        try:
            employee = Employee.objects.select_related('person').get(
                person__document_number=doc_number, is_active=True
            )
            # Verificar si ya tiene un periodo activo
            has_active = ManagementPeriod.objects.filter(employee=employee, is_active=True).exists()

            return JsonResponse({
                'success': True,
                'has_active_contract': has_active,
                'employee': {
                    'id': employee.id,
                    'full_name': employee.person.full_name,
                    'photo': employee.person.photo.url if employee.person.photo else None,
                }
            })
        except Employee.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Empleado no encontrado o inactivo.'})
