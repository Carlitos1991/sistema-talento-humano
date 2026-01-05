from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, View
from django.http import JsonResponse
from django.db.models import Q
from .models import BudgetLine, Program, Subprogram, Project, Activity
from .forms import BudgetLineForm, ProgramForm, ActivityForm, SubprogramForm, ProjectForm, block_parent_field


# --- 1. ENDPOINT PARA CASCADA (JSON) ---
class HierarchyOptionsJsonView(LoginRequiredMixin, View):
    def get(self, request):
        parent_id = request.GET.get('parent_id')
        target_type = request.GET.get('target_type')

        if not parent_id or not parent_id.isdigit():
            return JsonResponse({'results': []})

        parent_id = int(parent_id)
        results = []

        # Agregamos 'code' al values para enviarlo al frontend
        if target_type == 'subprogram':
            qs = Subprogram.objects.filter(program_id=parent_id, is_active=True).values('id', 'code', 'name')
        elif target_type == 'project':
            qs = Project.objects.filter(subprogram_id=parent_id, is_active=True).values('id', 'code', 'name')
        elif target_type == 'activity':
            qs = Activity.objects.filter(project_id=parent_id, is_active=True).values('id', 'code', 'name')
        else:
            return JsonResponse({'results': []})

        # Se envia el 'code' por separado para facilitar la concatenación en JS
        results = [
            {'id': x['id'], 'text': f"{x['code']} - {x['name']}", 'code': x['code']}
            for x in qs
        ]
        return JsonResponse({'results': results})


# --- 2. ESTADÍSTICAS (Python Calculation) ---
def get_budget_stats():
    return {
        'total': BudgetLine.objects.count(),
        'vacant': BudgetLine.objects.filter(status_item__code='VACANT').count(),
        'occupied': BudgetLine.objects.filter(status_item__code='OCCUPIED').count(),
    }


# --- 3. LISTADO ---
class BudgetListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = BudgetLine
    template_name = 'budget/budget_list.html'
    context_object_name = 'lines'
    paginate_by = 15
    permission_required = 'budget.view_budgetline'

    def get_queryset(self):
        # Optimización masiva: Traemos toda la info relacionada en una sola query
        qs = BudgetLine.objects.select_related(
            'activity__project__subprogram__program',
            'current_employee__person',
            'status_item', 'position_item', 'regime_item'
        ).all().order_by('code')

        q = self.request.GET.get('q')
        status = self.request.GET.get('status')

        if q:
            qs = qs.filter(
                Q(number_individual__icontains=q) |
                Q(code__icontains=q) |
                Q(position_item__name__icontains=q) |
                Q(current_employee__person__first_name__icontains=q) |
                Q(current_employee__person__last_name__icontains=q)
            )

        if status and status != 'all':
            qs = qs.filter(status_item__code=status)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = BudgetLineForm()  # Formulario vacío para el modal de crear
        context.update(get_budget_stats())
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return render(request, 'budget/partials/partial_budget_table.html', context)
        return super().get(request, *args, **kwargs)


# --- 4. CREAR ---
class BudgetCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = BudgetLine
    form_class = BudgetLineForm
    template_name = 'budget/modals/modal_budget_form.html'
    permission_required = 'budget.add_budgetline'

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            form.save()
            return JsonResponse({
                'success': True,
                'message': 'Partida presupuestaria creada.',
                'new_stats': get_budget_stats()
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


# --- 5. EDITAR (Carga HTML del Modal) ---
class BudgetUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = BudgetLine
    form_class = BudgetLineForm
    template_name = 'budget/modals/modal_budget_form.html'
    permission_required = 'budget.change_budgetline'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        # Renderizamos el HTML del formulario completo
        return render(request, self.template_name, {'form': form, 'is_editing': True})

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Partida actualizada correctamente.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    # --- 5. Estructura de partida ---


# --- VISTAS DE ESTRUCTURA (LISTADOS) ---
# apps/budget/views.py

class StructureBaseListView(LoginRequiredMixin, ListView):
    template_name = 'budget/program_list.html'
    context_object_name = 'items'

    def get_queryset_logic(self, queryset):
        q = self.request.GET.get('q')
        status = self.request.GET.get('status')
        if q:
            queryset = queryset.filter(Q(name__icontains=q) | Q(code__icontains=q))
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        return queryset.order_by('code')

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Renderizamos la tabla pasando todo el contexto necesario para los enlaces
            return render(request, 'budget/partials/partial_structure_table.html', context)
        return super().get(request, *args, **kwargs)


class ProgramListView(StructureBaseListView):
    model = Program
    template_name = 'budget/program_list.html'

    def get_queryset(self): return self.get_queryset_logic(Program.objects.all())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Program.objects.all()
        ctx.update({
            'model_type': 'program', 'level_title': 'Programas', 'level_title_singular': 'Programa',
            'level_desc': 'Gestión de Programas',
            'nav_url_name': 'budget:subprogram_list',  # El siguiente nivel
            'total': qs.count(), 'active': qs.filter(is_active=True).count(),
            'inactive': qs.filter(is_active=False).count()
        })
        return ctx


class SubprogramListView(StructureBaseListView):
    model = Subprogram
    template_name = 'budget/subprogram_list.html'

    def get_queryset(self):
        return self.get_queryset_logic(Subprogram.objects.filter(program_id=self.kwargs['program_id']))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # IMPORTANTE: Asegúrate que el ID en la URL existe en la DB
        parent = get_object_or_404(Program, id=self.kwargs['program_id'])
        qs = Subprogram.objects.filter(program=parent)
        ctx.update({
            'parent': parent, 'model_type': 'subprogram', 'level_title': 'Subprogramas',
            'nav_url_name': 'budget:project_list', 'level_title_singular': 'Subprograma',
            'total': qs.count(), 'active': qs.filter(is_active=True).count(),
            'inactive': qs.filter(is_active=False).count()
        })
        return ctx


class ProjectListView(StructureBaseListView):
    model = Project
    template_name = 'budget/project_list.html'

    def get_queryset(self):
        return self.get_queryset_logic(Project.objects.filter(subprogram_id=self.kwargs['subprogram_id']))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        parent = get_object_or_404(Subprogram, id=self.kwargs['subprogram_id'])
        qs = Project.objects.filter(subprogram=parent)
        ctx.update({
            'parent': parent, 'model_type': 'project', 'level_title': 'Proyectos',
            'nav_url_name': 'budget:activity_list', 'level_title_singular': 'Proyecto',
            'total': qs.count(), 'active': qs.filter(is_active=True).count(),
            'inactive': qs.filter(is_active=False).count()
        })
        return ctx


class ActivityListView(StructureBaseListView):
    model = Activity
    template_name = 'budget/activity_list.html'

    def get_queryset(self):
        return self.get_queryset_logic(Activity.objects.filter(project_id=self.kwargs['project_id']))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        parent = get_object_or_404(Project, id=self.kwargs['project_id'])
        qs = Activity.objects.filter(project=parent)
        ctx.update({
            'parent': parent, 'model_type': 'activity', 'level_title': 'Actividades',
            'nav_url_name': None, 'level_title_singular': 'Actividad',
            'total': qs.count(), 'active': qs.filter(is_active=True).count(),
            'inactive': qs.filter(is_active=False).count()
        })
        return ctx


# --- VISTAS DE ACCIÓN (MODALES Y TOGGLE) ---

class StructureCreateView(LoginRequiredMixin, View):
    def get(self, request, model_type, parent_id):
        titles = {
            'program': 'Programa',
            'subprogram': 'Subprograma',
            'project': 'Proyecto',
            'activity': 'Actividad'
        }
        forms_map = {
            'program': (ProgramForm, None),
            'subprogram': (SubprogramForm, 'program'),
            'project': (ProjectForm, 'subprogram'),
            'activity': (ActivityForm, 'project'),
        }
        form_class, field_name = forms_map[model_type]
        form = form_class()
        if field_name and int(parent_id) > 0:
            block_parent_field(form, field_name, parent_id)

        return render(request, 'budget/modals/modal_structure_form.html', {
            'form': form, 'model_type': model_type, 'parent_id': parent_id, 'pk': 0, 'is_editing': False,
            'title': f"Nuevo {titles[model_type]}"
        })

    def post(self, request, model_type, parent_id):
        forms_map = {'program': ProgramForm, 'subprogram': SubprogramForm, 'project': ProjectForm,
                     'activity': ActivityForm}
        form = forms_map[model_type](request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Creado correctamente'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class StructureUpdateView(LoginRequiredMixin, View):
    def get(self, request, model_type, pk):
        config = {
            'program': (Program, ProgramForm, None),
            'subprogram': (Subprogram, SubprogramForm, 'program'),
            'project': (Project, ProjectForm, 'subprogram'),
            'activity': (Activity, ActivityForm, 'project'),
        }
        titles = {
            'program': 'Programa',
            'subprogram': 'Subprograma',
            'project': 'Proyecto',
            'activity': 'Actividad'
        }
        model_class, form_class, field_name = config[model_type]
        obj = get_object_or_404(model_class, pk=pk)
        form = form_class(instance=obj)

        if field_name:
            block_parent_field(form, field_name, None)

        return render(request, 'budget/modals/modal_structure_form.html', {
            'form': form, 'model_type': model_type, 'pk': pk, 'is_editing': True, 'parent_id': 0,
            'title': f"Nuevo {titles[model_type]}"
        })

    def post(self, request, model_type, pk):
        config = {
            'program': (Program, ProgramForm), 'subprogram': (Subprogram, SubprogramForm),
            'project': (Project, ProjectForm), 'activity': (Activity, ActivityForm),
        }
        model_class, form_class = config[model_type]
        obj = get_object_or_404(model_class, pk=pk)
        form = form_class(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Actualizado correctamente'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class StructureToggleView(LoginRequiredMixin, View):
    def post(self, request, model_type, pk):
        models_map = {'program': Program, 'subprogram': Subprogram, 'project': Project, 'activity': Activity}
        obj = get_object_or_404(models_map[model_type], pk=pk)
        obj.is_active = not obj.is_active
        obj.save()
        return JsonResponse({'success': True, 'message': f'Registro {"activado" if obj.is_active else "desactivado"}'})
