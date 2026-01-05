from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, View
from django.http import JsonResponse
from django.db.models import Q
from .models import BudgetLine, Program, Subprogram, Project, Activity
from .forms import BudgetLineForm, ProgramForm, ActivityForm, SubprogramForm, ProjectForm, block_parent_field


# --- 1. ENDPOINT PARA CASCADA (JSON) ---
class HierarchyOptionsJsonView(LoginRequiredMixin, View):
    """
    Vista única para manejar la cascada:
    Program -> Subprogram -> Project -> Activity
    """

    def get(self, request):
        parent_id = request.GET.get('parent_id')
        target_type = request.GET.get('target_type')  # 'subprogram', 'project', 'activity'

        if not parent_id or not parent_id.isdigit():
            return JsonResponse({'results': []})

        parent_id = int(parent_id)
        results = []

        if target_type == 'subprogram':
            qs = Subprogram.objects.filter(program_id=parent_id).values('id', 'code', 'name')
            results = [{'id': x['id'], 'text': f"{x['code']} - {x['name']}"} for x in qs]

        elif target_type == 'project':
            qs = Project.objects.filter(subprogram_id=parent_id).values('id', 'code', 'name')
            results = [{'id': x['id'], 'text': f"{x['code']} - {x['name']}"} for x in qs]

        elif target_type == 'activity':
            qs = Activity.objects.filter(project_id=parent_id).values('id', 'code', 'name')
            results = [{'id': x['id'], 'text': f"{x['code']} - {x['name']}"} for x in qs]

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


class ProgramListView(LoginRequiredMixin, ListView):
    model = Program
    template_name = 'budget/program_list.html'
    context_object_name = 'items'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_type'] = 'program'
        context['level_title'] = 'Programas'
        return context


class SubprogramListView(LoginRequiredMixin, ListView):
    model = Subprogram
    template_name = 'budget/subprogram_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        return Subprogram.objects.filter(program_id=self.kwargs['program_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['parent'] = get_object_or_404(Program, id=self.kwargs['program_id'])
        context['model_type'] = 'subprogram'
        return context


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'budget/project_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        return Project.objects.filter(subprogram_id=self.kwargs['subprogram_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # IMPORTANTE: El padre de un Proyecto es un Subprograma
        context['parent'] = get_object_or_404(Subprogram, id=self.kwargs['subprogram_id'])
        context['model_type'] = 'project'
        return context


class ActivityListView(LoginRequiredMixin, ListView):
    model = Activity
    template_name = 'budget/activity_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        return Activity.objects.filter(project_id=self.kwargs['project_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # El padre de una Actividad es un Proyecto
        context['parent'] = get_object_or_404(Project, id=self.kwargs['project_id'])
        context['model_type'] = 'activity'
        return context


# --- VISTA GENÉRICA PARA MODALES (CREAR/EDITAR ESTRUCTURA) ---

class StructureCreateView(LoginRequiredMixin, View):
    def get(self, request, model_type, parent_id):
        forms_map = {
            'program': (ProgramForm, None),
            'subprogram': (SubprogramForm, 'program'),
            'project': (ProjectForm, 'subprogram'),
            'activity': (ActivityForm, 'project'),
        }
        form_class, field_name = forms_map[model_type]
        form = form_class()

        if field_name and parent_id != 0:
            block_parent_field(form, field_name, parent_id)

        return render(request, 'budget/modals/modal_structure_form.html', {
            'form': form,
            'model_type': model_type,
            'parent_id': parent_id,
            'title': f"Nuevo {model_type.capitalize()}"
        })

    def post(self, request, model_type, parent_id):
        forms_map = {'program': ProgramForm, 'subprogram': SubprogramForm, 'project': ProjectForm,
                     'activity': ActivityForm}
        form = forms_map[model_type](request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Registro creado correctamente'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)