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
        employee = get_object_or_404(Employee, pk=self.kwargs['employee_id'])

        # 1. Obtener valores del formulario
        days = form.cleaned_data.get('total_days', Decimal('0'))
        hours = form.cleaned_data.get('hours', 0)
        minutes = form.cleaned_data.get('minutes', 0)
        user_detail = form.cleaned_data.get('observation_detail', '')

        # 2. Convertir horas y minutos a decimal de días usando tus constantes del modelo
        # FACTOR_HOUR = 0.125 (1/8), FACTOR_MINUTE = 0.0020833 (1/480)
        from .models import FACTOR_HOUR, FACTOR_MINUTE

        extra_from_hours = Decimal(str(hours)) * FACTOR_HOUR
        extra_from_minutes = Decimal(str(minutes)) * FACTOR_MINUTE

        # Este es el valor real que el usuario quiere guardar
        final_calculated_days = days + extra_from_hours + extra_from_minutes

        # 3. Crear el balance ignorando la lógica automática restrictiva
        balance = form.save(commit=False)
        balance.employee = employee
        balance.total_days = final_calculated_days
        balance.balance_days = final_calculated_days
        balance.additional_days = Decimal('0.0')

        # Guardar el motivo ingresado por el usuario
        period_name = form.cleaned_data['period'].name
        balance.observation = f"CARGA INICIAL PERIODO {period_name}: {user_detail}"

        balance.is_active = True
        balance.created_by = self.request.user
        balance.save()

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Periodo inicial creado exitosamente con la cantidad especificada.',
                'redirect_url': reverse('vacation:employee_vacation_detail', kwargs={'employee_id': employee.id})
            })

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
    Optimizada para rendimiento con select_related y prefetch_related.
    """
    template_name = 'vacation/employee_vacation_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(
            Employee.objects.select_related('person', 'employment_status', 'area'),
            pk=self.kwargs['employee_id']
        )

        # Obtener parámetros de búsqueda y paginación
        search_query = self.request.GET.get('search', '').strip()
        page_number = self.request.GET.get('page', 1)
        per_page = int(self.request.GET.get('per_page', 10))

        # Obtener el balance activo (del periodo activo) para las estadísticas
        # Esta consulta es independiente y se hace solo una vez
        active_balance = EmployeeVacationBalance.objects.filter(
            employee=employee,
            is_active=True,
            period__is_active=True
        ).select_related('period').first()

        # Consulta optimizada para los balances del empleado
        vacation_balances = EmployeeVacationBalance.objects.filter(
            employee=employee,
            is_active=True
        ).select_related('period')

        # Aplicar búsqueda por periodo si existe
        if search_query:
            vacation_balances = vacation_balances.filter(
                period__name__icontains=search_query
            )

        # Ordenar por fecha de creación (más reciente primero)
        vacation_balances = vacation_balances.order_by('-created_at')

        # Paginación
        paginator = Paginator(vacation_balances, per_page)

        try:
            vacation_balances_page = paginator.page(page_number)
        except PageNotAnInteger:
            vacation_balances_page = paginator.page(1)
        except EmptyPage:
            vacation_balances_page = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

        context['employee'] = employee
        context['active_balance'] = active_balance
        context['vacation_balances'] = vacation_balances_page
        context['search_query'] = search_query
        context['per_page'] = per_page

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
        employee = get_object_or_404(Employee.objects.select_related('employment_status'),
                                     pk=self.kwargs['employee_id'])

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
        print("=" * 50)
        print("POST REQUEST RECEIVED - Hour Permit")
        print("POST data:", request.POST)
        print("Employee ID:", kwargs.get('employee_id'))
        print("=" * 50)
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
            end_time_calculated = (
                    datetime.combine(start_date, start_time) + timedelta(minutes=total_minutes_permit)).time()

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
            proportional_discount = (Decimal(str(hours)) * PROPORTIONAL_HOUR) + (
                    Decimal(str(minutes)) * PROPORTIONAL_MINUTE)

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
        print("=" * 50)
        print("FORM INVALID - Hour Permit")
        print("Form errors:", form.errors)
        print("Form data:", self.request.POST)
        print("=" * 50)

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
    Incluye búsqueda por fechas y paginación.
    Optimizada con select_related para mejor rendimiento.
    """
    template_name = 'vacation/modals/modal_permit_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(
            Employee.objects.select_related('person'),
            pk=self.kwargs['employee_id']
        )

        # Obtener permisos con cargo a vacaciones (tipo Personales)
        from permitrequest.models import PermitRequest, PermitType
        from datetime import datetime

        try:
            personal_permit_type = PermitType.objects.get(name='Personales', is_active=True)

            # Query optimizada con select_related
            permits_queryset = PermitRequest.objects.filter(
                employee=employee,
                permit_type=personal_permit_type
            ).select_related('permit_type', 'employee__person')

            # Búsqueda por fecha
            search_query = self.request.GET.get('search', '').strip()
            if search_query:
                # Intentar parsear la fecha en formato dd/mm/yyyy
                try:
                    search_date = datetime.strptime(search_query, '%d/%m/%Y').date()
                    permits_queryset = permits_queryset.filter(
                        Q(start_date=search_date) | Q(end_date=search_date)
                    )
                except ValueError:
                    # Si no es una fecha válida, no filtrar (evitar consultas lentas con __icontains en fechas)
                    pass
                context['search_query'] = search_query

            # Ordenar por fecha más reciente
            permits_queryset = permits_queryset.order_by('-start_date', '-id')

            # Paginación
            paginator = Paginator(permits_queryset, 10)  # 10 permisos por página
            page_number = self.request.GET.get('page', 1)

            try:
                permits = paginator.page(page_number)
            except PageNotAnInteger:
                permits = paginator.page(1)
            except EmptyPage:
                permits = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

        except PermitType.DoesNotExist:
            permits = []

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
                # Permiso por días: por cada 5 días se agregan 2 días (40% adicional)
                FACTOR_DAY = Decimal('1.0')
                PROPORTIONAL_DAY = Decimal('0.4')  # 2/5 = 0.4

                value_discount = Decimal(str(permit.days)) * FACTOR_DAY  # Base: 2 días = 2.0
                proportional_discount = Decimal(str(permit.days)) * PROPORTIONAL_DAY  # Adicional: 2 × 0.4 = 0.8
                total_discount = value_discount + proportional_discount  # Total: 2.0 + 0.8 = 2.8

            else:
                # Permiso por horas: 1 hora = 0.125 días, adicional = 40% de eso
                FACTOR_HOUR = Decimal('0.125')  # 1/8 día
                FACTOR_MINUTE = Decimal('0.00208333')  # 1/480 día
                PROPORTIONAL_HOUR = Decimal('0.05')  # 0.125 × 0.4 = 0.05
                PROPORTIONAL_MINUTE = Decimal('0.00083333')  # 0.00208333 × 0.4

                hours = permit.hours or 0
                minutes = permit.minutes or 0

                value_discount = (Decimal(str(hours)) * FACTOR_HOUR) + (Decimal(str(minutes)) * FACTOR_MINUTE)  # Base
                proportional_discount = (Decimal(str(hours)) * PROPORTIONAL_HOUR) + (
                        Decimal(str(minutes)) * PROPORTIONAL_MINUTE)  # Adicional
                total_discount = value_discount + proportional_discount  # Total

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

            # value_discount = valor base (ej: 2 días = 2.0)
            # proportional_discount = adicional (ej: 2 × 0.4 = 0.8)
            # total = value_discount + proportional_discount (ej: 2.8)
            VacationHistory.objects.create(
                vacation_balance=active_balance,
                permit_request=permit,
                value_discount=float(value_discount),  # Base
                proportional_discount=float(proportional_discount),  # Adicional
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


class CreateVacationLiquidationView(LoginRequiredMixin, FormView):
    """
    Vista para crear una solicitud de liquidación de vacaciones.
    """
    template_name = 'vacation/modals/modal_liquidation_form.html'
    form_class = VacationLiquidationForm

    def get_employee(self):
        from employee.models import Employee
        employee_id = self.kwargs.get('employee_id')
        return get_object_or_404(Employee, pk=employee_id)

    def get_active_balance(self, employee):
        """
        Obtiene el balance activo más reciente del empleado.
        """
        try:
            return EmployeeVacationBalance.objects.filter(
                employee=employee,
                is_active=True
            ).order_by('-created_at').first()
        except EmployeeVacationBalance.DoesNotExist:
            return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.get_employee()
        balance = self.get_active_balance(employee)

        context['employee'] = employee
        context['balance'] = balance
        context['available_days'] = balance.balance_days if balance else 0

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        employee = self.get_employee()
        balance = self.get_active_balance(employee)
        kwargs['available_days'] = balance.balance_days if balance else 0
        return kwargs

    def form_valid(self, form):
        try:
            from vacation.models import VacationRequest
            from personnel_actions.models import PersonnelAction, ActionType
            from decimal import Decimal
            from django.db import transaction
            import datetime

            employee = self.get_employee()
            balance = self.get_active_balance(employee)

            if not balance:
                return JsonResponse({
                    'success': False,
                    'message': 'El empleado no tiene un saldo de vacaciones activo.'
                }, status=400)

            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            days_requested = form.cleaned_data['days_requested']

            # Validar que no haya otra solicitud de liquidación en el mismo rango de fechas
            overlapping = VacationRequest.objects.filter(
                employee=employee,
                balance_used=balance,
                status__in=['PENDING', 'APPROVED']
            ).filter(
                start_date__lte=end_date,
                end_date__gte=start_date
            ).exists()

            if overlapping:
                return JsonResponse({
                    'success': False,
                    'message': 'Ya existe una solicitud de liquidación en este rango de fechas.'
                }, status=400)

            # Usar transacción para crear todo junto
            with transaction.atomic():
                # Obtener el tipo de acción "VACACIONES"
                action_type = ActionType.objects.filter(name__iexact='VACACIONES').first()
                if not action_type:
                    return JsonResponse({
                        'success': False,
                        'message': 'No se encontró el tipo de acción "VACACIONES".'
                    }, status=400)

                # Generar el número de acción automáticamente
                current_year = datetime.date.today().year
                last_action = PersonnelAction.objects.filter(
                    number__endswith=f'-{current_year}'
                ).order_by('-number').first()

                if last_action:
                    # Extraer el número de la última acción y sumar 1
                    try:
                        last_number = int(last_action.number.split('-')[0])
                        new_number = last_number + 1
                    except (ValueError, IndexError):
                        new_number = 1
                else:
                    new_number = 1

                action_number = f"{new_number:04d}-{current_year}"

                # Formatear fechas para la explicación
                start_date_str = start_date.strftime('%d de %B de %Y')
                end_date_str = end_date.strftime('%d de %B de %Y')

                # Mapeo de meses en español
                meses = {
                    'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
                    'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
                    'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
                    'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
                }
                for eng, esp in meses.items():
                    start_date_str = start_date_str.replace(eng, esp)
                    end_date_str = end_date_str.replace(eng, esp)

                # Calcular fecha de reintegro (un día después del fin)
                reintegro_date = end_date + datetime.timedelta(days=1)
                reintegro_date_str = reintegro_date.strftime('%d de %B de %Y')
                for eng, esp in meses.items():
                    reintegro_date_str = reintegro_date_str.replace(eng, esp)

                explanation = (
                    f'SEGÚN REQUERIMIENTO DEL SERVIDOR Y AUTORIZACIÓN DEL JEFE INMEDIATO SE LIQUIDA '
                    f'{days_requested} DÍAS DE VACACIONES AL SERVIDOR DESDE EL "{start_date_str}" '
                    f'AL "{end_date_str}" CORRESPONDIENTE AL PERIODO "{balance.period}". '
                    f'Debiendo reintegrarse el día {reintegro_date_str}'
                )

                # Crear la acción de personal
                personnel_action = PersonnelAction.objects.create(
                    employee=employee,
                    action_type=action_type,
                    number=action_number,
                    explanation=explanation,
                    motivation='SOLICITUD DE VACACIONES',
                    date_issue=datetime.date.today(),
                    date_effective=start_date,
                    is_registered=False,
                    authority_1=form.cleaned_data['nominating_authority'],
                    authority_2=form.cleaned_data['human_resources_responsible'],
                    register=form.cleaned_data['registration_responsible'],
                    reviewer=form.cleaned_data['review_responsible'],
                    elaboration=form.cleaned_data['elaborated_by'],
                    created_by=self.request.user
                )

                # Crear la solicitud de liquidación vinculada a la acción de personal
                vacation_request = VacationRequest.objects.create(
                    employee=employee,
                    balance_used=balance,
                    start_date=start_date,
                    end_date=end_date,
                    days_quantity=Decimal(str(days_requested)),
                    status='PENDING',
                    personnel_action=personnel_action,
                    created_by=self.request.user,
                    date_issued=datetime.date.today()
                )

            return JsonResponse({
                'success': True,
                'message': f'Solicitud de liquidación creada exitosamente por {days_requested} días. Acción de Personal No. {action_number}'
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'message': f'Error al crear la solicitud: {str(e)}'
            }, status=500)

    def form_invalid(self, form):
        errors = form.errors.as_json()
        error_message = 'Error en el formulario'

        if form.non_field_errors():
            error_message = form.non_field_errors()[0]

        return JsonResponse({
            'success': False,
            'message': error_message,
            'errors': errors
        }, status=400)


class EmployeeLiquidationListView(LoginRequiredMixin, TemplateView):
    """
    Vista para listar las liquidaciones de vacaciones (acciones de personal de tipo VACACIONES) de un empleado.
    Optimizada con select_related y prefetch_related para mejor rendimiento.
    """
    template_name = 'vacation/modals/modal_liquidation_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from employee.models import Employee
        from personnel_actions.models import PersonnelAction, ActionType
        from django.core.paginator import Paginator
        from django.db.models import Prefetch

        employee_id = self.kwargs.get('employee_id')
        employee = get_object_or_404(
            Employee.objects.select_related('person'),
            pk=employee_id
        )

        # Obtener el tipo de acción VACACIONES (cachear para evitar consultas repetidas)
        vacation_action_type = ActionType.objects.filter(name__iexact='VACACIONES').first()

        # Query optimizada con select_related para todas las relaciones necesarias
        actions = PersonnelAction.objects.filter(
            employee=employee,
            action_type=vacation_action_type
        ).select_related(
            'action_type',
            'authority_1',
            'authority_2',
            'reviewer',
            'elaboration',
            'register',
            'employee__person',
            'vacation_request'  # OneToOne relation
        )

        # Búsqueda optimizada
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            from datetime import datetime
            try:
                # Intento parsear la fecha
                search_date = datetime.strptime(search_query, '%d/%m/%Y').date()
                actions = actions.filter(date_issue=search_date)
            except ValueError:
                # Búsqueda por número
                actions = actions.filter(number__icontains=search_query)

        # Ordenar por fecha más reciente
        actions = actions.order_by('-date_issue', '-id')

        # Paginación
        paginator = Paginator(actions, 10)
        page_number = self.request.GET.get('page', 1)

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

        context['employee'] = employee
        context['actions'] = page_obj
        context['search_query'] = search_query

        return context


class RegisterLiquidationView(LoginRequiredMixin, View):
    """
    Vista para registrar una liquidación de vacaciones.
    Cambia is_registered a True, crea el historial y descuenta del balance.
    """

    def post(self, request, action_id):
        try:
            from personnel_actions.models import PersonnelAction
            from vacation.models import VacationRequest, VacationHistory
            from django.db import transaction
            from decimal import Decimal
            import datetime

            action = get_object_or_404(PersonnelAction, pk=action_id)

            if action.is_registered:
                return JsonResponse({
                    'success': False,
                    'message': 'Esta acción ya está registrada.'
                }, status=400)

            # Obtener la solicitud de vacaciones asociada
            try:
                vacation_request = VacationRequest.objects.get(personnel_action=action)
            except VacationRequest.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'No se encontró la solicitud de vacaciones asociada.'
                }, status=400)

            with transaction.atomic():
                # Marcar como registrada
                action.is_registered = True
                action.date_registered = datetime.date.today()
                action.save()

                # Actualizar estado de la solicitud
                vacation_request.status = 'APPROVED'
                vacation_request.approved_by = request.user
                vacation_request.save()

                # Convertir days_quantity a float para guardar en el historial
                days_to_discount = float(vacation_request.days_quantity)

                # Crear registro en el historial de vacaciones
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

                # Descontar del balance
                from django.db.models import F
                EmployeeVacationBalance.objects.filter(id=vacation_request.balance_used.id).update(
                    balance_days=F('balance_days') - vacation_request.days_quantity,
                    vacation_days=F('vacation_days') + vacation_request.days_quantity
                )

            return JsonResponse({
                'success': True,
                'message': 'Liquidación registrada exitosamente.'
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'message': f'Error al registrar la liquidación: {str(e)}'
            }, status=500)


class EditLiquidationView(LoginRequiredMixin, FormView):
    """
    Vista para editar una liquidación de vacaciones (solo si no está registrada).
    """
    template_name = 'vacation/modals/modal_liquidation_edit.html'
    form_class = VacationLiquidationForm

    def get_action(self):
        from personnel_actions.models import PersonnelAction
        action_id = self.kwargs.get('action_id')
        return get_object_or_404(PersonnelAction, pk=action_id)

    def get_vacation_request(self):
        from vacation.models import VacationRequest
        action = self.get_action()
        return get_object_or_404(VacationRequest, personnel_action=action)

    def get_active_balance(self, employee):
        try:
            return EmployeeVacationBalance.objects.filter(
                employee=employee,
                is_active=True
            ).order_by('-created_at').first()
        except EmployeeVacationBalance.DoesNotExist:
            return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        action = self.get_action()
        vacation_request = self.get_vacation_request()
        balance = vacation_request.balance_used

        context['action'] = action
        context['vacation_request'] = vacation_request
        context['employee'] = action.employee
        context['balance'] = balance
        context['available_days'] = balance.balance_days if balance else 0

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        vacation_request = self.get_vacation_request()
        balance = vacation_request.balance_used

        from decimal import Decimal

        # Agregar días actuales de esta liquidación al balance disponible para validación
        balance_days = Decimal(str(balance.balance_days)) if balance else Decimal('0')
        request_days = Decimal(str(vacation_request.days_quantity))
        kwargs['available_days'] = float(balance_days + request_days)

        # Prellenar el formulario con datos existentes
        if not self.request.POST:
            action = self.get_action()
            # Convertir fechas al formato correcto para input type="date" (YYYY-MM-DD)
            start_date_str = vacation_request.start_date.strftime('%Y-%m-%d') if vacation_request.start_date else None
            end_date_str = vacation_request.end_date.strftime('%Y-%m-%d') if vacation_request.end_date else None

            kwargs['initial'] = {
                'start_date': start_date_str,
                'end_date': end_date_str,
                'nominating_authority': action.authority_1.id if action.authority_1 else None,
                'human_resources_responsible': action.authority_2.id if action.authority_2 else None,
                'registration_responsible': action.register.id if action.register else None,
                'review_responsible': action.reviewer.id if action.reviewer else None,
                'elaborated_by': action.elaboration.id if action.elaboration else None,
            }

        return kwargs

    def form_valid(self, form):
        try:
            from vacation.models import VacationRequest
            from decimal import Decimal
            from django.db import transaction
            import datetime

            action = self.get_action()
            vacation_request = self.get_vacation_request()

            if action.is_registered:
                return JsonResponse({
                    'success': False,
                    'message': 'No se puede editar una liquidación ya registrada.'
                }, status=400)

            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            days_requested = form.cleaned_data['days_requested']

            with transaction.atomic():
                # Actualizar la solicitud de vacaciones
                vacation_request.start_date = start_date
                vacation_request.end_date = end_date
                vacation_request.days_quantity = Decimal(str(days_requested))
                vacation_request.save()

                # Actualizar la explicación de la acción
                start_date_str = start_date.strftime('%d de %B de %Y')
                end_date_str = end_date.strftime('%d de %B de %Y')

                meses = {
                    'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
                    'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
                    'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
                    'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
                }
                for eng, esp in meses.items():
                    start_date_str = start_date_str.replace(eng, esp)
                    end_date_str = end_date_str.replace(eng, esp)

                explanation = (
                    f'SEGÚN REQUERIMIENTO DEL SERVIDOR Y AUTORIZACIÓN DEL JEFE INMEDIATO SE LIQUIDA '
                    f'{days_requested} DÍAS DE VACACIONES AL SERVIDOR DESDE EL "{start_date_str}" '
                    f'AL "{end_date_str}" CORRESPONDIENTE AL PERIODO "{vacation_request.balance_used.period}"'
                )

                # Actualizar la acción de personal
                action.explanation = explanation
                action.date_effective = start_date
                action.authority_1 = form.cleaned_data['nominating_authority']
                action.authority_2 = form.cleaned_data['human_resources_responsible']
                action.register = form.cleaned_data['registration_responsible']
                action.reviewer = form.cleaned_data['review_responsible']
                action.elaboration = form.cleaned_data['elaborated_by']
                action.save()

            return JsonResponse({
                'success': True,
                'message': 'Liquidación actualizada exitosamente.'
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'message': f'Error al actualizar la liquidación: {str(e)}'
            }, status=500)

    def form_invalid(self, form):
        errors = form.errors.as_json()
        error_message = 'Error en el formulario'

        if form.non_field_errors():
            error_message = form.non_field_errors()[0]

        return JsonResponse({
            'success': False,
            'message': error_message,
            'errors': errors
        }, status=400)


class VacationHistoryDetailView(LoginRequiredMixin, TemplateView):
    """
    Vista para mostrar el historial de liquidaciones de vacaciones de un periodo específico.
    """
    template_name = 'vacation/modals/modal_vacation_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from employee.models import Employee
        from vacation.models import VacationHistory

        balance_id = self.kwargs.get('balance_id')
        balance = get_object_or_404(EmployeeVacationBalance.objects.select_related('employee__person', 'period'),
                                    pk=balance_id)

        # Obtener historial de liquidaciones (vacation_request) del periodo
        history_records = VacationHistory.objects.filter(
            vacation_balance=balance,
            vacation_request__isnull=False
        ).select_related(
            'vacation_request',
            'vacation_request__personnel_action'
        ).order_by('-created_at')

        # Calcular el total con adicional para cada registro
        for record in history_records:
            record.total_with_additional = (record.value_discount or 0) + (record.proportional_discount or 0)

        context['employee'] = balance.employee
        context['period'] = balance.period
        context['balance'] = balance
        context['history_records'] = history_records

        return context


class PermitHistoryDetailView(LoginRequiredMixin, TemplateView):
    """
    Vista para mostrar el historial de permisos con cargo a vacaciones de un periodo específico.
    """
    template_name = 'vacation/modals/modal_permit_history.html'

    def dispatch(self, request, *args, **kwargs):
        # Comprobar que el balance solicitado exista y pertenezca al usuario que realiza la petición,
        # para evitar devolver contenido a usuarios no autorizados. Si no es así, devolver 403.
        balance_id = kwargs.get('balance_id')
        try:
            balance = EmployeeVacationBalance.objects.select_related('employee__person').get(pk=balance_id)
        except EmployeeVacationBalance.DoesNotExist:
            from django.http import Http404
            raise Http404()

        # Si el empleado asociado al balance no coincide con la persona del usuario actual,
        # bloquear el acceso salvo que el usuario sea staff/superuser.
        person_of_request = _safe_related(request.user, 'person', None)
        if balance.employee and getattr(balance.employee, 'person', None) is not None:
            if person_of_request is None or balance.employee.person.pk != person_of_request.pk:
                if not (request.user.is_staff or request.user.is_superuser):
                    from django.http import HttpResponseForbidden
                    return HttpResponseForbidden('No autorizado para ver este historial.')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from employee.models import Employee
        from vacation.models import VacationHistory

        balance_id = self.kwargs.get('balance_id')
        balance = get_object_or_404(EmployeeVacationBalance.objects.select_related('employee__person', 'period'),
                                    pk=balance_id)

        # Obtener historial de permisos (permit_request) del periodo
        history_records = VacationHistory.objects.filter(
            vacation_balance=balance,
            permit_request__isnull=False
        ).select_related(
            'permit_request'
        ).order_by('-created_at')

        # Calcular el total con adicional para cada registro
        for record in history_records:
            record.total_with_additional = (record.value_discount or 0) + (record.proportional_discount or 0)

        context['employee'] = balance.employee
        context['period'] = balance.period
        context['balance'] = balance
        context['history_records'] = history_records

        return context


class PermitReportModalView(LoginRequiredMixin, TemplateView):
    """
    Vista para mostrar el modal de selección de fechas para reporte de permisos.
    """
    template_name = 'vacation/modals/modal_permit_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from employee.models import Employee

        employee_id = self.kwargs.get('employee_id')
        employee = get_object_or_404(Employee.objects.select_related('person'), pk=employee_id)

        context['employee'] = employee

        return context


class PermitReportPDFView(LoginRequiredMixin, View):
    """
    Vista para generar el reporte PDF de permisos con cargo a vacaciones.
    """

    def get(self, request, employee_id):
        from django.http import HttpResponse
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.pdfgen import canvas
        from io import BytesIO
        import datetime as dt
        from employee.models import Employee
        from vacation.models import VacationHistory
        from django.db.models import Q

        # Obtener parámetros
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        if not start_date_str or not end_date_str:
            return HttpResponse('Fechas no proporcionadas', status=400)

        start_date = dt.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = dt.datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Obtener empleado
        employee = get_object_or_404(Employee.objects.select_related('person', 'area'), pk=employee_id)

        # Obtener permisos con cargo a vacaciones en el rango de fechas
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

        # Crear PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
        elements = []
        styles = getSampleStyleSheet()

        # Estilos personalizados
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=20,
            alignment=TA_CENTER
        )

        # Título
        elements.append(Paragraph('REPORTE DE PERMISOS CON CARGO A VACACIONES', title_style))
        elements.append(
            Paragraph(f'Período: {start_date.strftime("%d/%m/%Y")} - {end_date.strftime("%d/%m/%Y")}', subtitle_style))
        elements.append(Spacer(1, 0.2 * inch))

        # Información del empleado
        from reportlab.platypus import Paragraph as P
        area_text = P(employee.area.name if employee.area else 'N/A', styles['Normal'])
        employee_data = [
            ['Empleado:', employee.person.full_name, 'Identificación:', employee.person.document_number],
            ['Área:', area_text, 'Fecha Reporte:', dt.datetime.now().strftime('%d/%m/%Y %H:%M')]
        ]

        employee_table = Table(employee_data, colWidths=[1.2 * inch, 2.5 * inch, 1.2 * inch, 2 * inch])
        employee_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0e7ff')),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#e0e7ff')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e293b')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('WORDWRAP', (1, 1), (1, 1), True),  # Word wrap para el área
        ]))

        elements.append(employee_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Tabla de permisos
        if permits.exists():
            table_data = [['#', 'Fecha', 'Tipo', 'Días', 'Horas', 'Min', 'Período', 'Descuento Total']]

            total_days = 0
            total_hours = 0
            total_minutes = 0
            total_discount = 0

            for idx, permit in enumerate(permits, 1):
                days = permit.days_discount or 0
                hours = permit.hours_discount or 0
                minutes = permit.minutes_discount or 0
                discount = (permit.value_discount or 0) + (permit.proportional_discount or 0)

                total_days += days
                total_hours += hours
                total_minutes += minutes
                total_discount += discount

                table_data.append([
                    str(idx),
                    permit.permit_request.start_date.strftime('%d/%m/%Y'),
                    permit.permit_request.permit_type.name if permit.permit_request.permit_type else 'N/A',
                    f'{days:.0f}' if days > 0 else '-',
                    f'{hours:.0f}' if hours > 0 else '-',
                    f'{minutes:.0f}' if minutes > 0 else '-',
                    permit.vacation_balance.period.name,
                    f'{discount:.4f}'
                ])

            # Fila de totales con las primeras 3 columnas fusionadas
            table_data.append([
                'TOTALES:', '', '',
                f'{total_days:.0f}',
                f'{total_hours:.0f}',
                f'{total_minutes:.0f}',
                '',
                f'{total_discount:.4f}'
            ])

            permits_table = Table(table_data,
                                  colWidths=[0.4 * inch, 0.9 * inch, 1.5 * inch, 0.6 * inch, 0.6 * inch, 0.6 * inch,
                                             1 * inch, 1 * inch])
            permits_table.setStyle(TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),

                # Datos
                ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -2), 8),
                ('ALIGN', (0, 1), (0, -2), 'CENTER'),  # Número
                ('ALIGN', (1, 1), (2, -2), 'LEFT'),  # Fecha y Tipo
                ('ALIGN', (3, 1), (-1, -2), 'CENTER'),  # Días, Horas, Min, Período, Descuento
                ('TEXTCOLOR', (0, 1), (-1, -2), colors.HexColor('#334155')),
                ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#cbd5e1')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -2), 5),
                ('BOTTOMPADDING', (0, 1), (-1, -2), 5),

                # Fila de totales - Fusionar las primeras 3 columnas
                ('SPAN', (0, -1), (2, -1)),  # Fusionar columnas 0, 1, 2 en la última fila
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fef3c7')),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#92400e')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 9),
                ('ALIGN', (0, -1), (-1, -1), 'CENTER'),
                ('GRID', (0, -1), (-1, -1), 1, colors.HexColor('#92400e')),
                ('TOPPADDING', (0, -1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 8),

                # Alternar colores
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
            ]))

            elements.append(permits_table)
        else:
            elements.append(
                Paragraph('No se encontraron permisos con cargo a vacaciones en el rango de fechas seleccionado.',
                          styles['Normal']))

        # Construir PDF
        doc.build(elements)

        # Preparar respuesta
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        filename = f'Reporte_Permisos_{employee.person.full_name.replace(" ", "_")}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.pdf'
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        return response


class LiquidationPrintPDFView(LoginRequiredMixin, View):
    """
    Vista para generar el PDF de impresión de liquidación de vacaciones usando xhtml2pdf.
    Optimizada para carga rápida.
    """

    def get(self, request, action_id):
        from django.http import HttpResponse
        from django.template.loader import get_template
        from xhtml2pdf import pisa
        import datetime as dt
        from personnel_actions.models import PersonnelAction
        from vacation.models import VacationHistory
        from budget.models import BudgetLine
        import os
        from django.conf import settings

        # Consulta optimizada: solo traer los campos necesarios
        action = get_object_or_404(
            PersonnelAction.objects.select_related(
                'employee__person__document_type',
                'employee__area',
                'action_type',
                'authority_1',
                'authority_2',
                'reviewer',
                'elaboration',
                'register'
            ).prefetch_related(
                'vacation_request__balance_used__period'
            ),
            pk=action_id
        )

        vacation_request = action.vacation_request

        if not vacation_request:
            return HttpResponse('Esta acción no está relacionada con una liquidación de vacaciones', status=400)

        # Consultas paralelas optimizadas
        employee = action.employee

        # Budget: usar only() para traer solo campos necesarios
        budget = None
        try:
            budget = BudgetLine.objects.select_related('position_item').only(
                'id', 'current_employee', 'position_item__name', 'number_individual',
                'remuneration', 'status_item__name'
            ).get(current_employee=employee.pk)
        except BudgetLine.DoesNotExist:
            pass

        # History: optimizado
        history = None
        total_discount = 0
        if vacation_request:
            history = VacationHistory.objects.filter(
                vacation_request=vacation_request
            ).select_related('vacation_balance__period').only(
                'days_discount', 'value_discount', 'proportional_discount',
                'vacation_balance__period__name'
            ).first()

            if history:
                total_discount = (history.value_discount or 0) + (history.proportional_discount or 0)

        # Renderizar template (el logo se resuelve con {% static %} en el template)
        template = get_template('vacation/reports/pdf_liquidation.html')
        html = template.render({
            'action': action,
            'employee': employee,
            'budget': budget,
            'vacation_request': vacation_request,
            'history': history,
            'total_discount': total_discount,
            'today': dt.datetime.now()
        })

        # Link callback para resolver rutas estáticas (igual que sistema tthh)
        def link_callback(uri, rel):
            """
            Convierte URIs de HTML/CSS en rutas absolutas del sistema de archivos
            """
            import os
            from django.conf import settings

            # Si la URI empieza con STATIC_URL
            if uri.startswith(settings.STATIC_URL):
                # Remover STATIC_URL del inicio
                path = uri.replace(settings.STATIC_URL, '')
                # Usar STATICFILES_DIRS
                if settings.STATICFILES_DIRS:
                    static_root = settings.STATICFILES_DIRS[0]
                else:
                    static_root = settings.STATIC_ROOT or os.path.join(settings.BASE_DIR, 'static')
                return os.path.join(static_root, path)
            return uri

        # Generar PDF usando pisaDocument (igual que sistema tthh)
        response = HttpResponse(content_type='application/pdf')
        filename = f'Liquidacion_{employee.person.full_name.replace(" ", "_")}_{action.number.replace("/", "-")}.pdf'
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        from io import BytesIO
        result = BytesIO()
        pdf = pisa.pisaDocument(
            BytesIO(html.encode("UTF-8")),
            result,
            encoding='UTF-8',
            link_callback=link_callback
        )

        if not pdf.err:
            response.write(result.getvalue())
            return response
        else:
            return HttpResponse('Error al generar el PDF', status=500)
