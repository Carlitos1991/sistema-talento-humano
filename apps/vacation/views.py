from django.contrib import messages
from django.http import request, JsonResponse
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, TemplateView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db.models import Q, Prefetch
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect
from decimal import Decimal

from .forms import *
# Importamos los nuevos modelos refactorizados
from .models import VacationRequest, VacationPeriod, EmployeeVacationBalance
from employee.models import Employee
from budget.models import BudgetLine


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
        kwargs['employee_id'] = self.kwargs.get('employee_id')
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
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
        
        # Obtener todos los balances del empleado ordenados por creación (más reciente primero)
        vacation_balances = EmployeeVacationBalance.objects.filter(
            employee=employee,
            is_active=True
        ).select_related('period').order_by('-created_at')
        
        context['employee'] = employee
        context['vacation_balances'] = vacation_balances
        
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
        kwargs['employee_id'] = self.kwargs.get('employee_id')
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])
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
