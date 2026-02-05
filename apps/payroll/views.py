from django.db.models import Q
from django.views.generic import ListView, TemplateView, View, DeleteView, UpdateView, CreateView, DetailView
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404

from .forms import PayrollPeriodForm, PayrollConstantForm
from .models import PayrollPeriod, Payslip, PayrollConstant
from .services import PayrollCalculatorService
from employee.models import Employee


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


class PeriodCreateView(View):
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

            # Simulamos empleados (aquí debes filtrar tus empleados activos)
            employees = Employee.objects.all()  # .filter(status='ACTIVO')

            service = PayrollCalculatorService(period, employees)
            service.generate_bulk()

            return JsonResponse({'status': 'success', 'message': 'Cálculo completado exitosamente.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class ConstantListView(ListView):
    model = PayrollConstant
    template_name = 'payroll/constant_list.html'
    context_object_name = 'constants'


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


class PayslipListView(ListView):
    model = Payslip
    template_name = 'payroll/payslip_list.html'
    context_object_name = 'payslips'
    paginate_by = 50  # Clave para la velocidad: solo muestra 50 a la vez

    def get_queryset(self):
        # Optimización SQL: select_related evita el problema N+1 queries
        qs = Payslip.objects.select_related(
            'employee',
            'employee__person',  # Asumiendo que Employee tiene relación con Person
            'period'
        ).all()

        # Filtro por Periodo (Obligatorio)
        period_id = self.request.GET.get('period_id')
        if period_id:
            qs = qs.filter(period_id=period_id)

        # Filtro por Búsqueda (Cédula o Nombre)
        search = self.request.GET.get('q')
        if search:
            qs = qs.filter(
                Q(employee__person__identification__icontains=search) |
                Q(employee__person__lastname__icontains=search) |
                Q(employee__person__name__icontains=search)
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period_id = self.request.GET.get('period_id')
        if period_id:
            context['current_period'] = PayrollPeriod.objects.filter(pk=period_id).first()
        return context


class PayslipDetailView(DetailView):
    """Para el Modal de Detalle (reemplaza a rol_detalle antiguo)"""
    model = Payslip
    template_name = 'payroll/modals/modal_payslip_detail.html'
    context_object_name = 'payslip'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Separamos ingresos y egresos para mostrarlos ordenados como en el antiguo modal
        context['incomes'] = self.object.items.filter(item_type='INCOME')
        context['deductions'] = self.object.items.filter(item_type='DEDUCTION')
        return context
