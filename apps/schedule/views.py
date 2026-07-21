from django.shortcuts import get_object_or_404
from django.views.generic import ListView, View
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.urls import reverse
from datetime import date

from .models import Schedule, ScheduleObservation, ScheduleChangeHistory
from .forms import ScheduleForm, ScheduleSearchForm, ScheduleObservationForm, ObservationSearchForm
from employee.models import Employee
from budget.models import BudgetLine
from .models import EmployeeScheduleHistory


class ScheduleListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Schedule
    template_name = 'schedule/schedule_list.html'
    context_object_name = 'schedules'
    permission_required = 'schedule.view_schedule'
    paginate_by = 10

    def get_queryset(self):
        return Schedule.objects.all().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_schedules = Schedule.objects.all()
        context['total_schedules'] = all_schedules.count()
        context['active_schedules'] = all_schedules.filter(is_active=True).count()
        context['inactive_schedules'] = all_schedules.filter(is_active=False).count()
        return context


class ScheduleCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'schedule.add_schedule'

    def post(self, request):
        form = ScheduleForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.created_by = request.user
                instance.save()
                # Si se proporcionó una fecha 'vigente_desde', crear entrada en historial
                vdesde = form.cleaned_data.get('vigente_desde')
                if vdesde:
                    ScheduleChangeHistory.objects.create(
                        schedule=instance,
                        effective_from=vdesde,
                        morning_start=instance.morning_start,
                        morning_end=instance.morning_end,
                        morning_crosses_midnight=instance.morning_crosses_midnight,
                        afternoon_start=instance.afternoon_start,
                        afternoon_end=instance.afternoon_end,
                        afternoon_crosses_midnight=instance.afternoon_crosses_midnight,
                        monday=instance.monday, tuesday=instance.tuesday, wednesday=instance.wednesday,
                        thursday=instance.thursday, friday=instance.friday, saturday=instance.saturday,
                        sunday=instance.sunday, late_tolerance_minutes=instance.late_tolerance_minutes,
                        daily_hours=instance.daily_hours,
                        created_by=request.user
                    )
            return JsonResponse({'success': True, 'message': 'Horario creado exitosamente'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ScheduleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'schedule.change_schedule'

    def post(self, request, pk):
        schedule = get_object_or_404(Schedule, pk=pk)
        form = ScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.updated_by = request.user
            instance.save()
            # Si se proporcionó 'vigente_desde', registrar versión del horario
            vdesde = form.cleaned_data.get('vigente_desde')
            if vdesde:
                ScheduleChangeHistory.objects.create(
                    schedule=instance,
                    effective_from=vdesde,
                    morning_start=instance.morning_start,
                    morning_end=instance.morning_end,
                    morning_crosses_midnight=instance.morning_crosses_midnight,
                    afternoon_start=instance.afternoon_start,
                    afternoon_end=instance.afternoon_end,
                    afternoon_crosses_midnight=instance.afternoon_crosses_midnight,
                    monday=instance.monday, tuesday=instance.tuesday, wednesday=instance.wednesday,
                    thursday=instance.thursday, friday=instance.friday, saturday=instance.saturday,
                    sunday=instance.sunday, late_tolerance_minutes=instance.late_tolerance_minutes,
                    daily_hours=instance.daily_hours,
                    created_by=request.user
                )
            return JsonResponse({'success': True, 'message': 'Horario actualizado exitosamente'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ScheduleHistoryAPIView(LoginRequiredMixin, View):
    """Retorna el modal HTML con el historial de cambios de un horario."""
    def get(self, request, pk):
        schedule = get_object_or_404(Schedule, pk=pk)
        histories = ScheduleChangeHistory.objects.filter(schedule=schedule).select_related('created_by').order_by('-effective_from')
        html = render_to_string('schedule/modals/modal_schedule_history.html', {'histories': histories, 'schedule': schedule}, request=request)
        from django.http import HttpResponse
        return HttpResponse(html)


class ScheduleDetailAPIView(View):
    """Retorna los datos de un horario en JSON para cargar el formulario de edición"""

    def get(self, request, pk):
        schedule = get_object_or_404(Schedule, pk=pk)
        data = {
            'id': schedule.id,
            'name': schedule.name,
            'late_tolerance_minutes': schedule.late_tolerance_minutes,
            'daily_hours': float(schedule.daily_hours),
            'morning_start': schedule.morning_start.strftime('%H:%M'),
            'morning_end': schedule.morning_end.strftime('%H:%M'),
            'morning_crosses_midnight': schedule.morning_crosses_midnight,
            # Manejo de nulos para la segunda jornada
            'afternoon_start': schedule.afternoon_start.strftime('%H:%M') if schedule.afternoon_start else '',
            'afternoon_end': schedule.afternoon_end.strftime('%H:%M') if schedule.afternoon_end else '',
            'afternoon_crosses_midnight': schedule.afternoon_crosses_midnight,
            # Días
            'monday': schedule.monday, 'tuesday': schedule.tuesday, 'wednesday': schedule.wednesday,
            'thursday': schedule.thursday, 'friday': schedule.friday, 'saturday': schedule.saturday,
            'sunday': schedule.sunday,
        }
        return JsonResponse({'success': True, 'schedule': data})


class ScheduleActivateView(View):
    def post(self, request, pk):
        instance = get_object_or_404(Schedule, pk=pk)
        instance.is_active = True
        instance.updated_by = request.user
        instance.save()
        return JsonResponse({'success': True, 'message': 'Horario dado de ALTA correctamente'})


class ScheduleDeactivateView(View):
    def post(self, request, pk):
        instance = get_object_or_404(Schedule, pk=pk)
        instance.is_active = False
        instance.updated_by = request.user
        instance.save()
        return JsonResponse({'success': True, 'message': 'Horario dado de BAJA correctamente'})


class ScheduleTablePartialView(LoginRequiredMixin, View):
    """Vista para recargar la tabla mediante filtros AJAX"""

    def get(self, request):
        from django.core.paginator import Paginator
        
        name = request.GET.get('name', '')
        is_active = request.GET.get('is_active', '')
        page_number = request.GET.get('page', 1)

        # 1. Queryset filtrado para la tabla
        queryset = Schedule.objects.all().order_by('-created_at')

        if name:
            queryset = queryset.filter(name__icontains=name)

        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)

        # 2. Paginación
        paginator = Paginator(queryset, 10)
        page_obj = paginator.get_page(page_number)

        # 3. Cálculo de estadísticas (SIEMPRE sobre el total de la base)
        all_schedules = Schedule.objects.all()
        stats_data = {
            'total': all_schedules.count(),
            'active': all_schedules.filter(is_active=True).count(),
            'inactive': all_schedules.filter(is_active=False).count(),
        }

        # 4. Renderizado del fragmento HTML
        html = render_to_string('schedule/partials/partial_schedule_table.html', {
            'schedules': page_obj.object_list
        }, request=request)

        # 5. Respuesta JSON con HTML, Stats y datos de paginación
        return JsonResponse({
            'table_html': html,
            'stats': stats_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
                'total_count': paginator.count,
                'start_index': page_obj.start_index(),
                'end_index': page_obj.end_index()
            }
        })


class ObservationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScheduleObservation
    template_name = 'schedule/observation_list.html'
    permission_required = 'schedule.view_scheduleobservation'
    context_object_name = 'observations'
    paginate_by = 10

    def get_queryset(self):
        return ScheduleObservation.objects.all().order_by('-start_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = ScheduleObservation.objects.all()
        # Datos iniciales para evitar el parpadeo "0"
        context['total_obs'] = qs.count()
        context['holiday_obs'] = qs.filter(is_holiday=True).count()
        context['special_obs'] = qs.filter(is_holiday=False).count()
        return context


class ObservationTablePartialView(LoginRequiredMixin, View):
    def get(self, request):
        from django.core.paginator import Paginator
        
        name = request.GET.get('name', '')
        is_holiday = request.GET.get('is_holiday', '')
        page_number = request.GET.get('page', 1)

        queryset = ScheduleObservation.objects.all().order_by('-start_date')
        if name: queryset = queryset.filter(name__icontains=name)
        if is_holiday == 'true':
            queryset = queryset.filter(is_holiday=True)
        elif is_holiday == 'false':
            queryset = queryset.filter(is_holiday=False)

        # Paginación
        paginator = Paginator(queryset, 10)
        page_obj = paginator.get_page(page_number)

        # Estadísticas en tiempo real
        all_qs = ScheduleObservation.objects.all()
        stats = {
            'total': all_qs.count(),
            'holiday': all_qs.filter(is_holiday=True).count(),
            'special': all_qs.filter(is_holiday=False).count(),
        }

        html = render_to_string('schedule/partials/partial_observation_table.html', {
            'observations': page_obj.object_list
        }, request=request)
        
        return JsonResponse({
            'table_html': html,
            'stats': stats,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
                'total_count': paginator.count,
                'start_index': page_obj.start_index(),
                'end_index': page_obj.end_index()
            }
        })


class ObservationCreateView(LoginRequiredMixin, View):
    def post(self, request):
        form = ScheduleObservationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                observation = form.save(commit=False)
                observation.created_by = request.user
                observation.save()
            return JsonResponse({'success': True, 'message': 'Registrado correctamente'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ObservationUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        observation = get_object_or_404(ScheduleObservation, pk=pk)
        form = ScheduleObservationForm(request.POST, instance=observation)
        if form.is_valid():
            with transaction.atomic():
                updated_observation = form.save(commit=False)
                # Si el formulario de edición no envía is_active, conservar el estado actual.
                if 'is_active' not in request.POST:
                    updated_observation.is_active = observation.is_active
                updated_observation.updated_by = request.user
                updated_observation.save()
            return JsonResponse({'success': True, 'message': 'Actualizado correctamente'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ObservationDetailAPIView(LoginRequiredMixin, View):
    def get(self, request, pk):
        obs = get_object_or_404(ScheduleObservation, pk=pk)
        return JsonResponse({
            'success': True,
            'observation': {
                'id': obs.id,
                'name': obs.name,
                'description': obs.description or '',
                'start_date': obs.start_date.strftime('%Y-%m-%d'),
                'end_date': obs.end_date.strftime('%Y-%m-%d'),
                'is_holiday': obs.is_holiday,
                'is_active': obs.is_active,
            }
        })


class ObservationToggleStatusView(LoginRequiredMixin, View):
    def post(self, request, pk):
        instance = get_object_or_404(ScheduleObservation, pk=pk)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save()
        return JsonResponse({'success': True, 'message': 'Estado actualizado correctamente'})


def _get_employee_current_schedule_row(employee, target_date=None):
    target_date = target_date or date.today()
    return EmployeeScheduleHistory.objects.filter(
        employee=employee,
        start_date__lte=target_date,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=target_date)
    ).select_related('schedule', 'created_by').order_by('-start_date', '-created_at').first()


def _get_employee_assignment_payload(employee, target_date=None):
    try:
        current_history = _get_employee_current_schedule_row(employee, target_date)
        budget_line = None
        budget_manager = getattr(employee, 'current_budget_line', None)
        if budget_manager is not None:
            budget_line = budget_manager.select_related('position_item').first()

        return {
            'employee': employee,
            'position_name': budget_line.position_item.name if budget_line and budget_line.position_item else 'Sin cargo asignado',
            'type_name': employee.employment_status.name if employee.employment_status else 'Sin tipo',
            'area_name': employee.area.name if employee.area else 'Sin área',
            'current_schedule': current_history.schedule if current_history else None,
            'current_history': current_history,
        }
    except Exception:
        return {
            'employee': employee,
            'position_name': 'Sin cargo asignado',
            'type_name': employee.employment_status.name if employee.employment_status else 'Sin tipo',
            'area_name': employee.area.name if employee.area else 'Sin área',
            'current_schedule': None,
            'current_history': None,
        }


class EmployeeScheduleAssignmentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Employee
    template_name = 'schedule/employee_schedule_assignment_list.html'
    context_object_name = 'employees'
    permission_required = 'schedule.view_schedule'
    paginate_by = 10

    def get_queryset(self):
        qs = Employee.objects.filter(is_active=True).select_related('person', 'area', 'employment_status').prefetch_related(
            Prefetch('current_budget_line', queryset=BudgetLine.objects.select_related('position_item'))
        )

        query = (self.request.GET.get('q') or '').strip()
        if query:
            qs = qs.filter(
                Q(person__first_name__icontains=query)
                | Q(person__last_name__icontains=query)
                | Q(person__document_number__icontains=query)
                | Q(area__name__icontains=query)
                | Q(employment_status__name__icontains=query)
                | Q(current_budget_line__position_item__name__icontains=query)
            ).distinct()

        sort_field = self.request.GET.get('sort_field', 'person__last_name')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        
        allowed_sort_fields = {
            'person__last_name': 'person__last_name',
            'position_name': 'current_budget_line__position_item__name',
            'area_name': 'area__name',
        }

        if sort_field in allowed_sort_fields:
            order = f"{'-' if sort_dir == 'desc' else ''}{allowed_sort_fields[sort_field]}"
            qs = qs.order_by(order, 'person__first_name')
        else:
            qs = qs.order_by('person__last_name', 'person__first_name')
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_obj = context.get('page_obj')
        employees = page_obj.object_list if page_obj else context.get('employees', [])
        context['employees_data'] = [_get_employee_assignment_payload(emp) for emp in employees]
        context['query'] = (self.request.GET.get('q') or '').strip()
        return context


class EmployeeScheduleAssignmentTablePartialView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'schedule.view_schedule'

    def get(self, request):
        from django.core.paginator import Paginator

        query = (request.GET.get('q') or '').strip()
        page_number = request.GET.get('page', 1)

        qs = Employee.objects.filter(is_active=True).select_related('person', 'area', 'employment_status').prefetch_related(
            Prefetch('current_budget_line', queryset=BudgetLine.objects.select_related('position_item'))
        )

        if query:
            qs = qs.filter(
                Q(person__first_name__icontains=query)
                | Q(person__last_name__icontains=query)
                | Q(person__document_number__icontains=query)
                | Q(area__name__icontains=query)
                | Q(employment_status__name__icontains=query)
                | Q(current_budget_line__position_item__name__icontains=query)
            ).distinct()

        sort_field = self.request.GET.get('sort_field', 'person__last_name')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        
        allowed_sort_fields = {
            'person__last_name': 'person__last_name',
            'position_name': 'current_budget_line__position_item__name',
            'area_name': 'area__name',
        }

        if sort_field in allowed_sort_fields:
            order = f"{'-' if sort_dir == 'desc' else ''}{allowed_sort_fields[sort_field]}"
            qs = qs.order_by(order, 'person__first_name')
        else:
            qs = qs.order_by('person__last_name', 'person__first_name')

        paginator = Paginator(qs, 10)
        page_obj = paginator.get_page(page_number)

        html = render_to_string('schedule/partials/partial_employee_assignment_table.html', {
            'employees_data': [_get_employee_assignment_payload(emp) for emp in page_obj.object_list],
            'page_obj': page_obj,
        }, request=request)

        return JsonResponse({
            'table_html': html,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
                'total_count': paginator.count,
                'start_index': page_obj.start_index(),
                'end_index': page_obj.end_index(),
            }
        })


class EmployeeScheduleHistoryAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'schedule.view_schedule'

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee.objects.select_related('person', 'area', 'employment_status'), pk=employee_id)
        histories = EmployeeScheduleHistory.objects.filter(employee=employee).select_related('schedule', 'created_by').order_by('-start_date', '-created_at')
        current_row = _get_employee_current_schedule_row(employee)
        html = render_to_string('schedule/modals/modal_employee_schedule_history.html', {
            'employee': employee,
            'histories': histories,
            'current_row': current_row,
        }, request=request)
        from django.http import HttpResponse
        return HttpResponse(html)


class EmployeeScheduleChangeModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'schedule.change_schedule'

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee.objects.select_related('person', 'area', 'employment_status'), pk=employee_id)
        schedules = Schedule.objects.filter(is_active=True).order_by('name')
        current_row = _get_employee_current_schedule_row(employee)
        modal_title = "Asignar Horario" if not current_row else "Cambiar Horario"
        
        html = render_to_string('schedule/modals/modal_employee_schedule_form.html', {
            'employee': employee,
            'schedules': schedules,
            'current_row': current_row,
            'today': date.today(),
            'action_url': reverse('schedule:employee_schedule_assign', args=[employee_id]),
            'modal_title': modal_title,
        }, request=request)
        from django.http import HttpResponse
        return HttpResponse(html)


class EmployeeScheduleAssignView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'schedule.change_schedule'

    def post(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)
        schedule_id = request.POST.get('schedule_id')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date') or None
        reason = (request.POST.get('reason') or '').strip() or None

        if not schedule_id:
            return JsonResponse({'success': False, 'errors': {'schedule_id': ['Seleccione un horario.']}}, status=400)

        schedule = get_object_or_404(Schedule, pk=schedule_id)

        try:
            parsed_start = date.fromisoformat(start_date) if start_date else date.today()
            parsed_end = date.fromisoformat(end_date) if end_date else None
        except Exception:
            return JsonResponse({'success': False, 'errors': {'start_date': ['Formato de fecha inválido.']}}, status=400)

        if parsed_end and parsed_end < parsed_start:
            return JsonResponse({'success': False, 'errors': {'end_date': ['La fecha hasta no puede ser menor a la fecha desde.']}}, status=400)

        with transaction.atomic():
            EmployeeScheduleHistory.objects.create(
                employee=employee,
                schedule=schedule,
                start_date=parsed_start,
                end_date=parsed_end,
                reason=reason,
                is_current=True,
                created_by=request.user,
            )

        return JsonResponse({'success': True, 'message': 'Horario asignado correctamente.'})
