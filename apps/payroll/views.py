import calendar
import json
from datetime import date
from decimal import Decimal
from core.models import CatalogItem
import openpyxl
from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, Sum, Case, When, IntegerField, Value
from django.db.models.functions import Cast
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.template.loader import render_to_string, get_template
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, TemplateView, View, DeleteView, UpdateView, CreateView, DetailView
from xhtml2pdf import pisa

from accounting.models import JournalItem
from budget.models import BudgetLine, BudgetAssignmentHistory, BudgetGroup
from contract.models import ManagementPeriod
from employee.models import Employee
from payroll.models import RubroBudgetMapping
from .forms import PayrollPeriodForm, PayrollConstantForm, RubroBudgetMappingForm, IncomeForm, DeductionForm, \
    InstitutionalContributionForm
from .models import Income, Deduction
from .models import PayrollPeriod, Payslip, PayrollConstant, PayslipItem, PayrollNovelty, InstitutionalContribution
from .models import PendingDebt
from .services import PayrollCalculatorService
from .services import rebuild_accounting_for_period


class PayrollListView(ListView):
    """Vista principal con renderizado híbrido"""
    model = Payslip
    template_name = 'payroll/payroll_list.html'
    context_object_name = 'payslips'
    paginate_by = 50  # Paginación esencial para velocidad de carga (rendering)

    def get_queryset(self):
        period_id = self.request.GET.get('period_id')
        if period_id:
            return Payslip.objects.filter(period_id=period_id).select_related('employee', 'period')
        return Payslip.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['periods'] = PayrollPeriod.objects.all()
        # Si hay periodo seleccionado, enviarlo al contexto
        if self.request.GET.get('period_id'):
            context['current_period'] = get_object_or_404(PayrollPeriod, pk=self.request.GET.get('period_id'))
        return context

    def render_to_response(self, context, **response_kwargs):
        """Híbrido: Si es AJAX devuelve solo la tabla, si no, la página entera"""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string('payroll/partial_payroll_table.html', context)
            return JsonResponse({'html': html})
        return super().render_to_response(context, **response_kwargs)


class PeriodListView(ListView):
    model = PayrollPeriod
    template_name = 'payroll/payroll_period_list.html'
    context_object_name = 'periods'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PayrollPeriodForm()  # Formulario vacío para el modal
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        # Anotamos un número de mes para orden cronológica correcta (YYYYMM)
        month_case = Case(
            When(month='ENERO', then=Value(1)), When(month='FEBRERO', then=Value(2)),
            When(month='MARZO', then=Value(3)), When(month='ABRIL', then=Value(4)),
            When(month='MAYO', then=Value(5)), When(month='JUNIO', then=Value(6)),
            When(month='JULIO', then=Value(7)), When(month='AGOSTO', then=Value(8)),
            When(month='SEPTIEMBRE', then=Value(9)), When(month='OCTUBRE', then=Value(10)),
            When(month='NOVIEMBRE', then=Value(11)), When(month='DICIEMBRE', then=Value(12)),
            output_field=IntegerField()
        )
        qs = qs.annotate(month_num=month_case, year_int=Cast('year', IntegerField()))

        show_closed = self.request.GET.get('show_closed')
        ordered = qs.order_by('-year_int', '-month_num')
        if show_closed and str(show_closed).lower() in ['true', '1', 'on']:
            return ordered
        return ordered.filter(is_closed=False)

    def get(self, request, *args, **kwargs):
        # Si es petición AJAX devolvemos el partial completo (HTML) empaquetado en JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # configurar object_list y contexto para que la paginación de ListView funcione
            self.object_list = self.get_queryset()
            context = self.get_context_data()

            # Si el cliente solicita JSON de datos (modo JS-render), devolvemos estructuras JSON
            if request.GET.get('json') == '1':
                periods = context.get('periods') or self.object_list
                data = []
                for p in periods:
                    month_num = getattr(p, 'month_num', None) or getattr(p, 'month_number', 0)
                    data.append({
                        'id': p.id,
                        'month': p.month,
                        'year': p.year,
                        'month_num': int(month_num),
                        'start_date': p.start_date.strftime('%d/%m/%Y') if p.start_date else '',
                        'end_date': p.end_date.strftime('%d/%m/%Y') if p.end_date else '',
                        'working_days': p.working_days,
                        'is_closed': bool(p.is_closed),
                        'display': f"{p.month} {p.year}",
                        'payslip_url': reverse('payroll:payslip_list') + f"?period_id={p.id}",
                        'novelty_url': reverse('payroll:novelty_mass_load') + f"?period_id={p.id}"
                    })
                return JsonResponse({'periods': data})

            # Renderizamos el partial completo con contexto (incluye paginador)
            html = render_to_string('payroll/partials/partial_period_table.html', context, request=request)
            return JsonResponse({'html': html})
        return super().get(request, *args, **kwargs)


class PeriodCreateView(View):
    template_name = 'payroll/modals/modal_period_form.html'

    def get(self, request, *args, **kwargs):
        """Devuelve el formulario del modal (usado por el fetch GET en JS)."""
        form = PayrollPeriodForm()
        html = render_to_string(self.template_name, {'form': form}, request=request)
        return HttpResponse(html)

    def post(self, request):
        form = PayrollPeriodForm(request.POST)
        if form.is_valid():
            period = form.save(commit=False)
            period.created_by = request.user.username
            period.save()
            return JsonResponse({
                'status': 'success',
                'message': 'Periodo creado correctamente',
                'period': {
                    'id': period.id,
                    'str': str(period)
                }
            })
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class GeneratePayrollView(View):
    def post(self, request):
        period_id = request.POST.get('period_id')
        try:
            period = PayrollPeriod.objects.get(pk=period_id)
            if period.is_closed:
                return JsonResponse({'status': 'error', 'message': 'El periodo está cerrado.'}, status=400)

            employees = Employee.objects.all()

            service = PayrollCalculatorService(period, employees)
            # Recibimos el resultado del servicio
            result = service.generate_bulk()

            warnings = result.get('warnings', [])
            msg = 'Cálculo completado exitosamente.'

            if warnings:
                msg += ' (Se generaron advertencias contables, revisa los reportes)'

            return JsonResponse({
                'status': 'success',
                'message': msg,
                'warnings': warnings  # Enviamos esto al frontend para pintarlo en un modal o toast amarillo
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class PayrollGenerateForm(forms.Form):
    period_id = forms.IntegerField()


class GeneratePayrollUIView(View):
    """Interfaz simple para seleccionar empleados elegibles y generar rol con prorrateo."""
    template_name = 'payroll/generate_ui.html'

    def get(self, request):
        period_id = request.GET.get('period_id')
        periods = PayrollPeriod.objects.all()
        context = {'periods': periods}
        if period_id:
            period = PayrollPeriod.objects.get(pk=period_id)
            # empleados activos con partida asignada (current_employee) y persona activa
            emp_ids = BudgetLine.objects.filter(current_employee_id__isnull=False).values_list('current_employee_id',
                                                                                               flat=True)
            employees = Employee.objects.filter(id__in=emp_ids, is_active=True, person__is_active=True)

            rows = []
            for emp in employees:
                # determinar fecha de ingreso: usar el último ManagementPeriod firmado/activo
                join = None
                last_period = ManagementPeriod.objects.filter(employee=emp,
                                                              status__code__in=['FIRMADO', 'ACTIVO']).order_by(
                    '-start_date').first()
                if last_period and last_period.signed_document:
                    join = last_period.start_date
                else:
                    # fallback a campos en Employee o InstitutionalData
                    join = emp.date_joined
                    if not join:
                        inst = getattr(emp, 'institutional_data', None)
                        join = getattr(inst, 'entry_date', None) if inst else None
                # si no hay fecha, considerar completo
                if not join or join <= period.start_date:
                    worked = period.working_days
                elif join > period.end_date:
                    continue
                else:
                    days_not_worked = join.day - 1
                    worked = max(0, period.working_days - days_not_worked)

                rows.append({'employee': emp, 'worked_days': worked})

            context.update({'current_period': period, 'rows': rows})

        return render(request, self.template_name, context)


class GeneratePayrollSelectedView(View):
    def post(self, request):
        period_id = request.POST.get('period_id')
        selected = request.POST.getlist('employee')
        worked_map = {}
        for k, v in request.POST.items():
            if k.startswith('worked_'):
                emp_id = k.split('_', 1)[1]
                try:
                    worked_map[int(emp_id)] = int(v)
                except:
                    pass

        if not period_id:
            messages.error(request, 'Periodo no definido')
            return redirect(request.META.get('HTTP_REFERER', '/'))

        period = PayrollPeriod.objects.get(pk=period_id)
        employees_with_days = []
        for emp_id in selected:
            try:
                emp = Employee.objects.get(pk=emp_id)
            except Employee.DoesNotExist:
                continue
            wd = worked_map.get(emp.id, period.working_days)
            employees_with_days.append((emp, wd))

        svc = PayrollCalculatorService(period, [e for e, d in employees_with_days])
        svc.generate_for_selected(employees_with_days)
        messages.success(request, 'Rol generado para empleados seleccionados.')
        return redirect(request.META.get('HTTP_REFERER', '/'))


class ConstantListView(ListView):
    model = PayrollConstant
    template_name = 'payroll/constant_list.html'
    context_object_name = 'constants'

    def get_queryset(self):
        qs = super().get_queryset().order_by('name')
        show_inactive = self.request.GET.get('show_inactive')
        # Si la migración que añade `is_active` no se aplicó aún, evitar que toda la
        # página explote: intentamos filtrar por `is_active`, y si la columna no
        # existe devolvemos el queryset sin filtrar (fallback seguro).
        try:
            if show_inactive and str(show_inactive).lower() in ['true', '1', 'on']:
                return qs.all()
            return qs.filter(is_active=True)
        except Exception as e:
            # Fall back a todas las constantes si hay error en la consulta (p.ej. columna faltante)
            # Registro de consola para ayudar en debugging en desarrollo
            import logging
            logger = logging.getLogger(__name__)
            logger.warning('Error al filtrar PayrollConstant.is_active, retornando queryset sin filtro: %s', e)
            return qs

    def get(self, request, *args, **kwargs):
        # Si es petición AJAX devolvemos sólo las filas (partial)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            constants = self.get_queryset()
            html = render_to_string('payroll/partials/_constant_rows.html', {'constants': constants})
            from django.http import HttpResponse
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class ConstantCreateView(CreateView):
    model = PayrollConstant
    form_class = PayrollConstantForm
    template_name = 'payroll/modals/modal_constant_form.html'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Constante creada correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class ConstantUpdateView(UpdateView):
    model = PayrollConstant
    form_class = PayrollConstantForm
    template_name = 'payroll/modals/modal_constant_form.html'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Constante actualizada correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class ConstantDeleteView(DeleteView):
    model = PayrollConstant

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            self.object.delete()
            return JsonResponse({'status': 'success', 'message': 'Constante eliminada.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class PayslipListView(LoginRequiredMixin, ListView):
    model = Payslip
    template_name = 'payroll/payslip_list.html'
    context_object_name = 'payslips'
    paginate_by = 15

    def get_paginate_by(self, queryset):
        """Allow returning all results when frontend requests full dataset (full=1)."""
        full = (self.request.GET.get('full') or '').lower()
        if full in ['1', 'true', 'yes']:
            return None
        return self.paginate_by

    def get_queryset(self):
        period_id = self.request.GET.get('period_id')
        if not period_id or period_id == "None":
            return Payslip.objects.none()

        queryset = Payslip.objects.filter(period_id=period_id).select_related(
            'employee__person', 'period'
        ).order_by('employee__person__last_name')

        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(employee__person__first_name__icontains=q) |
                Q(employee__person__last_name__icontains=q) |
                Q(employee__person__document_number__icontains=q) |
                Q(items__budget_line__budget_group__short_code__icontains=q)
            ).distinct()
        regime = self.request.GET.get('regime', '').strip()
        if regime:
            queryset = queryset.filter(items__budget_line__regime_item_id=regime).distinct()
        show_withheld = (self.request.GET.get('show_withheld') or '').lower()
        if show_withheld in ['1', 'true', 'on', 'only']:
            queryset = queryset.filter(is_withheld=True)
        else:
            # Por defecto mostramos TODOS excepto los retenidos
            queryset = queryset.filter(is_withheld=False)

        # Soporte de ordenamiento desde el cliente (TableManager envía sort_field & sort_dir)
        sort_field = self.request.GET.get('sort_field') or self.request.GET.get('sort')
        sort_dir = (self.request.GET.get('sort_dir') or 'asc').lower()
        allowed = {'employee__person__last_name', 'employee__person__document_number',
                   'items__budget_line__budget_group__short_code', 'total_income', 'total_deduction', 'net_pay'}
        if sort_field in allowed:
            order = sort_field if sort_dir == 'asc' else f'-{sort_field}'
            try:
                queryset = queryset.order_by(order)
            except Exception:
                pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['budget_groups'] = BudgetGroup.objects.all()
        context['labor_regimes'] = CatalogItem.objects.filter(catalog__code='LABOR_REGIMES', is_active=True).order_by(
            'name')
        period_id = self.request.GET.get('period_id')
        if period_id and period_id != "None":
            context['current_period'] = PayrollPeriod.objects.filter(id=period_id).first()
            context['period_id'] = period_id
            # Pasamos la búsqueda para que el input no se borre
            context['search_query'] = self.request.GET.get('q', '')

        # Agregar totales para mostrar en la cabecera (evita usar filtros inexistentes en la plantilla)
        try:
            qs = self.get_queryset()
            context['total_roles'] = qs.count()
            total_liquidado = qs.aggregate(total=Sum('net_pay'))['total'] or 0
            context['total_liquidado'] = total_liquidado
        except Exception:
            context['total_roles'] = 0
            context['total_liquidado'] = 0

        return context

    # ---> ESTA ES LA PIEZA MÁGICA QUE FALTABA <---
    def render_to_response(self, context, **response_kwargs):
        """Si la petición es AJAX, devuelve solo la tabla en formato JSON"""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Renderiza solo el HTML del pedacito de la tabla
            html = render_to_string('payroll/partials/partial_payslip_table.html', context, request=self.request)
            # Lo empaqueta en JSON para que tu JavaScript no explote
            return JsonResponse({
                'html': html,
                'total_roles': context.get('total_roles', 0),
                'total_liquidado': context.get('total_liquidado', 0)
            })

        # Si es una carga normal de la página, hace lo de siempre
        return super().render_to_response(context, **response_kwargs)


class PayslipDetailView(DetailView):
    """Para el Modal de Detalle (reemplaza a rol_detalle antiguo)"""
    model = Payslip
    template_name = 'payroll/modals/modal_payslip_detail.html'
    context_object_name = 'payslip'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # FIX: Agregamos order_by para que respete tu configuración de "Orden"
        context['incomes'] = self.object.items.filter(
            item_type='INCOME'
        ).order_by('income_ref__order')

        context['deductions'] = self.object.items.filter(
            item_type='DEDUCTION'
        ).exclude(
            deduction_ref__code__icontains='PATRONAL'
        ).order_by('deduction_ref__order')

        return context


class IncomeListView(ListView):
    model = Income
    template_name = 'payroll/income_list.html'
    context_object_name = 'incomes'

    def get_queryset(self):
        qs = super().get_queryset()
        show_inactive = self.request.GET.get('show_inactive')
        if show_inactive and str(show_inactive).lower() in ['true', '1', 'on']:
            return qs.all()
        return qs.filter(is_active=True)

    def get(self, request, *args, **kwargs):
        # Si es petición AJAX devolvemos solo las filas (partial)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            incomes = self.get_queryset()
            html = render_to_string('payroll/partials/partial_income_table.html', {'incomes': incomes})
            from django.http import HttpResponse
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class IncomeCreateView(CreateView):
    model = Income
    form_class = IncomeForm
    template_name = 'payroll/modals/modal_income_form.html'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Ingreso creado correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class IncomeUpdateView(UpdateView):
    model = Income
    form_class = IncomeForm
    template_name = 'payroll/modals/modal_income_form.html'
    success_url = reverse_lazy('payroll:income_list')

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Ingreso actualizado correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class DeductionListView(ListView):
    model = Deduction
    template_name = 'payroll/deduction_list.html'
    context_object_name = 'deductions'

    def get_queryset(self):
        qs = super().get_queryset()
        show_inactive = self.request.GET.get('show_inactive')
        if show_inactive and str(show_inactive).lower() in ['true', '1', 'on']:
            return qs.all()
        return qs.filter(is_active=True)

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            deductions = self.get_queryset()
            html = render_to_string('payroll/partials/partial_deduction_table.html', {'deductions': deductions})
            from django.http import HttpResponse
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


class DeductionCreateView(CreateView):
    model = Deduction
    form_class = DeductionForm
    template_name = 'payroll/modals/modal_deduction_form.html'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Descuento creado correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class DeductionUpdateView(UpdateView):
    model = Deduction
    form_class = DeductionForm
    template_name = 'payroll/modals/modal_deduction_form.html'
    success_url = reverse_lazy('payroll:deduction_list')

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Descuento actualizado correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class FondosReservaListView(LoginRequiredMixin, ListView):
    """Lista de empleados activos mostrando Fondos de Reserva y Mensualiza Décimos."""
    model = Employee
    template_name = 'payroll/reserve_funds_list.html'
    context_object_name = 'employees'
    paginate_by = 10
    partial_template_name = 'payroll/partials/partial_reserve_funds_table.html'

    def get_queryset(self):
        qs = Employee.objects.filter(is_active=True, person__is_active=True)
        # Traer relaciones comúnmente usadas para evitar N+1
        qs = qs.select_related('person__economic_data__payroll_info', 'area').prefetch_related(
            'current_budget_line__position_item')
        # Soporte de búsqueda simple desde frontend
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(person__first_name__icontains=q) |
                Q(person__last_name__icontains=q) |
                Q(person__document_number__icontains=q)
            )
        return qs.order_by('person__last_name', 'person__first_name')

    def render_to_response(self, context, **response_kwargs):
        # Si es petición AJAX devolvemos solo el partial con la tabla y datos de paginación
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)
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

            return JsonResponse({'html': html, 'pagination': pagination_data})
        return super().render_to_response(context, **response_kwargs)

    def get_paginate_by(self, queryset):
        """Return None to disable server-side pagination and return all employees."""
        # Usar el valor definido en `paginate_by` para habilitar paginación servidor
        return self.paginate_by

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Fondos de Reserva'
        return context


class InstitutionalReportView(TemplateView):
    template_name = 'payroll/reports/institutional_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period_id = self.kwargs.get('period_id')
        period = get_object_or_404(PayrollPeriod, pk=period_id)

        # ==========================================
        # 1. JORNALIZACIÓN (Desde la Contabilidad)
        # ==========================================
        jornalizacion_items = JournalItem.objects.filter(reference=str(period))

        jornalizacion = []
        total_debe = 0
        total_haber = 0

        if jornalizacion_items.exists():
            jornalizacion = jornalizacion_items.values(
                'account__code', 'account__name'
            ).annotate(
                total_debe=Sum('debit'),
                total_haber=Sum('credit')
            ).order_by('account__code')

            total_debe = sum(item['total_debe'] for item in jornalizacion)
            total_haber = sum(item['total_haber'] for item in jornalizacion)

            # ==========================================
            # 2. DETALLE PRESUPUESTACIÓN (Desde la Nómina)
            # ==========================================
            presupuesto_list = []

            # 1. Buscamos qué IDs están explícitamente configurados en la tabla de Mapeo usando las Claves Foráneas
            mapped_income_ids = list(
                RubroBudgetMapping.objects.filter(income__isnull=False).values_list('income_id', flat=True))
            mapped_deduction_ids = list(
                RubroBudgetMapping.objects.filter(deduction__isnull=False).values_list('deduction_id', flat=True))
            mapped_contribution_ids = list(
                RubroBudgetMapping.objects.filter(contribution__isnull=False).values_list('contribution_id', flat=True))

            # Aseguramos que la "Remuneración Base" pase al reporte aunque no tenga mapeo explícito
            remun = Income.objects.filter(code__iexact='REMUNERACION').first()
            if remun and remun.id not in mapped_income_ids:
                mapped_income_ids.append(remun.id)

            # 2. Agrupamos los INGRESOS
            ingresos = PayslipItem.objects.filter(
                payslip__period=period,
                budget_line_code__isnull=False,
                item_type='INCOME',
                income_ref_id__in=mapped_income_ids
            ).values(
                'budget_line_code', 'income_ref__name'
            ).annotate(total=Sum('value'))

            # 3. Agrupamos los EGRESOS (Esto oculta al IESS Personal del presupuesto porque no está mapeado)
            egresos = PayslipItem.objects.filter(
                payslip__period=period,
                budget_line_code__isnull=False,
                item_type='DEDUCTION',
                deduction_ref_id__in=mapped_deduction_ids
            ).values(
                'budget_line_code', 'deduction_ref__name'
            ).annotate(total=Sum('value'))

            # 4. Agrupamos los APORTES INSTITUCIONALES (El nuevo Patronal)
            aportes = PayslipItem.objects.filter(
                payslip__period=period,
                budget_line_code__isnull=False,
                item_type='CONTRIBUTION',
                contribution_ref_id__in=mapped_contribution_ids
            ).values(
                'budget_line_code', 'contribution_ref__name'
            ).annotate(total=Sum('value'))

            # Unificamos las tres listas en el reporte final
            for item in ingresos:
                presupuesto_list.append({
                    'partida': item['budget_line_code'],
                    'concepto': item['income_ref__name'],
                    'monto': item['total']
                })

            for item in egresos:
                presupuesto_list.append({
                    'partida': item['budget_line_code'],
                    'concepto': item['deduction_ref__name'],
                    'monto': item['total']
                })

            for item in aportes:
                presupuesto_list.append({
                    'partida': item['budget_line_code'],
                    'concepto': item['contribution_ref__name'],
                    'monto': item['total']
                })

            # Ordenamos por código de partida
            presupuesto_list = sorted(presupuesto_list, key=lambda x: x['partida'])

        context.update({
            'period': period,
            'jornalizacion': jornalizacion,
            'total_debe': total_debe,
            'total_haber': total_haber,
            'presupuestacion': presupuesto_list,
        })
        return context


class MappingListView(ListView):
    model = RubroBudgetMapping
    template_name = 'payroll/mapping_list.html'
    context_object_name = 'mappings'
    ordering = ['rubro_type', 'rubro_code']


class MappingCreateView(CreateView):
    model = RubroBudgetMapping
    form_class = RubroBudgetMappingForm
    template_name = 'payroll/mapping_form.html'
    success_url = reverse_lazy('payroll:mapping_list')


class MappingUpdateView(UpdateView):
    model = RubroBudgetMapping
    form_class = RubroBudgetMappingForm
    template_name = 'payroll/mapping_form.html'
    success_url = reverse_lazy('payroll:mapping_list')


class MappingDeleteView(DeleteView):
    model = RubroBudgetMapping
    template_name = 'payroll/mapping_confirm_delete.html'
    success_url = reverse_lazy('payroll:mapping_list')


class NoveltyMassLoadView(TemplateView):
    """Vista principal para la pantalla de carga de novedades"""
    template_name = 'payroll/novelty_mass_load.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['periods'] = PayrollPeriod.objects.filter(is_closed=False)
        context['incomes'] = Income.objects.filter(is_active=True)
        context['deductions'] = Deduction.objects.filter(is_active=True)

        # Capturamos el periodo de la URL (si existe) y lo pasamos al HTML
        context['selected_period_id'] = self.request.GET.get('period_id', '')

        return context


class ParseNoveltyExcelView(View):
    """Lee el Excel temporalmente y lo devuelve como JSON para la tabla editable"""

    def post(self, request):
        excel_file = request.FILES.get('file')
        if not excel_file:
            return JsonResponse({'status': 'error', 'message': 'No se subió ningún archivo'})

        try:
            # data_only=True asegura que si hay fórmulas, lea el resultado
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            sheet = wb.active

            data = []
            not_found = []

            # Empezamos desde la FILA 1 (así no importa si el usuario olvidó poner encabezados)
            for row in sheet.iter_rows(min_row=1, values_only=True):
                if not row[0]: continue  # Si la celda está vacía, saltar

                raw_cedula = str(row[0]).strip()

                # 1. Si la celda tiene letras (ej: dice "CEDULA" o "Identificación"), es un encabezado, lo saltamos
                if not raw_cedula.replace('.', '').isdigit():
                    continue

                # 2. Limpiar si Excel lo transformó a float (ej: "1104898679.0" -> "1104898679")
                if raw_cedula.endswith('.0'):
                    raw_cedula = raw_cedula[:-2]

                # 3. Las cédulas ecuatorianas son de 10 dígitos. Si Excel borró el 0 inicial, lo reponemos
                cedula = raw_cedula.zfill(10)

                # Si la segunda columna está vacía, asumimos 0.00
                valor_bruto = row[1] if len(row) > 1 and row[1] is not None else 0.00

                try:
                    valor = float(valor_bruto)
                except (ValueError, TypeError):
                    valor = 0.00

                # Buscamos al empleado por la cédula (usamos document_number que es como lo tienes en DB)
                emp = Employee.objects.filter(person__document_number=cedula, is_active=True).first()
                if emp:
                    data.append({
                        'emp_id': emp.id,
                        'cedula': cedula,
                        'nombres': f"{emp.person.last_name} {emp.person.first_name}",
                        'valor': round(valor, 2)
                    })
                else:
                    not_found.append(cedula)

            return JsonResponse({'status': 'success', 'data': data, 'not_found': not_found})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})


class GetNoveltiesView(View):
    """Obtiene las novedades ya guardadas en base de datos para mostrarlas en la tabla"""

    def get(self, request):
        period_id = request.GET.get('period_id')
        rubro_type = request.GET.get('rubro_type')
        rubro_id = request.GET.get('rubro_id')

        if not all([period_id, rubro_type, rubro_id]):
            return JsonResponse({'status': 'error', 'message': 'Faltan parámetros'})

        try:
            if rubro_type == 'INCOME':
                novelties = PayrollNovelty.objects.filter(period_id=period_id, income_ref_id=rubro_id,
                                                          value__gt=0).select_related('employee__person')
            else:
                novelties = PayrollNovelty.objects.filter(period_id=period_id, deduction_ref_id=rubro_id,
                                                          value__gt=0).select_related('employee__person')

            data = []
            for nov in novelties:
                data.append({
                    'emp_id': nov.employee.id,
                    'cedula': nov.employee.person.document_number,
                    'nombres': f"{nov.employee.person.last_name} {nov.employee.person.first_name}",
                    'valor': float(nov.value)
                })

            # Ordenar alfabéticamente
            data = sorted(data, key=lambda x: x['nombres'])
            return JsonResponse({'status': 'success', 'data': data})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})


class SaveNoveltiesView(View):
    """Recibe la tabla editada y guarda (sobrescribe) en la base de datos"""

    def post(self, request):
        try:
            payload = json.loads(request.body)
            period_id = payload.get('period_id')
            rubro_type = payload.get('rubro_type')
            rubro_id = payload.get('rubro_id')
            items = payload.get('items', [])

            period = PayrollPeriod.objects.get(pk=period_id)

            with transaction.atomic():
                # ==============================================================
                # 1. TIERRA ARRASADA: Borramos todo lo anterior de ESTE rubro y periodo
                # ==============================================================
                if rubro_type == 'INCOME':
                    PayrollNovelty.objects.filter(period=period, income_ref_id=rubro_id).delete()
                else:
                    PayrollNovelty.objects.filter(period=period, deduction_ref_id=rubro_id).delete()

                # ==============================================================
                # 2. INSERTAR LO NUEVO (Evitando crear registros en 0.00)
                # ==============================================================
                novelties_to_create = []
                for item in items:
                    val = Decimal(str(item.get('valor', 0)))
                    emp_id = item.get('emp_id')

                    if val > Decimal('0.00'):
                        if rubro_type == 'INCOME':
                            novelties_to_create.append(PayrollNovelty(
                                period=period, employee_id=emp_id, income_ref_id=rubro_id, value=val
                            ))
                        else:
                            novelties_to_create.append(PayrollNovelty(
                                period=period, employee_id=emp_id, deduction_ref_id=rubro_id, value=val
                            ))

                # Guardado masivo ultra-rápido
                PayrollNovelty.objects.bulk_create(novelties_to_create)

            return JsonResponse({'status': 'success', 'message': 'Novedades sobrescritas y guardadas exitosamente'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})


class ContributionListView(ListView):
    model = InstitutionalContribution
    template_name = 'payroll/contribution_list.html'
    context_object_name = 'contributions'

    def get_queryset(self):
        qs = InstitutionalContribution.objects.all().order_by('code')
        # Filtramos si no nos piden explícitamente ver los inactivos
        if self.request.GET.get('show_inactive') != 'true':
            qs = qs.filter(is_active=True)
        return qs

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        context = self.get_context_data()

        # MAGIA AJAX: Si la petición viene por JS, devolvemos solo el fragmento de la tabla
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'payroll/partials/partial_contribution_table.html', context)

        # Si es una carga normal del navegador, devolvemos la página completa
        return super().get(request, *args, **kwargs)


class ContributionCreateView(CreateView):
    model = InstitutionalContribution
    form_class = InstitutionalContributionForm
    template_name = 'payroll/modals/modal_contribution_form.html'

    def form_valid(self, form):
        self.object = form.save()
        # Respondemos con JSON para que el modal sepa que debe cerrarse
        return JsonResponse({'status': 'success', 'message': 'Aporte creado exitosamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class ContributionUpdateView(UpdateView):
    model = InstitutionalContribution
    form_class = InstitutionalContributionForm
    template_name = 'payroll/modals/modal_contribution_form.html'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Aporte actualizado exitosamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class GroupedPayrollReportView(LoginRequiredMixin, View):
    """
    Motor de Generación de los 3 Reportes Financieros agrupados por Partida Presupuestaria.
    100% Dinámico con prevención de Colisión de IDs (DED_ vs CON_)
    """

    def get(self, request, pk):
        period = get_object_or_404(PayrollPeriod, pk=pk)

        # 1. CAPTURA DE FILTROS DESDE LA URL
        search_query = request.GET.get('q', '').strip()
        group_filter = request.GET.get('group', '').strip()
        regime_filter = request.GET.get('regime', '').strip()
        tipo_filtro = request.GET.get('filtro', 'NORMAL')

        payslips_qs = Payslip.objects.filter(period=period)

        if search_query:
            payslips_qs = payslips_qs.filter(
                Q(employee__person__first_name__icontains=search_query) |
                Q(employee__person__last_name__icontains=search_query) |
                Q(employee__person__document_number__icontains=search_query) |
                Q(items__budget_line__budget_group__short_code__icontains=search_query)
            ).distinct()

        if group_filter:
            payslips_qs = payslips_qs.filter(items__budget_line__budget_group__short_code=group_filter).distinct()

        if regime_filter:
            payslips_qs = payslips_qs.filter(items__budget_line__regime_item_id=regime_filter).distinct()

        show_withheld = (request.GET.get('show_withheld') or '').lower()
        if show_withheld in ['only', '1', 'true', 'yes']:
            payslips_qs = payslips_qs.filter(is_withheld=True)
        else:
            if tipo_filtro == 'NORMAL':
                payslips_qs = payslips_qs.filter(is_withheld=False)
            elif tipo_filtro == 'REZAGADOS':
                payslips_qs = payslips_qs.filter(is_withheld=False, is_paid=False)

        valid_payslip_ids = list(payslips_qs.values_list('id', flat=True))

        mapped_incomes = set(
            int(x) for x in RubroBudgetMapping.objects.filter(income__isnull=False).values_list('income_id', flat=True)
            if x)
        mapped_deductions = set(int(x) for x in
                                RubroBudgetMapping.objects.filter(deduction__isnull=False).values_list('deduction_id',
                                                                                                       flat=True) if x)
        mapped_contributions = set(int(x) for x in
                                   RubroBudgetMapping.objects.filter(contribution__isnull=False).values_list(
                                       'contribution_id', flat=True) if x)

        items = PayslipItem.objects.filter(
            payslip_id__in=valid_payslip_ids
        ).select_related(
            'payslip__employee__person',
            'budget_line__budget_group',
            'income_ref__debit_account', 'income_ref__credit_account',
            'deduction_ref__debit_account', 'deduction_ref__credit_account',
            'contribution_ref__debit_account', 'contribution_ref__credit_account'
        ).prefetch_related(
            'payslip__employee__person__economic_data__bank_account__bank',
            'payslip__employee__person__economic_data__bank_account__account_type'
        ).distinct()

        report_data = {}

        for it in items:
            val = Decimal(str(it.value))

            grupo_obj = it.budget_line.budget_group if it.budget_line else None
            grupo_key = grupo_obj.short_code if grupo_obj else 'SIN_AGRUPAR'

            if grupo_key not in report_data:
                report_data[grupo_key] = {
                    'group_obj': grupo_obj,
                    'group_name': grupo_obj.name if grupo_obj else 'Registros sin agrupación',
                    'empleados': {},
                    'contabilidad': {},
                    'presupuesto': {},
                    'ingresos_headers': {},
                    'descuentos_headers': {},
                    'aportes_headers': {}
                }

            grupo_data = report_data[grupo_key]
            emp_id = it.payslip.employee.id

            if emp_id not in grupo_data['empleados']:
                banco_nombre, cuenta_tipo, cuenta_numero = "NO REGISTRADO", "", ""
                try:
                    bank_acc = it.payslip.employee.person.economic_data.bank_account
                    banco_nombre = bank_acc.bank.name if bank_acc.bank else "Banco Desconocido"
                    cuenta_tipo = bank_acc.account_type.name if bank_acc.account_type else ""
                    cuenta_numero = bank_acc.account_number
                except Exception:
                    pass

                grupo_data['empleados'][emp_id] = {
                    'persona': it.payslip.employee.person,
                    'empleado': it.payslip.employee,
                    'banco': banco_nombre,
                    'tipo_cuenta': cuenta_tipo,
                    'numero_cuenta': cuenta_numero,

                    'ingresos': Decimal(0),
                    'descuentos': Decimal(0),
                    'liquido': Decimal(0),

                    'ingresos_dict': {},
                    'descuentos_dict': {},
                    'aportes_dict': {},
                }

            emp_dict = grupo_data['empleados'][emp_id]

            # A. LLENADO DINÁMICO CON BLINDAJE DE KEYS (Ej: INC_1, DED_1, CON_1)
            if it.item_type == 'INCOME' and it.income_ref:
                ref = it.income_ref
                key = f"INC_{ref.id}"
                order_val = ref.order if ref.order is not None else 999
                grupo_data['ingresos_headers'][key] = {'key': key, 'name': ref.name, 'order': order_val}
                emp_dict['ingresos_dict'][key] = emp_dict['ingresos_dict'].get(key, Decimal(0)) + val
                emp_dict['ingresos'] += val
                emp_dict['liquido'] += val

            elif it.item_type == 'DEDUCTION' and it.deduction_ref:
                ref = it.deduction_ref
                key = f"DED_{ref.id}"
                order_val = ref.order if ref.order is not None else 999
                code_up = (ref.code or '').upper()

                if 'IESS_PER' in code_up or ('APORTE' in code_up and 'PATRONAL' not in code_up):
                    grupo_data['aportes_headers'][key] = {'key': key, 'name': ref.name, 'order': order_val}
                    emp_dict['aportes_dict'][key] = emp_dict['aportes_dict'].get(key, Decimal(0)) + val
                else:
                    grupo_data['descuentos_headers'][key] = {'key': key, 'name': ref.name, 'order': order_val}
                    emp_dict['descuentos_dict'][key] = emp_dict['descuentos_dict'].get(key, Decimal(0)) + val

                emp_dict['descuentos'] += val
                emp_dict['liquido'] -= val

            elif it.item_type == 'CONTRIBUTION' and it.contribution_ref:
                ref = it.contribution_ref
                key = f"CON_{ref.id}"
                order_val = ref.order if ref.order is not None else 999
                grupo_data['aportes_headers'][key] = {'key': key, 'name': ref.name, 'order': order_val}
                emp_dict['aportes_dict'][key] = emp_dict['aportes_dict'].get(key, Decimal(0)) + val

            # B. PRESUPUESTO
            b_code = getattr(it, 'budget_line_code', None)
            if b_code and str(b_code).strip():
                afecta_presupuesto, nombre_rubro = False, ""

                if it.item_type == 'INCOME' and it.income_ref:
                    inc_id = it.income_ref.id
                    code_up = (it.income_ref.code or '').upper()
                    if (inc_id in mapped_incomes) or ('REMUNERACION' in code_up):
                        afecta_presupuesto, nombre_rubro = True, it.income_ref.name

                elif it.item_type == 'DEDUCTION' and it.deduction_ref:
                    if it.deduction_ref.id in mapped_deductions:
                        afecta_presupuesto, nombre_rubro = True, it.deduction_ref.name

                elif it.item_type == 'CONTRIBUTION' and it.contribution_ref:
                    if it.contribution_ref.id in mapped_contributions:
                        afecta_presupuesto, nombre_rubro = True, it.contribution_ref.name

                if afecta_presupuesto:
                    nombre_rubro = nombre_rubro or "Rubro Desconocido"
                    key_presup = f"{b_code}_{nombre_rubro}"

                    if key_presup not in grupo_data['presupuesto']:
                        grupo_data['presupuesto'][key_presup] = {'partida': b_code, 'concepto': nombre_rubro,
                                                                 'monto': Decimal(0)}
                    grupo_data['presupuesto'][key_presup]['monto'] += val

            # C. CONTABILIDAD
            obj_ref = None
            if it.item_type == 'INCOME':
                obj_ref = it.income_ref
            elif it.item_type == 'DEDUCTION':
                obj_ref = it.deduction_ref
            elif it.item_type == 'CONTRIBUTION':
                obj_ref = it.contribution_ref

            if obj_ref:
                cuenta_debe = getattr(obj_ref, 'debit_account', None)
                if cuenta_debe:
                    cta_debe = cuenta_debe.code
                    grupo_data['contabilidad'].setdefault(cta_debe, {'debe': Decimal(0), 'haber': Decimal(0),
                                                                     'nombre': cuenta_debe.name})
                    grupo_data['contabilidad'][cta_debe]['debe'] += val

                cuenta_haber = getattr(obj_ref, 'credit_account', None)
                if cuenta_haber:
                    cta_haber = cuenta_haber.code
                    grupo_data['contabilidad'].setdefault(cta_haber, {'debe': Decimal(0), 'haber': Decimal(0),
                                                                      'nombre': cuenta_haber.name})
                    grupo_data['contabilidad'][cta_haber]['haber'] += val

            if it.item_type == 'CONTRIBUTION' and obj_ref and 'PATRONAL' in getattr(obj_ref, 'code', '').upper():
                grupo_data['contabilidad'].setdefault('2.1.3.51', {'debe': Decimal(0), 'haber': Decimal(0),
                                                                   'nombre': 'GASTOS DE PERSONAL'})
                grupo_data['contabilidad']['2.1.3.51']['debe'] += val
                grupo_data['contabilidad']['2.1.3.51']['haber'] += val

        # ==============================================================
        # POST-PROCESO: Ordenamiento y Conversión a Listas
        # ==============================================================
        from accounting.models import Account
        cta_gp = Account.objects.filter(code='2.1.3.51').first()
        nombre_gp = cta_gp.name if cta_gp else 'GASTOS DE PERSONAL'
        cta_banco = Account.objects.filter(code='1.1.1.03.01').first()
        nombre_banco = cta_banco.name if cta_banco else 'Banco Central'

        for g_key, g_data in report_data.items():
            total_net_pay = sum((emp['liquido'] for emp in g_data['empleados'].values()), Decimal(0))

            if total_net_pay > 0:
                g_data['contabilidad'].setdefault('2.1.3.51',
                                                  {'debe': Decimal(0), 'haber': Decimal(0), 'nombre': nombre_gp})
                g_data['contabilidad']['2.1.3.51']['debe'] += total_net_pay
                g_data['contabilidad'].setdefault('1.1.1.03.01',
                                                  {'debe': Decimal(0), 'haber': Decimal(0), 'nombre': nombre_banco})
                g_data['contabilidad']['1.1.1.03.01']['haber'] += total_net_pay

            g_data['ingresos_headers'] = {k: v for k, v in g_data['ingresos_headers'].items() if sum(
                emp['ingresos_dict'].get(k, Decimal(0)) for emp in g_data['empleados'].values()) > 0}
            g_data['descuentos_headers'] = {k: v for k, v in g_data['descuentos_headers'].items() if sum(
                emp['descuentos_dict'].get(k, Decimal(0)) for emp in g_data['empleados'].values()) > 0}
            g_data['aportes_headers'] = {k: v for k, v in g_data['aportes_headers'].items() if sum(
                emp['aportes_dict'].get(k, Decimal(0)) for emp in g_data['empleados'].values()) > 0}

            g_data['ingresos_headers'] = sorted(g_data['ingresos_headers'].values(),
                                                key=lambda x: (x['order'], x['name']))
            g_data['descuentos_headers'] = sorted(g_data['descuentos_headers'].values(),
                                                  key=lambda x: (x['order'], x['name']))
            g_data['aportes_headers'] = sorted(g_data['aportes_headers'].values(),
                                               key=lambda x: (x['order'], x['name']))

            # Usamos h['key'] para extraer el dinero exacto de las columnas
            for emp in g_data['empleados'].values():
                emp['ingresos_list'] = [emp['ingresos_dict'].get(h['key'], Decimal(0)) for h in
                                        g_data['ingresos_headers']]
                emp['descuentos_list'] = [emp['descuentos_dict'].get(h['key'], Decimal(0)) for h in
                                          g_data['descuentos_headers']]
                emp['aportes_list'] = [emp['aportes_dict'].get(h['key'], Decimal(0)) for h in g_data['aportes_headers']]
                emp['total_aportes'] = sum(emp['aportes_dict'].values())

            ts = {
                'total_ingresos': sum((e['ingresos'] for e in g_data['empleados'].values()), Decimal(0)),
                'total_descuentos': sum((e['descuentos'] for e in g_data['empleados'].values()), Decimal(0)),
                'total_aportes': sum((e['total_aportes'] for e in g_data['empleados'].values()), Decimal(0)),
                'liquido': sum((e['liquido'] for e in g_data['empleados'].values()), Decimal(0)),

                'ingresos_list': [
                    sum((e['ingresos_dict'].get(h['key'], Decimal(0)) for e in g_data['empleados'].values()),
                        Decimal(0)) for h in g_data['ingresos_headers']],
                'descuentos_list': [
                    sum((e['descuentos_dict'].get(h['key'], Decimal(0)) for e in g_data['empleados'].values()),
                        Decimal(0)) for h in g_data['descuentos_headers']],
                'aportes_list': [
                    sum((e['aportes_dict'].get(h['key'], Decimal(0)) for e in g_data['empleados'].values()), Decimal(0))
                    for h in g_data['aportes_headers']],
            }
            g_data['totales_sabana'] = ts

            g_data['colspans'] = {
                'ingresos': len(g_data['ingresos_headers']) or 1,
                'aportes': len(g_data['aportes_headers']),
                'descuentos': len(g_data['descuentos_headers'])
            }

            cuentas_debe = []
            cuentas_solo_haber = []

            for cta, c_data in g_data['contabilidad'].items():
                if c_data['debe'] > 0:
                    cuentas_debe.append(
                        {'codigo': cta, 'nombre': c_data['nombre'], 'debe': c_data['debe'], 'haber': c_data['haber']})
                elif c_data['haber'] > 0:
                    cuentas_solo_haber.append(
                        {'codigo': cta, 'nombre': c_data['nombre'], 'debe': Decimal(0), 'haber': c_data['haber']})

            cuentas_debe.sort(key=lambda x: x['codigo'], reverse=True)
            cuentas_solo_haber.sort(key=lambda x: x['codigo'])

            g_data['contabilidad_ordenada'] = cuentas_debe + cuentas_solo_haber
            g_data['total_contabilidad_debe'] = sum((c['debe'] for c in g_data['contabilidad_ordenada']), Decimal(0))
            g_data['total_contabilidad_haber'] = sum((c['haber'] for c in g_data['contabilidad_ordenada']), Decimal(0))
            g_data['total_presupuesto'] = sum((p['monto'] for p in g_data['presupuesto'].values()), Decimal(0))

        sorted_reports = dict(sorted(report_data.items()))
        context = {
            'period': period,
            'grouped_reports': sorted_reports,
            'base_template': 'base_pdf.html' if request.GET.get('export') == 'pdf' else 'base.html'
        }
        return render(request, 'payroll/reports/grouped_financial_report.html', context)


class PayslipToggleWithholdView(LoginRequiredMixin, View):
    """
    API para encender/apagar la retención de pago de un rol específico.
    """

    def post(self, request, pk):
        payslip = get_object_or_404(Payslip, pk=pk)

        # Invertimos el estado actual
        payslip.is_withheld = not payslip.is_withheld
        payslip.save(update_fields=['is_withheld'])

        estado = "RETENIDO" if payslip.is_withheld else "LIBERADO"
        return JsonResponse({
            'success': True,
            'message': f'El pago de este empleado ha sido {estado}.',
            'is_withheld': payslip.is_withheld
        })


class PayslipItemUpdateAPIView(LoginRequiredMixin, View):
    """
    API para modificar un rubro manual (ej. subirle $10 a un descuento).
    Recalcula el total del empleado y RECONSTRUYE la contabilidad automáticamente.
    """

    def post(self, request, item_id):
        nuevo_valor = Decimal(request.POST.get('new_value', '0.00'))

        try:
            with transaction.atomic():
                item = get_object_or_404(PayslipItem, pk=item_id)
                item.value = nuevo_valor
                item.save(update_fields=['value'])

                # 1. RECALCULAR EL BOLSILLO DEL EMPLEADO
                payslip = item.payslip
                totales = PayslipItem.objects.filter(payslip=payslip).aggregate(
                    total_ing=Sum('value', filter=Q(item_type='INCOME')),
                    total_desc=Sum('value', filter=Q(item_type='DEDUCTION'))
                )

                t_ing = totales['total_ing'] or Decimal('0.00')
                t_desc = totales['total_desc'] or Decimal('0.00')

                payslip.total_income = t_ing
                payslip.total_deduction = t_desc
                payslip.net_pay = t_ing - t_desc
                payslip.save(update_fields=['total_income', 'total_deduction', 'net_pay'])

                # Ejecutar reconstrucción contable fuera de la transacción para evitar rollback
                def _safe_rebuild(pid):
                    try:
                        rebuild_accounting_for_period(pid)
                    except Exception as _e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.exception('Error al reconstruir contabilidad para periodo %s: %s', pid, _e)

                try:
                    transaction.on_commit(lambda: _safe_rebuild(payslip.period.id))
                except Exception:
                    # Fallback: intentar ejecutar sin on_commit
                    try:
                        _safe_rebuild(payslip.period.id)
                    except Exception:
                        pass

            return JsonResponse({
                'success': True,
                'message': 'Valor actualizado. Reconstrucción contable encolada.',
                'new_total_income': str(payslip.total_income),
                'new_total_deduction': str(payslip.total_deduction),
                'new_net_pay': str(payslip.net_pay)
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error en actualización: {str(e)}'})


class MarkPeriodAsPaidAPIView(LoginRequiredMixin, View):
    """
    Sella los roles actuales como PAGADOS para que no vuelvan a salir en futuros alcances.
    Si detecta que ya no queda nadie por cobrar, cierra el periodo automáticamente.
    """

    def post(self, request, period_id):
        # 1. Marcamos como pagados SOLO a los que no están retenidos y que aún no cobraban
        roles_actualizados = Payslip.objects.filter(
            period_id=period_id,
            is_withheld=False,
            is_paid=False
        ).update(is_paid=True)

        # 2. Verificamos si en este periodo todavía queda alguien sin cobrar
        faltan_por_pagar = Payslip.objects.filter(period_id=period_id, is_paid=False).exists()

        mensaje = f'Se han sellado {roles_actualizados} roles como PAGADOS en el SPI-SP.'

        if not faltan_por_pagar:
            # 3. ¡Magia! Si ya no hay nadie pendiente, cerramos el periodo para siempre
            PayrollPeriod.objects.filter(id=period_id).update(is_closed=True)
            mensaje += ' Como ya no quedan pagos pendientes, el Periodo se ha CERRADO automáticamente.'

        return JsonResponse({
            'success': True,
            'message': mensaje,
            'is_closed': not faltan_por_pagar
        })


class RecalculatePayslipsView(LoginRequiredMixin, View):
    """
    Recalcula los roles que coinciden con los filtros enviados (q, group, show_withheld).
    Se usa desde la interfaz para recalcular la búsqueda actual sin regenerar todo el periodo.
    """

    def post(self, request):
        period_id = request.POST.get('period_id') or request.GET.get('period_id')
        if not period_id:
            return JsonResponse({'success': False, 'message': 'Periodo no especificado.'}, status=400)

        period = get_object_or_404(PayrollPeriod, pk=period_id)

        # Capturar filtros opcionales
        search_query = (request.POST.get('q') or request.GET.get('q') or '').strip()
        group_filter = (request.POST.get('group') or request.GET.get('group') or '').strip()
        regime_filter = (request.POST.get('regime') or request.GET.get('regime') or '').strip()  # NUEVO
        show_withheld = (request.POST.get('show_withheld') or request.GET.get('show_withheld') or '').lower()

        qs = Payslip.objects.filter(period=period)
        if search_query:
            qs = qs.filter(
                Q(employee__person__first_name__icontains=search_query) |
                Q(employee__person__last_name__icontains=search_query) |
                Q(employee__person__document_number__icontains=search_query) |
                Q(items__budget_line__budget_group__short_code__icontains=search_query)
            ).distinct()
        if group_filter:
            qs = qs.filter(items__budget_line__budget_group__short_code=group_filter).distinct()

        if show_withheld in ['only', '1', 'true', 'yes']:
            qs = qs.filter(is_withheld=True)
        if regime_filter:
            qs = qs.filter(items__budget_line__regime_item_id=regime_filter).distinct()

        emp_ids = list(qs.values_list('employee_id', flat=True).distinct())
        if not emp_ids:
            return JsonResponse({'success': True, 'message': 'No hay roles que coincidan con los filtros.', 'count': 0})

        employees = list(Employee.objects.filter(id__in=emp_ids))

        pairs = []
        for p in Payslip.objects.filter(period=period, employee_id__in=emp_ids):
            pairs.append((p.employee, p.worked_days or period.working_days))

        try:
            svc = PayrollCalculatorService(period, employees)
            result = svc.generate_for_selected(pairs)
            return JsonResponse(
                {'success': True, 'message': 'Recalculo ejecutado.', 'result': result, 'count': len(emp_ids)})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class GenerateMissingPayrollView(LoginRequiredMixin, View):
    """
    Busca empleados que tengan un contrato activo en el mes pero que AÚN NO
    tengan un rol de pagos generado, y los agrega sin borrar al resto.
    """

    def post(self, request):
        try:
            period_id = request.POST.get('period_id')
            period = get_object_or_404(PayrollPeriod, pk=period_id)

            # 1. ¿Quiénes DEBERÍAN estar en este mes? (Máquina del tiempo)
            valid_history_emp_ids = set(BudgetAssignmentHistory.objects.filter(
                start_date__lte=period.end_date
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=period.start_date)
            ).values_list('employee_id', flat=True))

            # 2. ¿Quiénes YA ESTÁN en el rol actual?
            existing_emp_ids = set(Payslip.objects.filter(period=period).values_list('employee_id', flat=True))

            # 3. Matemática de conjuntos: Los que deberían estar MENOS los que ya están = Los Nuevos
            missing_ids = valid_history_emp_ids - existing_emp_ids

            if not missing_ids:
                return JsonResponse(
                    {'status': 'info', 'message': 'Todos los empleados activos ya están en el rol. No hay faltantes.'})

            # 4. Traemos a los empleados y los mandamos al motor
            missing_employees = Employee.objects.filter(id__in=missing_ids, is_active=True, person__is_active=True)
            employees_with_days = [(emp, period.working_days) for emp in missing_employees]

            service = PayrollCalculatorService(period, missing_employees)
            # Usamos la función que calcula solo a los seleccionados
            resultado = service.generate_for_selected(employees_with_days)

            if resultado.get("success"):
                return JsonResponse({'status': 'success',
                                     'message': f'Se agregaron {len(missing_employees)} nuevos empleados al rol exitosamente.'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Hubo advertencias al calcular.'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})


class BankTransferReportView(LoginRequiredMixin, View):
    """
    Vista EXCLUSIVA para el Archivo de Transferencias Bancarias (Reporte 4 / SPI-SP).
    """

    def get(self, request, pk):
        period = get_object_or_404(PayrollPeriod, pk=pk)
        tipo_filtro = request.GET.get('filtro', 'NORMAL')
        search_query = request.GET.get('q', '').strip()
        group_filter = request.GET.get('group', '').strip()
        regime_filter = request.GET.get('regime', '').strip()

        payslips_qs = Payslip.objects.filter(period=period).select_related(
            'employee__person'
        ).order_by('employee__person__last_name')

        # 1. APLICAMOS EL MISMO BUSCADOR DE LA PANTALLA PRINCIPAL
        if search_query:
            payslips_qs = payslips_qs.filter(
                Q(employee__person__first_name__icontains=search_query) |
                Q(employee__person__last_name__icontains=search_query) |
                Q(employee__person__document_number__icontains=search_query) |
                Q(items__budget_line__budget_group__short_code__icontains=search_query)
            ).distinct()  # Importante el distinct

        if group_filter:
            payslips_qs = payslips_qs.filter(items__budget_line__budget_group__short_code=group_filter).distinct()

        if regime_filter:
            payslips_qs = payslips_qs.filter(items__budget_line__regime_item_id=regime_filter).distinct()

        # 2. Filtros de Retención (Liberados vs Retenidos)
        # Soporte para parámetro `show_withheld` enviado por el frontend
        show_withheld = (request.GET.get('show_withheld') or '').lower()
        if show_withheld in ['only', '1', 'true', 'yes']:
            payslips_qs = payslips_qs.filter(is_withheld=True)
        else:
            if tipo_filtro == 'NORMAL':
                payslips_qs = payslips_qs.filter(is_withheld=False)
            elif tipo_filtro == 'REZAGADOS':
                payslips_qs = payslips_qs.filter(is_withheld=False, is_paid=False)

        if regime_filter:
            payslips_qs = payslips_qs.filter(items__budget_line__regime_item_id=regime_filter).distinct()

        # 3. PRE-CARGA CRÍTICA: Traemos los datos bancarios para evitar que el template colapse
        payslips_qs = payslips_qs.prefetch_related(
            'employee__person__economic_data__bank_account__bank',
            'employee__person__economic_data__bank_account__account_type'
        )

        total_transferir = sum(Decimal(str(p.net_pay)) for p in payslips_qs)

        context = {
            'period': period,
            'payslips': payslips_qs,
            'total_transferir': total_transferir,
            'filtro': tipo_filtro,
            'search_query': search_query
        }
        return render(request, 'payroll/reports/bank_transfer_report.html', context)


class PeriodUpdateView(UpdateView):
    model = PayrollPeriod
    form_class = PayrollPeriodForm
    template_name = 'payroll/modals/modal_period_form.html'

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'status': 'success', 'message': 'Periodo actualizado correctamente.'})

    def form_invalid(self, form):
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


def api_calculate_working_days(request):
    month_name = request.GET.get('month')
    year = request.GET.get('year')

    if not month_name or not year:
        return JsonResponse({'status': 'error', 'message': 'Faltan parámetros'}, status=400)

    try:
        # Mapeo de meses
        months_map = {
            'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
            'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
            'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12
        }
        month_num = months_map.get(month_name.upper())
        year_num = int(year)

        # Calcular primer y último día del mes
        first_day = date(year_num, month_num, 1)
        last_day_num = calendar.monthrange(year_num, month_num)[1]
        last_day = date(year_num, month_num, last_day_num)

        # Usamos un objeto temporal del modelo para aprovechar la lógica de feriados
        temp_period = PayrollPeriod(start_date=first_day, end_date=last_day)
        working_days = temp_period.get_working_days()  # Esta función ya existe en tu models.py

        # Además, detectamos si hay feriados activos en el rango y construimos una advertencia
        from schedule.models import ScheduleObservation

        holidays = ScheduleObservation.objects.filter(
            is_holiday=True,
            is_active=True,
            start_date__lte=last_day,
            end_date__gte=first_day
        )

        # Compilar conjunto de fechas de feriados
        holiday_dates = set()
        from datetime import timedelta
        for holiday in holidays:
            curr = max(holiday.start_date, first_day)
            end_limit = min(holiday.end_date, last_day)
            while curr <= end_limit:
                holiday_dates.add(curr)
                curr += timedelta(days=1)

        response = {
            'status': 'success',
            'start_date': first_day.strftime('%Y-%m-%d'),
            'end_date': last_day.strftime('%Y-%m-%d'),
            'working_days': working_days
        }

        if len(holiday_dates) > 0:
            # Formatear una advertencia legible
            sample_dates = ', '.join(sorted([d.strftime('%d/%m/%Y') for d in list(holiday_dates)[:3]]))
            more = '' if len(holiday_dates) <= 3 else f' y {len(holiday_dates) - 3} más'
            response['warning'] = f'Se detectaron {len(holiday_dates)} feriado(s) en el periodo ({sample_dates}{more}).'
        else:
            response['info'] = 'No se detectaron feriados en el periodo seleccionado.'

        return JsonResponse(response)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def export_negative_balances_report(request, period_id):
    """
    Genera un PDF Institucional con los empleados cuyo sueldo no alcanzó
    para cubrir sus descuentos, agrupado por tipo de descuento con subtotales.
    """
    period = get_object_or_404(PayrollPeriod, id=period_id)

    # Consultamos y ordenamos primero por el nombre del descuento, luego por empleado
    debts = PendingDebt.objects.filter(
        period=period,
        pending_balance__gt=0
    ).select_related(
        'employee__person', 'deduction_ref'
    ).order_by('deduction_ref__name', 'employee__person__last_name')

    # Diccionario para agrupar los datos y calcular subtotales
    grouped_data = {}
    total_original = Decimal('0.0')
    total_cobrado = Decimal('0.0')
    total_pendiente = Decimal('0.0')

    for debt in debts:
        concept_name = debt.deduction_ref.name
        if concept_name not in grouped_data:
            grouped_data[concept_name] = {
                'items': [],
                'sub_original': Decimal('0.0'),
                'sub_cobrado': Decimal('0.0'),
                'sub_pendiente': Decimal('0.0'),
            }

        # Agregamos el empleado al grupo
        grouped_data[concept_name]['items'].append(debt)

        # Sumamos a los subtotales del grupo
        grouped_data[concept_name]['sub_original'] += debt.original_value
        grouped_data[concept_name]['sub_cobrado'] += debt.collected_value
        grouped_data[concept_name]['sub_pendiente'] += debt.pending_balance

        # Sumamos a los totales generales
        total_original += debt.original_value
        total_cobrado += debt.collected_value
        total_pendiente += debt.pending_balance

    context = {
        'period': period,
        'grouped_data': grouped_data,
        'total_original': total_original,
        'total_cobrado': total_cobrado,
        'total_pendiente': total_pendiente,
        'has_debts': debts.exists()
    }

    template = get_template('payroll/reports/report_negative_balances.html')
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Saldos_Rezagados_{period.month}_{period.year}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Ocurrió un error al generar el PDF', status=500)

    return response


class MassUpdateReserveFundsView(View):
    """
    API para carga masiva de Fondos de Reserva.
    Lee un Excel con Cédulas:
    - Los que estén en el Excel pasan a ACUMULAR (False).
    - Los que NO estén pasan a MENSUALIZAR (True) automáticamente.
    """

    def post(self, request):
        excel_file = request.FILES.get('file')
        if not excel_file:
            return JsonResponse({'status': 'error', 'message': 'No se subió ningún archivo'})

        try:
            import openpyxl
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            sheet = wb.active

            # 1. Leer las cédulas del Excel (ignora si la primera celda dice "CEDULA")
            cedulas_acumulan = set()
            for row in sheet.iter_rows(min_row=1, values_only=True):
                if not row[0]: continue
                raw = str(row[0]).strip()
                if raw.replace('.', '').isdigit():
                    if raw.endswith('.0'): raw = raw[:-2]
                    cedulas_acumulan.add(raw.zfill(10))

            # 2. Traer a los empleados y preparar la actualización masiva
            empleados = Employee.objects.filter(is_active=True).select_related('person__economic_data__payroll_info')
            infos_to_update = []

            with transaction.atomic():
                for emp in empleados:
                    try:
                        # Navegamos hasta el perfil económico/nómina del empleado
                        info = emp.person.economic_data.payroll_info
                        if info:
                            cedula = emp.person.document_number

                            # LÓGICA MAESTRA: Si está en el Excel, Acumula (False). Si no, Mensualiza (True).
                            nuevo_estado = False if cedula in cedulas_acumulan else True

                            # Solo lo actualizamos si es diferente a lo que ya tenía, para ahorrar memoria
                            if getattr(info, 'reserve_funds') != nuevo_estado:
                                info.reserve_funds = nuevo_estado
                                infos_to_update.append(info)
                    except AttributeError:
                        continue

                # 3. Guardado ultra-rápido en base de datos (Bulk Update)
                if infos_to_update:
                    ModelClass = type(infos_to_update[0])  # Obtenemos el modelo dinámicamente
                    ModelClass.objects.bulk_update(infos_to_update, ['reserve_funds'])

            return JsonResponse({
                'status': 'success',
                'message': f'¡Proceso exitoso! Se configuraron {len(cedulas_acumulan)} empleados para ACUMULAR en el IESS. El resto mensualizará automáticamente.'
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error procesando el archivo: {str(e)}'})
