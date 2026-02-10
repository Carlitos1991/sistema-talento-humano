from django.contrib import messages
from django.http import request, JsonResponse
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import ListView, TemplateView, CreateView, UpdateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db.models import Q, Prefetch
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from decimal import Decimal
from django.utils import timezone

from .forms import *
# Importamos los nuevos modelos refactorizados
from .models import VacationRequest, VacationPeriod, EmployeeVacationBalance, VacationHistory
from employee.models import Employee
from budget.models import BudgetLine
from permitrequest.models import PermitRequest


class VacationRequestListView(LoginRequiredMixin, ListView):
    """
    Vista para 'Administrar Solicitudes' - Listado de empleados con sus vacaciones.
    Similar al listado de empleados-permisos.
    """
    model = Employee
    template_name = 'vacation/vacation_request_list.html'
    context_object_name = 'employees_data'
    paginate_by = 10

    def get_queryset(self):
        # Obtener empleados activos con sus relaciones
        qs = Employee.objects.filter(
            is_active=True
        ).select_related(
            'person',
            'area'
        ).prefetch_related(
            Prefetch('employeevacationbalance_set', 
                    queryset=EmployeeVacationBalance.objects.select_related('period').filter(is_active=True))
        ).order_by('person__last_name', 'person__first_name')
        
        # Búsqueda
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(person__first_name__icontains=q) |
                Q(person__last_name__icontains=q) |
                Q(person__document_number__icontains=q)
            )
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Preparar datos para cada empleado
        employees_data = []
        for employee in context['object_list']:
            # Obtener el presupuesto activo
            budget = BudgetLine.objects.filter(
                current_employee=employee,
                is_active=True
            ).select_related('position_item').first()
            
            # Obtener saldo de vacaciones activo
            vacation_balance = employee.employeevacationbalance_set.filter(is_active=True).first()
            
            employees_data.append({
                'employee': employee,
                'budget': budget,
                'vacation_balance': vacation_balance,
                'has_vacation': vacation_balance is not None
            })
        
        context['employees_data'] = employees_data
        context['search_query'] = self.request.GET.get('q', '')
        return context
    
    def render_to_response(self, context, **response_kwargs):
        # Si es AJAX, devolver solo la tabla
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('vacation/partials/partial_vacation_employee_list.html', 
                                   context, request=self.request)
            
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


class VacationCreateView(LoginRequiredMixin, TemplateView):
    """
    Vista para 'Generar Solicitud'.
    Usamos TemplateView por ahora, luego la cambiaremos a CreateView con Ajax.
    """
    template_name = 'vacation/modals/modal_vacation_form.html'


class PeriodListView(LoginRequiredMixin, ListView):
    """
    Vista para 'Administrar Periodos/Saldos'.
    """
    model = VacationPeriod
    template_name = 'vacation/period_list.html'
    context_object_name = 'periods'
    paginate_by = 10
    
    def get_queryset(self):
        qs = VacationPeriod.objects.all()
        
        # Ordenamiento dinámico
        order_by = self.request.GET.get('order_by', 'name')
        direction = self.request.GET.get('direction', 'asc')
        
        # Validar campos permitidos
        allowed_fields = ['name', 'is_active']
        if order_by in allowed_fields:
            if direction == 'desc':
                order_by = f'-{order_by}'
            qs = qs.order_by(order_by)
        else:
            qs = qs.order_by('name')
        
        # Búsqueda por nombre de periodo
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
    """
    Vista para crear un nuevo periodo vía Modal.
    """
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
            response = super().form_valid(form)
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Periodo "{self.object.name}" creado exitosamente',
                    'redirect_url': str(self.success_url)
                })
            messages.success(self.request, f'Periodo "{self.object.name}" creado exitosamente')
            return response
        except IntegrityError:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Este periodo ya existe en el sistema',
                    'errors': {'name': ['Ya existe un periodo con este nombre']}
                }, status=400)
            form.add_error('name', 'Ya existe un periodo con este nombre')
            return self.form_invalid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(error) for error in error_list]
            return JsonResponse({
                'success': False,
                'message': 'Por favor corrija los errores en el formulario',
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


class PeriodUpdateView(LoginRequiredMixin, UpdateView):
    """
    Vista para editar un periodo existente vía Modal.
    """
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
            response = super().form_valid(form)
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Periodo "{self.object.name}" actualizado exitosamente',
                    'redirect_url': str(self.success_url)
                })
            messages.success(self.request, f'Periodo "{self.object.name}" actualizado exitosamente')
            return response
        except IntegrityError:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Este periodo ya existe en el sistema',
                    'errors': {'name': ['Ya existe un periodo con este nombre']}
                }, status=400)
            form.add_error('name', 'Ya existe un periodo con este nombre')
            return self.form_invalid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(error) for error in error_list]
            return JsonResponse({
                'success': False,
                'message': 'Por favor corrija los errores en el formulario',
                'errors': errors
            }, status=400)
        return super().form_invalid(form)

class CreateFirstVacationView(LoginRequiredMixin, CreateView):
    """
    Vista para crear el primer periodo de vacaciones de un empleado.
    """
    model = EmployeeVacationBalance
    form_class = FirstVacationForm
    template_name = 'vacation/modals/modal_first_vacation_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        employee_id = self.kwargs.get('employee_id')
        kwargs['employee_id'] = employee_id
        
        # Calcular días para mostrar en el formulario
        employee = get_object_or_404(Employee.objects.select_related('employment_status'), pk=employee_id)
        previous_balances = EmployeeVacationBalance.objects.filter(employee=employee).order_by('created_at')
        
        is_trabajador = employee.employment_status and employee.employment_status.code == 'TRABAJADOR'
        base_days = Decimal('15.0') if is_trabajador else Decimal('30.0')
        
        additional_days = Decimal('0.0')
        if is_trabajador:
            num_periods = previous_balances.count()
            if num_periods >= 4:
                years_bonus = min(num_periods - 3, 15)
                additional_days = Decimal(str(years_bonus))
        
        new_period_days = base_days + additional_days
        kwargs['initial_days'] = new_period_days
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(
            Employee.objects.select_related('person').prefetch_related('current_budget_line__position_item'),
            pk=self.kwargs['employee_id']
        )
        context['employee'] = employee
        context['titulo'] = f'Crear Primera Vacación para {employee.person.full_name}'
        context['action_url'] = reverse('vacation:create_first_vacation', kwargs={'employee_id': employee.id})
        return context

    def form_valid(self, form):
        employee = get_object_or_404(Employee.objects.select_related('employment_status'), pk=self.kwargs['employee_id'])
        
        # Obtener todos los periodos anteriores (ordenados por fecha de creación)
        previous_balances = EmployeeVacationBalance.objects.filter(
            employee=employee
        ).order_by('created_at')
        
        # Determinar días base según el estado laboral
        is_trabajador = employee.employment_status and employee.employment_status.code == 'TRABAJADOR'
        base_days = Decimal('15.0') if is_trabajador else Decimal('30.0')
        
        # Calcular días adicionales para TRABAJADOR (a partir del quinto año)
        additional_days = Decimal('0.0')
        if is_trabajador:
            num_periods = previous_balances.count()
            if num_periods >= 4:  # A partir del 5to período (índice 4)
                years_bonus = min(num_periods - 3, 15)  # Máximo 15 años extra
                additional_days = Decimal(str(years_bonus))
        
        # Días totales para este período
        new_period_days = base_days + additional_days
        
        # Calcular balance
        if previous_balances.exists():
            # Obtener el balance anterior
            last_balance = previous_balances.last()
            previous_balance = last_balance.balance_days
            
            # Calcular nuevo balance
            calculated_balance = previous_balance + new_period_days
            
            # Límite máximo según tipo
            max_limit = Decimal('45.0') if is_trabajador else Decimal('60.0')
            
            # Calcular días perdidos
            lost_days = Decimal('0.0')
            if calculated_balance > max_limit:
                lost_days = calculated_balance - max_limit
                final_balance = max_limit
            else:
                final_balance = calculated_balance
            
            # Generar observación
            period_name = form.cleaned_data['period'].name
            
            if lost_days > 0:
                if is_trabajador:
                    observation = (
                        f"Se creó el período {period_name} con un balance de {final_balance} días. "
                        f"IMPORTANTE: El empleado perdió {lost_days} días del período {period_name} "
                        f"por exceder el límite máximo de tres periodos "
                        f"(balance anterior: {previous_balance} días + {new_period_days} días nuevos = {calculated_balance} días)."
                    )
                else:
                    observation = (
                        f"Se creó el período {period_name} con un balance de {final_balance} días. "
                        f"IMPORTANTE: El empleado perdió {lost_days} días "
                        f"por exceder el límite máximo de 60 días "
                        f"(balance anterior: {previous_balance} días + {new_period_days} días nuevos = {calculated_balance} días)."
                    )
            else:
                observation = (
                    f"Se creó el período {period_name} con un balance de {final_balance} días "
                    f"(balance anterior: {previous_balance} días + {new_period_days} días nuevos)."
                )
        else:
            # Primer período
            final_balance = new_period_days
            period_name = form.cleaned_data['period'].name
            observation = (
                f"Se creó el período {period_name} con un balance inicial de {final_balance} días "
                f"(primer período del empleado)."
            )
        
        # Crear el balance
        balance = form.save(commit=False)
        balance.employee = employee
        balance.total_days = new_period_days
        balance.balance_days = final_balance
        balance.observation = observation
        
        # Guardar días adicionales (balance del período anterior)
        if previous_balances.exists():
            last_balance = previous_balances.last()
            balance.additional_days = last_balance.balance_days
        else:
            balance.additional_days = Decimal('0.0')
        
        balance.is_active = True
        balance.created_by = self.request.user
        balance.save()
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Periodo de vacaciones creado exitosamente',
                'redirect_url': reverse('vacation:employee_vacation_detail', kwargs={'employee_id': employee.id})
            })
        
        messages.success(self.request, 'Periodo de vacaciones creado exitosamente')
        return redirect('vacation:employee_vacation_detail', employee_id=employee.id)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(error) for error in error_list]
            return JsonResponse({
                'success': False,
                'message': 'Por favor corrija los errores en el formulario',
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


class EmployeeVacationDetailView(LoginRequiredMixin, TemplateView):
    """
    Vista para mostrar el detalle de vacaciones de un empleado (segunda imagen).
    """
    template_name = 'vacation/employee_vacation_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
        
        # Obtener parámetros de búsqueda y paginación
        search_query = self.request.GET.get('search', '').strip()
        page_number = self.request.GET.get('page', 1)
        per_page = self.request.GET.get('per_page', 10)
        
        # Obtener todos los balances del empleado ordenados por creación (más reciente primero)
        vacation_balances = EmployeeVacationBalance.objects.filter(
            employee=employee,
            is_active=True
        ).select_related('period').order_by('-created_at')
        
        # Obtener el balance activo (del periodo activo) para las estadísticas
        active_balance = EmployeeVacationBalance.objects.filter(
            employee=employee,
            is_active=True,
            period__is_active=True
        ).select_related('period').first()
        
        # Aplicar búsqueda por periodo si existe
        if search_query:
            vacation_balances = vacation_balances.filter(period__name__icontains=search_query)
        
        # Paginación
        paginator = Paginator(vacation_balances, per_page)
        
        # Si no hay resultados, usar página 1
        if paginator.count == 0:
            vacation_balances_page = paginator.page(1)
        else:
            try:
                vacation_balances_page = paginator.page(page_number)
            except PageNotAnInteger:
                vacation_balances_page = paginator.page(1)
            except EmptyPage:
                vacation_balances_page = paginator.page(paginator.num_pages)
        
        context['employee'] = employee
        context['active_balance'] = active_balance
        context['vacation_balances'] = vacation_balances_page
        context['search_query'] = search_query
        context['per_page'] = int(per_page)
        
        return context


class CreateNewVacationPeriodView(LoginRequiredMixin, CreateView):
    """
    Vista para crear un nuevo periodo de vacaciones (segundo período en adelante).
    Similar a CreateFirstVacationView pero para períodos subsecuentes.
    """
    model = EmployeeVacationBalance
    form_class = FirstVacationForm
    template_name = 'vacation/modals/modal_new_vacation_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        employee_id = self.kwargs.get('employee_id')
        kwargs['employee_id'] = employee_id
        
        # Calcular días para mostrar en el formulario
        employee = get_object_or_404(Employee.objects.select_related('employment_status'), pk=employee_id)
        previous_balances = EmployeeVacationBalance.objects.filter(employee=employee).order_by('created_at')
        
        is_trabajador = employee.employment_status and employee.employment_status.code == 'TRABAJADOR'
        base_days = Decimal('15.0') if is_trabajador else Decimal('30.0')
        
        additional_days = Decimal('0.0')
        if is_trabajador:
            num_periods = previous_balances.count()
            if num_periods >= 4:
                years_bonus = min(num_periods - 3, 15)
                additional_days = Decimal(str(years_bonus))
        
        new_period_days = base_days + additional_days
        kwargs['initial_days'] = new_period_days
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(
            Employee.objects.select_related('person').prefetch_related('current_budget_line__position_item'),
            pk=self.kwargs['employee_id']
        )
        context['employee'] = employee
        context['titulo'] = f'Nueva Vacación para {employee.person.full_name}'
        context['action_url'] = reverse('vacation:create_new_vacation', kwargs={'employee_id': employee.id})
        return context

    def form_valid(self, form):
        employee = get_object_or_404(Employee.objects.select_related('employment_status'), pk=self.kwargs['employee_id'])
        
        # Obtener todos los periodos anteriores (ordenados por fecha de creación)
        previous_balances = EmployeeVacationBalance.objects.filter(
            employee=employee
        ).order_by('created_at')
        
        # Determinar días base según el estado laboral
        is_trabajador = employee.employment_status and employee.employment_status.code == 'TRABAJADOR'
        base_days = Decimal('15.0') if is_trabajador else Decimal('30.0')
        
        # Calcular días adicionales para TRABAJADOR (a partir del quinto año)
        additional_days = Decimal('0.0')
        if is_trabajador:
            num_periods = previous_balances.count()
            if num_periods >= 4:  # A partir del 5to período (índice 4)
                years_bonus = min(num_periods - 3, 15)  # Máximo 15 años extra
                additional_days = Decimal(str(years_bonus))
        
        # Días totales para este período
        new_period_days = base_days + additional_days
        
        # Obtener el balance anterior
        last_balance = previous_balances.last()
        previous_balance = last_balance.balance_days if last_balance else Decimal('0.0')
        
        # Calcular nuevo balance
        calculated_balance = previous_balance + new_period_days
        
        # Límite máximo según tipo
        max_limit = Decimal('45.0') if is_trabajador else Decimal('60.0')
        
        # Calcular días perdidos
        lost_days = Decimal('0.0')
        if calculated_balance > max_limit:
            lost_days = calculated_balance - max_limit
            final_balance = max_limit
        else:
            final_balance = calculated_balance
        
        # Generar observación
        period_name = form.cleaned_data['period'].name
        
        if lost_days > 0:
            if is_trabajador:
                observation = (
                    f"Se creó el período {period_name} con un balance de {final_balance} días. "
                    f"IMPORTANTE: El empleado perdió {lost_days} días del período {period_name} "
                    f"por exceder el límite máximo de tres periodos "
                    f"(balance anterior: {previous_balance} días + {new_period_days} días nuevos = {calculated_balance} días)."
                )
            else:
                observation = (
                    f"Se creó el período {period_name} con un balance de {final_balance} días. "
                    f"IMPORTANTE: El empleado perdió {lost_days} días del período {period_name} "
                    f"por exceder el límite máximo de 60 días "
                    f"(balance anterior: {previous_balance} días + {new_period_days} días nuevos = {calculated_balance} días)."
                )
        else:
            observation = (
                f"Se creó el período {period_name} con un balance de {final_balance} días "
                f"(balance anterior: {previous_balance} días + {new_period_days} días nuevos)."
            )
        
        # Crear el balance
        balance = form.save(commit=False)
        balance.employee = employee
        balance.total_days = new_period_days
        balance.balance_days = final_balance
        balance.observation = observation
        
        # Guardar días adicionales (balance del período anterior)
        if last_balance:
            balance.additional_days = last_balance.balance_days
        else:
            balance.additional_days = Decimal('0.0')
        
        balance.is_active = True
        balance.created_by = self.request.user
        balance.save()
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Nuevo periodo de vacaciones creado exitosamente',
                'redirect_url': reverse('vacation:employee_vacation_detail', kwargs={'employee_id': employee.id})
            })
        
        messages.success(self.request, 'Nuevo periodo de vacaciones creado exitosamente')
        return redirect('vacation:employee_vacation_detail', employee_id=employee.id)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(error) for error in error_list]
            return JsonResponse({
                'success': False,
                'message': 'Por favor corrija los errores en el formulario',
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


class CreateHourPermitVacationView(LoginRequiredMixin, FormView):
    """
    Vista para crear permisos por horas con cargo a vacaciones.
    """
    template_name = 'vacation/modals/modal_hour_permit_form.html'
    
    def get_form_class(self):
        from .forms_permit import HourPermitVacationForm
        return HourPermitVacationForm
    
    def post(self, request, *args, **kwargs):
        print("="*50)
        print("POST REQUEST RECEIVED - Hour Permit")
        print("POST data:", request.POST)
        print("Employee ID:", kwargs.get('employee_id'))
        print("="*50)
        try:
            result = super().post(request, *args, **kwargs)
            print("POST RESULT:", result.status_code if hasattr(result, 'status_code') else 'No status')
            return result
        except Exception as e:
            print("ERROR IN POST:", str(e))
            import traceback
            traceback.print_exc()
            raise
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
        
        # Obtener el balance activo del empleado
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
        print("FORM IS VALID - Starting processing")
        try:
            employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
            print(f"Employee found: {employee}")
            
            # Obtener el balance activo
            active_balance = EmployeeVacationBalance.objects.filter(
                employee=employee,
                is_active=True,
                period__is_active=True
            ).select_related('period').first()
            print(f"Active balance: {active_balance}")
            
            if not active_balance:
                print("ERROR: No active balance found")
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'El empleado no tiene un periodo de vacaciones activo'
                    }, status=400)
                messages.error(self.request, 'El empleado no tiene un periodo de vacaciones activo')
                return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
            
            # Obtener datos del formulario
            start_date = form.cleaned_data['start_date']
            start_time = form.cleaned_data['start_time']
            hours = form.cleaned_data.get('hours', 0) or 0
            minutes = form.cleaned_data.get('minutes', 0) or 0
            print(f"Form data - Date: {start_date}, Time: {start_time}, Hours: {hours}, Minutes: {minutes}")
            
            # Validar que no exista un permiso en la misma fecha y hora
            from datetime import datetime, timedelta
            total_minutes_permit = (hours * 60) + minutes
            end_time_calculated = (datetime.combine(start_date, start_time) + timedelta(minutes=total_minutes_permit)).time()
            
            existing_permit = PermitRequest.objects.filter(
                employee=employee,
                start_date=start_date,
                status__in=['REQUESTED', 'APPROVED']
            ).exclude(
                start_time__gte=end_time_calculated
            ).exclude(
                end_time__lte=start_time
            ).first()
            
            if existing_permit:
                # Construir mensaje descriptivo con fechas
                if existing_permit.end_date and existing_permit.end_date != existing_permit.start_date:
                    date_range = f"del {existing_permit.start_date.strftime('%d/%m/%Y')} al {existing_permit.end_date.strftime('%d/%m/%Y')}"
                else:
                    date_range = f"el {existing_permit.start_date.strftime('%d/%m/%Y')}"
                
                error_message = f"Ya existe un permiso registrado en estas fechas ({date_range}). No se pueden crear permisos duplicados."
                
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_message
                    }, status=400)
                messages.error(self.request, error_message)
                return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
            
            # Calcular descuentos
            
            # Factores de descuento
            FACTOR_HOUR = Decimal('0.125')  # 1/8
            FACTOR_MINUTE = Decimal('0.00208333')  # 1/480
            
            # Factores proporcionales
            PROPORTIONAL_HOUR = Decimal('0.05')
            PROPORTIONAL_MINUTE = Decimal('0.00083')
            
            # Calcular descuento base
            value_discount = (Decimal(str(hours)) * FACTOR_HOUR) + (Decimal(str(minutes)) * FACTOR_MINUTE)
            
            # Calcular descuento proporcional
            proportional_discount = (Decimal(str(hours)) * PROPORTIONAL_HOUR) + (Decimal(str(minutes)) * PROPORTIONAL_MINUTE)
            
            # Descuento total
            total_discount = value_discount + proportional_discount
            print(f"Discounts - Base: {value_discount}, Proportional: {proportional_discount}, Total: {total_discount}")
            print(f"Balance available: {active_balance.balance_days}")
            
            # Verificar si hay saldo suficiente
            if active_balance.balance_days < total_discount:
                print("ERROR: Insufficient balance")
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Saldo insuficiente. Disponible: {active_balance.balance_days} días, Requerido: {total_discount} días'
                    }, status=400)
                messages.error(self.request, f'Saldo insuficiente. Disponible: {active_balance.balance_days} días')
                return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
            
            print("Balance check passed")
            
            # Obtener el tipo de permiso Personales
            from permitrequest.models import PermitType
            
            try:
                permit_type = PermitType.objects.get(
                    name='Personales',
                    is_active=True
                )
                print(f"Permit type found: {permit_type}")
            except PermitType.DoesNotExist:
                print("ERROR: PermitType 'Personales' not found")
                # Listar todos los tipos de permiso disponibles para debug
                all_permit_types = PermitType.objects.filter(is_active=True)
                print(f"Available permit types: {[pt.name for pt in all_permit_types]}")
                
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'No se encontró el tipo de permiso "Personales" activo'
                    }, status=400)
                messages.error(self.request, 'No se encontró el tipo de permiso "Personales"')
                return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
            
            # Calcular la hora de fin
            from datetime import datetime, timedelta
            total_minutes = (hours * 60) + minutes
            end_time = (datetime.combine(start_date, start_time) + timedelta(minutes=total_minutes)).time()
            
            # Crear el permiso manualmente (ya no usamos ModelForm)
            permit = PermitRequest(
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
            permit.save()
            print(f"Permit created successfully: {permit.id}")
            
            # NO crear VacationHistory ni descontar del balance hasta que se apruebe
            # El descuento se realizará cuando se apruebe el permiso
            print(f"Permit saved in REQUESTED status. Discount will be applied on approval.")
            print(f"Calculated discount would be: {total_discount} days (will be applied when approved)")
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Solicitud de permiso creada exitosamente. Pendiente de aprobación.',
                    'redirect_url': reverse('vacation:employee_vacation_detail', kwargs={'employee_id': employee.id})
                })
            
            messages.success(self.request, f'Solicitud de permiso creada exitosamente. Pendiente de aprobación.')
            return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
        
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"Error en CreateHourPermitVacationView: {str(e)}")
            print(error_detail)
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': f'Error al crear el permiso: {str(e)}'
                }, status=400)
            messages.error(self.request, f'Error al crear el permiso: {str(e)}')
            return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
    
    def form_invalid(self, form):
        print("="*50)
        print("FORM INVALID - Hour Permit")
        print("Form errors:", form.errors)
        print("Form data:", self.request.POST)
        print("="*50)
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(error) for error in error_list]
            
            # Si hay errores no relacionados a campos específicos, enviarlos como mensaje principal
            message = 'Por favor corrija los errores en el formulario'
            if form.non_field_errors():
                errors['__all__'] = [str(error) for error in form.non_field_errors()]
                message = str(form.non_field_errors()[0])  # Usar el primer error como mensaje principal
            
            return JsonResponse({
                'success': False,
                'message': message,
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


class CreateDayPermitVacationView(LoginRequiredMixin, FormView):
    """
    Vista para crear permisos por días con cargo a vacaciones.
    """
    template_name = 'vacation/modals/modal_day_permit_form.html'
    
    def get_form_class(self):
        from .forms_permit import DayPermitVacationForm
        return DayPermitVacationForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
        
        # Obtener el balance activo del empleado
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
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'El empleado no tiene un periodo de vacaciones activo'
                    }, status=400)
                messages.error(self.request, 'El empleado no tiene un periodo de vacaciones activo')
                return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
            
            start_date = form.cleaned_data['start_date']
            days = form.cleaned_data['days']
            
            # Validar que no exista un permiso en el rango de fechas
            from datetime import timedelta
            end_date_calculated = start_date + timedelta(days=days - 1)
            
            # Buscar permisos que se solapen con el rango de fechas
            existing_permit = PermitRequest.objects.filter(
                employee=employee,
                status__in=['REQUESTED', 'APPROVED']
            ).filter(
                start_date__lte=end_date_calculated,
                end_date__gte=start_date
            ).first()
            
            if existing_permit:
                # Construir mensaje descriptivo con fechas
                if existing_permit.end_date and existing_permit.end_date != existing_permit.start_date:
                    date_range = f"del {existing_permit.start_date.strftime('%d/%m/%Y')} al {existing_permit.end_date.strftime('%d/%m/%Y')}"
                else:
                    date_range = f"el {existing_permit.start_date.strftime('%d/%m/%Y')}"
                
                error_message = f"Ya existe un permiso registrado en estas fechas ({date_range}). No se pueden crear permisos duplicados."
                
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_message
                    }, status=400)
                messages.error(self.request, error_message)
                return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
            
            # Calcular descuentos: 1 día base + 0.4 días proporcional = 1.4 días total
            FACTOR_DAY = Decimal('1.0')
            PROPORTIONAL_DAY = Decimal('0.4')
            
            value_discount = Decimal(str(days)) * FACTOR_DAY
            proportional_discount = Decimal(str(days)) * PROPORTIONAL_DAY
            total_discount = value_discount + proportional_discount
            
            if active_balance.balance_days < total_discount:
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Saldo insuficiente. Disponible: {active_balance.balance_days} días, Requerido: {total_discount} días'
                    }, status=400)
                messages.error(self.request, f'Saldo insuficiente. Disponible: {active_balance.balance_days} días')
                return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
            
            from permitrequest.models import PermitType
            try:
                permit_type = PermitType.objects.get(name='Personales', is_active=True)
            except PermitType.DoesNotExist:
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'No se encontró el tipo de permiso "Personales" activo'
                    }, status=400)
                messages.error(self.request, 'No se encontró el tipo de permiso "Personales"')
                return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
            
            from datetime import timedelta, time
            end_date = start_date + timedelta(days=days - 1)
            start_time = time(8, 0)
            
            permit = PermitRequest(
                employee=employee,
                permit_type=permit_type,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date,
                end_time=None,
                days=days,
                hours=0,
                minutes=0,
                status='REQUESTED',
                created_by=self.request.user
            )
            permit.save()
            print(f"Day permit created successfully: {permit.id}")
            
            # NO crear VacationHistory ni descontar del balance hasta que se apruebe
            # El descuento se realizará cuando se apruebe el permiso
            print(f"Permit saved in REQUESTED status. Discount will be applied on approval.")
            print(f"Calculated discount would be: {total_discount} days (will be applied when approved)")
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Solicitud de permiso creada exitosamente. Pendiente de aprobación.',
                    'redirect_url': reverse('vacation:employee_vacation_detail', kwargs={'employee_id': employee.id})
                })
            
            messages.success(self.request, f'Solicitud de permiso creada exitosamente. Pendiente de aprobación.')
            return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': f'Error al crear el permiso: {str(e)}'
                }, status=400)
            messages.error(self.request, f'Error al crear el permiso: {str(e)}')
            return redirect('vacation:employee_vacation_detail', employee_id=employee.id)
    
    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(error) for error in error_list]
            
            # Si hay errores no relacionados a campos específicos, enviarlos como mensaje principal
            message = 'Por favor corrija los errores en el formulario'
            if form.non_field_errors():
                errors['__all__'] = [str(error) for error in form.non_field_errors()]
                message = str(form.non_field_errors()[0])  # Usar el primer error como mensaje principal
            
            return JsonResponse({
                'success': False,
                'message': message,
                'errors': errors
            }, status=400)
        return super().form_invalid(form)


class EmployeePermitListView(LoginRequiredMixin, TemplateView):
    """
    Vista para listar permisos con cargo a vacaciones de un empleado.
    """
    template_name = 'vacation/modals/modal_permit_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
        
        # Obtener permisos con cargo a vacaciones (tipo Personales)
        from permitrequest.models import PermitRequest, PermitType
        try:
            personal_permit_type = PermitType.objects.get(name='Personales', is_active=True)
            permits = PermitRequest.objects.filter(
                employee=employee,
                permit_type=personal_permit_type
            ).select_related('permit_type').order_by('-start_date', '-created_at')
        except PermitType.DoesNotExist:
            permits = PermitRequest.objects.none()
        
        context['employee'] = employee
        context['permits'] = permits
        context['titulo'] = f'Listado de Permisos con Cargo a Vacaciones - {employee.person.full_name}'
        return context


class ApprovePermitView(LoginRequiredMixin, View):
    """
    Vista para aprobar un permiso con cargo a vacaciones.
    Crea el VacationHistory y descuenta del balance.
    """
    def post(self, request, permit_id):
        try:
            from permitrequest.models import PermitRequest
            permit = get_object_or_404(PermitRequest, pk=permit_id)
            
            if permit.status != 'REQUESTED':
                return JsonResponse({
                    'success': False,
                    'message': f'El permiso ya fue procesado. Estado actual: {permit.get_status_display()}'
                }, status=400)
            
            # Obtener el balance activo del empleado
            active_balance = EmployeeVacationBalance.objects.filter(
                employee=permit.employee,
                is_active=True,
                period__is_active=True
            ).select_related('period').first()
            
            if not active_balance:
                return JsonResponse({
                    'success': False,
                    'message': 'El empleado no tiene un período de vacaciones activo'
                }, status=400)
            
            # Calcular descuentos según el tipo de permiso
            if permit.days > 0:
                # Permiso por días
                FACTOR_DAY = Decimal('1.0')
                PROPORTIONAL_DAY = Decimal('0.4')
                
                value_discount = Decimal(str(permit.days)) * FACTOR_DAY
                proportional_discount = Decimal(str(permit.days)) * PROPORTIONAL_DAY
                total_discount = value_discount + proportional_discount
                
            else:
                # Permiso por horas
                FACTOR_HOUR = Decimal('0.125')
                FACTOR_MINUTE = Decimal('0.00208333')
                PROPORTIONAL_HOUR = Decimal('0.05')
                PROPORTIONAL_MINUTE = Decimal('0.00083')
                
                hours = permit.hours or 0
                minutes = permit.minutes or 0
                
                value_discount = (Decimal(str(hours)) * FACTOR_HOUR) + (Decimal(str(minutes)) * FACTOR_MINUTE)
                proportional_discount = (Decimal(str(hours)) * PROPORTIONAL_HOUR) + (Decimal(str(minutes)) * PROPORTIONAL_MINUTE)
                total_discount = value_discount + proportional_discount
            
            # Verificar saldo suficiente
            if active_balance.balance_days < total_discount:
                return JsonResponse({
                    'success': False,
                    'message': f'Saldo insuficiente. Disponible: {active_balance.balance_days} días, Requerido: {total_discount} días'
                }, status=400)
            
            # Crear VacationHistory
            if permit.days > 0:
                observation = f'Permiso por {permit.days} día(s) APROBADO con cargo a vacaciones del período {active_balance.period.name}'
            else:
                observation = f'Permiso por {permit.hours}h {permit.minutes}min APROBADO con cargo a vacaciones del período {active_balance.period.name}'
            
            VacationHistory.objects.create(
                vacation_balance=active_balance,
                permit_request=permit,
                value_discount=float(value_discount),
                proportional_discount=float(proportional_discount),
                days_discount=float(permit.days) if permit.days > 0 else None,
                hours_discount=float(permit.hours) if permit.hours > 0 else None,
                minutes_discount=float(permit.minutes) if permit.minutes > 0 else None,
                observation=observation,
                created_by=request.user
            )
            
            # Descontar del balance
            from django.db.models import F
            EmployeeVacationBalance.objects.filter(id=active_balance.id).update(
                balance_days=F('balance_days') - total_discount,
                permit_days=F('permit_days') + total_discount
            )
            
            # Actualizar estado del permiso
            permit.status = 'APPROVED'
            permit.response_by = request.user
            permit.response_date = timezone.now()
            permit.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Permiso aprobado exitosamente. Descuento aplicado: {total_discount} días'
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'message': f'Error al aprobar el permiso: {str(e)}'
            }, status=500)


class RejectPermitView(LoginRequiredMixin, View):
    """
    Vista para rechazar un permiso con cargo a vacaciones.
    No crea VacationHistory ni descuenta del balance.
    """
    def post(self, request, permit_id):
        try:
            from permitrequest.models import PermitRequest
            permit = get_object_or_404(PermitRequest, pk=permit_id)
            
            if permit.status != 'REQUESTED':
                return JsonResponse({
                    'success': False,
                    'message': f'El permiso ya fue procesado. Estado actual: {permit.get_status_display()}'
                }, status=400)
            
            # Actualizar estado del permiso
            permit.status = 'REJECTED'
            permit.response_by = request.user
            permit.response_date = timezone.now()
            permit.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Permiso rechazado exitosamente'
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'message': f'Error al rechazar el permiso: {str(e)}'
            }, status=500)


class CancelPermitView(LoginRequiredMixin, View):
    """
    Vista para anular un permiso con cargo a vacaciones.
    Si ya estaba aprobado, revierte el descuento.
    """
    def post(self, request, permit_id):
        try:
            from permitrequest.models import PermitRequest
            permit = get_object_or_404(PermitRequest, pk=permit_id)
            
            if permit.status not in ['REQUESTED', 'APPROVED']:
                return JsonResponse({
                    'success': False,
                    'message': f'No se puede anular un permiso en estado: {permit.get_status_display()}'
                }, status=400)
            
            # Guardar el estado anterior para determinar el mensaje
            was_approved = permit.status == 'APPROVED'
            
            # Si estaba aprobado, revertir el descuento y eliminar registros
            if was_approved:
                try:
                    history = VacationHistory.objects.get(permit_request=permit)
                    
                    # Calcular el total descontado
                    total_discount = Decimal(str(history.value_discount)) + Decimal(str(history.proportional_discount))
                    
                    # Revertir el descuento en el balance
                    from django.db.models import F
                    EmployeeVacationBalance.objects.filter(id=history.vacation_balance.id).update(
                        balance_days=F('balance_days') + total_discount,
                        permit_days=F('permit_days') - total_discount
                    )
                    
                    # Eliminar el registro de historial
                    history.delete()
                    
                except VacationHistory.DoesNotExist:
                    pass  # Si no hay historial, continuar
            
            # Eliminar el permiso completamente
            permit.delete()
            
            if was_approved:
                message = 'Permiso anulado exitosamente. El descuento ha sido revertido y el registro eliminado.'
            else:
                message = 'Permiso anulado exitosamente. El registro ha sido eliminado.'
            
            return JsonResponse({
                'success': True,
                'message': message
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'message': f'Error al anular el permiso: {str(e)}'
            }, status=500)
