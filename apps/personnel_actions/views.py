import json
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView

from budget.models import BudgetLine, BudgetAssignmentHistory, BudgetModificationHistory
from core.models import CatalogItem, User
from institution.models import AdministrativeUnit
from .forms import PersonnelActionForm, ActionTypeForm
from .models import PersonnelAction, ActionMovement, ActionType


def _save_action_movement(action, request, is_create=False):
    """
    Función auxiliar para procesar y guardar el movimiento (Situación Actual vs Propuesta)
    """
    from budget.models import BudgetLine
    from institution.models import AdministrativeUnit

    # 1. Obtener o crear el objeto de movimiento
    if is_create:
        movement = ActionMovement(personnel_action=action)
        # Solo en la creación capturamos la "Situación Actual" (Snapshot)
        employee = action.employee
        current_budget = employee.current_budget_line.first()
        current_unit = employee.area

        movement.previous_unit = current_unit.name if current_unit else ''
        movement.previous_budget_line = current_budget
        movement.previous_position = current_budget.position_item.name if current_budget and current_budget.position_item else ''
        movement.previous_remuneration = current_budget.remuneration if current_budget else 0
    else:
        # En edición, buscamos el movimiento existente
        movement, _ = ActionMovement.objects.get_or_create(personnel_action=action)

    # 2. Capturar "Situación Propuesta" desde los inputs ocultos que genera el JS
    new_unit_id = request.POST.get('movement_new_unit')
    new_budget_line_id = request.POST.get('movement_new_budget_line')
    location_text = request.POST.get('location_text')  # Si tienes este campo en el form

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
        1: 'enero',
        2: 'febrero',
        3: 'marzo',
        4: 'abril',
        5: 'mayo',
        6: 'junio',
        7: 'julio',
        8: 'agosto',
        9: 'septiembre',
        10: 'octubre',
        11: 'noviembre',
        12: 'diciembre',
    }

    return f"{date_value.day} de {months.get(date_value.month, '')}"


def _movement_reason(action):
    action_name = (action.action_type.name or '').strip().lower()
    if not action_name:
        action_name = 'acción de personal'
    return f"{action_name} a partir del {_spanish_date_without_year(action.date_effective)}"


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
        # Filtros básicos y avanzados
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
            # Búsqueda combinada: divide el término en palabras
            # y busca registros que contengan todas las palabras en nombres/apellidos
            terms = q.split()
            if len(terms) > 1:
                # Búsqueda combinada: todos los términos deben estar en nombres/apellidos
                query = Q()
                for term in terms:
                    query &= (
                            Q(employee__person__first_name__icontains=term) |
                            Q(employee__person__last_name__icontains=term)
                    )
                qs = qs.filter(query)
            else:
                # Búsqueda simple: un solo término
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

        # Aplicar orden dinámico si se solicita
        order_by = self.request.GET.get('order_by', '').strip()
        direction = self.request.GET.get('direction', 'asc').strip().lower()
        if order_by:
            prefix = '-' if direction == 'desc' else ''
            try:
                ordered = qs.order_by(f"{prefix}{order_by}")
                return ordered[:3000]
            except Exception:
                pass

        # Orden por defecto y limitar a últimos 3000 registros
        ordered = qs.order_by('-pk')
        return ordered[:3000]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añadir lista de tipos para el select de filtros
        context['action_types'] = ActionType.objects.all()
        return context

    def render_to_response(self, context, **response_kwargs):
        """Si es AJAX, devolver JSON con HTML de la tabla"""
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html_table = render_to_string(
                'personnel_action/partials/partial_personnel_action_admin_table.html',
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
        """Devolver el formulario vacío o con empleado preseleccionado (Blindado)"""
        try:
            from employee.models import Employee

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
            import traceback
            print("🔥 ERROR CRÍTICO AL ABRIR EL MODAL DE ACCIÓN DE PERSONAL:")
            traceback.print_exc()
            return HttpResponse(f"Error interno del servidor: {str(e)}", status=500)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.created_by = self.request.user
                self.object.elaboration = self.request.user

                # Asignación automática de firmas
                if self.object.action_type:
                    self.object.authority_1 = self.object.action_type.default_authority_1
                    self.object.authority_2 = self.object.action_type.default_authority_2
                    self.object.reviewer = self.object.action_type.default_reviewer
                    self.object.register = self.object.action_type.default_register

                # Lógica de número automático
                if not self.object.number or self.object.number.strip() == '':
                    from datetime import datetime
                    year = datetime.now().year
                    last_action = PersonnelAction.objects.filter(number__endswith=f'-{year}').order_by(
                        '-created_at').first()
                    new_num = 1
                    if last_action:
                        try:
                            new_num = int(last_action.number.split('-')[0]) + 1
                        except:
                            pass
                    self.object.number = f'{new_num:04d}-{year}'

                self.object.save()

                _save_action_movement(self.object, self.request, is_create=True)

            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Acción de personal creada correctamente'})

            return super().form_valid(form)

        except Exception as e:
            import traceback
            traceback.print_exc()
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Fallo interno: {str(e)}'}, status=500)
            raise e

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'success': False,
                'message': 'Error de validación',
                'errors': errors_data
            }, status=400)

        return super().form_invalid(form)


class ActionInactivateView(LoginRequiredMixin, View):
    """Cambia el estado is_active a False (Anulación)"""

    def post(self, request, pk):
        action = get_object_or_404(PersonnelAction, pk=pk)

        if not request.user.has_perm('personnel_actions.delete_personnelaction'):
            return JsonResponse({'success': False, 'message': 'No tienes permiso'}, status=403)
        action.is_active = False
        action.save()

        return JsonResponse({
            'success': True,
            'message': f'Acción {action.number} inactivada correctamente.'
        })


class ActionTypeListView(LoginRequiredMixin, ListView):
    model = ActionType
    template_name = 'personnel_action/action_type_list.html'
    context_object_name = 'types'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.GET.get('q')
        status = self.request.GET.get('status')

        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query))

        if status == 'true':
            qs = qs.filter(is_active=True)
        elif status == 'false':
            qs = qs.filter(is_active=False)

        return qs.order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Estadísticas Globales
        ctx['stats_total'] = ActionType.objects.count()
        ctx['stats_active'] = ActionType.objects.filter(is_active=True).count()
        ctx['stats_inactive'] = ActionType.objects.filter(is_active=False).count()
        return ctx

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['personnel_action/partials/partial_action_type_list.html']
        return [self.template_name]


class ActionTypeCreateOrUpdateView(LoginRequiredMixin, View):
    """Maneja Crear (POST sin ID) y Actualizar (POST con ID) de Tipos de Acción"""

    def post(self, request, pk=None):
        try:
            # 1. Leer el JSON enviado por Vue
            data = json.loads(request.body)

            # 2. LIMPIEZA VITAL: Convertir strings vacíos a None
            firmas_fields = ['default_authority_1', 'default_authority_2', 'default_reviewer', 'default_register']
            for field in firmas_fields:
                if data.get(field) == '':
                    data[field] = None

            # 3. Instanciar el formulario (Editar si hay PK, Crear si no hay)
            if pk:
                instance = get_object_or_404(ActionType, pk=pk)
                form = ActionTypeForm(data, instance=instance)
            else:
                form = ActionTypeForm(data)

            # 4. Validar y Guardar
            if form.is_valid():
                form.save()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'El formato JSON enviado es inválido.'}, status=400)

        except Exception as e:
            print(f"🔥 ERROR CRÍTICO EN ActionTypeCreateOrUpdateView: {str(e)}")
            return JsonResponse({'success': False, 'message': f"Error interno: {str(e)}"}, status=500)


class ActionTypeDetailJsonView(LoginRequiredMixin, View):
    """Devuelve los datos de un registro en JSON para cargarlos en Vue"""

    def get(self, request, pk):
        obj = get_object_or_404(ActionType, pk=pk)
        data = {
            'id': obj.pk,
            'name': obj.name,
            'code': obj.code,
            'is_active': obj.is_active,

            # Devolvemos ID y Texto (Nombre de firma) para inyectar en Select2
            'auth1_id': obj.default_authority_1.id if obj.default_authority_1 else None,
            'auth1_text': obj.default_authority_1.signature_name if obj.default_authority_1 else '',

            'auth2_id': obj.default_authority_2.id if obj.default_authority_2 else None,
            'auth2_text': obj.default_authority_2.signature_name if obj.default_authority_2 else '',

            'reviewer_id': obj.default_reviewer.id if obj.default_reviewer else None,
            'reviewer_text': obj.default_reviewer.signature_name if obj.default_reviewer else '',

            'register_id': obj.default_register.id if obj.default_register else None,
            'register_text': obj.default_register.signature_name if obj.default_register else '',
        }
        return JsonResponse(data)


class ActionTypeDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(ActionType, pk=pk)
        obj.delete()
        types = ActionType.objects.all().order_by('name')
        html_table = render_to_string(
            'personnel_action/partials/partial_action_type_list.html',
            {'types': types},
            request=request
        )
        return JsonResponse({'success': True, 'html': html_table})


class ActionTypeCreateView(LoginRequiredMixin, CreateView):
    model = ActionType
    form_class = ActionTypeForm
    template_name = 'personnel_action/modals/modal_action_type_form.html'

    def form_valid(self, form):
        form.save()
        return render(self.request, 'personnel_action/partials/partial_action_type_list.html', {
            'types': ActionType.objects.all().order_by('name')
        })


class ActionTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = ActionType
    form_class = ActionTypeForm
    template_name = 'personnel_action/modals/modal_action_type_form.html'

    def form_valid(self, form):
        form.save()
        return render(self.request, 'personnel_action/partials/partial_action_type_list.html', {
            'types': ActionType.objects.all().order_by('name')
        })


# Vista especial para cambiar estado (Toggle) vía AJAX
class ActionTypeToggleStatusView(LoginRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(ActionType, pk=pk)
        obj.is_active = not obj.is_active
        obj.save()
        types = ActionType.objects.all().order_by('name')
        html_table = render_to_string(
            'personnel_action/partials/partial_action_type_list.html',
            {'types': types},
            request=request
        )
        return JsonResponse({'success': True, 'html': html_table})


class EmployeeActionListView(LoginRequiredMixin, ListView):
    """View to list active employees for generating personnel actions"""
    model = PersonnelAction
    template_name = 'personnel_action/employee_action_list.html'
    context_object_name = 'employees'
    paginate_by = 10

    def get_queryset(self):
        from employee.models import Employee

        queryset = Employee.objects.filter(
            is_active=True
        ).select_related(
            'person',
            'area'
        ).order_by('person__last_name', 'person__first_name')

        # Search filter
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(person__first_name__icontains=query) |
                Q(person__last_name__icontains=query) |
                Q(person__document_number__icontains=query)
            )

        return queryset

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            from employee.models import Employee

            html = render_to_string(
                'personnel_action/partials/partial_employee_action_list.html',
                context,
                request=self.request
            )

            # Pagination information
            page_obj = context.get('page_obj')
            if page_obj:
                pagination_data = {
                    'start_index': page_obj.start_index(),
                    'end_index': page_obj.end_index(),
                    'total_count': page_obj.paginator.count,
                    'current_page': page_obj.number,
                    'total_pages': page_obj.paginator.num_pages,
                    'has_previous': page_obj.has_previous(),
                    'has_next': page_obj.has_next(),
                }
            else:
                pagination_data = {
                    'start_index': 0,
                    'end_index': 0,
                    'total_count': 0,
                    'current_page': 1,
                    'total_pages': 1,
                    'has_previous': False,
                    'has_next': False,
                }

            return JsonResponse({
                'html': html,
                'pagination': pagination_data
            })
        return super().render_to_response(context, **response_kwargs)


class ActionHistoryView(LoginRequiredMixin, ListView):
    """Vista para mostrar el historial de acciones de un empleado específico"""
    model = PersonnelAction
    template_name = 'personnel_action/action_history.html'
    context_object_name = 'actions'
    paginate_by = 10

    def get_queryset(self):
        from employee.models import Employee
        self.employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])

        queryset = PersonnelAction.objects.filter(
            employee=self.employee
        ).select_related('action_type').order_by('-date_issue', '-number')

        # Búsqueda
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
            page_obj = context['page_obj']

            return JsonResponse({
                'html': html,
                'page_number': page_obj.number,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'num_pages': context['paginator'].num_pages,
                'total_records': context['paginator'].count
            })
        return super().render_to_response(context, **response_kwargs)


class ActionDetailView(LoginRequiredMixin, View):
    """Vista para mostrar detalles de una acción en modal"""

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

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'html': html})

        return HttpResponse(html)


def user_search_json(request):
    """JSON endpoint para buscar usuarios (Select2 AJAX)"""
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
    """Vista para editar una acción (solo si no está registrada)"""
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
        """Sobrescribir para pasar datos iniciales con fechas en formato correcto"""
        kwargs = super().get_form_kwargs()

        # Si es GET y tenemos un objeto, preparar initial data con fechas correctas
        if self.request.method == 'GET' and hasattr(self, 'object') and self.object:
            kwargs['initial'] = {
                'date_issue': self.object.date_issue.strftime('%Y-%m-%d') if self.object.date_issue else '',
                'date_effective': self.object.date_effective.strftime('%Y-%m-%d') if self.object.date_effective else '',
            }

        return kwargs

    def get(self, request, *args, **kwargs):
        """Devolver el formulario con los datos de la acción"""
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

        # Si es vista directa, renderizar página completa que incluya el modal
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
                return JsonResponse({'success': True, 'message': 'Acción actualizada correctamente'})

            return super().form_valid(form)

        except Exception as e:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=400)
            raise e

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
        return super().form_invalid(form)


class ActionRegisterView(LoginRequiredMixin, View):
    """Vista para registrar una acción (cambiar is_registered a True)"""

    def post(self, request, pk):
        action = get_object_or_404(
            PersonnelAction.objects.select_related('employee__area', 'action_type'),
            pk=pk
        )

        if action.is_registered:
            return JsonResponse({
                'success': False,
                'message': 'Esta acción ya está registrada'
            }, status=400)

        try:
            with transaction.atomic():
                movement = getattr(action, 'movement', None)
                if not movement:
                    raise ValueError("Esta acción no tiene un movimiento asociado.")
                effective_date = action.date_effective
                reason = _movement_reason(action)
                previous_budget_line = movement.previous_budget_line if movement and movement.previous_budget_line else action.employee.current_budget_line.first()
                new_budget_line = movement.new_budget_line if movement and movement.new_budget_line else None

                if new_budget_line and previous_budget_line and previous_budget_line.pk != new_budget_line.pk:
                    previous_history = BudgetAssignmentHistory.objects.filter(
                        budget_line=previous_budget_line,
                        employee=action.employee,
                        is_current=True
                    ).first()

                    if previous_history:
                        release_date = effective_date - timedelta(days=1)
                        if previous_history.start_date and release_date < previous_history.start_date:
                            raise ValueError(
                                'La fecha efectiva de la acción no permite liberar la partida antes de su inicio.')

                if movement and movement.new_unit:
                    from institution.models import AdministrativeUnit
                    try:
                        unit = AdministrativeUnit.objects.get(name=movement.new_unit)
                        action.employee.area = unit
                        action.employee.save(update_fields=['area'])
                    except AdministrativeUnit.DoesNotExist:
                        # no se encontró unidad con ese nombre; no actualizar área
                        pass

                if new_budget_line:
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
                            observation=reason,
                        )

                        BudgetModificationHistory.objects.create(
                            budget_line=new_budget_line,
                            modified_by=request.user,
                            modification_type='ASSIGNMENT',
                            field_name='Estado y Ocupante',
                            old_value='Libre',
                            new_value=f'Ocupada por {action.employee.person.full_name}',
                            reason=reason,
                        )

                action.is_registered = True
                action.register = request.user
                action.save(update_fields=['is_registered', 'register'])
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'No se pudo registrar la acción: {str(e)}'
            }, status=400)

        return JsonResponse({
            'success': True,
            'message': 'Acción registrada correctamente'
        })


class ActionPDFView(LoginRequiredMixin, View):
    """Vista para generar PDF de la acción"""

    def get(self, request, pk):
        action = get_object_or_404(
            PersonnelAction.objects.select_related(
                'employee__person',
                'action_type',
                'employee__area',
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

        # Para datos migrados, 'previous_unit' y 'new_unit' son CharFields.
        # Debemos obtener los objetos AdministrativeUnit correspondientes.
        current_unit = None
        if movement and movement.new_unit:
            try:
                proposed_unit = AdministrativeUnit.objects.get(name=movement.new_unit)
            except AdministrativeUnit.DoesNotExist:
                proposed_unit = None
        if not current_unit:
            current_unit = action.employee.area  # Fallback al área actual del empleado

        proposed_unit = None
        if movement and movement.new_unit:
            try:
                proposed_unit = AdministrativeUnit.objects.get(name=movement.new_unit)
            except AdministrativeUnit.DoesNotExist:
                proposed_unit = None

        current_budget = None
        proposed_budget = None

        management_period = getattr(action, 'management_period', None)
        show_without_current_situation = bool(
            management_period
            and getattr(getattr(management_period, 'contract_type', None), 'contract_type_category',
                        '') == 'ACCION_PERSONAL'
        )

        if movement and movement.previous_budget_line:
            current_budget = movement.previous_budget_line
        elif management_period and management_period.budget_line:
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
            proposed_unit = movement.new_unit if movement and movement.new_unit else management_period.administrative_unit
            proposed_budget = movement.new_budget_line if movement and movement.new_budget_line else management_period.budget_line

        try:
            from weasyprint import HTML

            current_unit_snapshot = _unit_snapshot(current_unit)
            proposed_unit_snapshot = _unit_snapshot(proposed_unit) if proposed_unit else None

            html = render_to_string(
                'personnel_action/pdf/action_pdf.html',
                {
                    'action': action,
                    'movement': movement,
                    'current_unit': current_unit,
                    'proposed_unit': proposed_unit,
                    'current_unit_snapshot': current_unit_snapshot,
                    'proposed_unit_snapshot': proposed_unit_snapshot,
                    'current_budget': _budget_snapshot(current_budget),
                    'proposed_budget': _budget_snapshot(proposed_budget) if proposed_budget else None,
                    # Pasará Limpio como None si no cambió
                    'show_without_current_situation': show_without_current_situation,
                    'standard_action_types': ['INGRESO', 'TRASPASO', 'INCREMENTO DE RMU', 'REVISIÓN CLAS. PUEST.',
                                              'REINGRESO', 'CAMBIO ADMINISTRATIVO', 'SUBROGACION', 'RESTITUCION',
                                              'INTERC. VOLUNTARIO', 'ENCARGO', 'REINTEGRO', 'LICENCIA',
                                              'CESACIÓN DE FUNCIONES', 'ASCENSO', 'COMISIÓN DE SERVICIOS',
                                              'DESTITUCIÓN', 'TRASLADO', 'SANCIONES', 'VACACIONES'],
                },
                request=request
            )
            pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            filename = f'Accion_{action.number.replace("/", "-")}.pdf'
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
        except Exception:
            return HttpResponse('Error al generar el PDF de la acción', status=500)


# ==========================================
# APIs PARA MODAL DE ACCIONES DE PERSONAL
# ==========================================

class AdministrativeUnitChildrenJsonView(LoginRequiredMixin, View):
    """API para obtener unidades administrativas en cascada (Para Reubicar)"""

    def get(self, request):
        parent_id = request.GET.get('parent_id')

        if not parent_id:
            # Nivel raíz: unidades sin padre (nivel 1)
            from institution.models import AdministrativeUnit
            units = AdministrativeUnit.objects.filter(
                is_active=True,
                parent__isnull=True
            ).values('id', 'name').order_by('name')
        else:
            # Unidades que dependen de parent_id
            from institution.models import AdministrativeUnit
            units = AdministrativeUnit.objects.filter(
                is_active=True,
                parent_id=parent_id
            ).values('id', 'name').order_by('name')

        # Convertir a lista y agregar información de si tienen hijos
        result = []
        for unit in units:
            from institution.models import AdministrativeUnit
            has_children = AdministrativeUnit.objects.filter(
                parent_id=unit['id'],
                is_active=True
            ).exists()
            result.append({
                'id': unit['id'],
                'name': unit['name'],
                'has_children': has_children
            })

        return JsonResponse({
            'success': True,
            'units': result
        })


class SearchBudgetLinesJsonView(LoginRequiredMixin, View):
    """API para buscar partidas presupuestarias con estado LIBRE"""

    def get(self, request):
        search_term = request.GET.get('term', '').strip()

        # Base queryset: partidas con estado LIBRE
        qs = BudgetLine.objects.filter(
            status_item__code='LIBRE'
        ).select_related(
            'activity__project__subprogram__program',
            'position_item',
            'current_employee__person'
        ).only(
            'id', 'code', 'number_individual', 'remuneration',
            'activity__project__subprogram__program__name',
            'position_item__name',
            'current_employee__person__first_name',
            'current_employee__person__last_name'
        )

        # Filtrar por búsqueda si existe
        if search_term:
            qs = qs.filter(
                Q(code__icontains=search_term) |
                Q(number_individual__icontains=search_term) |
                Q(position_item__name__icontains=search_term)
            )

        # Limitar los resultados
        qs = qs[:20]

        # Formato de respuesta para Select2
        results = []
        for line in qs:
            program_name = line.activity.project.subprogram.program.name if line.activity else ''
            position_name = line.position_item.name if line.position_item else ''

            results.append({
                'id': line.id,
                'text': f"{line.code} - {position_name} - RMU: ${line.remuneration:.2f}",
                'code': line.code,
                'position': position_name,
                'remuneration': str(line.remuneration),
                'program': program_name
            })

        return JsonResponse({'results': results})
