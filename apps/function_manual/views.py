from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.template.loader import render_to_string
from .models import Competency, JobProfile, ManualCatalog, OccupationalMatrix

class CompetencyListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Competency
    template_name = "function_manual/competency_list.html"
    permission_required = "function_manual.view_competency"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Obtenemos los items del catálogo de niveles de complejidad
        from .models import ManualCatalogItem
        context['complexity_levels'] = ManualCatalogItem.objects.filter(
            catalog__code='COMPLEXITY_LEVELS',
            is_active=True
        ).order_by('order')
        return context

    def get_queryset(self):
        return Competency.objects.all().order_by('type', 'name')

class CompetencyTablePartialView(CompetencyListView):
    """ Retorna solo el fragmento HTML de la tabla para actualización dinámica """
    template_name = "function_manual/partials/partial_competency_table.html"


class CompetencyCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Competency
    fields = ['name', 'type', 'definition', 'suggested_level']
    permission_required = "function_manual.add_competency"

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Competencia creada correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class CompetencyUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Competency
    fields = ['name', 'type', 'definition', 'suggested_level']
    permission_required = "function_manual.change_competency"

    def form_valid(self, form):
        form.save()
        return JsonResponse({'status': 'success', 'message': 'Competencia actualizada correctamente.'})


class CompetencyToggleStatusView(LoginRequiredMixin, View):
    """ Alterna el estado activo/inactivo vía AJAX """

    def post(self, request, pk):
        competency = Competency.objects.get(pk=pk)
        competency.is_active = not competency.is_active
        competency.save()
        return JsonResponse({'status': 'success'})


class JobProfileListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = JobProfile
    template_name = "function_manual/profile_list.html"
    permission_required = "function_manual.view_jobprofile"


class ManualCatalogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ManualCatalog
    template_name = "function_manual/catalog_list.html"
    permission_required = "function_manual.view_manualcatalog"


class OccupationalMatrixListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = OccupationalMatrix
    template_name = "function_manual/matrix_list.html"
    permission_required = "function_manual.view_occupationalmatrix"
