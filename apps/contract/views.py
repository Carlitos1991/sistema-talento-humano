from django.db import transaction
from django.views.generic import ListView, View
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from .models import LaborRegime, ContractType
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
