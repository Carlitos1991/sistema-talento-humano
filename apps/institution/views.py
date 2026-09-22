"""
Módulo de Vistas para la Gestión Institucional y Estructura Organizacional (SIGETH).
Maneja operaciones CRUD, navegación jerárquica (drill-down), asignación de jefaturas,
gestión atómica de entregables y exportación a Excel.
"""

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.cache import cache
from django.db.models import Q, F, Count, Case, When, IntegerField, Max
from django.db.models.functions import Length, Cast
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View

from employee.models import Employee
from .forms import (
    AdministrativeUnitForm,
    OrganizationalLevelForm,
    DeliverableForm,
    OrganigramForm,
    AssignBossForm
)
from .models import (
    AdministrativeUnit,
    OrganizationalLevel,
    Deliverable,
    InstitutionOrganigram
)


# ==============================================================================
# UTILIDADES Y HELPERS DE CONSULTA
# ==============================================================================

def get_unit_stats():
    """Retorna un resumen numérico del estado global de las unidades administrativas."""
    return {
        'total': AdministrativeUnit.objects.count(),
        'active': AdministrativeUnit.objects.filter(is_active=True).count(),
        'inactive': AdministrativeUnit.objects.filter(is_active=False).count(),
    }


def get_all_descendant_unit_ids(unit):
    """
    Obtiene recursivamente los IDs de una unidad y todas sus dependencias subordinadas.
    Incluye un conjunto de control (visited) para evitar bucles infinitos por ciclos.
    """
    descendants = [unit.pk]
    visited = {unit.pk}
    queue = list(AdministrativeUnit.objects.filter(parent=unit, is_active=True).values_list('id', flat=True))

    while queue:
        current_id = queue.pop(0)
        if current_id not in visited:
            visited.add(current_id)
            descendants.append(current_id)
            children_ids = AdministrativeUnit.objects.filter(
                parent_id=current_id, is_active=True
            ).values_list('id', flat=True)
            queue.extend(children_ids)

    return descendants


def _get_reassigned_unit_names_for_boss(boss, exclude_unit_id=None):
    """Retorna los nombres de las unidades donde el funcionario ya figuraba como jefe."""
    if not boss:
        return []
    qs = AdministrativeUnit.objects.filter(boss=boss)
    if exclude_unit_id:
        qs = qs.exclude(pk=exclude_unit_id)
    return list(qs.order_by('name').values_list('name', flat=True))


# ==============================================================================
# 1. GESTIÓN DE UNIDADES ADMINISTRATIVAS (CRUD Y DRILL-DOWN)
# ==============================================================================

class UnitListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Vista principal de la estructura organizacional.
    Soporta filtrado jerárquico por nivel, búsqueda por texto y renderizado AJAX parcial.
    """
    model = AdministrativeUnit
    template_name = 'institution/unit_list.html'
    context_object_name = 'units'
    permission_required = 'institution.view_administrativeunit'

    def get_queryset(self):
        qs = AdministrativeUnit.objects.all().select_related(
            'level', 'parent', 'boss__person'
        ).annotate(
            code_len=Length('code'),
            children_count=Count('children')
        ).order_by('level__level_order', 'code_len', 'code', 'name')

        q = self.request.GET.get('q')
        show_inactive = self.request.GET.get('show_inactive')

        qs = qs.filter(level__level_order=1)
        qs = qs.filter(is_active=(show_inactive == 'true' if show_inactive == 'true' else True))

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AdministrativeUnitForm()
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            html = render_to_string('institution/partials/partial_unit_table.html', context, request=request)
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)


class UnitCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Creación modal de unidades administrativas vía AJAX."""
    model = AdministrativeUnit
    form_class = AdministrativeUnitForm
    template_name = 'institution/modals/modal_unit_form.html'
    permission_required = 'institution.add_administrativeunit'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            selected_boss = form.cleaned_data.get('boss')
            reassigned_from = _get_reassigned_unit_names_for_boss(selected_boss)

            unit = form.save(commit=False)
            unit.is_active = True
            unit.save()

            message = 'Unidad creada correctamente.'
            if reassigned_from:
                message += f" El jefe fue reasignado automáticamente desde: {', '.join(reassigned_from)}."

            return JsonResponse({
                'success': True,
                'message': message,
                'new_stats': get_unit_stats()
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class UnitDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Vista integral de detalle de una dependencia.
    Muestra personal directo, estadísticas consolidadas de subdependencias y entregables.
    """
    model = AdministrativeUnit
    template_name = 'institution/institution_unit_detail.html'
    context_object_name = 'unit'
    permission_required = 'institution.view_administrativeunit'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_unit = self.object

        # Subdependencias directas
        children = AdministrativeUnit.objects.filter(
            parent=current_unit, is_active=True
        ).order_by('code', 'name')

        # Nómina directa de la unidad actual
        employees = Employee.objects.filter(
            area_id=current_unit.pk, is_active=True
        ).exclude(
            employment_status__name__icontains='EX '
        ).select_related('person').prefetch_related(
            'current_budget_line__position_item'
        )

        # Cálculo agregado consolidado de personal (unidad actual + descendientes)
        all_unit_ids = get_all_descendant_unit_ids(current_unit)
        all_employees = Employee.objects.filter(
            area_id__in=all_unit_ids, is_active=True
        ).exclude(employment_status__name__icontains='EX ')

        propios_cond = Q(institutional_data__original_dependency=current_unit.pk) | \
                       Q(institutional_data__original_dependency__isnull=True, area_id=current_unit.pk)
        reubicados_cond = Q(institutional_data__original_dependency__isnull=False) & \
                          ~Q(institutional_data__original_dependency=F('area'))

        stats = all_employees.aggregate(
            total=Count('id'),
            empleados=Count(Case(When(employment_status__code='EMPLEADO', then=1), output_field=IntegerField())),
            trabajadores=Count(Case(When(employment_status__code='TRABAJADOR', then=1), output_field=IntegerField())),
            contratados=Count(Case(When(employment_status__code='CONTRATADO', then=1), output_field=IntegerField())),
            propios=Count(Case(When(propios_cond, then=1), output_field=IntegerField())),
            reubicados=Count(Case(When(reubicados_cond, then=1), output_field=IntegerField())),
        )

        context['unit_stats'] = {
            'total': stats['total'] or 0,
            'empleado': stats['empleados'] or 0,
            'trabajador': stats['trabajadores'] or 0,
            'contratado': stats['contratados'] or 0,
            'propios': stats['propios'] or 0,
            'reubicados': stats['reubicados'] or 0,
        }
        context['deliverables'] = Deliverable.objects.filter(
            unit=current_unit, is_active=True
        ).order_by('-created_at')
        context['children'] = children
        context['employees'] = employees
        context['form'] = AdministrativeUnitForm()
        return context


class UnitDetailJsonView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Endpoint JSON con la información base de una unidad para alimentar modales de edición."""
    permission_required = 'institution.view_administrativeunit'

    def get(self, request, pk):
        unit = get_object_or_404(AdministrativeUnit, pk=pk)
        boss_data = None
        if unit.boss:
            position = ''
            cb = unit.boss.current_budget_line.first()
            if cb and getattr(cb, 'position_item', None):
                position = cb.position_item.name

            boss_data = {
                'id': unit.boss.id,
                'text': f"{unit.boss.person.first_name} {unit.boss.person.last_name}",
                'person_id': unit.boss.person.id,
                'photo_url': unit.boss.person.photo.url if getattr(unit.boss.person, 'photo', None) else '',
                'position': position,
            }

        data = {
            'name': unit.name,
            'level': unit.level_id,
            'parent': unit.parent_id,
            'parent_name': unit.parent.name if unit.parent else None,
            'parent_level': unit.parent.level_id if unit.parent else None,
            'boss': unit.boss_id,
            'boss_data': boss_data,
            'code': unit.code,
            'address': unit.address or '',
            'phone': unit.phone or '',
            'is_active': unit.is_active,
        }
        return JsonResponse({'success': True, 'data': data})


class UnitUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Actualización modal de dependencias administrativas vía AJAX."""
    model = AdministrativeUnit
    form_class = AdministrativeUnitForm
    template_name = 'institution/modals/modal_unit_form.html'
    permission_required = 'institution.change_administrativeunit'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        original_boss = self.object.boss
        form = self.get_form()

        if form.is_valid():
            selected_boss = form.cleaned_data.get('boss') or original_boss
            reassigned_from = _get_reassigned_unit_names_for_boss(selected_boss, exclude_unit_id=self.object.id)

            unit = form.save()

            message = 'Unidad actualizada correctamente.'
            if reassigned_from:
                message += f" El jefe fue reasignado automáticamente desde: {', '.join(reassigned_from)}."

            return JsonResponse({'success': True, 'message': message})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class UnitChangeParentView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Procesa el cambio de unidad padre en la jerarquía (reubicación organizacional)."""
    permission_required = 'institution.change_administrativeunit'

    def post(self, request, pk):
        unit = get_object_or_404(AdministrativeUnit, pk=pk)
        new_parent_id = request.POST.get('parent')

        try:
            if new_parent_id and str(new_parent_id).isdigit():
                new_parent = get_object_or_404(AdministrativeUnit, pk=int(new_parent_id), is_active=True)

                if new_parent.id == unit.id:
                    return JsonResponse({
                        'success': False,
                        'message': 'No puedes asignar la unidad como su propio padre.'
                    }, status=400)

                if new_parent.level.level_order >= unit.level.level_order:
                    return JsonResponse({
                        'success': False,
                        'message': 'El padre debe pertenecer a un nivel jerárquico superior.'
                    }, status=400)

                unit.parent = new_parent
            else:
                unit.parent = None

            unit.save()
            return JsonResponse({
                'success': True,
                'message': f'Unidad "{unit.name}" reubicada correctamente.'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error al reubicar: {str(e)}'}, status=400)


@method_decorator(require_POST, name='dispatch')
class UnitToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Activa o desactiva lógicamente una unidad administrativa."""
    permission_required = 'institution.change_administrativeunit'

    def post(self, request, pk):
        unit = get_object_or_404(AdministrativeUnit, pk=pk)
        unit.is_active = not unit.is_active
        unit.save()
        cache.delete('level_stats')

        status_label = "activada" if unit.is_active else "desactivada"
        return JsonResponse({
            'success': True,
            'message': f'La unidad "{unit.name}" ha sido {status_label}.',
        })


@login_required
def unit_partial_table(request):
    """Renderiza exclusivamente las filas de la tabla de unidades para recargas AJAX."""
    show_inactive = request.GET.get('show_inactive')
    parent_id = request.GET.get('parent_id')
    q = request.GET.get('q')

    qs = AdministrativeUnit.objects.all().select_related(
        'level', 'parent', 'boss__person'
    ).annotate(
        code_len=Length('code'),
        children_count=Count('children')
    ).order_by('level__level_order', 'code_len', 'code', 'name')

    qs = qs.filter(is_active=(show_inactive != 'true'))

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    elif parent_id:
        qs = qs.filter(parent_id=parent_id)
    else:
        qs = qs.filter(level__level_order=1)

    html = render_to_string(
        'institution/partials/partial_unit_table.html',
        {'units': qs},
        request=request
    )
    return HttpResponse(html)


class UnitAssignBossView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Asigna o transfiere el jefe inmediato responsable de una dependencia."""
    model = AdministrativeUnit
    form_class = AssignBossForm
    template_name = 'institution/modals/modal_assign_boss.html'
    permission_required = 'institution.change_administrativeunit'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()

        if form.is_valid():
            selected_boss = form.cleaned_data.get('boss')
            reassigned_from = _get_reassigned_unit_names_for_boss(selected_boss, exclude_unit_id=self.object.id)

            unit = form.save()
            message = f'Jefe asignado correctamente a {unit.name}.'
            if reassigned_from:
                message += f" Reasignado automáticamente desde: {', '.join(reassigned_from)}."

            return JsonResponse({'success': True, 'message': message})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


# ==============================================================================
# 2. GESTIÓN DE NIVELES JERÁRQUICOS
# ==============================================================================

def get_level_stats():
    """Retorna los niveles organizacionales con su conteo de dependencias activas (en caché)."""
    cached = cache.get('level_stats')
    if cached:
        return cached

    levels = OrganizationalLevel.objects.filter(is_active=True).order_by('level_order')[:5]
    colors = ['color-one', 'color-two', 'color-three', 'color-four', 'color-five']
    icons = ['fa-globe', 'fa-building', 'fa-briefcase', 'fa-users', 'fa-user-tag']

    stats = [{
        'id': 'total',
        'name': 'Total',
        'order': 0,
        'count': AdministrativeUnit.objects.filter(is_active=True).count(),
        'color': 'color-zero',
        'icon': 'fa-layer-group'
    }]

    for i, lvl in enumerate(levels):
        stats.append({
            'id': lvl.id,
            'name': lvl.name,
            'order': lvl.level_order,
            'count': AdministrativeUnit.objects.filter(level=lvl, is_active=True).count(),
            'color': colors[i] if i < len(colors) else 'color-one',
            'icon': icons[i] if i < len(icons) else 'fa-sitemap'
        })

    result = {'level_stats': stats}
    cache.set('level_stats', result, timeout=300)
    return result


class LevelListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Catálogo y administración de estratos jerárquicos institucionales."""
    model = OrganizationalLevel
    template_name = 'institution/level_list.html'
    context_object_name = 'levels'
    permission_required = 'institution.view_organizationallevel'

    def get_queryset(self):
        qs = OrganizationalLevel.objects.all().order_by('level_order')
        q = self.request.GET.get('q')
        show_inactive = self.request.GET.get('show_inactive')

        if q:
            qs = qs.filter(name__icontains=q)
        if show_inactive == 'true':
            qs = qs.filter(is_active=False)
        else:
            qs = qs.filter(is_active=True)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = OrganizationalLevelForm()
        context['total'] = OrganizationalLevel.objects.count()
        context['active'] = OrganizationalLevel.objects.filter(is_active=True).count()
        context['inactive'] = OrganizationalLevel.objects.filter(is_active=False).count()
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            html = render_to_string('institution/partials/partial_level_table.html', context, request=request)
            return JsonResponse({
                'html': html,
                'stats': {
                    'total': context['total'],
                    'active': context['active'],
                    'inactive': context['inactive']
                }
            })
        return super().get(request, *args, **kwargs)


class LevelCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Creación de un nuevo nivel jerárquico vía modal AJAX."""
    model = OrganizationalLevel
    form_class = OrganizationalLevelForm
    template_name = 'institution/modals/modal_level_form.html'
    permission_required = 'institution.add_organizationallevel'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            form.save()
            cache.delete('level_stats')
            return JsonResponse({
                'success': True,
                'message': 'Nivel jerárquico creado.',
                'new_stats': get_level_stats()
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class LevelDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Información en formato JSON de un nivel jerárquico."""
    permission_required = 'institution.view_organizationallevel'

    def get(self, request, pk):
        lvl = get_object_or_404(OrganizationalLevel, pk=pk)
        return JsonResponse({'success': True, 'data': {'name': lvl.name, 'level_order': lvl.level_order}})


class LevelUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Actualización de nivel jerárquico vía modal AJAX."""
    model = OrganizationalLevel
    form_class = OrganizationalLevelForm
    template_name = 'institution/modals/modal_level_form.html'
    permission_required = 'institution.change_organizationallevel'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            form.save()
            cache.delete('level_stats')
            return JsonResponse({'success': True, 'message': 'Nivel actualizado correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@require_POST
@permission_required('institution.change_organizationallevel', raise_exception=True)
def level_toggle_status(request, pk):
    """Activa o desactiva un nivel jerárquico previniendo colisiones de orden."""
    lvl = get_object_or_404(OrganizationalLevel, pk=pk)
    next_status = not lvl.is_active

    if next_status:
        conflict = OrganizationalLevel.objects.filter(
            level_order=lvl.level_order, is_active=True
        ).exclude(pk=pk).exists()
        if conflict:
            return JsonResponse({
                'success': False,
                'message': f"Conflicto: Ya existe un nivel jerárquico #{lvl.level_order} activo. Desactive el anterior primero."
            }, status=400)

    lvl.is_active = next_status
    lvl.save()
    cache.delete('level_stats')

    status_label = "activado" if lvl.is_active else "desactivado"
    return JsonResponse({
        'success': True,
        'message': f'Nivel "{lvl.name}" {status_label}.',
        'new_stats': get_level_stats()
    })


@login_required
def level_partial_table(request):
    """Renderiza exclusivamente las filas de niveles para recarga AJAX."""
    show_inactive = request.GET.get('show_inactive')
    levels = OrganizationalLevel.objects.filter(is_active=(show_inactive != 'true')).order_by('level_order')
    html = render_to_string('institution/partials/partial_level_table.html', {'levels': levels}, request=request)
    return HttpResponse(html)


# ==============================================================================
# 3. GESTIÓN DE ENTREGABLES (DELIVERABLES)
# ==============================================================================

class DeliverableCreateUpdateView(LoginRequiredMixin, View):
    """Crea o edita un entregable mediante modal AJAX."""
    template_name = 'institution/modals/modal_deliverable_form.html'

    def get(self, request, unit_id, pk=None):
        instance = get_object_or_404(Deliverable, pk=pk, unit_id=unit_id) if pk else None
        form = DeliverableForm(instance=instance)
        return render(request, self.template_name, {
            'form': form,
            'unit_id': unit_id,
            'object': instance
        })

    def post(self, request, unit_id, pk=None):
        instance = get_object_or_404(Deliverable, pk=pk, unit_id=unit_id) if pk else None
        form = DeliverableForm(request.POST, instance=instance)

        if form.is_valid():
            deliverable = form.save(commit=False)
            deliverable.unit_id = unit_id
            deliverable.save()
            return JsonResponse({'success': True, 'message': 'Entregable guardado correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class DeliverableDeleteView(LoginRequiredMixin, View):
    """Eliminación lógica (soft-delete) de un entregable vía AJAX."""

    def post(self, request, pk):
        deliverable = get_object_or_404(Deliverable, pk=pk)
        deliverable.is_active = False
        deliverable.save()
        return JsonResponse({'success': True, 'message': 'Entregable eliminado.'})


@login_required
def deliverables_partial_table(request, unit_id):
    """Recarga atómica de la tabla parcial de entregables dentro del acordeón."""
    unit = get_object_or_404(AdministrativeUnit, pk=unit_id)
    deliverables = Deliverable.objects.filter(unit=unit, is_active=True).order_by('-created_at')
    return render(request, 'institution/partials/partial_deliverables_table.html', {
        'unit': unit,
        'deliverables': deliverables
    })


@login_required
def api_unit_deliverables(request, unit_id):
    """Endpoint JSON consolidado de entregables activos (usado por Wizards y componentes dinámicos)."""
    deliverables = Deliverable.objects.filter(
        unit_id=unit_id, is_active=True
    ).order_by('name').values('id', 'name', 'description')
    return JsonResponse({'success': True, 'data': list(deliverables)})


# ==============================================================================
# 4. ENDPOINTS DE SOPORTE API (SELECT2 Y CÓDIGOS CORRELATIVOS)
# ==============================================================================

class ParentOptionsJsonView(LoginRequiredMixin, View):
    """Provee la lista de unidades candidatas a ser padre según el estrato jerárquico."""

    def get(self, request):
        level_id = request.GET.get('level_id')
        direct_parent_only = request.GET.get('direct_parent_only', 'false').lower() == 'true'

        if not level_id or not str(level_id).isdigit():
            return JsonResponse({'results': []})

        try:
            current_level = OrganizationalLevel.objects.get(pk=int(level_id))
            if current_level.level_order <= 1:
                return JsonResponse({'results': []})

            if direct_parent_only:
                parents = AdministrativeUnit.objects.filter(
                    level__level_order=current_level.level_order - 1, is_active=True
                )
            else:
                parents = AdministrativeUnit.objects.filter(
                    level__level_order__lt=current_level.level_order, is_active=True
                )

            parents = parents.select_related('level').order_by('level__level_order', 'name')
            results = [{'id': p.id, 'text': f"{p.name} ➝ {p.level.name}"} for p in parents]
            return JsonResponse({'results': results})

        except OrganizationalLevel.DoesNotExist:
            return JsonResponse({'results': []})


class EmployeeSearchJsonView(LoginRequiredMixin, View):
    """Buscador asíncrono de funcionarios para componentes Select2."""

    def get(self, request):
        term = request.GET.get('term', '').strip()
        qs = Employee.objects.filter(is_active=True).select_related('person')

        if term:
            qs = qs.filter(
                Q(person__first_name__icontains=term) |
                Q(person__last_name__icontains=term) |
                Q(person__document_number__icontains=term)
            )

        results = [
            {'id': str(emp.id),
             'text': f"{emp.person.last_name} {emp.person.first_name} ({emp.person.document_number})"}
            for emp in qs[:20]
        ]
        return JsonResponse({'results': results})


def api_get_administrative_children(request):
    """Retorna subunidades directas o unidades raíz activas (formato dual array y Select2)."""
    parent_id = request.GET.get('parent_id')
    term = (request.GET.get('term') or '').strip()

    filters = {'is_active': True}
    if parent_id:
        filters['parent_id'] = parent_id
    elif not term:
        filters['parent__isnull'] = True
        filters['level__level_order'] = 1

    units = AdministrativeUnit.objects.filter(**filters).order_by('name')
    if term:
        units = units.filter(Q(name__icontains=term) | Q(code__icontains=term))

    units_data = [
        {'id': u.id, 'name': u.name, 'has_children': u.children.filter(is_active=True).exists()}
        for u in units[:30]
    ]
    select2_results = [{'id': str(item['id']), 'text': item['name']} for item in units_data]
    return JsonResponse({'success': True, 'units': units_data, 'results': select2_results})


class GetNextCodeJsonView(LoginRequiredMixin, View):
    """Calcula el código numérico o correlativo sugerido para una nueva unidad administrativa."""

    def get(self, request):
        parent_id = request.GET.get('parent_id')
        next_code = "1"
        suggested_level_id = None

        try:
            if parent_id and parent_id not in ('null', 'undefined'):
                parent = get_object_or_404(AdministrativeUnit, pk=parent_id)
                parent_code = parent.code or "0"
                last_child = AdministrativeUnit.objects.filter(parent=parent).order_by('-id').first()

                if last_child and last_child.code:
                    try:
                        parts = last_child.code.split('.')
                        next_code = f"{'.'.join(parts[:-1])}.{int(parts[-1]) + 1}"
                    except (ValueError, IndexError):
                        next_code = f"{parent_code}.1"
                else:
                    next_code = f"{parent_code}.1"

                next_lvl = OrganizationalLevel.objects.filter(level_order=parent.level.level_order + 1).first()
                if next_lvl:
                    suggested_level_id = next_lvl.id
            else:
                max_code_root = AdministrativeUnit.objects.filter(
                    parent__isnull=True, code__regex=r'^\d+$'
                ).annotate(
                    code_int=Cast('code', output_field=IntegerField())
                ).aggregate(max_val=Max('code_int'))['max_val']

                next_code = str((max_code_root or 0) + 1)
                first_lvl = OrganizationalLevel.objects.filter(level_order=1).first()
                if first_lvl:
                    suggested_level_id = first_lvl.id

            return JsonResponse({'success': True, 'next_code': next_code, 'suggested_level': suggested_level_id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# 5. ORGANIGRAMA OFICIAL Y REPORTES EXCEL
# ==============================================================================

class OrganigramView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'institution.view_administrativeunit'
    template_name = 'institution/organigram.html'

    def get(self, request):
        organigram = InstitutionOrganigram.objects.filter(image__isnull=False).exclude(image='').last()
        form = OrganigramForm()
        return render(request, self.template_name, {
            'organigram': organigram,
            'form': form
        })

    def post(self, request):
        if not request.user.has_perm('institution.change_administrativeunit'):
            return render(request, '403.html', status=403)

        if 'image' not in request.FILES:
            return redirect('institution:organigram_view')

        instance = InstitutionOrganigram.objects.last()
        form = OrganigramForm(request.POST, request.FILES, instance=instance)

        if form.is_valid():
            organigram = form.save(commit=False)
            organigram.updated_by = request.user
            organigram.save()
            return redirect('institution:organigram_view')

        return render(request, self.template_name, {
            'organigram': instance,
            'form': form
        })


class RootLevelListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Navegación posicional estructurada del organigrama en cuadrícula."""
    model = AdministrativeUnit
    template_name = 'institution/root_level_list.html'
    context_object_name = 'units'
    permission_required = 'institution.view_administrativeunit'

    def get(self, request, pk=None):
        if pk:
            current_unit = get_object_or_404(AdministrativeUnit, pk=pk)
            children = AdministrativeUnit.objects.filter(parent=current_unit, is_active=True).order_by('code', 'name')
            employees = Employee.objects.filter(
                area_id=current_unit.pk, is_active=True
            ).exclude(
                employment_status__name__icontains='EX '
            ).select_related('person').prefetch_related('current_budget_line__position_item')

            context = {
                'mode': 'detail',
                'current_unit': current_unit,
                'children': children,
                'employees': employees,
            }
        else:
            units = AdministrativeUnit.objects.filter(
                level__level_order=1, is_active=True
            ).select_related('level').order_by('code', 'name')

            context = {
                'mode': 'root',
                'units': units,
                'total_active': units.count()
            }

        context['form'] = AdministrativeUnitForm()
        return render(request, self.template_name, context)


@login_required
@permission_required('institution.view_administrativeunit', raise_exception=True)
def export_unit_employees_excel(request, pk):
    """Genera y descarga el reporte Excel de funcionarios filtrados por tipo de vinculación."""
    unit = get_object_or_404(AdministrativeUnit, pk=pk)
    status_code = (request.GET.get('status') or 'TOTAL').upper()

    all_unit_ids = get_all_descendant_unit_ids(unit)

    employees = Employee.objects.filter(
        area_id__in=all_unit_ids, is_active=True
    ).exclude(
        employment_status__name__icontains='EX '
    ).select_related(
        'person',
        'employment_status',
        'area',
        'institutional_data__original_dependency'
    ).order_by('area__name', 'person__last_name')

    propios_cond = Q(institutional_data__original_dependency=unit.pk) | \
                   Q(institutional_data__original_dependency__isnull=True, area_id=unit.pk)

    if status_code == 'PROPIOS':
        employees = employees.filter(propios_cond)
    elif status_code == 'REUBICADOS':
        employees = employees.exclude(propios_cond)
    elif status_code != 'TOTAL':
        employees = employees.filter(employment_status__code=status_code)

    wb = Workbook()
    ws = wb.active
    ws.title = status_code if status_code != 'TOTAL' else "Todos"

    headers = [
        'N°', 'Apellidos y Nombres', 'Cédula/Documento', 'Dependencia Actual',
        'Dependencia Original', 'Cargo', 'Remuneración'
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color="198754", end_color="198754", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_align = Alignment(horizontal="center", vertical="center")

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align

    for idx, emp in enumerate(employees, start=1):
        full_name = f"{emp.person.last_name} {emp.person.first_name}"
        document = emp.person.document_number or '-'
        current_area = emp.area.name if emp.area else '-'

        orig_area = current_area
        if hasattr(emp, 'institutional_data') and emp.institutional_data and emp.institutional_data.original_dependency:
            orig_area = emp.institutional_data.original_dependency.name

        cargo = '-'
        remuneracion = '-'
        budget_line = emp.current_budget_line.first()
        if budget_line:
            if budget_line.position_item:
                cargo = budget_line.position_item.name
            if getattr(budget_line, 'remuneration', None):
                remuneracion = f"${budget_line.remuneration:,.2f}"

        ws.append([idx, full_name, document, current_area, orig_area, cargo, remuneracion])

    column_widths = [8, 40, 18, 35, 35, 35, 15]
    for i, width in enumerate(column_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    safe_name = unit.name.replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="Empleados_{safe_name}_{status_code}.xlsx"'

    wb.save(response)
    return response
