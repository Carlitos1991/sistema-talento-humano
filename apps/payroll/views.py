from django.db.models import Q, Sum
from django.views.generic import ListView, TemplateView, View, DeleteView, UpdateView, CreateView, DetailView
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
import openpyxl
import json
from accounting.models import Journal, JournalItem
from .forms import PayrollPeriodForm, PayrollConstantForm, RubroBudgetMappingForm, IncomeForm, DeductionForm, \
    InstitutionalContributionForm
from .models import PayrollPeriod, Payslip, PayrollConstant, PayslipItem, PayrollNovelty, InstitutionalContribution
from .services import PayrollCalculatorService
from employee.models import Employee
from .models import Income, Deduction
from django.urls import reverse_lazy
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django import forms
from django.contrib import messages
from payroll.models import RubroBudgetMapping
from budget.models import BudgetLine
from contract.models import ManagementPeriod
from datetime import date


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
                Q(employee__person__document_number__icontains=search) |
                Q(employee__person__last_name__icontains=search) |
                Q(employee__person__first_name__icontains=search)
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
        # Separamos ingresos y egresos para mostrarlos ordenados
        context['incomes'] = self.object.items.filter(item_type='INCOME')

        # Filtro Mágico: Trae los descuentos, PERO excluye los que digan "PATRONAL"
        context['deductions'] = self.object.items.filter(
            item_type='DEDUCTION'
        ).exclude(
            deduction_ref__code__icontains='PATRONAL'
        )

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
    """Recibe la tabla editada y guarda (o elimina) en la base de datos"""

    def post(self, request):
        try:
            payload = json.loads(request.body)
            period_id = payload.get('period_id')
            rubro_type = payload.get('rubro_type')
            rubro_id = payload.get('rubro_id')
            items = payload.get('items', [])

            period = PayrollPeriod.objects.get(pk=period_id)

            for item in items:
                val = float(item.get('valor', 0))
                emp_id = item.get('emp_id')

                # Buscamos si ya existía una novedad previa para actualizarla
                if rubro_type == 'INCOME':
                    novelty = PayrollNovelty.objects.filter(period=period, employee_id=emp_id,
                                                            income_ref_id=rubro_id).first()
                else:
                    novelty = PayrollNovelty.objects.filter(period=period, employee_id=emp_id,
                                                            deduction_ref_id=rubro_id).first()

                if val <= 0:
                    # MAGIA: Si en la tabla le pusieron 0.00, borramos la novedad de la base de datos
                    if novelty:
                        novelty.delete()
                else:
                    if novelty:
                        novelty.value = val
                        novelty.save()
                    else:
                        # Si no existía, la creamos
                        if rubro_type == 'INCOME':
                            PayrollNovelty.objects.create(period=period, employee_id=emp_id, income_ref_id=rubro_id,
                                                          value=val)
                        else:
                            PayrollNovelty.objects.create(period=period, employee_id=emp_id, deduction_ref_id=rubro_id,
                                                          value=val)

            return JsonResponse({'status': 'success', 'message': 'Novedades guardadas exitosamente'})
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
