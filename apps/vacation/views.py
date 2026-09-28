import datetime as dt
from decimal import Decimal
from io import BytesIO
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import IntegrityError, transaction
from django.db.models import Q, Prefetch, F
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string, get_template
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView, CreateView, UpdateView, FormView

from .forms import (
    PeriodForm,
    FirstVacationForm,
    HourPermitVacationForm,
    DayPermitVacationForm,
    VacationLiquidationForm
)
from .models import (
    VacationRequest,
    VacationPeriod,
    EmployeeVacationBalance,
    VacationHistory,
    FACTOR_HOUR,
    FACTOR_MINUTE
)
from employee.models import Employee
from budget.models import BudgetLine
from permitrequest.models import PermitRequest, PermitType
from personnel_actions.models import PersonnelAction, ActionType


# ==============================================================================
# BUSINESS LOGIC (CALCULATION BY REGIME AND SERVICE YEARS)
# ==============================================================================

def calculate_earned_days(employee, calculation_date=None):
    """
    Calcula los días ganados de vacaciones:
    - LOSEP / Empleado: 30 días fijos.
    - TRABAJADOR (Código del Trabajo): 15 días base.
      A partir del 5to año cumplido (año 6 en adelante), 1 día adicional por año (tope 15 extra = 30 máx).
    """
    if not employee or not employee.employment_status:
        return Decimal('30.0')

    regime = (employee.employment_status.code or '').upper()

    # Régimen Código del Trabajo / Trabajador
    if 'TRABAJADOR' in regime or 'CÓDIGO' in regime or 'CODIGO' in regime:
        base_days = Decimal('15.0')
        extra_days = Decimal('0.0')

        # Contar periodos previos asignados
        previous_periods_count = EmployeeVacationBalance.objects.filter(employee=employee).count()

        # Calcular años de servicio si existe fecha de ingreso formal
        entry_date = getattr(employee, 'entry_date', None) or getattr(employee.person, 'entry_date', None)
        if entry_date:
            anniversary_date = calculation_date or timezone.now().date()
            years_of_service = relativedelta(anniversary_date, entry_date).years
        else:
            years_of_service = previous_periods_count

        # A partir del quinto año cumplido (desde el año 6)
        if years_of_service >= 5:
            bonus = min(years_of_service - 4, 15)
            extra_days = Decimal(str(bonus))

        return base_days + extra_days

    # Por defecto todo empleado / servidor público recibe 30 días
    return Decimal('30.0')


# ==============================================================================
# MAIN EMPLOYEE / REQUESTS LIST VIEW
# ==============================================================================

class VacationRequestListView(LoginRequiredMixin, ListView):
    """
    Listado principal de empleados para administrar vacaciones.
    """
    model = Employee
    template_name = 'vacation/vacation_request_list.html'
    context_object_name = 'employees_data'
    paginate_by = 10

    def get_queryset(self):
        qs = Employee.objects.filter(
            is_active=True
        ).select_related(
            'person',
            'area'
        ).prefetch_related(
            Prefetch(
                'employeevacationbalance_set',
                queryset=EmployeeVacationBalance.objects.select_related('period').filter(is_active=True)
            )
        ).order_by('person__last_name', 'person__first_name')

        q = self.request.GET.get('q', '').strip()
        if q:
            terms = q.split()
            for term in terms:
                qs = qs.filter(
                    Q(person__first_name__icontains=term) |
                    Q(person__last_name__icontains=term) |
                    Q(person__document_number__icontains=term)
                )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employees_data = []

        for employee in context['object_list']:
            budget = BudgetLine.objects.filter(
                current_employee=employee,
                is_active=True
            ).select_related('position_item').first()

            vacation_balance = employee.employeevacationbalance_set.filter(is_active=True).first()

            # Verificación en disco de la foto física
            has_valid_photo = False
            person = employee.person
            if person and person.photo:
                try:
                    has_valid_photo = person.photo.storage.exists(person.photo.name)
                except Exception:
                    has_valid_photo = False

            employees_data.append({
                'employee': employee,
                'budget': budget,
                'vacation_balance': vacation_balance,
                'has_vacation': vacation_balance is not None,
                'has_valid_photo': has_valid_photo
            })

        context['employees_data'] = employees_data
        context['search_query'] = self.request.GET.get('q', '')
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'vacation/partials/partial_vacation_employee_list.html',
                context,
                request=self.request
            )
            page_obj = context.get('page_obj')
            pagination_data = {
                'start_index': page_obj.start_index() if page_obj else 0,
                'end_index': page_obj.end_index() if page_obj else 0,
                'total_count': page_obj.paginator.count if page_obj else 0,
                'current_page': page_obj.number if page_obj else 1,
                'total_pages': page_obj.paginator.num_pages if page_obj else 1,
                'has_previous': page_obj.has_previous() if page_obj else False,
                'has_next': page_obj.has_next() if page_obj else False,
            }
            return JsonResponse({'html': html, 'pagination': pagination_data})

        return super().render_to_response(context, **response_kwargs)


class VacationCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'vacation/modals/modal_vacation_form.html'


# ==============================================================================
# VACATION PERIOD MANAGEMENT
# ==============================================================================

class PeriodListView(LoginRequiredMixin, ListView):
    model = VacationPeriod
    template_name = 'vacation/period_list.html'
    context_object_name = 'periods'
    paginate_by = 10

    def get_queryset(self):
        qs = VacationPeriod.objects.all()
        order_by = self.request.GET.get('order_by', 'name')
        direction = self.request.GET.get('direction', 'asc')

        if order_by in ['name', 'is_active']:
            if direction == 'desc':
                order_by = f'-{order_by}'
            qs = qs.order_by(order_by)
        else:
            qs = qs.order_by('name')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['current_order'] = self.request.GET.get('order_by', 'name')
        context['current_direction'] = self.request.GET.get('direction', 'asc')
        return context


class PeriodCreateView(LoginRequiredMixin, CreateView):
    model = VacationPeriod
    form_class = PeriodForm
    template_name = 'vacation/modals/modal_period_vacation_form.html'
    success_url = reverse_lazy('vacation:period_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Nuevo Periodo'
        context['action_url'] = reverse_lazy('vacation:period_create')
        return context

    def form_valid(self, form):
        try:
            self.object = form.save()
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'success': True,
                    'message': f'Periodo "{self.object.name}" creado exitosamente',
                    'redirect_url': str(self.success_url)
                })
            messages.success(self.request, f'Periodo "{self.object.name}" creado exitosamente')
            return redirect(self.success_url)
        except IntegrityError:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': 'Ya existe un periodo con este nombre',
                    'errors': {'name': 'Ya existe un periodo con este nombre'}
                }, status=400)
            form.add_error('name', 'Ya existe un periodo con este nombre')
            return self.form_invalid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {k: v[0] for k, v in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor corrija los errores en el formulario',
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


class PeriodUpdateView(LoginRequiredMixin, UpdateView):
    model = VacationPeriod
    form_class = PeriodForm
    template_name = 'vacation/modals/modal_period_vacation_form.html'
    success_url = reverse_lazy('vacation:period_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Periodo'
        context['action_url'] = reverse_lazy('vacation:period_edit', kwargs={'pk': self.object.pk})
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        try:
            self.object = form.save()
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'success': True,
                    'message': f'Periodo "{self.object.name}" actualizado exitosamente',
                    'redirect_url': str(self.success_url)
                })
            messages.success(self.request, f'Periodo "{self.object.name}" actualizado exitosamente')
            return redirect(self.success_url)
        except IntegrityError:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': 'Ya existe un periodo con este nombre',
                    'errors': {'name': 'Ya existe un periodo con este nombre'}
                }, status=400)
            form.add_error('name', 'Ya existe un periodo con este nombre')
            return self.form_invalid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {k: v[0] for k, v in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor corrija los errores en el formulario',
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


# ==============================================================================
# VACATION BALANCES (FIRST PERIOD & SUBSEQUENT PERIODS)
# ==============================================================================

class CreateFirstVacationView(LoginRequiredMixin, CreateView):
    model = EmployeeVacationBalance
    form_class = FirstVacationForm
    template_name = 'vacation/modals/modal_first_vacation_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        employee_id = self.kwargs.get('employee_id')
        kwargs['employee_id'] = employee_id

        employee = get_object_or_404(
            Employee.objects.select_related('employment_status', 'person'),
            pk=employee_id
        )
        kwargs['initial_days'] = calculate_earned_days(employee)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(
            Employee.objects.select_related('person', 'employment_status').prefetch_related(
                'current_budget_line__position_item'),
            pk=self.kwargs['employee_id']
        )

        has_valid_photo = False
        if employee.person and employee.person.photo:
            try:
                has_valid_photo = employee.person.photo.storage.exists(employee.person.photo.name)
            except Exception:
                has_valid_photo = False

        context['employee'] = employee
        context['has_valid_photo'] = has_valid_photo
        context['titulo'] = f'Crear Primera Vacación para {employee.person.full_name}'
        context['action_url'] = reverse('vacation:create_first_vacation', kwargs={'employee_id': employee.id})
        return context

    def form_valid(self, form):
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])

        days = form.cleaned_data.get('total_days', Decimal('0'))
        hours = form.cleaned_data.get('hours', 0)
        minutes = form.cleaned_data.get('minutes', 0)
        user_detail = form.cleaned_data.get('observation_detail', '')

        extra_from_hours = Decimal(str(hours)) * FACTOR_HOUR
        extra_from_minutes = Decimal(str(minutes)) * FACTOR_MINUTE
        final_calculated_days = days + extra_from_hours + extra_from_minutes

        balance = form.save(commit=False)
        balance.employee = employee
        balance.total_days = final_calculated_days
        balance.balance_days = final_calculated_days
        balance.additional_days = Decimal('0.0')

        period_name = form.cleaned_data['period'].name
        balance.observation = f"CARGA INICIAL PERIODO {period_name}: {user_detail}"
        balance.is_active = True
        balance.created_by = self.request.user
        balance.save()

        redirect_url = reverse('vacation:employee_vacation_detail', kwargs={'employee_id': employee.id})
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': 'Periodo inicial creado exitosamente.',
                'redirect_url': redirect_url
            })
        return redirect(redirect_url)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {k: v[0] for k, v in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor corrija los errores en el formulario',
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


class CreateNewVacationPeriodView(LoginRequiredMixin, CreateView):
    model = EmployeeVacationBalance
    form_class = FirstVacationForm
    template_name = 'vacation/modals/modal_new_vacation_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        employee_id = self.kwargs.get('employee_id')
        kwargs['employee_id'] = employee_id

        employee = get_object_or_404(Employee.objects.select_related('employment_status', 'person'), pk=employee_id)
        kwargs['initial_days'] = calculate_earned_days(employee)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(
            Employee.objects.select_related('person', 'employment_status').prefetch_related(
                'current_budget_line__position_item'),
            pk=self.kwargs['employee_id']
        )

        has_valid_photo = False
        if employee.person and employee.person.photo:
            try:
                has_valid_photo = employee.person.photo.storage.exists(employee.person.photo.name)
            except Exception:
                has_valid_photo = False

        context['employee'] = employee
        context['has_valid_photo'] = has_valid_photo
        context['titulo'] = f'Nueva Vacación para {employee.person.full_name}'
        context['action_url'] = reverse('vacation:create_new_vacation', kwargs={'employee_id': employee.id})
        return context

    def form_valid(self, form):
        employee = get_object_or_404(Employee.objects.select_related('employment_status'),
                                     pk=self.kwargs['employee_id'])
        previous_balances = EmployeeVacationBalance.objects.filter(employee=employee).order_by('created_at')

        is_trabajador = employee.employment_status and 'TRABAJADOR' in (employee.employment_status.code or '').upper()
        new_period_days = calculate_earned_days(employee)

        last_balance = previous_balances.last()
        previous_balance = last_balance.balance_days if last_balance else Decimal('0.0')
        calculated_balance = previous_balance + new_period_days
        max_limit = Decimal('45.0') if is_trabajador else Decimal('60.0')

        lost_days = Decimal('0.0')
        if calculated_balance > max_limit:
            lost_days = calculated_balance - max_limit
            final_balance = max_limit
        else:
            final_balance = calculated_balance

        period_name = form.cleaned_data['period'].name
        if lost_days > 0:
            observation = (
                f"Se creó el período {period_name} con un balance de {final_balance} días. "
                f"IMPORTANTE: El empleado perdió {lost_days} días del período {period_name} "
                f"por exceder el límite máximo legal "
                f"(balance anterior: {previous_balance} días + {new_period_days} días nuevos = {calculated_balance} días)."
            )
        else:
            observation = (
                f"Se creó el período {period_name} con un balance de {final_balance} días "
                f"(balance anterior: {previous_balance} días + {new_period_days} días nuevos)."
            )

        balance = form.save(commit=False)
        balance.employee = employee
        balance.total_days = new_period_days
        balance.balance_days = final_balance
        balance.observation = observation
        balance.additional_days = last_balance.balance_days if last_balance else Decimal('0.0')
        balance.is_active = True
        balance.created_by = self.request.user
        balance.save()

        redirect_url = reverse('vacation:employee_vacation_detail', kwargs={'employee_id': employee.id})
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': 'Nuevo periodo de vacaciones creado exitosamente.',
                'redirect_url': redirect_url
            })
        messages.success(self.request, 'Nuevo periodo de vacaciones creado exitosamente')
        return redirect(redirect_url)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {k: v[0] for k, v in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor corrija los errores en el formulario',
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


# ==============================================================================
# EMPLOYEE VACATION DETAIL VIEW
# ==============================================================================

class EmployeeVacationDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'vacation/employee_vacation_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(
            Employee.objects.select_related('person', 'employment_status', 'area'),
            pk=self.kwargs['employee_id']
        )

        search_query = self.request.GET.get('search', '').strip()
        page_number = self.request.GET.get('page', 1)
        per_page = int(self.request.GET.get('per_page', 10))

        active_balance = EmployeeVacationBalance.objects.filter(
            employee=employee,
            is_active=True,
            period__is_active=True
        ).select_related('period').first()

        vacation_balances = EmployeeVacationBalance.objects.filter(
            employee=employee,
            is_active=True
        ).select_related('period')

        if search_query:
            vacation_balances = vacation_balances.filter(period__name__icontains=search_query)

        vacation_balances = vacation_balances.order_by('-created_at')
        paginator = Paginator(vacation_balances, per_page)

        try:
            vacation_balances_page = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            vacation_balances_page = paginator.page(1)

        context['employee'] = employee
        context['active_balance'] = active_balance
        context['vacation_balances'] = vacation_balances_page
        context['search_query'] = search_query
        context['per_page'] = per_page
        return context


# ==============================================================================
# VACATION CHARGED PERMITS
# ==============================================================================

class CreateHourPermitVacationView(LoginRequiredMixin, FormView):
    template_name = 'vacation/modals/modal_hour_permit_form.html'
    form_class = HourPermitVacationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
        active_balance = EmployeeVacationBalance.objects.filter(
            employee=employee,
            is_active=True,
            period__is_active=True
        ).select_related('period').first()

        context['employee'] = employee
        context['active_balance'] = active_balance
        context['titulo'] = f'Permiso por Horas - {employee.person.full_name}'
        context['action_url'] = reverse('vacation:create_hour_permit', kwargs={'employee_id': employee.id})
        return context

    def form_valid(self, form):
        try:
            employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
            active_balance = EmployeeVacationBalance.objects.filter(
                employee=employee,
                is_active=True,
                period__is_active=True
            ).select_related('period').first()

            if not active_balance:
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': 'El empleado no tiene un periodo de vacaciones activo'
                }, status=400)

            start_date = form.cleaned_data['start_date']
            start_time = form.cleaned_data['start_time']
            hours = form.cleaned_data.get('hours', 0) or 0
            minutes = form.cleaned_data.get('minutes', 0) or 0

            from datetime import datetime, timedelta
            total_minutes_permit = (hours * 60) + minutes
            end_time_calculated = (
                    datetime.combine(start_date, start_time) + timedelta(minutes=total_minutes_permit)
            ).time()

            existing_permit = PermitRequest.objects.filter(
                employee=employee,
                start_date=start_date,
                status__in=['REQUESTED', 'APPROVED']
            ).exclude(start_time__gte=end_time_calculated).exclude(end_time__lte=start_time).first()

            if existing_permit:
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': 'Ya existe un permiso registrado en ese horario.'
                }, status=400)

            factor_hour_base = Decimal('0.125')
            factor_minute_base = Decimal('0.00208333')
            proportional_hour = Decimal('0.05')
            proportional_minute = Decimal('0.00083')

            value_discount = (Decimal(str(hours)) * factor_hour_base) + (Decimal(str(minutes)) * factor_minute_base)
            proportional_discount = (Decimal(str(hours)) * proportional_hour) + (
                    Decimal(str(minutes)) * proportional_minute)
            total_discount = value_discount + proportional_discount

            if active_balance.balance_days < total_discount:
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': f'Saldo insuficiente. Disponible: {active_balance.balance_days} días, Requerido: {total_discount:.2f} días'
                }, status=400)

            permit_type = PermitType.objects.filter(name='Personales', is_active=True).first()
            if not permit_type:
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': 'No se encontró el tipo de permiso "Personales" activo'
                }, status=400)

            end_time = (datetime.combine(start_date, start_time) + timedelta(minutes=total_minutes_permit)).time()

            PermitRequest.objects.create(
                employee=employee,
                permit_type=permit_type,
                start_date=start_date,
                start_time=start_time,
                end_date=start_date,
                end_time=end_time,
                days=0,
                hours=hours,
                minutes=minutes,
                status='REQUESTED',
                created_by=self.request.user
            )

            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': 'Solicitud de permiso creada exitosamente. Pendiente de aprobación.',
                'redirect_url': reverse('vacation:employee_vacation_detail', kwargs={'employee_id': employee.id})
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'success': False, 'message': str(e)}, status=500)

    def form_invalid(self, form):
        errors = {k: v[0] for k, v in form.errors.items()}
        return JsonResponse({
            'status': 'error',
            'success': False,
            'message': 'Por favor corrija los errores en el formulario',
            'errors': errors
        }, status=400)


class CreateDayPermitVacationView(LoginRequiredMixin, FormView):
    template_name = 'vacation/modals/modal_day_permit_form.html'
    form_class = DayPermitVacationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
        active_balance = EmployeeVacationBalance.objects.filter(
            employee=employee,
            is_active=True,
            period__is_active=True
        ).select_related('period').first()

        context['employee'] = employee
        context['active_balance'] = active_balance
        context['titulo'] = f'Permiso por Días - {employee.person.full_name}'
        context['action_url'] = reverse('vacation:create_day_permit', kwargs={'employee_id': employee.id})
        return context

    def form_valid(self, form):
        try:
            employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
            active_balance = EmployeeVacationBalance.objects.filter(
                employee=employee,
                is_active=True,
                period__is_active=True
            ).select_related('period').first()

            if not active_balance:
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': 'El empleado no tiene un periodo de vacaciones activo'
                }, status=400)

            start_date = form.cleaned_data['start_date']
            days = form.cleaned_data['days']

            from datetime import timedelta, time
            end_date_calculated = start_date + timedelta(days=days - 1)

            existing_permit = PermitRequest.objects.filter(
                employee=employee,
                status__in=['REQUESTED', 'APPROVED'],
                start_date__lte=end_date_calculated,
                end_date__gte=start_date
            ).first()

            if existing_permit:
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': 'Ya existe un permiso registrado en estas fechas.'
                }, status=400)

            factor_day = Decimal('1.0')
            proportional_day = Decimal('0.4')
            total_discount = (Decimal(str(days)) * factor_day) + (Decimal(str(days)) * proportional_day)

            if active_balance.balance_days < total_discount:
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': f'Saldo insuficiente. Disponible: {active_balance.balance_days} días, Requerido: {total_discount:.2f} días'
                }, status=400)

            permit_type = PermitType.objects.filter(name='Personales', is_active=True).first()
            if not permit_type:
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': 'No se encontró el tipo de permiso "Personales"'
                }, status=400)

            PermitRequest.objects.create(
                employee=employee,
                permit_type=permit_type,
                start_date=start_date,
                start_time=time(8, 0),
                end_date=end_date_calculated,
                end_time=None,
                days=days,
                hours=0,
                minutes=0,
                status='REQUESTED',
                created_by=self.request.user
            )

            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': 'Solicitud de permiso creada exitosamente. Pendiente de aprobación.',
                'redirect_url': reverse('vacation:employee_vacation_detail', kwargs={'employee_id': employee.id})
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'success': False, 'message': str(e)}, status=500)

    def form_invalid(self, form):
        errors = {k: v[0] for k, v in form.errors.items()}
        return JsonResponse({
            'status': 'error',
            'success': False,
            'message': 'Por favor corrija los errores en el formulario',
            'errors': errors
        }, status=400)


class EmployeePermitListView(LoginRequiredMixin, TemplateView):
    template_name = 'vacation/modals/modal_permit_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee.objects.select_related('person'), pk=self.kwargs['employee_id'])

        try:
            personal_permit_type = PermitType.objects.get(name='Personales', is_active=True)
            permits_queryset = PermitRequest.objects.filter(
                employee=employee,
                permit_type=personal_permit_type
            ).select_related('permit_type', 'employee__person')

            search_query = self.request.GET.get('search', '').strip()
            if search_query:
                from datetime import datetime
                try:
                    search_date = datetime.strptime(search_query, '%d/%m/%Y').date()
                    permits_queryset = permits_queryset.filter(Q(start_date=search_date) | Q(end_date=search_date))
                except ValueError:
                    pass
                context['search_query'] = search_query

            permits_queryset = permits_queryset.order_by('-start_date', '-id')
            paginator = Paginator(permits_queryset, 10)
            permits = paginator.page(self.request.GET.get('page', 1))
        except Exception:
            permits = []

        context['employee'] = employee
        context['permits'] = permits
        context['titulo'] = f'Listado de Permisos - {employee.person.full_name}'
        return context


class ApprovePermitView(LoginRequiredMixin, View):
    def post(self, request, permit_id):
        try:
            permit = get_object_or_404(PermitRequest, pk=permit_id)
            if permit.status != 'REQUESTED':
                return JsonResponse({
                    'status': 'error',
                    'success': False,
                    'message': f'Estado actual: {permit.get_status_display()}'
                }, status=400)

            active_balance = EmployeeVacationBalance.objects.filter(
                employee=permit.employee,
                is_active=True,
                period__is_active=True
            ).select_related('period').first()

            if not active_balance:
                return JsonResponse({'status': 'error', 'success': False, 'message': 'No tiene período activo'},
                                    status=400)

            if permit.days > 0:
                value_discount = Decimal(str(permit.days)) * Decimal('1.0')
                proportional_discount = Decimal(str(permit.days)) * Decimal('0.4')
            else:
                hours = permit.hours or 0
                minutes = permit.minutes or 0
                value_discount = (Decimal(str(hours)) * Decimal('0.125')) + (
                        Decimal(str(minutes)) * Decimal('0.00208333'))
                proportional_discount = (Decimal(str(hours)) * Decimal('0.05')) + (
                        Decimal(str(minutes)) * Decimal('0.00083333'))

            total_discount = value_discount + proportional_discount
            if active_balance.balance_days < total_discount:
                return JsonResponse({'status': 'error', 'success': False, 'message': 'Saldo insuficiente.'}, status=400)

            obs = f'Permiso {permit.days}d' if permit.days > 0 else f'Permiso {permit.hours}h {permit.minutes}m'
            VacationHistory.objects.create(
                vacation_balance=active_balance,
                permit_request=permit,
                value_discount=float(value_discount),
                proportional_discount=float(proportional_discount),
                days_discount=float(permit.days) if permit.days > 0 else None,
                hours_discount=float(permit.hours) if permit.hours > 0 else None,
                minutes_discount=float(permit.minutes) if permit.minutes > 0 else None,
                observation=f"{obs} APROBADO período {active_balance.period.name}",
                created_by=request.user
            )

            EmployeeVacationBalance.objects.filter(id=active_balance.id).update(
                balance_days=F('balance_days') - total_discount,
                permit_days=F('permit_days') + total_discount
            )

            permit.status = 'APPROVED'
            permit.response_by = request.user
            permit.response_date = timezone.now()
            permit.save()

            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': f'Permiso aprobado exitosamente. Descuento: {total_discount:.2f} días'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'success': False, 'message': str(e)}, status=500)


class RejectPermitView(LoginRequiredMixin, View):
    def post(self, request, permit_id):
        permit = get_object_or_404(PermitRequest, pk=permit_id)
        if permit.status != 'REQUESTED':
            return JsonResponse({'status': 'error', 'success': False, 'message': 'Permiso ya procesado'}, status=400)

        permit.status = 'REJECTED'
        permit.response_by = request.user
        permit.response_date = timezone.now()
        permit.save()
        return JsonResponse({'status': 'success', 'success': True, 'message': 'Permiso rechazado exitosamente'})


class CancelPermitView(LoginRequiredMixin, View):
    def post(self, request, permit_id):
        permit = get_object_or_404(PermitRequest, pk=permit_id)
        if permit.status not in ['REQUESTED', 'APPROVED']:
            return JsonResponse({'status': 'error', 'success': False, 'message': 'No se puede anular este permiso'},
                                status=400)

        if permit.status == 'APPROVED':
            try:
                hist = VacationHistory.objects.get(permit_request=permit)
                total_discount = Decimal(str(hist.value_discount)) + Decimal(str(hist.proportional_discount))
                EmployeeVacationBalance.objects.filter(id=hist.vacation_balance.id).update(
                    balance_days=F('balance_days') + total_discount,
                    permit_days=F('permit_days') - total_discount
                )
                hist.delete()
            except VacationHistory.DoesNotExist:
                pass

        permit.delete()
        return JsonResponse({'status': 'success', 'success': True, 'message': 'Permiso anulado exitosamente'})


# ==============================================================================
# VACATION LIQUIDATIONS
# ==============================================================================

class CreateVacationLiquidationView(LoginRequiredMixin, FormView):
    template_name = 'vacation/modals/modal_liquidation_form.html'
    form_class = VacationLiquidationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
        balance = EmployeeVacationBalance.objects.filter(employee=employee, is_active=True).order_by(
            '-created_at').first()
        context['employee'] = employee
        context['balance'] = balance
        context['available_days'] = balance.balance_days if balance else 0
        context['action_url'] = reverse('vacation:create_liquidation', kwargs={'employee_id': employee.id})
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
        balance = EmployeeVacationBalance.objects.filter(employee=employee, is_active=True).order_by(
            '-created_at').first()
        kwargs['available_days'] = balance.balance_days if balance else 0
        return kwargs

    def form_valid(self, form):
        try:
            employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
            balance = EmployeeVacationBalance.objects.filter(employee=employee, is_active=True).order_by(
                '-created_at').first()

            if not balance:
                return JsonResponse({'status': 'error', 'success': False, 'message': 'Sin saldo de vacaciones activo.'},
                                    status=400)

            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            days_requested = form.cleaned_data['days_requested']

            overlapping = VacationRequest.objects.filter(
                employee=employee,
                balance_used=balance,
                status__in=['PENDING', 'APPROVED'],
                start_date__lte=end_date,
                end_date__gte=start_date
            ).exists()

            if overlapping:
                return JsonResponse(
                    {'status': 'error', 'success': False, 'message': 'Ya existe una solicitud en ese rango de fechas.'},
                    status=400)

            with transaction.atomic():
                action_type = ActionType.objects.filter(name__iexact='VACACIONES').first()
                if not action_type:
                    return JsonResponse(
                        {'status': 'error', 'success': False, 'message': 'Tipo de acción VACACIONES no encontrado.'},
                        status=400)

                current_year = dt.date.today().year
                last_action = PersonnelAction.objects.filter(number__endswith=f'-{current_year}').order_by(
                    '-number').first()
                new_number = 1
                if last_action:
                    try:
                        new_number = int(last_action.number.split('-')[0]) + 1
                    except (ValueError, IndexError):
                        new_number = 1
                action_number = f"{new_number:04d}-{current_year}"

                reintegro_date = end_date + dt.timedelta(days=1)
                explanation = (
                    f'LIQUIDACIÓN DE {days_requested} DÍAS DE VACACIONES AL SERVIDOR DESDE EL "{start_date}" '
                    f'AL "{end_date}" CORRESPONDIENTE AL PERIODO "{balance.period}". '
                    f'REINTEGRO: {reintegro_date}'
                )

                personnel_action = PersonnelAction.objects.create(
                    employee=employee,
                    action_type=action_type,
                    number=action_number,
                    explanation=explanation,
                    motivation='SOLICITUD DE VACACIONES',
                    date_issue=dt.date.today(),
                    date_effective=start_date,
                    is_registered=False,
                    authority_1=form.cleaned_data['nominating_authority'],
                    authority_2=form.cleaned_data['human_resources_responsible'],
                    register=form.cleaned_data['registration_responsible'],
                    reviewer=form.cleaned_data['review_responsible'],
                    elaboration=form.cleaned_data['elaborated_by'],
                    created_by=self.request.user
                )

                VacationRequest.objects.create(
                    employee=employee,
                    balance_used=balance,
                    start_date=start_date,
                    end_date=end_date,
                    days_quantity=Decimal(str(days_requested)),
                    status='PENDING',
                    personnel_action=personnel_action,
                    created_by=self.request.user,
                    date_issued=dt.date.today()
                )

            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': f'Solicitud de liquidación creada exitosamente. Acción No. {action_number}'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'success': False, 'message': str(e)}, status=500)

    def form_invalid(self, form):
        errors = {k: v[0] for k, v in form.errors.items()}
        return JsonResponse({
            'status': 'error',
            'success': False,
            'message': 'Por favor corrija los errores en el formulario',
            'errors': errors
        }, status=400)


class EmployeeLiquidationListView(LoginRequiredMixin, TemplateView):
    template_name = 'vacation/modals/modal_liquidation_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee.objects.select_related('person'), pk=self.kwargs['employee_id'])
        vacation_action_type = ActionType.objects.filter(name__iexact='VACACIONES').first()

        actions = PersonnelAction.objects.filter(
            employee=employee,
            action_type=vacation_action_type
        ).select_related('action_type', 'employee__person', 'vacation_request')

        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            actions = actions.filter(number__icontains=search_query)

        actions = actions.order_by('-date_issue', '-id')
        paginator = Paginator(actions, 10)
        page_obj = paginator.page(self.request.GET.get('page', 1))

        context['employee'] = employee
        context['actions'] = page_obj
        context['search_query'] = search_query
        return context


class RegisterLiquidationView(LoginRequiredMixin, View):
    def post(self, request, action_id):
        try:
            action = get_object_or_404(PersonnelAction, pk=action_id)
            if action.is_registered:
                return JsonResponse({'status': 'error', 'success': False, 'message': 'Esta acción ya está registrada.'},
                                    status=400)

            vacation_request = VacationRequest.objects.get(personnel_action=action)

            with transaction.atomic():
                action.is_registered = True
                action.date_registered = dt.date.today()
                action.save()

                vacation_request.status = 'APPROVED'
                vacation_request.approved_by = request.user
                vacation_request.save()

                days_to_discount = float(vacation_request.days_quantity)
                VacationHistory.objects.create(
                    vacation_balance=vacation_request.balance_used,
                    vacation_request=vacation_request,
                    value_discount=days_to_discount,
                    days_discount=days_to_discount,
                    proportional_discount=0.0,
                    hours_discount=0.0,
                    minutes_discount=0.0,
                    observation=f'Liquidación de vacaciones registrada - Acción {action.number}',
                    created_by=request.user
                )

                EmployeeVacationBalance.objects.filter(id=vacation_request.balance_used.id).update(
                    balance_days=F('balance_days') - vacation_request.days_quantity,
                    vacation_days=F('vacation_days') + vacation_request.days_quantity
                )

            return JsonResponse(
                {'status': 'success', 'success': True, 'message': 'Liquidación registrada exitosamente.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'success': False, 'message': str(e)}, status=500)


class EditLiquidationView(LoginRequiredMixin, FormView):
    template_name = 'vacation/modals/modal_liquidation_edit.html'
    form_class = VacationLiquidationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        action = get_object_or_404(PersonnelAction, pk=self.kwargs['action_id'])
        vacation_request = get_object_or_404(VacationRequest, personnel_action=action)
        context['action'] = action
        context['vacation_request'] = vacation_request
        context['employee'] = action.employee
        context['balance'] = vacation_request.balance_used
        context['action_url'] = reverse('vacation:edit_liquidation', kwargs={'action_id': action.id})
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        action = get_object_or_404(PersonnelAction, pk=self.kwargs['action_id'])
        vacation_request = get_object_or_404(VacationRequest, personnel_action=action)
        balance = vacation_request.balance_used
        kwargs['available_days'] = float(balance.balance_days + vacation_request.days_quantity) if balance else 0

        if not self.request.POST:
            kwargs['initial'] = {
                'start_date': vacation_request.start_date.strftime('%Y-%m-%d') if vacation_request.start_date else None,
                'end_date': vacation_request.end_date.strftime('%Y-%m-%d') if vacation_request.end_date else None,
                'nominating_authority': action.authority_1.id if action.authority_1 else None,
                'human_resources_responsible': action.authority_2.id if action.authority_2 else None,
                'registration_responsible': action.register.id if action.register else None,
                'review_responsible': action.reviewer.id if action.reviewer else None,
                'elaborated_by': action.elaboration.id if action.elaboration else None,
            }
        return kwargs

    def form_valid(self, form):
        try:
            action = get_object_or_404(PersonnelAction, pk=self.kwargs['action_id'])
            vacation_request = get_object_or_404(VacationRequest, personnel_action=action)

            if action.is_registered:
                return JsonResponse({'status': 'error', 'success': False,
                                     'message': 'No se puede editar una liquidación ya registrada.'}, status=400)

            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            days_requested = form.cleaned_data['days_requested']

            with transaction.atomic():
                vacation_request.start_date = start_date
                vacation_request.end_date = end_date
                vacation_request.days_quantity = Decimal(str(days_requested))
                vacation_request.save()

                action.date_effective = start_date
                action.authority_1 = form.cleaned_data['nominating_authority']
                action.authority_2 = form.cleaned_data['human_resources_responsible']
                action.register = form.cleaned_data['registration_responsible']
                action.reviewer = form.cleaned_data['review_responsible']
                action.elaboration = form.cleaned_data['elaborated_by']
                action.save()

            return JsonResponse(
                {'status': 'success', 'success': True, 'message': 'Liquidación actualizada exitosamente.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'success': False, 'message': str(e)}, status=500)

    def form_invalid(self, form):
        errors = {k: v[0] for k, v in form.errors.items()}
        return JsonResponse({
            'status': 'error',
            'success': False,
            'message': 'Por favor corrija los errores en el formulario',
            'errors': errors
        }, status=400)


# ==============================================================================
# HISTORIES AND PDF REPORTS
# ==============================================================================

class VacationHistoryDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'vacation/modals/modal_vacation_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        balance = get_object_or_404(
            EmployeeVacationBalance.objects.select_related('employee__person', 'period'),
            pk=self.kwargs.get('balance_id')
        )
        history_records = VacationHistory.objects.filter(
            vacation_balance=balance,
            vacation_request__isnull=False
        ).select_related('vacation_request', 'vacation_request__personnel_action').order_by('-created_at')

        context['employee'] = balance.employee
        context['period'] = balance.period
        context['balance'] = balance
        context['history_records'] = history_records
        return context


class PermitHistoryDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'vacation/modals/modal_permit_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        balance = get_object_or_404(
            EmployeeVacationBalance.objects.select_related('employee__person', 'period'),
            pk=self.kwargs.get('balance_id')
        )
        history_records = VacationHistory.objects.filter(
            vacation_balance=balance,
            permit_request__isnull=False
        ).select_related('permit_request').order_by('-created_at')

        context['employee'] = balance.employee
        context['period'] = balance.period
        context['balance'] = balance
        context['history_records'] = history_records
        return context


class PermitReportModalView(LoginRequiredMixin, TemplateView):
    template_name = 'vacation/modals/modal_permit_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee.objects.select_related('person'), pk=self.kwargs.get('employee_id'))
        context['employee'] = employee
        return context


class PermitReportPDFView(LoginRequiredMixin, View):
    def get(self, request, employee_id):
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        if not start_date_str or not end_date_str:
            return HttpResponse('Fechas no proporcionadas', status=400)

        start_date = dt.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = dt.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        employee = get_object_or_404(Employee.objects.select_related('person', 'area'), pk=employee_id)

        permits = VacationHistory.objects.filter(
            vacation_balance__employee=employee,
            permit_request__isnull=False,
            permit_request__start_date__gte=start_date,
            permit_request__start_date__lte=end_date,
            permit_request__status='APPROVED'
        ).select_related(
            'permit_request',
            'permit_request__permit_type',
            'vacation_balance__period'
        ).order_by('permit_request__start_date')

        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph('REPORTE DE PERMISOS CON CARGO A VACACIONES', styles['Heading1']))
        elements.append(Paragraph(f'Empleado: {employee.person.full_name}', styles['Normal']))
        elements.append(Paragraph(f'Período: {start_date} al {end_date}', styles['Normal']))
        elements.append(Spacer(1, 20))

        doc.build(elements)
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Reporte_Permisos_{employee_id}.pdf"'
        return response


class LiquidationPrintPDFView(LoginRequiredMixin, View):
    def get(self, request, action_id):
        from xhtml2pdf import pisa
        action = get_object_or_404(
            PersonnelAction.objects.select_related('employee__person', 'action_type'),
            pk=action_id
        )
        vacation_request = getattr(action, 'vacation_request', None)

        if not vacation_request:
            return HttpResponse('Esta acción no está relacionada con liquidación de vacaciones', status=400)

        template = get_template('vacation/reports/pdf_liquidation.html')
        html = template.render({
            'action': action,
            'employee': action.employee,
            'vacation_request': vacation_request,
            'today': dt.datetime.now()
        })

        buffer = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), buffer, encoding='UTF-8')
        if not pdf.err:
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Liquidacion_{action.number}.pdf"'
            return response
        return HttpResponse('Error al generar PDF', status=500)
