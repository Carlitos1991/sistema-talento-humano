# apps/function_manual/views.py
from django.db import models, transaction
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import permission_required
import json

from institution.models import AdministrativeUnit
from .models import Competency, JobProfile, ManualCatalog, OccupationalMatrix, ManualCatalogItem, ValuationNode
from .forms import ManualCatalogForm, ManualCatalogItemForm


# ============================================================================
# 1. MIXINS Y AUXILIARES
# ============================================================================

class JobProfileMixin:
    """Mixin centralizado para proveer catálogos a cualquier vista del manual"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        def get_items(catalog_code):
            return list(ManualCatalogItem.objects.filter(
                catalog__code=catalog_code, is_active=True
            ).values('id', 'name'))

        matrix_data = list(OccupationalMatrix.objects.all().values(
            'id', 'occupational_group', 'grade', 'remuneration',
            'required_role_id', 'minimum_instruction_id',
            'minimum_experience_months', 'required_decision_id',
            'required_impact_id', 'complexity_level_id'
        ))

        catalogs_dict = {
            "instruction": get_items('INSTRUCTION_LEVELS'),
            "decisions": get_items('DECISION_LEVELS'),
            "impact": get_items('IMPACT_LEVELS'),
            "roles": get_items('JOB_ROLES'),
            "verbs": get_items('ACTION_VERBS'),
            "frequency": get_items('FREQUENCY'),
            "complexity": get_items('COMPLEXITY_LEVELS'),
            "matrix": matrix_data
        }
        context['catalogs_json'] = json.dumps(catalogs_dict, cls=DjangoJSONEncoder)
        return context


def get_manual_catalog_stats():
    """Retorna estadísticas de catálogos"""
    total = ManualCatalog.objects.count()
    active = ManualCatalog.objects.filter(is_active=True).count()
    return {'total': total, 'active': active, 'inactive': total - active}


# ============================================================================
# 2. VISTAS DE PERFILES (WIZARD)
# ============================================================================

class JobProfileListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = JobProfile
    permission_required = "function_manual.view_jobprofile"
    context_object_name = "profiles"

    def get_template_names(self):
        if self.request.GET.get('partial'):
            return ["function_manual/partials/partial_function_manual_table.html"]
        return ["function_manual/function_manual_list.html"]

    def get_queryset(self):
        queryset = JobProfile.objects.select_related('administrative_unit', 'occupational_classification').filter(
            is_active=True)
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                models.Q(specific_job_title__icontains=query) | models.Q(administrative_unit__name__icontains=query))
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.request.GET.get('partial'):
            qs = self.get_queryset()
            context['stats_total'] = qs.count()
            context['stats_classified'] = qs.filter(occupational_classification__isnull=False).count()
            context['stats_pending'] = qs.filter(occupational_classification__isnull=True).count()
            context['stats_active'] = qs.filter(is_active=True).count()
        return context


class JobProfileCreateView(LoginRequiredMixin, PermissionRequiredMixin, JobProfileMixin, CreateView):
    model = JobProfile
    template_name = "function_manual/function_manual_form.html"
    permission_required = "function_manual.add_jobprofile"
    fields = ['position_code', 'specific_job_title', 'administrative_unit', 'referential_employee']
    success_url = reverse_lazy('function_manual:profile_list')


class JobProfileUpdateView(LoginRequiredMixin, PermissionRequiredMixin, JobProfileMixin, UpdateView):
    model = JobProfile
    template_name = "function_manual/function_manual_form.html"
    permission_required = "function_manual.change_jobprofile"
    fields = ['position_code', 'specific_job_title', 'administrative_unit', 'referential_employee']
    success_url = reverse_lazy('function_manual:profile_list')


# ============================================================================
# 3. ESCALAS / ESTRUCTURA DE VALORACIÓN (DRILL-DOWN)
# ============================================================================

class OccupationalMatrixListView(LoginRequiredMixin, PermissionRequiredMixin, JobProfileMixin, ListView):
    model = ValuationNode
    template_name = "function_manual/valuation_structure_list.html"
    context_object_name = "nodes"
    permission_required = "function_manual.view_valuationnode"

    def get_queryset(self):
        parent_id = self.request.GET.get('parent')
        return ValuationNode.objects.filter(parent_id=parent_id,
                                            is_active=True) if parent_id else ValuationNode.objects.filter(
            parent__isnull=True, is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent_id = self.request.GET.get('parent')
        context['parent_name'] = "Raíz"
        context['next_level_name'] = "Rol de Puesto"
        context['next_node_type'] = "ROLE"
        context['breadcrumbs'] = []

        if parent_id:
            parent = get_object_or_404(ValuationNode, pk=parent_id)
            context['parent_node'] = parent
            context['parent_name'] = parent.catalog_item.name if parent.catalog_item else parent.name_extra
            bc = []
            curr = parent
            while curr:
                bc.insert(0, curr)
                curr = curr.parent
            context['breadcrumbs'] = bc
            mapping = {'ROLE': ('INSTRUCTION', 'Instrucción'), 'INSTRUCTION': ('EXPERIENCE', 'Experiencia'),
                       'EXPERIENCE': ('DECISION', 'Decisión'), 'DECISION': ('IMPACT', 'Impacto'),
                       'IMPACT': ('COMPLEXITY', 'Complejidad'), 'COMPLEXITY': ('RESULT', 'Resultado Final')}
            res = mapping.get(parent.node_type, ('RESULT', 'Resultado'))
            context['next_node_type'], context['next_level_name'] = res
        return context


# ============================================================================
# 4. GESTIÓN DE CATÁLOGOS (La sección que faltaba)
# ============================================================================

class ManualCatalogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ManualCatalog
    template_name = 'function_manual/catalog_list.html'
    context_object_name = 'catalogs'
    permission_required = 'function_manual.view_manualcatalog'

    def get_queryset(self):
        query = self.request.GET.get('q')
        qs = ManualCatalog.objects.all()
        if query: qs = qs.filter(name__icontains=query)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ManualCatalogForm()
        stats = get_manual_catalog_stats()
        context.update(
            {'stats_total': stats['total'], 'stats_active': stats['active'], 'stats_inactive': stats['inactive']})
        return context


class ManualCatalogCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ManualCatalog
    form_class = ManualCatalogForm

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            catalog = form.save()
            return JsonResponse({'success': True, 'message': 'Catálogo creado.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ManualCatalogUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ManualCatalog
    form_class = ManualCatalogForm

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Catálogo actualizado.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


def manual_catalog_detail_json(request, pk):
    c = get_object_or_404(ManualCatalog, pk=pk)
    return JsonResponse({'success': True,
                         'data': {'id': c.id, 'name': c.name, 'code': c.code, 'description': c.description or '',
                                  'is_active': c.is_active}})


@require_POST
def manual_catalog_toggle_status(request, pk):
    c = get_object_or_404(ManualCatalog, pk=pk)
    c.toggle_status()
    return JsonResponse({'success': True})


# --- VISTAS DE ITEMS DE CATÁLOGO ---

class ManualCatalogItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ManualCatalogItem
    form_class = ManualCatalogItemForm

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            item = form.save(commit=False)
            item.catalog_id = request.POST.get('catalog_id')
            item.save()
            return JsonResponse({'success': True, 'message': 'Item creado.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ManualCatalogItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ManualCatalogItem
    form_class = ManualCatalogItemForm

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Item actualizado.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


def manual_catalog_item_list_json(request, catalog_id):
    items = ManualCatalogItem.objects.filter(catalog_id=catalog_id).values('id', 'code', 'name', 'description', 'order',
                                                                           'is_active')
    return JsonResponse({'success': True, 'data': list(items)})


def manual_catalog_item_detail_json(request, pk):
    i = get_object_or_404(ManualCatalogItem, pk=pk)
    return JsonResponse({'success': True,
                         'data': {'id': i.id, 'catalog_id': i.catalog_id, 'name': i.name, 'code': i.code,
                                  'description': i.description or '', 'order': i.order}})


@require_POST
def manual_catalog_item_toggle_status(request, pk):
    i = get_object_or_404(ManualCatalogItem, pk=pk)
    i.toggle_status()
    return JsonResponse({'success': True})


# ============================================================================
# 5. COMPETENCIAS
# ============================================================================

class CompetencyListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Competency
    template_name = "function_manual/competency_list.html"
    permission_required = "function_manual.view_competency"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        complexity_items = ManualCatalogItem.objects.filter(catalog__code='COMPLEXITY_LEVELS', is_active=True).order_by(
            'order')
        context['complexity_levels'] = json.dumps(
            [{'id': item.id, 'name': item.name, 'code': item.code} for item in complexity_items])
        qs = Competency.objects.filter(is_active=True)
        context.update({'stats_total': qs.count(), 'stats_behavioral': qs.filter(type='BEHAVIORAL').count(),
                        'stats_technical': qs.filter(type='TECHNICAL').count(),
                        'stats_transversal': qs.filter(type='TRANSVERSAL').count()})
        return context


class CompetencyTablePartialView(CompetencyListView):
    template_name = "function_manual/partials/partial_competency_table.html"


class CompetencyCreateView(LoginRequiredMixin, View):
    def post(self, request):
        data = json.loads(request.body)
        Competency.objects.create(name=data.get('name'), type=data.get('type'), definition=data.get('definition'),
                                  suggested_level_id=data.get('suggested_level') or None)
        return JsonResponse({'status': 'success', 'message': 'Competencia creada.'})


class CompetencyUpdateView(LoginRequiredMixin, UpdateView):
    model = Competency

    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        c = self.get_object()
        c.name, c.type, c.definition, c.suggested_level_id = data.get('name'), data.get('type'), data.get(
            'definition'), data.get('suggested_level') or None
        c.save()
        return JsonResponse({'status': 'success', 'message': 'Competencia actualizada.'})


class CompetencyToggleStatusView(LoginRequiredMixin, View):
    def post(self, request, pk):
        c = get_object_or_404(Competency, pk=pk)
        c.is_active = not c.is_active
        c.save()
        return JsonResponse({'status': 'success'})


# ============================================================================
# 6. APIs DE SOPORTE (Navegación y Autocompletado)
# ============================================================================

class ApiValuationNodesView(View):
    def get(self, request):
        parent_id = request.GET.get('parent')
        filters = {'parent_id': parent_id} if parent_id else {'parent__isnull': True}
        nodes = ValuationNode.objects.filter(**filters, is_active=True)
        data = [{'id': n.id, 'name': n.catalog_item.name if n.catalog_item else n.name_extra, 'type': n.node_type,
                 'classification': {'group': n.occupational_classification.occupational_group,
                                    'rmu': n.occupational_classification.remuneration,
                                    'grade': n.occupational_classification.grade} if n.node_type == 'RESULT' else None}
                for n in nodes]
        return JsonResponse(data, safe=False)


class ValuationNodeDetailApi(View):
    def get(self, request, pk):
        n = get_object_or_404(ValuationNode, pk=pk)
        return JsonResponse(
            {'id': n.id, 'node_type': n.node_type, 'catalog_item_id': n.catalog_item_id, 'name_extra': n.name_extra,
             'occupational_classification_id': n.occupational_classification_id})


class ValuationNodeSaveApi(LoginRequiredMixin, View):
    def post(self, request):
        data = json.loads(request.body)
        node_id = data.get('id')
        node = get_object_or_404(ValuationNode, pk=node_id) if node_id else ValuationNode(
            parent_id=data.get('parent_id'), node_type=data.get('node_type'))
        node.catalog_item_id, node.name_extra, node.occupational_classification_id = data.get(
            'catalog_item_id') or None, data.get('name_extra'), data.get('occupational_classification_id') or None
        node.save()
        return JsonResponse({'success': True})


class ApiNextPositionCodeView(View):
    def get(self, request, unit_id):
        unit = get_object_or_404(AdministrativeUnit, pk=unit_id)
        last = JobProfile.objects.filter(administrative_unit_id=unit_id).order_by('position_code').last()
        next_num = (int(last.position_code.split('.')[-1]) + 1) if (last and last.position_code) else 1
        return JsonResponse({'next_code': f"{unit.code or '0'}.{next_num:02d}"})


class ApiUnitChildrenView(View):
    def get(self, request, parent_id=None):
        filters = {'parent_id': parent_id} if parent_id else {'parent__isnull': True}
        units = AdministrativeUnit.objects.filter(**filters, is_active=True).values('id', 'name', 'code')
        return JsonResponse(list(units), safe=False)