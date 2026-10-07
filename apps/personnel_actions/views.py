import datetime as dt
import traceback
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView

from budget.models import BudgetLine, BudgetAssignmentHistory, BudgetModificationHistory
from core.models import CatalogItem, User
from employee.models import Employee
from institution.models import AdministrativeUnit
from .forms import PersonnelActionForm, ActionTypeForm
from .models import PersonnelAction, ActionMovement, ActionType


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _save_action_movement(action, request, is_create=False):
    """
    Función auxiliar para procesar y guardar el movimiento (Situación Actual vs Propuesta)
    """
    if is_create:
        movement = ActionMovement(personnel_action=action)
        employee = action.employee
        current_budget = employee.current_budget_line.first()
        current_unit = employee.area

        movement.previous_unit = current_unit.name if current_unit else ''
        movement.previous_budget_line = current_budget
        movement.previous_position = current_budget.position_item.name if current_budget and current_budget.position_item else ''
        movement.previous_remuneration = current_budget.remuneration if current_budget else 0
    else:
        movement, _ = ActionMovement.objects.get_or_create(personnel_action=action)

    new_unit_id = request.POST.get('movement_new_unit')
    new_budget_line_id = request.POST.get('movement_new_budget_line')
    location_text = request.POST.get('location_text')

    if new_unit_id:
        try:
            unit_obj = AdministrativeUnit.objects.get(pk=new_unit_id)
            movement.new_unit = unit_obj.name
        except AdministrativeUnit.DoesNotExist:
            pass

    if new_budget_line_id:
        try:
            new_bl = BudgetLine.objects.select_related('position_item').get(pk=new_budget_line_id)
            movement.new_budget_line = new_bl
            movement.new_position = new_bl.position_item.name if new_bl.position_item else ''
            movement.new_remuneration = new_bl.remuneration
        except BudgetLine.DoesNotExist:
            pass

    if location_text:
        movement.location_text = location_text

    movement.save()


def _flatten_unit_descendants(unit, depth=0):
    descendants = []
    if not unit:
        return descendants

    children = unit.children.filter(is_active=True).select_related('level').order_by('level__level_order', 'name')
    for child in children:
        descendants.append({
            'depth': depth,
            'name': child.name,
            'path': child.get_full_path(),
        })
        descendants.extend(_flatten_unit_descendants(child, depth + 1))

    return descendants


def _budget_snapshot(budget_line):
    if not budget_line:
        return None

    program_name = ''
    try:
        program_name = budget_line.activity.project.subprogram.program.name
    except Exception:
        program_name = ''

    return {
        'code': budget_line.number_individual or budget_line.code or 'N/A',
        'position': budget_line.position_item.name if budget_line.position_item else 'N/A',
        'group': budget_line.group_item.name if budget_line.group_item else 'N/A',
        'grade': budget_line.grade_item.name if budget_line.grade_item else 'N/A',
        'rmu': budget_line.remuneration,
        'program': program_name or 'N/A',
    }


def _unit_snapshot(unit):
    if not unit:
        return {
            'unit': None,
            'path': 'N/A',
            'descendants': [],
        }

    return {
        'unit': unit,
        'path': unit.get_full_path(),
        'descendants': _flatten_unit_descendants(unit),
    }


def _spanish_date_without_year(date_value):
    if not date_value:
        return ''

    months = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
        7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre',
    }
    return f"{date_value.day} de {months.get(date_value.month, '')}"


def _movement_reason(action):
    action_name = (action.action_type.name or '').strip().lower()
    if not action_name:
        action_name = 'acción de personal'
    return f"{action_name} a partir del {_spanish_date_without_year(action.date_effective)}"


# ==============================================================================
# MAIN PERSONNEL ACTIONS VIEWS
# ==============================================================================

class PersonnelActionListView(LoginRequiredMixin, ListView):
    model = PersonnelAction
    template_name = 'personnel_action/personnel_action_list.html'
    context_object_name = 'actions'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'employee__person',
            'action_type'
        ).prefetch_related('movement')

        q = self.request.GET.get('q', '').strip()
        action_type = self.request.GET.get('action_type', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()
        prev_unit = self.request.GET.get('prev_unit', '').strip()
        new_unit = self.request.GET.get('new_unit', '').strip()
        prev_pos = self.request.GET.get('prev_pos', '').strip()
        new_pos = self.request.GET.get('new_pos', '').strip()
        detail = self.request.GET.get('detail', '').strip()

        if q:
            terms = q.split()
            if len(terms) > 1:
                query = Q()
                for term in terms:
                    query &= (
                            Q(employee__person__first_name__icontains=term) |
                            Q(employee__person__last_name__icontains=term)
                    )
                qs = qs.filter(query)
            else:
                qs = qs.filter(
                    Q(employee__person__first_name__icontains=q) |
                    Q(employee__person__last_name__icontains=q) |
                    Q(employee__person__document_number__icontains=q) |
                    Q(number__icontains=q) |
                    Q(action_type__name__icontains=q)
                )

        if action_type:
            qs = qs.filter(Q(action_type__id=action_type) | Q(action_type__name__icontains=action_type))
        if date_from:
            try:
                qs = qs.filter(date_effective__gte=date_from)
            except Exception:
                pass
        if date_to:
            try:
                qs = qs.filter(date_effective__lte=date_to)
            except Exception:
                pass
        if prev_unit:
            qs = qs.filter(movement__previous_unit__icontains=prev_unit)
        if new_unit:
            qs = qs.filter(movement__new_unit__icontains=new_unit)
        if prev_pos:
            qs = qs.filter(movement__previous_position__icontains=prev_pos)
        if new_pos:
            qs = qs.filter(movement__new_position__icontains=new_pos)
        if detail:
            qs = qs.filter(Q(explanation__icontains=detail) | Q(motivation__icontains=detail))

        order_by = self.request.GET.get('order_by', '').strip()
        direction = self.request.GET.get('direction', 'asc').strip().lower()
        if order_by:
            prefix = '-' if direction == 'desc' else ''
            try:
                ordered = qs.order_by(f"{prefix}{order_by}")
                return ordered[:3000]
            except Exception:
                pass

        return qs.order_by('-pk')[:3000]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_types'] = ActionType.objects.all()
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html_table = render_to_string(
                'personnel_action/partials/partial_personnel_action_table.html',
                context,
                request=self.request
            )
            page_obj = context['page_obj']
            return JsonResponse({
                'html': html_table,
                'page_number': page_obj.number,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'num_pages': context['paginator'].num_pages,
                'total_records': context['paginator'].count
            })
        return super().render_to_response(context, **response_kwargs)


class PersonnelActionCreateView(LoginRequiredMixin, CreateView):
    permission_required = 'personnel_actions.add_personnelaction'
    model = PersonnelAction
    form_class = PersonnelActionForm
    template_name = 'personnel_action/modals/modal_personnel_action_form.html'

    def get(self, request, *args, **kwargs):
        try:
            employee_id = request.GET.get('employee_id')
            employee = None

            if employee_id and str(employee_id).strip() not in ['undefined', 'null', '']:
                employee = get_object_or_404(Employee, pk=employee_id)

            form = self.form_class()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return render(request, self.template_name, {
                    'form': form,
                    'employee': employee,
                    'employee_id': employee_id
                })

            return render(request, 'personnel_action/action_form_page.html', {
                'form': form,
                'employee': employee,
                'employee_id': employee_id,
                'is_edit': False
            })


        except Exception as e:
            traceback.print_exc()
            return HttpResponse(f"Error interno del servidor: {str(e)}", status=500)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.created_by = self.request.user
                self.object.elaboration = self.request.user

                if self.object.action_type:
                    self.object.authority_1 = self.object.action_type.default_authority_1
                    self.object.authority_2 = self.object.action_type.default_authority_2
                    self.object.reviewer = self.object.action_type.default_reviewer
                    self.object.register = self.object.action_type.default_register

                if not self.object.number or self.object.number.strip() == '':
                    year = dt.datetime.now().year
                    last_action = PersonnelAction.objects.filter(number__endswith=f'-{year}').order_by(
                        '-created_at').first()
                    new_num = 1
                    if last_action:
                        try:
                            new_num = int(last_action.number.split('-')[0]) + 1
                        except Exception:
                            pass
                    self.object.number = f'{new_num:04d}-{year}'

                self.object.save()
                _save_action_movement(self.object, self.request, is_create=True)

            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'success', 'success': True, 'message': 'Acción de personal creada correctamente'})

            return super().form_valid(form)

        except Exception as e:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'success': False, 'message': f'Fallo interno: {str(e)}'},
                                    status=500)
            raise e

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor, revise los campos del formulario.',
                'errors': errors_data
            }, status=400)
        return super().form_invalid(form)


class ActionInactivateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        action = get_object_or_404(PersonnelAction, pk=pk)
        if not request.user.has_perm('personnel_actions.delete_personnelaction'):
            return JsonResponse({'status': 'error', 'success': False, 'message': 'No tienes permiso'}, status=403)
        action.is_active = False
        action.save()
        return JsonResponse(
            {'status': 'success', 'success': True, 'message': f'Acción {action.number} inactivada correctamente.'})


# ==============================================================================
# TIPOS DE ACCIÓN (ESTANDARIZADO DJANGO + MAIN.JS)
# ==============================================================================

class ActionTypeListView(LoginRequiredMixin, ListView):
    model = ActionType
    template_name = 'personnel_action/action_type_list.html'
    context_object_name = 'types'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()

        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query))

        if status == 'true':
            qs = qs.filter(is_active=True)
        elif status == 'false':
            qs = qs.filter(is_active=False)

        return qs.order_by('name')

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html_table = render_to_string(
                'personnel_action/partials/partial_action_type_list.html',
                context,
                request=self.request
            )
            page_obj = context.get('page_obj')
            paginator = context.get('paginator')
            return JsonResponse({
                'html': html_table,
                'page_number': page_obj.number if page_obj else 1,
                'has_next': page_obj.has_next() if page_obj else False,
                'has_previous': page_obj.has_previous() if page_obj else False,
                'num_pages': paginator.num_pages if paginator else 1,
                'total_records': paginator.count if paginator else 0,
            })
        return super().render_to_response(context, **response_kwargs)


class ActionTypeCreateView(LoginRequiredMixin, CreateView):
    model = ActionType
    form_class = ActionTypeForm
    template_name = 'personnel_action/modals/modal_action_type_form.html'
    success_url = reverse_lazy('personnel_actions:action_type_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_url'] = reverse('personnel_actions:action_type_create')
        context['is_edit'] = False
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': f'Tipo de Acción "{self.object.name}" creado correctamente.'
            })
        messages.success(self.request, f'Tipo de Acción "{self.object.name}" creado correctamente.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor corrija los errores en el formulario.',
                'errors': errors_data
            }, status=400)
        return super().form_invalid(form)


class ActionTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = ActionType
    form_class = ActionTypeForm
    template_name = 'personnel_action/modals/modal_action_type_form.html'
    success_url = reverse_lazy('personnel_actions:action_type_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_url'] = reverse('personnel_actions:action_type_edit', kwargs={'pk': self.object.pk})
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': f'Tipo de Acción "{self.object.name}" actualizado correctamente.'
            })
        messages.success(self.request, f'Tipo de Acción "{self.object.name}" actualizado correctamente.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor corrija los errores en el formulario.',
                'errors': errors_data
            }, status=400)
        return super().form_invalid(form)


class ActionTypeDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(ActionType, pk=pk)
        name = obj.name

        # Verificar si existen acciones de personal vinculadas
        if PersonnelAction.objects.filter(action_type=obj).exists():
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': f'No se puede eliminar el tipo "{name}" porque ya tiene Acciones de Personal registradas.'
            }, status=400)

        try:
            obj.delete()
            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': f'Tipo de Acción "{name}" eliminado correctamente.'
            })
        except ProtectedError:
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': f'No se puede eliminar "{name}" debido a que existen registros vinculados.'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': f'Error al eliminar el registro: {str(e)}'
            }, status=500)


# ==============================================================================
# EMPLOYEE LIST FOR CREATING ACTIONS
# ==============================================================================

class EmployeeActionListView(LoginRequiredMixin, ListView):
    model = Employee
    template_name = 'personnel_action/employee_action_list.html'
    context_object_name = 'employees'
    paginate_by = 10

    def get_queryset(self):
        qs = Employee.objects.filter(is_active=True).select_related('person', 'area')
        q = self.request.GET.get('q', '').strip()
        if q:
            terms = q.split()
            for term in terms:
                qs = qs.filter(
                    Q(person__first_name__icontains=term) |
                    Q(person__last_name__icontains=term) |
                    Q(person__document_number__icontains=term)
                )
        return qs.order_by('person__last_name', 'person__first_name', 'person__document_number')

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'personnel_action/partials/partial_employee_action_list.html',
                context,
                request=self.request
            )
            page_obj = context.get('page_obj')
            paginator = context.get('paginator')
            return JsonResponse({
                'html': html,
                'success': True,
                'page_number': page_obj.number if page_obj else 1,
                'has_next': page_obj.has_next() if page_obj else False,
                'has_previous': page_obj.has_previous() if page_obj else False,
                'num_pages': paginator.num_pages if paginator else 1,
                'total_records': paginator.count if paginator else 0,
            })
        return super().render_to_response(context, **response_kwargs)


class ActionHistoryView(LoginRequiredMixin, ListView):
    model = PersonnelAction
    template_name = 'personnel_action/action_history.html'
    context_object_name = 'actions'

    def get_queryset(self):
        self.employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
        queryset = PersonnelAction.objects.filter(
            employee=self.employee,
            is_active=True
        ).select_related('action_type').order_by('-date_issue', '-number')

        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(number__icontains=query) |
                Q(action_type__name__icontains=query) |
                Q(date_issue__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filtered_employee'] = self.employee
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'personnel_action/partials/partial_action_history_table.html',
                context,
                request=self.request
            )
            return HttpResponse(html)
        return super().render_to_response(context, **response_kwargs)


class ActionDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        action = get_object_or_404(
            PersonnelAction.objects.select_related(
                'employee__person',
                'action_type',
                'action_type__default_authority_1',
                'action_type__default_authority_2',
                'action_type__default_reviewer',
                'action_type__default_register',
                'authority_1',
                'authority_2',
                'reviewer',
                'register'
            ),
            pk=pk
        )
        movement = getattr(action, 'movement', None)
        html = render_to_string(
            'personnel_action/modals/modal_action_detail.html',
            {'action': action, 'history_action': movement},
            request=request
        )
        return HttpResponse(html)


def user_search_json(request):
    if not request.user.is_authenticated:
        return JsonResponse({'results': []}, status=401)

    term = request.GET.get('term', '').strip()
    qs = User.objects.filter(is_active=True)
    if term:
        qs = qs.filter(
            Q(first_name__icontains=term) |
            Q(last_name__icontains=term) |
            Q(username__icontains=term) |
            Q(email__icontains=term)
        )

    qs = qs.order_by('first_name', 'last_name')[:20]
    results = []
    for u in qs:
        label = f"{u.signature_name or (u.first_name + ' ' + u.last_name).strip()}"
        if getattr(u, 'signature_position', None):
            label = f"{label} - {u.signature_position}"
        results.append({'id': str(u.id), 'text': f"{label} ({u.username})"})

    return JsonResponse({'results': results})


class ActionUpdateView(LoginRequiredMixin, UpdateView):
    model = PersonnelAction
    form_class = PersonnelActionForm
    template_name = 'personnel_action/modals/modal_personnel_action_form.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.is_registered:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("No se puede editar una acción ya registrada")
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == 'GET' and hasattr(self, 'object') and self.object:
            kwargs['initial'] = {
                'date_issue': self.object.date_issue.strftime('%Y-%m-%d') if self.object.date_issue else '',
                'date_effective': self.object.date_effective.strftime('%Y-%m-%d') if self.object.date_effective else '',
            }
        return kwargs

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render(request, self.template_name, {
                'form': form,
                'action': self.object,
                'employee': self.object.employee,
                'employee_id': self.object.employee.id,
                'is_edit': True
            })

        return render(request, 'personnel_action/action_form_page.html', {
            'form': form,
            'action': self.object,
            'employee': self.object.employee,
            'employee_id': self.object.employee.id,
            'is_edit': True
        })

    def form_valid(self, form):
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                if not self.object.number:
                    original = PersonnelAction.objects.get(pk=self.object.pk)
                    self.object.number = original.number

                self.object.save()
                _save_action_movement(self.object, self.request, is_create=False)

            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'success', 'success': True, 'message': 'Acción actualizada correctamente'})

            return super().form_valid(form)

        except Exception as e:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'success': False, 'message': f'Error: {str(e)}'}, status=400)
            raise e

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Error de validación en el formulario',
                'errors': errors_data
            }, status=400)
        return super().form_invalid(form)


# apps/personnel_actions/views.py dentro de ActionRegisterView.post:

class ActionRegisterView(LoginRequiredMixin, View):
    def post(self, request, pk):
        action = get_object_or_404(
            PersonnelAction.objects.select_related('employee__area', 'action_type'),
            pk=pk
        )

        if action.is_registered:
            return JsonResponse({'status': 'error', 'success': False, 'message': 'Esta acción ya está registrada'},
                                status=400)
        try:
            with transaction.atomic():
                movement = getattr(action, 'movement', None)
                if not movement:
                    raise ValueError("Esta acción no tiene un movimiento asociado.")

                effective_date = action.date_effective
                reason = _movement_reason(action)
                previous_budget_line = (
                    movement.previous_budget_line
                    if movement and movement.previous_budget_line
                    else action.employee.current_budget_line.first()
                )
                new_budget_line = movement.new_budget_line if movement and movement.new_budget_line else None

                # Banderas del tipo de acción
                is_acting_action = bool(action.action_type and getattr(action.action_type, 'is_acting', False))
                is_termination_action = bool(
                    action.action_type and getattr(action.action_type, 'is_acting_termination', False))

                # Asegurar registro de partida original en InstitutionalData si no existe
                inst_data = getattr(action.employee, 'institutional_data', None)
                if inst_data and not inst_data.original_budget_line and previous_budget_line:
                    inst_data.original_budget_line = previous_budget_line
                    inst_data.save(update_fields=['original_budget_line'])

                # ── RAMA 1: CONCLUSIÓN DE ENCARGO / REINTEGRO ─────────────────
                if is_termination_action:
                    # 1. Cerrar el encargo temporal activo del servidor
                    active_acting = BudgetAssignmentHistory.objects.filter(
                        employee=action.employee,
                        is_acting=True,
                        is_current=True
                    ).first()

                    if active_acting:
                        active_acting.end_date = effective_date - timedelta(days=1)
                        active_acting.is_current = False
                        active_acting.observation = f"Conclusión de encargo según Acción {action.number}: {reason}"
                        active_acting.save()

                        BudgetModificationHistory.objects.create(
                            budget_line=active_acting.budget_line,
                            modified_by=request.user,
                            modification_type='RELEASE',
                            field_name='Finalización de Encargo',
                            old_value=f'Encargada a {action.employee.person.full_name}',
                            new_value='Retorno a funciones exclusivas del titular',
                            reason=reason,
                        )

                    # 2. Reintegrar al área original si hubo cambio de unidad
                    if inst_data and inst_data.original_dependency:
                        action.employee.area = inst_data.original_dependency
                        action.employee.save(update_fields=['area'])

                # ── RAMA 2: NUEVO ENCARGO / SUBROGACIÓN ───────────────────────
                elif is_acting_action and new_budget_line:
                    # Actualización de Área si el encargo lo especifica
                    if movement and movement.new_unit:
                        try:
                            unit = AdministrativeUnit.objects.get(name=movement.new_unit)
                            action.employee.area = unit
                            action.employee.save(update_fields=['area'])
                        except AdministrativeUnit.DoesNotExist:
                            pass

                    # No se libera la partida del titular ni la del empleado
                    BudgetAssignmentHistory.objects.create(
                        budget_line=new_budget_line,
                        employee=action.employee,
                        start_date=effective_date,
                        end_date=None,
                        is_current=True,
                        is_acting=True,
                        observation=f"Encargo según Acción {action.number}: {reason}"
                    )
                    BudgetModificationHistory.objects.create(
                        budget_line=new_budget_line,
                        modified_by=request.user,
                        modification_type='ASSIGNMENT',
                        field_name='Encargo Temporal',
                        old_value='Titular en funciones',
                        new_value=f'Encargada a {action.employee.person.full_name}',
                        reason=reason,
                    )

                # ── RAMA 3: CASO REGULAR / DEFINITIVO (NOMBRAMIENTO, ASCENSO, TRASLADO)
                elif new_budget_line:
                    # Actualización de Área regular
                    if movement and movement.new_unit:
                        try:
                            unit = AdministrativeUnit.objects.get(name=movement.new_unit)
                            action.employee.area = unit
                            action.employee.save(update_fields=['area'])
                        except AdministrativeUnit.DoesNotExist:
                            pass

                    libre_status = CatalogItem.objects.get(code='LIBRE', catalog__code='BUDGET_STATUS')
                    occupied_status = CatalogItem.objects.get(code='OCUPADA', catalog__code='BUDGET_STATUS')

                    if previous_budget_line and previous_budget_line.pk != new_budget_line.pk:
                        release_date = effective_date - timedelta(days=1)
                        previous_history = BudgetAssignmentHistory.objects.filter(
                            budget_line=previous_budget_line,
                            employee=action.employee,
                            is_current=True
                        ).first()

                        if previous_history:
                            previous_history.end_date = release_date
                            previous_history.is_current = False
                            previous_history.observation = reason
                            previous_history.save()

                        previous_budget_line.current_employee = None
                        previous_budget_line.status_item = libre_status
                        previous_budget_line.save(modified_by=request.user)

                        BudgetModificationHistory.objects.create(
                            budget_line=previous_budget_line,
                            modified_by=request.user,
                            modification_type='RELEASE',
                            field_name='Estado y Ocupante',
                            old_value=f'Ocupada por {action.employee.person.full_name}',
                            new_value='Libre',
                            reason=reason,
                        )

                    if previous_budget_line is None or previous_budget_line.pk != new_budget_line.pk:
                        new_budget_line.current_employee = action.employee
                        new_budget_line.status_item = occupied_status
                        new_budget_line.save(modified_by=request.user)

                        new_history = BudgetAssignmentHistory.objects.filter(
                            budget_line=new_budget_line,
                            is_current=True
                        ).first()
                        if new_history:
                            new_history.is_current = False
                            new_history.end_date = effective_date - timedelta(days=1)
                            new_history.save()

                        BudgetAssignmentHistory.objects.create(
                            budget_line=new_budget_line,
                            employee=action.employee,
                            start_date=effective_date,
                            is_current=True,
                            is_acting=False,
                            observation=reason,
                        )

                        if inst_data:
                            inst_data.original_budget_line = new_budget_line
                            inst_data.save(update_fields=['original_budget_line'])

                # Marcar la acción como registrada
                action.is_registered = True
                action.register = request.user
                action.save(update_fields=['is_registered', 'register'])

        except Exception as e:
            return JsonResponse(
                {'status': 'error', 'success': False, 'message': f'No se pudo registrar la acción: {str(e)}'},
                status=400
            )

        return JsonResponse(
            {'status': 'success', 'success': True, 'message': 'Acción registrada correctamente'})


class ActionPDFView(LoginRequiredMixin, View):
    def get(self, request, pk):
        action = get_object_or_404(
            PersonnelAction.objects.select_related(
                'employee__person',
                'employee__person__document_type',
                'action_type',
                'employee__area',
                'action_type__default_authority_1',
                'action_type__default_authority_2',
                'action_type__default_reviewer',
                'action_type__default_register',
                'authority_1',
                'authority_2',
                'reviewer',
                'register',
                'elaboration',
                'created_by'
            ),
            pk=pk
        )

        movement = getattr(action, 'movement', None)
        current_unit = action.employee.area if action.employee else None
        proposed_unit = None

        if movement and movement.new_unit:
            try:
                proposed_unit = AdministrativeUnit.objects.get(name=movement.new_unit)
            except AdministrativeUnit.DoesNotExist:
                proposed_unit = None

        current_budget = None
        proposed_budget = None

        management_period = getattr(action, 'management_period', None)
        contract_type = getattr(management_period, 'contract_type', None) if management_period else None
        contract_category = getattr(contract_type, 'contract_type_category', '') if contract_type else ''
        show_without_current_situation = bool(contract_category == 'ACCION_PERSONAL')

        if movement and movement.previous_budget_line:
            current_budget = movement.previous_budget_line
        elif management_period and getattr(management_period, 'budget_line', None):
            current_budget = management_period.budget_line
        else:
            current_budget = BudgetLine.objects.select_related(
                'position_item', 'group_item', 'grade_item', 'activity__project__subprogram__program'
            ).filter(current_employee_id=action.employee.pk).first()

        if movement and movement.new_budget_line:
            proposed_budget = movement.new_budget_line

        if show_without_current_situation:
            current_unit = None
            current_budget = None
            if movement and movement.new_unit:
                proposed_unit = proposed_unit
            elif management_period:
                proposed_unit = getattr(management_period, 'administrative_unit', None)

            if movement and movement.new_budget_line:
                proposed_budget = movement.new_budget_line
            elif management_period:
                proposed_budget = getattr(management_period, 'budget_line', None)

        auth1_user = action.authority_1 or action.action_type.default_authority_1
        auth2_user = action.authority_2 or action.action_type.default_authority_2
        reviewer_user = action.reviewer or action.action_type.default_reviewer
        register_user = action.register or action.action_type.default_register
        elaboration_user = action.elaboration or action.created_by

        signatures = {
            'auth1_name': auth1_user.signature_name if auth1_user else '',
            'auth1_pos': auth1_user.signature_position if auth1_user else 'AUTORIDAD NOMINADORA O DELEGADO',
            'auth2_name': auth2_user.signature_name if auth2_user else '',
            'auth2_pos': auth2_user.signature_position if auth2_user else 'RESPONSABLE DE TALENTO HUMANO',
            'reviewer_name': reviewer_user.signature_name if reviewer_user else '',
            'reviewer_pos': reviewer_user.signature_position if reviewer_user else 'REVISIÓN',
            'register_name': register_user.signature_name if register_user else '',
            'register_pos': register_user.signature_position if register_user else 'REGISTRO',
            'elaboration_name': elaboration_user.signature_name if elaboration_user else '',
            'elaboration_pos': elaboration_user.signature_position if elaboration_user else 'ELABORACIÓN',
        }

        try:
            from weasyprint import HTML

            context = {
                'action': action,
                'movement': movement,
                'current_unit': current_unit,
                'proposed_unit': proposed_unit,
                'current_unit_snapshot': _unit_snapshot(current_unit),
                'proposed_unit_snapshot': _unit_snapshot(proposed_unit) if proposed_unit else None,
                'current_budget': _budget_snapshot(current_budget),
                'proposed_budget': _budget_snapshot(proposed_budget) if proposed_budget else None,
                'show_without_current_situation': show_without_current_situation,
                'signatures': signatures,
                'standard_action_types': [
                    'INGRESO', 'TRASPASO', 'INCREMENTO DE RMU', 'REVISIÓN CLAS. PUEST.',
                    'REINGRESO', 'CAMBIO ADMINISTRATIVO', 'SUBROGACION', 'RESTITUCION',
                    'INTERC. VOLUNTARIO', 'ENCARGO', 'REINTEGRO', 'LICENCIA',
                    'CESACIÓN DE FUNCIONES', 'ASCENSO', 'COMISIÓN DE SERVICIOS',
                    'DESTITUCIÓN', 'TRASLADO', 'SANCIONES', 'VACACIONES'
                ],
            }

            html = render_to_string('personnel_action/pdf/action_pdf.html', context, request=request)
            pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()

            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            filename = f'Accion_{str(action.number).replace("/", "-")}.pdf'
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response

        except Exception as e:
            return HttpResponse(f"<h3>Error al generar PDF:</h3><p>{str(e)}</p>", status=500)


# ==============================================================================
# APIS FOR ADMINISTRATIVE UNITS AND BUDGET LINES
# ==============================================================================

class AdministrativeUnitChildrenJsonView(LoginRequiredMixin, View):
    def get(self, request):
        parent_id = request.GET.get('parent_id')

        if not parent_id:
            units = AdministrativeUnit.objects.filter(is_active=True, parent__isnull=True).values('id',
                                                                                                  'name').order_by(
                'name')
        else:
            units = AdministrativeUnit.objects.filter(is_active=True, parent_id=parent_id).values('id',
                                                                                                  'name').order_by(
                'name')

        result = []
        for unit in units:
            has_children = AdministrativeUnit.objects.filter(parent_id=unit['id'], is_active=True).exists()
            result.append({
                'id': unit['id'],
                'name': unit['name'],
                'has_children': has_children
            })

        return JsonResponse({'success': True, 'units': result})


class SearchBudgetLinesJsonView(LoginRequiredMixin, View):
    def get(self, request):
        search_term = request.GET.get('term', '').strip()

        qs = BudgetLine.objects.filter(
            is_active=True
        ).select_related(
            'position_item',
            'activity__project__subprogram__program',
            'current_employee__person',
            'status_item'
        )

        if search_term:
            qs = qs.filter(
                Q(code__icontains=search_term) |
                Q(number_individual__icontains=search_term) |
                Q(position_item__name__icontains=search_term) |
                Q(current_employee__person__first_name__icontains=search_term) |
                Q(current_employee__person__last_name__icontains=search_term)
            )

        qs = qs.order_by('code')[:40]
        results = []
        for line in qs:
            program_name = ''
            try:
                if line.activity and line.activity.project and line.activity.project.subprogram:
                    program_name = line.activity.project.subprogram.program.name or ''
            except Exception:
                program_name = ''

            position_name = line.position_item.name if line.position_item else 'Sin cargo asignado'
            display_code = line.number_individual or line.code or f"Partida #{line.id}"
            remun = float(line.remuneration) if line.remuneration else 0.0

            # Indicador de estado y ocupante para claridad en el selector
            if line.current_employee and getattr(line.current_employee, 'person', None):
                occupant_info = f"[OCUPADA: {line.current_employee.person.full_name}]"
            else:
                occupant_info = "[LIBRE]"

            results.append({
                'id': line.id,
                'text': f"{display_code} - {position_name} (RMU: ${remun:.2f}) {occupant_info}",
                'code': display_code,
                'position': position_name,
                'remuneration': f"{remun:.2f}",
                'program': program_name or 'N/A'
            })

        return JsonResponse({'results': results})


class ActionTypeDetailAPIView(LoginRequiredMixin, View):
    def get(self, request, pk):
        action_type = get_object_or_404(
            ActionType.objects.select_related(
                'default_authority_1',
                'default_authority_2',
                'default_reviewer',
                'default_register',
            ),
            pk=pk
        )
        requires_budget = action_type.requires_budget_movement or action_type.is_acting

        def _user_label(user):
            if not user:
                return ''
            name = getattr(user, 'signature_name', None) or user.get_full_name() or user.username
            pos = getattr(user, 'signature_position', '')
            return f"{name} - {pos}" if pos else name

        return JsonResponse({
            'success': True,
            'is_acting': bool(action_type.is_acting),
            'requires_budget': bool(requires_budget),
            'requires_unit': bool(action_type.requires_unit_movement),
            'auth1_id': action_type.default_authority_1_id,
            'auth1_text': _user_label(action_type.default_authority_1),
            'auth2_id': action_type.default_authority_2_id,
            'auth2_text': _user_label(action_type.default_authority_2),
            'reviewer_id': action_type.default_reviewer_id,
            'reviewer_text': _user_label(action_type.default_reviewer),
            'register_id': action_type.default_register_id,
            'register_text': _user_label(action_type.default_register),
        })
