from django.db.models import Q
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponse

from budget.models import BudgetLine
from .models import PersonnelAction, ActionMovement, ActionType
from .forms import PersonnelActionForm, ActionMovementForm, ActionTypeForm


class PersonnelActionListView(LoginRequiredMixin, ListView):
    model = PersonnelAction
    template_name = 'personnel_action/personnel_action_list.html'
    context_object_name = 'actions'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().select_related('employee__person', 'action_type')

        # Filtro de búsqueda
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(employee__person__first_name__icontains=q) |
                Q(employee__person__last_name__icontains=q) |
                Q(employee__person__document_number__icontains=q) |
                Q(number__icontains=q) |
                Q(action_type__name__icontains=q)
            )

        return qs.order_by('-date_issue', '-number')

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
    model = PersonnelAction
    form_class = PersonnelActionForm
    template_name = 'personnel_action/modals/modal_personnel_action_form.html'

    def get(self, request, *args, **kwargs):
        """Devolver el formulario vacío o con empleado preseleccionado"""
        from employee.models import Employee

        employee_id = request.GET.get('employee_id')
        employee = None

        if employee_id:
            employee = get_object_or_404(Employee, pk=employee_id)
            form = self.form_class()
        else:
            form = self.form_class()

        # Si es AJAX, devolver solo el HTML del formulario
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render(request, self.template_name, {
                'form': form,
                'employee': employee,
                'employee_id': employee_id
            })

        # Si no es AJAX, renderizar la página completa
        return render(request, self.template_name, {'form': form})

    def form_valid(self, form):
        # Lógica transaccional para guardar Cabecera + Detalle
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user

            # Generar número automáticamente si está vacío
            if not self.object.number or self.object.number.strip() == '':
                from datetime import datetime
                year = datetime.now().year
                last_action = PersonnelAction.objects.filter(
                    number__endswith=f'-{year}'
                ).order_by('-created_at').first()

                if last_action:
                    try:
                        last_num = int(last_action.number.split('-')[0])
                        new_num = last_num + 1
                    except (ValueError, IndexError):
                        new_num = 1
                else:
                    new_num = 1

                self.object.number = f'{new_num:04d}-{year}'

            self.object.save()

            # Crear detalle vacío o procesar segundo form aquí si se envía junto
            ActionMovement.objects.create(
                personnel_action=self.object,
                previous_remuneration=0  # Aquí podrías buscar datos actuales del empleado
            )

        # Responder con JSON si es AJAX
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Acción de personal creada correctamente'
            })

        return render(self.request, 'personnel_action/partials/partial_personnel_action_list.html', {
            'actions': PersonnelAction.objects.select_related('employee', 'action_type').all().order_by('-date_issue')[
                       :10]
        })

    def form_invalid(self, form):
        # Si es AJAX, devolver errores en JSON
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)

        return super().form_invalid(form)


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
    """Maneja Crear (POST sin ID) y Actualizar (POST con ID)"""

    def post(self, request, pk=None):
        if pk:
            instance = get_object_or_404(ActionType, pk=pk)
            form = ActionTypeForm(request.POST, instance=instance)
        else:
            form = ActionTypeForm(request.POST)

        if form.is_valid():
            form.save()
            # Renderizamos la tabla actualizada para devolverla
            types = ActionType.objects.all().order_by('name')
            html_table = render_to_string(
                'personnel_action/partials/partial_action_type_list.html',
                {'types': types},
                request=request
            )
            return JsonResponse({'success': True, 'html': html_table})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ActionTypeDetailJsonView(LoginRequiredMixin, View):
    """Devuelve los datos de un registro en JSON para cargarlos en Vue"""

    def get(self, request, pk):
        obj = get_object_or_404(ActionType, pk=pk)
        data = {
            'id': obj.pk,
            'name': obj.name,
            'code': obj.code,
            'is_active': obj.is_active
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
            PersonnelAction.objects.select_related('employee__person', 'action_type'),
            pk=pk
        )

        html = render_to_string(
            'personnel_action/modals/modal_action_detail.html',
            {'action': action},
            request=request
        )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'html': html})

        from django.http import HttpResponse
        return HttpResponse(html)


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

        return render(request, self.template_name, {
            'form': form,
            'action': self.object,
            'is_edit': True
        })

    def form_valid(self, form):
        self.object = form.save()

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Acción actualizada correctamente'
            })
        return super().form_valid(form)

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
        action = get_object_or_404(PersonnelAction, pk=pk)

        if action.is_registered:
            return JsonResponse({
                'success': False,
                'message': 'Esta acción ya está registrada'
            }, status=400)

        action.is_registered = True
        action.save()

        return JsonResponse({
            'success': True,
            'message': 'Acción registrada correctamente'
        })


class ActionPDFView(LoginRequiredMixin, View):
    """Vista para generar PDF de la acción"""

    def get(self, request, pk):
        action = get_object_or_404(
            PersonnelAction.objects.select_related('employee__person', 'action_type'),
            pk=pk
        )
        budget = None
        management_period = getattr(action, 'management_period', None)
        if management_period and management_period.budget_line:
            budget = management_period.budget_line
        else:
            budget = BudgetLine.objects.filter(current_employee_id=action.employee.pk).select_related(
                'position_item', 'group_item', 'grade_item'
            ).first()

        try:
            from weasyprint import HTML

            html = render_to_string(
                'personnel_action/pdf/action_pdf.html',
                {'action': action, 'budget': budget},
                request=request
            )
            pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            filename = f'Accion_{action.number.replace("/", "-")}.pdf'
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
        except Exception:
            return HttpResponse('Error al generar el PDF de la acción', status=500)
