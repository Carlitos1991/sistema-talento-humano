# apps/institution/views.py
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.views.generic import ListView, CreateView, UpdateView, View, DetailView
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from employee.models import Employee
from .models import AdministrativeUnit, OrganizationalLevel, Deliverable
from .forms import AdministrativeUnitForm, OrganizationalLevelForm, DeliverableForm


class ParentOptionsJsonView(LoginRequiredMixin, View):
    def get(self, request):
        level_id = request.GET.get('level_id')

        # Validación básica
        if not level_id or not str(level_id).isdigit():
            return JsonResponse({'results': []})

        try:
            current_level = OrganizationalLevel.objects.get(pk=int(level_id))

            # Si es el nivel 1 (Raíz), no hay padres posibles.
            if current_level.level_order <= 1:
                return JsonResponse({'results': []})
            parents = AdministrativeUnit.objects.filter(
                level__level_order__lt=current_level.level_order,
                is_active=True
            ).select_related('level').order_by('level__level_order', 'name')

            results = []
            for p in parents:
                results.append({
                    'id': p.id,
                    'text': f"{p.name} ➝ {p.level.name}"
                })

            return JsonResponse({'results': results})

        except OrganizationalLevel.DoesNotExist:
            return JsonResponse({'results': []})


class EmployeeSearchJsonView(LoginRequiredMixin, View):
    """Búsqueda optimizada de empleados para Select2 (Maneja miles de registros)."""

    def get(self, request):
        term = request.GET.get('term', '').strip()  # Lo que escribe el usuario

        qs = Employee.objects.filter(is_active=True).select_related('person')

        if term:
            # Búsqueda por múltiples campos (OR)
            qs = qs.filter(
                Q(person__first_name__icontains=term) |
                Q(person__last_name__icontains=term) |
                Q(person__document_number__icontains=term)
            )

        qs = qs[:20]

        results = []
        for emp in qs:
            # Formato claro: Apellidos Nombres (Cédula)
            full_name = f"{emp.person.last_name} {emp.person.first_name}"
            document = emp.person.document_number
            text = f"{full_name} ({document})"

            results.append({
                'id': str(emp.id),  # Convertir a string para evitar problemas de tipo en JS
                'text': text
            })

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
    paginate_by = 10
    permission_required = 'institution.view_administrativeunit'

    def get_queryset(self):
        # Optimizamos consultas (select_related para FKs)
        qs = AdministrativeUnit.objects.select_related('level', 'parent', 'boss__person').all().order_by(
            'level__level_order', 'name')

        q = self.request.GET.get('q')
        status = self.request.GET.get('status')

        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(code__icontains=q) |
                Q(boss__person__first_name__icontains=q) |
                Q(boss__person__last_name__icontains=q)
            )

        if status == 'true':
            qs = qs.filter(is_active=True)
        elif status == 'false':
            qs = qs.filter(is_active=False)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AdministrativeUnitForm()  # Para el modal vacío
        context.update(get_unit_stats())
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return render(request, 'institution/partials/partial_unit_table.html', context)
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


# --- DETALLES (JSON para Modal) ---
class UnitDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = AdministrativeUnit
    template_name = 'institution/institution_unit_detail.html'
    context_object_name = 'unit'
    permission_required = 'institution.view_administrativeunit'


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
        unit.save()

        status_label = "activada" if unit.is_active else "desactivada"
        return JsonResponse({
            'success': True,
            'message': f'La unidad "{unit.name}" ha sido {status_label}.',
            'new_stats': get_unit_stats()
        })


# ==========================================
# GESTIÓN DE NIVELES JERÁRQUICOS
# ==========================================

def get_level_stats():
    return {
        'total': OrganizationalLevel.objects.count(),
        'active': OrganizationalLevel.objects.filter(is_active=True).count(),
        'inactive': OrganizationalLevel.objects.filter(is_active=False).count(),
    }


class LevelListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = OrganizationalLevel
    template_name = 'institution/levels/level_list.html'
    context_object_name = 'levels'
    paginate_by = 10
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
        context.update(get_level_stats())
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return render(request, 'institution/levels/partials/partial_level_table.html', context)
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

    # Lógica de Cambio
    next_status = not lvl.is_active

    # --- VALIDACIÓN NUEVA ---
    # Si vamos a ACTIVAR (next_status es True), verificamos conflicto
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

    # Si pasa la validación, guardamos
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

    # Si no hay parent_id, traemos las de nivel raíz (sin padre)
    filters = {'parent__isnull': True} if not parent_id else {'parent_id': parent_id}
    filters['is_active'] = True

    units = AdministrativeUnit.objects.filter(**filters).order_by('name')
    data = [{'id': u.id, 'name': u.name} for u in units]

    return JsonResponse({'success': True, 'units': data})


class DeliverableListJsonView(LoginRequiredMixin, View):
    def get(self, request, unit_id):
        deliverables = Deliverable.objects.filter(unit_id=unit_id, is_active=True).order_by('-created_at')
        data = [{
            'id': d.id,
            'name': d.name,
            'description': d.description or '',
            'frequency': d.frequency or ''
        } for d in deliverables]
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


class UnitDetailJsonView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'institution.view_administrativeunit'

    def get(self, request, pk):
        unit = get_object_or_404(AdministrativeUnit, pk=pk)
        boss_data = None
        if unit.boss:
            boss_data = {
                'id': unit.boss.id,
                'text': f"{unit.boss.person.last_name} {unit.boss.person.first_name}"
            }
        data = {
            'name': unit.name, 'level': unit.level_id, 'parent': unit.parent_id,
            'boss': unit.boss_id, 'boss_data': boss_data, 'code': unit.code,
            'address': unit.address, 'phone': unit.phone
        }
        return JsonResponse({'success': True, 'data': data})
