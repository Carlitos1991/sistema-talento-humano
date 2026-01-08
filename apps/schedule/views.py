from django.shortcuts import get_object_or_404
from django.views.generic import ListView, View
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction

from .models import Schedule, ScheduleObservation
from .forms import ScheduleForm, ScheduleSearchForm, ScheduleObservationForm, ObservationSearchForm


class ScheduleListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Schedule
    template_name = 'schedule/schedule_list.html'
    context_object_name = 'schedules'
    permission_required = 'schedule.view_schedule'

    def get_queryset(self):
        return Schedule.objects.all().order_by('-created_at')[:50]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ScheduleSearchForm()
        # Stats basadas en el BaseModel (is_active)
        qs = Schedule.objects.all()
        context['total_count'] = qs.count()
        context['active_count'] = qs.filter(is_active=True).count()
        context['inactive_count'] = qs.filter(is_active=False).count()
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
            return JsonResponse({'success': True, 'message': 'Horario actualizado exitosamente'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


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
        name = request.GET.get('name', '')
        is_active = request.GET.get('is_active', '')

        queryset = Schedule.objects.all().order_by('-created_at')
        if name:
            queryset = queryset.filter(name__icontains=name)
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)

        html = render_to_string('schedule/partials/partial_schedule_table.html', {
            'schedules': queryset[:50]
        }, request=request)
        return JsonResponse({'table_html': html})


class ObservationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScheduleObservation
    template_name = 'schedule/observation_list.html'
    context_object_name = 'observations'
    permission_required = 'schedule.can_manage_observations'

    def get_queryset(self):
        # Filtramos por los últimos feriados registrados
        return ScheduleObservation.objects.all().order_by('-start_date')[:50]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ObservationSearchForm()

        # Stats para las tarjetas superiores
        qs = ScheduleObservation.objects.all()
        context.update({
            'total_count': qs.count(),
            'holiday_count': qs.filter(is_holiday=True).count(),
            'observation_count': qs.filter(is_holiday=False).count(),
        })
        return context


class ObservationCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'schedule.can_manage_observations'

    def post(self, request):
        form = ScheduleObservationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.created_by = request.user
                instance.save()
            return JsonResponse({'success': True, 'message': 'Registro guardado exitosamente'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
