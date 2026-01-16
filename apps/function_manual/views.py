from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from .models import Competency, JobProfile, ManualCatalog, OccupationalMatrix, ManualCatalogItem
from .forms import ManualCatalogForm, ManualCatalogItemForm


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_manual_catalog_stats():
    """Retorna estadísticas de catálogos del manual"""
    total = ManualCatalog.objects.count()
    active = ManualCatalog.objects.filter(is_active=True).count()
    inactive = total - active
    return {'total': total, 'active': active, 'inactive': inactive}


# ============================================================================
# COMPETENCIAS
# ============================================================================

class CompetencyListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Competency
    template_name = "function_manual/competency_list.html"
    permission_required = "function_manual.view_competency"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Obtenemos los items del catálogo de niveles de complejidad
        from .models import ManualCatalogItem
        import json
        
        complexity_items = ManualCatalogItem.objects.filter(
            catalog__code='COMPLEXITY_LEVELS',
            is_active=True
        ).order_by('order')
        
        # Serializar para Vue
        context['complexity_levels'] = json.dumps([
            {'id': item.id, 'name': item.name, 'code': item.code}
            for item in complexity_items
        ])
        
        # Estadísticas de competencias por tipo
        from django.db.models import Count, Q
        competencies = Competency.objects.filter(is_active=True)
        context['stats_total'] = competencies.count()
        context['stats_behavioral'] = competencies.filter(type='BEHAVIORAL').count()
        context['stats_technical'] = competencies.filter(type='TECHNICAL').count()
        context['stats_transversal'] = competencies.filter(type='TRANSVERSAL').count()
        
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

    def post(self, request, *args, **kwargs):
        import json
        try:
            data = json.loads(request.body)
            competency = Competency.objects.create(
                name=data.get('name'),
                type=data.get('type'),
                definition=data.get('definition'),
                suggested_level_id=data.get('suggested_level') if data.get('suggested_level') else None
            )
            return JsonResponse({'status': 'success', 'message': 'Competencia creada correctamente.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'errors': str(e)}, status=400)


class CompetencyUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Competency
    fields = ['name', 'type', 'definition', 'suggested_level']
    permission_required = "function_manual.change_competency"

    def post(self, request, *args, **kwargs):
        import json
        try:
            data = json.loads(request.body)
            competency = self.get_object()
            competency.name = data.get('name')
            competency.type = data.get('type')
            competency.definition = data.get('definition')
            competency.suggested_level_id = data.get('suggested_level') if data.get('suggested_level') else None
            competency.save()
            return JsonResponse({'status': 'success', 'message': 'Competencia actualizada correctamente.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'errors': str(e)}, status=400)


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


# ============================================================================
# CATÁLOGOS DEL MANUAL DE FUNCIONES
# ============================================================================

class ManualCatalogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ManualCatalog
    template_name = 'function_manual/catalog_list.html'
    context_object_name = 'catalogs'
    permission_required = 'function_manual.view_manualcatalog'

    def get_queryset(self):
        query = self.request.GET.get('q')
        qs = ManualCatalog.objects.all()
        if query:
            qs = qs.filter(name__icontains=query)
        return qs.order_by('-created_at')[:200]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ManualCatalogForm()
        stats = get_manual_catalog_stats()
        context['stats_total'] = stats['total']
        context['stats_active'] = stats['active']
        context['stats_inactive'] = stats['inactive']
        return context


class ManualCatalogCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ManualCatalog
    form_class = ManualCatalogForm
    permission_required = 'function_manual.add_manualcatalog'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            catalog = form.save()
            stats = get_manual_catalog_stats()
            return JsonResponse({
                'success': True,
                'message': 'Catálogo creado correctamente.',
                'data': {'id': catalog.id, 'name': catalog.name, 'new_stats': stats}
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


def manual_catalog_detail_json(request, pk):
    """Retorna los datos de un catálogo específico para editar"""
    catalog = get_object_or_404(ManualCatalog, pk=pk)
    return JsonResponse({
        'success': True,
        'data': {
            'id': catalog.id,
            'name': catalog.name,
            'code': catalog.code,
            'description': catalog.description or '',
            'is_active': catalog.is_active
        }
    })


class ManualCatalogUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ManualCatalog
    form_class = ManualCatalogForm
    permission_required = 'function_manual.change_manualcatalog'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            catalog = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Catálogo actualizado correctamente.',
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


@require_POST
@permission_required('function_manual.change_manualcatalog', raise_exception=True)
def manual_catalog_toggle_status(request, pk):
    """Alterna el estado (Activo/Inactivo) de un catálogo"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'No autorizado'}, status=403)

    catalog = get_object_or_404(ManualCatalog, pk=pk)
    catalog.toggle_status()

    status_label = "activado" if catalog.is_active else "desactivado"
    stats = get_manual_catalog_stats()
    return JsonResponse({
        'success': True,
        'message': f'El catálogo "{catalog.name}" ha sido {status_label} correctamente.',
        'new_stats': stats
    })


# ============================================================================
# ITEMS DE CATÁLOGO DEL MANUAL
# ============================================================================

class ManualCatalogItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ManualCatalogItem
    form_class = ManualCatalogItemForm
    permission_required = 'function_manual.add_manualcatalogitem'

    def post(self, request, *args, **kwargs):
        catalog_id = request.POST.get('catalog_id')
        if not catalog_id:
            return JsonResponse({'success': False, 'message': 'Falta el ID del catálogo.'}, status=400)
        
        catalog = get_object_or_404(ManualCatalog, pk=catalog_id)
        form = self.get_form()
        
        if form.is_valid():
            code = form.cleaned_data.get('code')
            if ManualCatalogItem.objects.filter(catalog=catalog, code=code).exists():
                return JsonResponse({
                    'success': False,
                    'errors': {'code': ['Ya existe un item con este código en este catálogo.']}
                }, status=400)

            try:
                item = form.save(commit=False)
                item.catalog = catalog
                item.save()

                return JsonResponse({
                    'success': True,
                    'message': f'Item creado en "{catalog.name}".',
                    'data': {'id': item.id, 'name': item.name}
                })
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)}, status=500)
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)


def manual_catalog_item_list_json(request, catalog_id):
    """Devuelve los items de un catálogo específico"""
    items = ManualCatalogItem.objects.filter(catalog_id=catalog_id).order_by('order', 'code')
    data = []
    for item in items:
        data.append({
            'id': item.id,
            'code': item.code,
            'name': item.name,
            'description': item.description or '',
            'order': item.order,
            'is_active': item.is_active
        })
    return JsonResponse({'success': True, 'data': data})


def manual_catalog_item_detail_json(request, pk):
    """Para cargar el formulario de edición de item"""
    item = get_object_or_404(ManualCatalogItem, pk=pk)
    return JsonResponse({
        'success': True,
        'data': {
            'id': item.id,
            'catalog_id': item.catalog_id,
            'name': item.name,
            'code': item.code,
            'description': item.description or '',
            'order': item.order
        }
    })


class ManualCatalogItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ManualCatalogItem
    form_class = ManualCatalogItemForm
    permission_required = 'function_manual.change_manualcatalogitem'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            item = form.save()
            return JsonResponse({'success': True, 'message': 'Item actualizado correctamente.'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@require_POST
@permission_required('function_manual.change_manualcatalogitem', raise_exception=True)
def manual_catalog_item_toggle_status(request, pk):
    """Activar/Inactivar Item"""
    item = get_object_or_404(ManualCatalogItem, pk=pk)
    item.toggle_status()
    return JsonResponse({
        'success': True,
        'message': f'Item "{item.name}" {"activado" if item.is_active else "desactivado"}.',
        'is_active': item.is_active
    })
