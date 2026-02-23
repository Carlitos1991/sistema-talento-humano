# apps/institution/views.py
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, render, redirect
from django.views.generic import ListView, CreateView, UpdateView, View, DetailView
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.core.cache import cache
from .forms import AssignBossForm
from employee.models import Employee
from .models import AdministrativeUnit, OrganizationalLevel, Deliverable, InstitutionOrganigram
from .forms import AdministrativeUnitForm, OrganizationalLevelForm, DeliverableForm, OrganigramForm
from django.apps import apps


class ParentOptionsJsonView(LoginRequiredMixin, View):
    def get(self, request):
        level_id = request.GET.get('level_id')

        if not level_id or not str(level_id).isdigit():
            return JsonResponse({'results': []})

        try:
            current_level = OrganizationalLevel.objects.get(pk=int(level_id))

            if current_level.level_order <= 1:
                return JsonResponse({'results': []})

            parents = AdministrativeUnit.objects.filter(
                level__level_order__lt=current_level.level_order,
                is_active=True
            ).select_related('level').order_by('level__level_order', 'name')

            results = [{'id': p.id, 'text': f"{p.name} ➝ {p.level.name}"} for p in parents]
            return JsonResponse({'results': results})

        except OrganizationalLevel.DoesNotExist:
            return JsonResponse({'results': []})


class EmployeeSearchJsonView(LoginRequiredMixin, View):
    def get(self, request):
        term = request.GET.get('term', '').strip()
        qs = Employee.objects.filter(is_active=True).select_related('person')

        if term:
            qs = qs.filter(
                Q(person__first_name__icontains=term) |
                Q(person__last_name__icontains=term) |
                Q(person__document_number__icontains=term)
            )

        qs = qs[:20]
        results = []
        for emp in qs:
            full_name = f"{emp.person.last_name} {emp.person.first_name}"
            document = emp.person.document_number
            results.append({'id': str(emp.id), 'text': f"{full_name} ({document})"})

        return JsonResponse({'results': results})


# --- ESTADÍSTICAS ---
def get_unit_stats():
    return {
        'total': AdministrativeUnit.objects.count(),
        'active': AdministrativeUnit.objects.filter(is_active=True).count(),
        'inactive': AdministrativeUnit.objects.filter(is_active=False).count(),
    }


# --- LISTA ---
class UnitListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AdministrativeUnit
    template_name = 'institution/unit_list.html'
    context_object_name = 'units'
    permission_required = 'institution.view_administrativeunit'

    # Sin paginate_by: enviamos TODOS los registros al frontend

    def get_queryset(self):
        # Cargamos TODAS las unidades (activas e inactivas) para que
        qs = AdministrativeUnit.objects.all().select_related(
            'level', 'parent', 'boss__person'
        ).only(
            'id', 'name', 'code', 'is_active',
            'level__id', 'level__name', 'level__level_order',
            'parent__id', 'parent__name',
            'boss__id', 'boss__person__first_name',
            'boss__person__last_name', 'boss__person__photo',
        ).order_by('level__level_order', 'code', 'name')
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AdministrativeUnitForm()
        context.update(get_level_stats())

        # Estadísticas para las tarjetas de nivel (conteos por nivel)
        context['total'] = AdministrativeUnit.objects.count()
        context['active'] = AdministrativeUnit.objects.filter(is_active=True).count()
        context['inactive'] = AdministrativeUnit.objects.filter(is_active=False).count()

        return context

    def get(self, request, *args, **kwargs):
        # Soporte AJAX para recargar solo la tabla parcial
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            html = render_to_string(
                'institution/partials/partial_unit_table.html',
                context,
                request=request
            )
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)


# --- CREAR ---
class UnitCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = AdministrativeUnit
    form_class = AdministrativeUnitForm
    template_name = 'institution/modals/modal_unit_form.html'
    permission_required = 'institution.add_administrativeunit'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            unit = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Unidad creada correctamente.',
                'new_stats': get_unit_stats()
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


# --- DETALLES (HTML) ---
class UnitDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = AdministrativeUnit
    template_name = 'institution/institution_unit_detail.html'
    context_object_name = 'unit'
    permission_required = 'institution.view_administrativeunit'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_unit = self.object
        children = AdministrativeUnit.objects.filter(
            parent=current_unit, is_active=True
        ).order_by('code', 'name')
        context['children'] = children
        return context


# --- DETALLES JSON (para modal de edición) ---
from django.core.exceptions import PermissionDenied

class UnitDetailJsonView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'institution.view_administrativeunit'

    def handle_no_permission(self):
        # Devuelve JSON en vez de redirigir a login o error HTML
        return JsonResponse({'success': False, 'error': 'Permiso denegado.'}, status=403)

    def get(self, request, pk):
        # Verificar permisos manualmente para AJAX
        if not request.user.has_perm(self.permission_required):
            return self.handle_no_permission()
        unit = get_object_or_404(AdministrativeUnit, pk=pk)
        boss_data = None
        if unit.boss:
            boss_data = {
                'id': unit.boss.id,
                'text': f"{unit.boss.person.last_name} {unit.boss.person.first_name}"
            }
        data = {
            'name': unit.name,
            'level': unit.level_id,
            'parent': unit.parent_id,
            'boss': unit.boss_id,
            'boss_data': boss_data,
            'code': unit.code,
            'address': getattr(unit, 'address', '') or '',
            'phone': getattr(unit, 'phone', '') or '',
            'mission': getattr(unit, 'mission', '') or '',
            'is_active': unit.is_active,
        }
        return JsonResponse({'success': True, 'data': data})


# --- ACTUALIZAR ---
class UnitUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = AdministrativeUnit
    form_class = AdministrativeUnitForm
    template_name = 'institution/modals/modal_unit_form.html'
    permission_required = 'institution.change_administrativeunit'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Unidad actualizada correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


# --- TOGGLE STATUS ---
@method_decorator(require_POST, name='dispatch')
class UnitToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'institution.change_administrativeunit'

    def post(self, request, pk):
        unit = get_object_or_404(AdministrativeUnit, pk=pk)
        unit.is_active = not unit.is_active
        cache.delete('level_stats')
        unit.save()

        status_label = "activada" if unit.is_active else "desactivada"
        return JsonResponse({
            'success': True,
            'message': f'La unidad "{unit.name}" ha sido {status_label}.',
        })


@login_required
def unit_partial_table(request):
    units = AdministrativeUnit.objects.all().select_related(
        'level', 'parent', 'boss__person'
    ).order_by('level__level_order', 'code', 'name')
    context = {'units': units}
    html = render_to_string(
        'institution/partials/partial_unit_table.html',
        context,
        request=request
    )
    return HttpResponse(html)


# ==========================================
# GESTIÓN DE NIVELES JERÁRQUICOS
# ==========================================

def get_level_stats():
    """
    Retorna niveles con conteo, colores e ICONOS dinámicos.
    """
    cached = cache.get('level_stats')
    if cached:
        return cached
    levels = OrganizationalLevel.objects.filter(is_active=True).order_by('level_order')[:5]
    stats = []
    cache.set('level_stats', stats, timeout=300)  # 5 minutos
    total_count = AdministrativeUnit.objects.filter(is_active=True).count()
    stats.append({
        'id': 'total',
        'name': 'Total',
        'order': 0,
        'count': total_count,
        'color': 'color-zero',
        'icon': 'fa-layer-group'
    })

    colors = ['color-one', 'color-two', 'color-three', 'color-four', 'color-five']
    icons = ['fa-globe', 'fa-building', 'fa-briefcase', 'fa-users', 'fa-user-tag']

    for i, lvl in enumerate(levels):
        count = AdministrativeUnit.objects.filter(level=lvl, is_active=True).count()
        stats.append({
            'id': lvl.id,
            'name': lvl.name,
            'order': lvl.level_order,
            'count': count,
            'color': colors[i] if i < len(colors) else 'color-one',
            'icon': icons[i] if i < len(icons) else 'fa-sitemap'
        })

    return {'level_stats': stats}


# ============================================================
# GESTIÓN DE NIVELES JERÁRQUICOS
# ============================================================
class LevelListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = OrganizationalLevel
    template_name = 'institution/levels/level_list.html'
    context_object_name = 'levels'
    permission_required = 'institution.view_organizationallevel'

    def get_queryset(self):
        qs = OrganizationalLevel.objects.all().order_by('level_order')
        q = self.request.GET.get('q')
        status = self.request.GET.get('status')

        if q:
            qs = qs.filter(name__icontains=q)

        if status == 'true':
            qs = qs.filter(is_active=True)
        elif status == 'false':
            qs = qs.filter(is_active=False)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = OrganizationalLevelForm()
        context['total'] = OrganizationalLevel.objects.all().count()
        context['active'] = OrganizationalLevel.objects.filter(is_active=True).count()
        context['inactive'] = OrganizationalLevel.objects.filter(is_active=False).count()
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            html = render_to_string(
                'institution/levels/partials/partial_level_table.html',
                context,
                request=request
            )
            stats = {
                'total': context.get('total', 0),
                'active': context.get('active', 0),
                'inactive': context.get('inactive', 0),
            }
            return JsonResponse({'html': html, 'stats': stats})
        return super().get(request, *args, **kwargs)


class LevelCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = OrganizationalLevel
    form_class = OrganizationalLevelForm
    template_name = 'institution/levels/modals/modal_level_form.html'
    permission_required = 'institution.add_organizationallevel'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            form.save()
            return JsonResponse({
                'success': True,
                'message': 'Nivel jerárquico creado.',
                'new_stats': get_level_stats()
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class LevelDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'institution.view_organizationallevel'

    def get(self, request, pk):
        lvl = get_object_or_404(OrganizationalLevel, pk=pk)
        return JsonResponse({
            'success': True,
            'data': {'name': lvl.name, 'level_order': lvl.level_order}
        })


class LevelUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = OrganizationalLevel
    form_class = OrganizationalLevelForm
    template_name = 'institution/levels/modals/modal_level_form.html'
    permission_required = 'institution.change_organizationallevel'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Nivel actualizado correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@require_POST
@permission_required('institution.change_organizationallevel', raise_exception=True)
def level_toggle_status(request, pk):
    lvl = get_object_or_404(OrganizationalLevel, pk=pk)
    next_status = not lvl.is_active

    if next_status:
        conflict = OrganizationalLevel.objects.filter(
            level_order=lvl.level_order,
            is_active=True
        ).exclude(pk=pk).exists()

        if conflict:
            return JsonResponse({
                'success': False,
                'message': f"Conflicto: Ya existe un nivel jerárquico #{lvl.level_order} activo. Desactive el anterior primero."
            }, status=400)

    lvl.is_active = next_status
    lvl.save()

    status_label = "activado" if lvl.is_active else "desactivado"
    return JsonResponse({
        'success': True,
        'message': f'Nivel "{lvl.name}" {status_label}.',
        'new_stats': get_level_stats()
    })


def api_get_administrative_children(request):
    parent_id = request.GET.get('parent_id')
    filters = {'parent__isnull': True} if not parent_id else {'parent_id': parent_id}
    filters['is_active'] = True

    units = AdministrativeUnit.objects.filter(**filters).order_by('name')
    data = []
    for u in units:
        has_children = u.children.filter(is_active=True).exists()
        data.append({'id': u.id, 'name': u.name, 'has_children': has_children})

    return JsonResponse({'success': True, 'units': data})


class DeliverableListJsonView(LoginRequiredMixin, View):
    def get(self, request, unit_id):
        deliverables = Deliverable.objects.filter(unit_id=unit_id, is_active=True).order_by('-created_at')
        data = [{'id': d.id, 'name': d.name, 'description': d.description or ''} for d in deliverables]
        return JsonResponse({'success': True, 'data': data})


class DeliverableCreateUpdateView(LoginRequiredMixin, View):
    def post(self, request, unit_id, pk=None):
        if pk:
            instance = get_object_or_404(Deliverable, pk=pk, unit_id=unit_id)
            form = DeliverableForm(request.POST, instance=instance)
        else:
            form = DeliverableForm(request.POST)

        if form.is_valid():
            deliverable = form.save(commit=False)
            deliverable.unit_id = unit_id
            deliverable.save()
            return JsonResponse({'success': True, 'message': 'Entregable guardado correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class DeliverableDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        deliverable = get_object_or_404(Deliverable, pk=pk)
        deliverable.is_active = False  # Soft delete
        deliverable.save()
        return JsonResponse({'success': True, 'message': 'Entregable eliminado.'})


@login_required
def api_unit_deliverables(request, unit_id):
    """
    Endpoint para obtener los entregables de una unidad administrativa.
    Utilizado por Vue.js en la vista de detalle y en el Wizard de Perfiles de Puesto.
    """
    try:
        deliverables = Deliverable.objects.filter(
            unit_id=unit_id,
            is_active=True
        ).order_by('name')
        data = [{'id': d.id, 'name': d.name, 'description': d.description or ''} for d in deliverables]
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


class GetNextCodeJsonView(LoginRequiredMixin, View):
    def get(self, request):
        parent_id = request.GET.get('parent_id')

        # Si viene un parent_id, es una dependencia
        if parent_id and parent_id != 'null':
            parent = get_object_or_404(AdministrativeUnit, pk=parent_id)
            parent_code = parent.code if parent.code else "0"

            last_sibling = AdministrativeUnit.objects.filter(
                parent=parent
            ).exclude(code__isnull=True).exclude(code='').order_by('-created_at').first()

            if last_sibling and last_sibling.code:
                try:
                    parts = last_sibling.code.split('.')
                    last_num = int(parts[-1])
                    new_last_num = last_num + 1
                    base_prefix = ".".join(parts[:-1])
                    next_code = f"{base_prefix}.{new_last_num}"
                except ValueError:
                    next_code = f"{parent_code}.1"
            else:
                next_code = f"{parent_code}.1"

            level_id = parent.level.level_order + 1

            # Buscar el objeto nivel correspondiente al orden
            try:
                level_obj = OrganizationalLevel.objects.get(level_order=level_id)
                level_pk = level_obj.id
            except OrganizationalLevel.DoesNotExist:
                level_pk = None

        else:
            # Si NO hay parent_id, es una unidad de NIVEL 1 (Raíz)
            # Buscamos el último código de nivel raíz que sea numérico simple (1, 2, 3...)
            last_root = AdministrativeUnit.objects.filter(
                parent__isnull=True
            ).exclude(code__isnull=True).exclude(code='').order_by('-created_at')

            # Intentamos encontrar el máximo numérico
            max_code = 0
            for unit in last_root:
                try:
                    val = int(unit.code)
                    if val > max_code:
                        max_code = val
                except ValueError:
                    continue

            next_code = str(max_code + 1)

            try:
                level_obj = OrganizationalLevel.objects.get(level_order=1)
                level_pk = level_obj.id
            except OrganizationalLevel.DoesNotExist:
                level_pk = None

        return JsonResponse({'success': True, 'next_code': next_code, 'suggested_level': level_pk})


class OrganigramView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'institution.view_administrativeunit'
    template_name = 'institution/organigram.html'

    def get(self, request):
        organigram = InstitutionOrganigram.objects.last()
        form = OrganigramForm()
        return render(request, self.template_name, {'organigram': organigram, 'form': form})

    def post(self, request):
        if not request.user.has_perm('institution.change_administrativeunit'):
            return render(request, '403.html', status=403)

        form = OrganigramForm(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updated_by = request.user
            instance.save()
            return redirect('institution:organigram_view')

        organigram = InstitutionOrganigram.objects.last()
        return render(request, self.template_name, {'organigram': organigram, 'form': form})


class RootLevelListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AdministrativeUnit
    template_name = 'institution/root_level_list.html'
    context_object_name = 'units'
    permission_required = 'institution.view_administrativeunit'

    def get(self, request, pk=None):
        context = {}

        if pk:
            current_unit = get_object_or_404(AdministrativeUnit, pk=pk)
            children = AdministrativeUnit.objects.filter(
                parent=current_unit, is_active=True
            ).order_by('code', 'name')
            employees = Employee.objects.filter(
                area_id=current_unit.pk, is_active=True
            ).exclude(
                Q(employment_status__name__icontains='EX EMPLEADO') |
                Q(employment_status__name__icontains='EX TRABAJADOR')
            ).select_related('person').prefetch_related(
                'current_budget_line', 'current_budget_line__position_item'
            )
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


class UnitAssignBossView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = AdministrativeUnit
    form_class = AssignBossForm
    template_name = 'institution/modals/modal_assign_boss.html'
    permission_required = 'institution.change_administrativeunit'
    context_object_name = 'unit'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        old_boss = self.object.boss
        form = self.get_form()

        if form.is_valid():
            unit = form.save()
            new_boss = unit.boss

            if new_boss:
                new_boss.is_boss = True
                new_boss.save(update_fields=['is_boss'])

            if old_boss and old_boss != new_boss:
                if not old_boss.managed_units.exists():
                    old_boss.is_boss = False
                    old_boss.save(update_fields=['is_boss'])

            return JsonResponse({
                'success': True,
                'message': f'Jefe asignado correctamente a {self.object.name}.'
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
def level_partial_table(request):
    levels = OrganizationalLevel.objects.all()
    context = {'levels': levels}
    html = render_to_string('institution/levels/partials/partial_level_table.html', context, request=request)
    return HttpResponse(html)
