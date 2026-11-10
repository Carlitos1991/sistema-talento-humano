from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, UpdateView
from django.views.generic import ListView
from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
import uuid

LICENSE_MONTH_NAMES = (
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
)

# Importación desde otras apps raíz del sys.path
from employee.models import Employee
from contract.models import ManagementPeriod
from core.models import User
from institution.models import AdministrativeUnit
from .forms import (
    MedicalLicenseForm,
    LicensePersonnelActionForm,
    LicenseTypeForm,
    LicenseTypeRequirementForm
)
# Importaciones locales dentro de licenses
from .models import (
    MedicalLicense,
    MedicalLicenseType,
    LicenseReception,
    LicenseReceptionCheck,
    LicenseSchedule,
    LicensePayrollEffect,
)
from .services import (
    _ensure_license_action_movement,
    apply_validation_effects,
    create_draft_license_action,
)


def _human_resources_employees():
    th_unit = AdministrativeUnit.objects.filter(
        is_human_resources=True, is_active=True
    ).first()
    if not th_unit:
        return Employee.objects.none()
    return Employee.objects.select_related('person').filter(
        area_id__in=th_unit.get_descendant_ids(),
        is_active=True
    ).order_by('person__last_name', 'person__first_name')


def _human_resources_users():
    th_unit = AdministrativeUnit.objects.filter(
        is_human_resources=True, is_active=True
    ).first()
    if not th_unit:
        return User.objects.none()
    unit_ids = th_unit.get_descendant_ids()
    employees = _human_resources_employees()
    users = User.objects.filter(
        person__employee_profile__area_id__in=unit_ids,
        person__employee_profile__is_active=True,
        is_active=True
    ).order_by('last_name', 'first_name', 'username')
    if users.exists():
        return users
    document_numbers = employees.exclude(
        person__document_number__isnull=True
    ).exclude(
        person__document_number=''
    ).values_list('person__document_number', flat=True)
    return User.objects.filter(
        username__in=document_numbers,
        is_active=True
    ).order_by('last_name', 'first_name', 'username')


def _ensure_medical_license_from_reception(reception, user):
    """Create the management record once a physical reception is delivered."""
    if hasattr(reception, 'medical_license') and reception.medical_license:
        return reception.medical_license

    start_date = reception.license_start_date or reception.reception_date.date()
    end_date = reception.license_end_date
    return MedicalLicense.objects.create(
        reception=reception,
        employee=reception.employee,
        license_type=reception.license_type,
        start_date=start_date,
        end_date=end_date,
        diagnosis=reception.observations or 'Licencia remitida desde recepción documental.',
        issuing_entity='Pendiente de registrar',
        status=MedicalLicense.STATUS_SUBMITTED,
        created_by=user,
    )


def _subsidy_cutoff(year, month):
    cutoff_end = datetime(year, month, 20).date()
    previous_month = cutoff_end.replace(day=1) - timedelta(days=1)
    return previous_month.replace(day=21), cutoff_end


def _subsidy_amount(effect):
    budget_line = effect.license.employee.current_budget_line.select_related(
        'position_item'
    ).first()
    remuneration = getattr(budget_line, 'remuneration', None) or Decimal('0.00')
    daily_remuneration = remuneration / Decimal('30')
    return (
            daily_remuneration * min(effect.employer_covered_days, 3) * Decimal('0.50')
            + daily_remuneration * effect.days_to_discount
    ).quantize(Decimal('0.01'))


# ==========================================
# 1. GESTIÓN DE TIPOS DE LICENCIAS
# ==========================================

class LicenseTypeListView(LoginRequiredMixin, ListView):
    model = MedicalLicenseType
    template_name = 'licenses/type_list.html'
    context_object_name = 'types'
    permission_required = 'licenses.view_medicallicensetype'
    raise_exception = True
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related(
            'requirements',
            'default_authority_1',
            'default_authority_2',
            'default_reviewer',
            'default_register'
        )

        query = self.request.GET.get('q', '').strip()
        show_inactive = self.request.GET.get('show_inactive')

        # Si el switch se activa (show_inactive == 'true'), filtra ÚNICAMENTE inactivos
        if show_inactive == 'true':
            qs = qs.filter(is_active=False)
        else:
            qs = qs.filter(is_active=True)

        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query))

        return qs.order_by('name')

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html_table = render_to_string(
                'licenses/partials/partial_type_table.html',
                context,
                request=self.request
            )
            page_obj = context.get('page_obj')
            paginator = context.get('paginator')
            return JsonResponse({
                'success': True,
                'html': html_table,
                'page_number': page_obj.number if page_obj else 1,
                'has_next': page_obj.has_next() if page_obj else False,
                'has_previous': page_obj.has_previous() if page_obj else False,
                'num_pages': paginator.num_pages if paginator else 1,
                'total_records': paginator.count if paginator else 0,
            })
        return super().render_to_response(context, **response_kwargs)


class LicenseTypeCreateView(LoginRequiredMixin, CreateView):
    model = MedicalLicenseType
    form_class = LicenseTypeForm
    template_name = 'licenses/modals/modal_type_form.html'
    success_url = reverse_lazy('licenses:type_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_url'] = reverse('licenses:type_create')
        context['is_edit'] = False
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': f'Tipo de Licencia "{self.object.name}" creado correctamente.'
            })
        return redirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor corrija los errores en el formulario.',
                'errors': errors_data
            }, status=400)
        return super().form_invalid(form)


class LicenseTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = MedicalLicenseType
    form_class = LicenseTypeForm
    template_name = 'licenses/modals/modal_type_form.html'
    success_url = reverse_lazy('licenses:type_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_url'] = reverse('licenses:type_update', kwargs={'pk': self.object.pk})
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'success': True,
                'message': f'Tipo de Licencia "{self.object.name}" actualizado correctamente.'
            })
        return redirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor corrija los errores en el formulario.',
                'errors': errors_data
            }, status=400)
        return super().form_invalid(form)


# ==========================================
# 2. VISTAS PARA CREACIÓN RÁPIDA DE REQUISITOS
# ==========================================

class RequirementCreateModalView(LoginRequiredMixin, View):
    """Renderiza el submodal para registrar un nuevo requisito/anexo."""

    def get(self, request, *args, **kwargs):
        form = LicenseTypeRequirementForm()
        html = render_to_string(
            'licenses/modals/modal_requirement_form.html',
            {'form': form},
            request=request
        )
        return JsonResponse({'success': True, 'html': html})


class RequirementSaveAjaxView(LoginRequiredMixin, View):
    """Guarda el nuevo requisito y lo retorna para agregarlo dinámicamente al Select2."""

    def post(self, request, *args, **kwargs):
        form = LicenseTypeRequirementForm(request.POST)
        if form.is_valid():
            req_obj = form.save()
            return JsonResponse({
                'success': True,
                'status': 'success',
                'message': 'Requisito creado correctamente.',
                'requirement': {
                    'id': req_obj.id,
                    'name': req_obj.name,
                }
            })
        errors = {field: [str(err) for err in errs] for field, errs in form.errors.items()}
        return JsonResponse({'success': False, 'status': 'error', 'errors': errors}, status=400)


# ==========================================
# 3. RECEPCIÓN E INSPECCIÓN DOCUMENTAL
# ==========================================

class LicenseReceptionListView(LoginRequiredMixin, ListView):
    model = LicenseReception
    template_name = 'licenses/reception_list.html'
    permission_required = 'licenses.view_licensereception'
    raise_exception = True
    context_object_name = 'receptions'
    paginate_by = 10

    def get_queryset(self):
        qs = LicenseReception.objects.select_related(
            'employee__person', 'license_type', 'received_by'
        ).prefetch_related('checked_items__requirement').all()

        # 1. Filtro por búsqueda de texto (Nombre, Apellidos o Cédula)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(employee__person__first_name__icontains=q) |
                Q(employee__person__last_name__icontains=q) |
                Q(employee__person__document_number__icontains=q)
            )

        # 2. Filtro por Estado (Stat Cards)
        status = self.request.GET.get('status', '').strip()
        if status == LicenseReception.STATUS_CANCELLED:
            qs = qs.filter(status=status)
        elif status and status != 'all':
            qs = qs.filter(status=status).exclude(status=LicenseReception.STATUS_CANCELLED)
        else:
            qs = qs.exclude(status=LicenseReception.STATUS_CANCELLED)

        # 3. Filtros avanzados
        license_type_id = self.request.GET.get('license_type', '').strip()
        if license_type_id:
            qs = qs.filter(license_type_id=license_type_id)

        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()
        if date_from:
            qs = qs.filter(reception_date__date__gte=date_from)
        if date_to:
            qs = qs.filter(reception_date__date__lte=date_to)

        return qs.order_by('-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Base completa para las tarjetas estadísticas
        full_qs = LicenseReception.objects.exclude(status=LicenseReception.STATUS_CANCELLED)
        registered_count = full_qs.filter(status=LicenseReception.STATUS_REGISTERED).count()
        approved_count = full_qs.filter(status=LicenseReception.STATUS_APPROVED).count()
        delivered_count = full_qs.filter(status=LicenseReception.STATUS_DELIVERED).count()
        context['stats'] = {
            'total': registered_count + approved_count + delivered_count,
            'registered': registered_count,
            'approved': approved_count,
            'delivered': delivered_count,
        }
        context['license_types'] = MedicalLicenseType.objects.filter(is_active=True)
        context['reception_statuses'] = LicenseReception.STATUS_CHOICES
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html_table = render_to_string(
                'licenses/partials/partial_reception_table.html',
                context,
                request=self.request
            )
            return JsonResponse({
                'success': True,
                'html': html_table,
                'stats': context.get('stats', {})
            })
        return super().render_to_response(context, **response_kwargs)


class LicenseReceptionSaveView(LoginRequiredMixin, View):
    """Guarda la recepción evaluando si el checklist está completo para marcar Aprobado o Registrado."""

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        employee_id = request.POST.get('employee')
        license_type_id = request.POST.get('license_type')
        observations = request.POST.get('observations', '')
        start_date_raw = request.POST.get('license_start_date')
        days_raw = request.POST.get('license_days', '').strip()
        supporting_document = request.POST.get('supporting_document', '').strip()
        checked_req_ids = [int(i) for i in request.POST.getlist('requirements_checked')]

        if not days_raw:
            return JsonResponse({'success': False, 'message': 'El número de días de licencia es obligatorio.'},
                                status=400)
        if not supporting_document:
            return JsonResponse({'success': False, 'message': 'El documento habilitante es obligatorio.'}, status=400)
        if len(supporting_document) > 255:
            return JsonResponse(
                {'success': False, 'message': 'El documento habilitante no puede superar 255 caracteres.'}, status=400)
        try:
            license_days = int(days_raw)
        except ValueError:
            return JsonResponse({'success': False, 'message': 'El número de días debe ser un valor entero.'},
                                status=400)
        if license_days < 0:
            return JsonResponse({'success': False, 'message': 'El número de días no puede ser negativo.'}, status=400)

        employee = get_object_or_404(Employee, pk=employee_id)
        license_type = get_object_or_404(MedicalLicenseType, pk=license_type_id)
        try:
            license_start_date = datetime.strptime(start_date_raw, '%Y-%m-%d').date() if start_date_raw else None
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Las fechas de la licencia no son válidas.'}, status=400)
        if not license_start_date:
            return JsonResponse({'success': False, 'message': 'La fecha de inicio de la licencia es obligatoria.'},
                                status=400)
        license_end_date = (
            license_start_date + timedelta(days=license_days - 1)
            if license_days > 0 else None
        )
        if license_days == 0:
            observations = (
                f'{observations}\nLicencia indefinida desde '
                f'{license_start_date:%d/%m/%Y}.'
            ).strip()

        # 1. Crear cabecera inicial
        reception = LicenseReception.objects.create(
            employee=employee,
            license_type=license_type,
            received_by=request.user,
            license_start_date=license_start_date,
            license_end_date=license_end_date,
            license_days=license_days,
            supporting_document=supporting_document,
            observations=observations,
            status=LicenseReception.STATUS_REGISTERED
        )

        # 2. Registrar checklist de anexos
        all_requirements = license_type.requirements.filter(is_active=True)
        for req in all_requirements:
            is_checked = req.id in checked_req_ids
            LicenseReceptionCheck.objects.create(
                reception=reception,
                requirement=req,
                is_checked=is_checked
            )

        # 3. Lógica de Estado Automático: Si no debe ningún anexo obligatorio, pasa directo a APROBADO
        mandatory_missing = license_type.requirements.filter(is_active=True, is_mandatory=True).exclude(
            id__in=checked_req_ids).exists()
        if not mandatory_missing and all_requirements.exists():
            reception.status = LicenseReception.STATUS_APPROVED
            reception.save()

        receptions = LicenseReception.objects.select_related(
            'employee__person', 'license_type', 'received_by'
        ).prefetch_related('checked_items__requirement').all().order_by('-id')

        html_table = render_to_string(
            'licenses/partials/partial_reception_table.html',
            {'receptions': receptions},
            request=request
        )

        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': 'Registro de recepción guardado correctamente.',
            'html': html_table
        })


class LicenseReceptionToggleStatusView(LoginRequiredMixin, View):
    """Transiciones directas de Estado: Entregar a Acción de Personal o Dar de Baja."""

    def post(self, request, pk, *args, **kwargs):
        reception = get_object_or_404(LicenseReception, pk=pk)
        target_status = request.POST.get('status', '')

        if target_status == 'DELIVERED':
            reception.status = LicenseReception.STATUS_DELIVERED
            msg = f"La recepción #REC-{reception.id} ha sido remitida (Estado: Entregado)."
        elif target_status == 'CANCELLED':
            reception.status = LicenseReception.STATUS_CANCELLED
            msg = f"La recepción #REC-{reception.id} ha sido dada de baja."
        else:
            return JsonResponse({'success': False, 'message': 'Estado no válido.'}, status=400)

        reception.save()

        receptions = LicenseReception.objects.select_related(
            'employee__person', 'license_type', 'received_by'
        ).prefetch_related('checked_items__requirement').all().order_by('-id')

        html_table = render_to_string(
            'licenses/partials/partial_reception_table.html',
            {'receptions': receptions},
            request=request
        )

        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': msg,
            'html': html_table
        })


class LicenseReceptionCreateModalView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        employees = Employee.objects.select_related('person').filter(
            is_active=True
        ).order_by('person__last_name', 'person__first_name')
        license_types = MedicalLicenseType.objects.filter(is_active=True)
        html = render_to_string(
            'licenses/modals/modal_reception_form.html',
            {
                'employees': employees,
                'license_types': license_types
            },
            request=request
        )
        return JsonResponse({'success': True, 'html': html})


# ==========================================
# 4. GESTIÓN DE LICENCIAS MÉDICAS
# ==========================================

class MedicalLicenseListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = MedicalLicense
    template_name = 'licenses/license_list.html'
    context_object_name = 'licenses'
    paginate_by = 10
    permission_required = 'licenses.view_medicallicense'
    raise_exception = True

    def _is_global_admin(self):
        user = self.request.user
        return user.is_superuser or user.has_perm('licenses.can_admin')

    def get_queryset(self):
        qs = MedicalLicense.objects.select_related(
            'employee__person',
            'license_type',
            'personnel_action',
            'substitute_assignment__substitute_employee'
        ).prefetch_related('payroll_effects').filter(is_active=True)

        if not self._is_global_admin():
            user = self.request.user

            # Relaciones reales del modelo:
            reception_filter = (
                    Q(reception__delivered_to=user) |
                    Q(reception__received_by=user)
            )
            owner_filter = (
                    Q(created_by=user) |
                    Q(employee__person__user=user) |
                    Q(employee__person__document_number=user.username)
            )

            qs = qs.filter(reception_filter | owner_filter).distinct()

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(employee__person__first_name__icontains=q) |
                Q(employee__person__last_name__icontains=q) |
                Q(employee__person__document_number__icontains=q) |
                Q(medical_certificate_number__icontains=q) |
                Q(diagnosis__icontains=q)
            )

        license_type_id = self.request.GET.get('license_type', '').strip()
        if license_type_id:
            qs = qs.filter(license_type_id=license_type_id)

        legalized = self.request.GET.get('is_legalized', '').strip()
        if legalized in ['registered']:
            qs = qs.filter(personnel_action__is_registered=True)
        elif legalized in ['legalized', 'true', '1', 'True']:
            qs = qs.filter(
                Q(personnel_action__isnull=False, personnel_action__is_registered=False)
                | Q(
                    personnel_action__isnull=True,
                    status__in=[MedicalLicense.STATUS_VALIDATED, MedicalLicense.STATUS_ACTION_ISSUED],
                )
            )
        elif legalized in ['pending', 'pending_registered', 'false', '0', 'False']:
            qs = qs.filter(
                status__in=[MedicalLicense.STATUS_DRAFT, MedicalLicense.STATUS_SUBMITTED]
            )

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['license_types'] = MedicalLicenseType.objects.filter(is_active=True)
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_type'] = self.request.GET.get('license_type', '').strip()
        context['selected_legalized'] = self.request.GET.get('is_legalized', '').strip()

        for license_instance in context['licenses']:
            period = (
                ManagementPeriod.objects
                .select_related('contract_type__labor_regime')
                .filter(
                    employee=license_instance.employee,
                    start_date__lte=license_instance.start_date,
                )
                .order_by('-start_date')
                .first()
            )
            regime = period.contract_type.labor_regime if period and period.contract_type else None
            license_instance.labor_regime_display = regime.code if regime else 'N/D'
            license_instance.subsidy_total = sum(
                (effect.estimated_discount_amount for effect in license_instance.payroll_effects.all()),
                Decimal('0.00'),
            )

        active_qs = MedicalLicense.objects.filter(is_active=True)
        if not self._is_global_admin():
            user = self.request.user
            reception_filter = (
                    Q(reception__delivered_to=user) |
                    Q(reception__received_by=user)
            )
            owner_filter = (
                    Q(created_by=user) |
                    Q(employee__person__user=user) |
                    Q(employee__person__document_number=user.username)
            )
            active_qs = active_qs.filter(reception_filter | owner_filter).distinct()

        context['license_stats'] = {
            'total': active_qs.count(),
            'pending': active_qs.filter(
                status__in=[MedicalLicense.STATUS_DRAFT, MedicalLicense.STATUS_SUBMITTED]
            ).count(),
            'legalized': active_qs.filter(
                Q(personnel_action__isnull=False, personnel_action__is_registered=False)
                | Q(
                    personnel_action__isnull=True,
                    status__in=[MedicalLicense.STATUS_VALIDATED, MedicalLicense.STATUS_ACTION_ISSUED],
                )
            ).count(),
            'registered': active_qs.filter(personnel_action__is_registered=True).count(),
        }
        context['total_substitutes'] = active_qs.filter(substitute_assignment__isnull=False).count()
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'licenses/partials/partial_license_table.html',
                context,
                request=self.request
            )
            return JsonResponse({'success': True, 'html': html})
        return super().render_to_response(context, **response_kwargs)


class LicenseSubsidyReportModalView(LoginRequiredMixin, View):
    def get(self, request):
        html = render_to_string(
            'licenses/modals/modal_subsidy_report.html',
            {'current_month': timezone.now().date().strftime('%Y-%m')},
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseSubsidyReportExportView(LoginRequiredMixin, View):
    @transaction.atomic
    def post(self, request):
        period = (request.POST.get('period') or '').strip()
        try:
            year, month = (int(value) for value in period.split('-', 1))
            _cutoff_start, cutoff_end = _subsidy_cutoff(year, month)
        except (TypeError, ValueError):
            return JsonResponse(
                {'success': False, 'message': 'Seleccione un mes válido.'},
                status=400,
            )

        pending_effects = (
            Q(
                subsidy_reported=False,
                license__start_date__lte=cutoff_end,
                created_at__date__lte=cutoff_end,
                target_year__isnull=True,
                target_month__isnull=True,
                license_year__isnull=False,
                license_month__isnull=False,
            )
        )
        reported_effects = Q(
            subsidy_reported=True,
            target_year=year,
            target_month=month,
        )
        effects = list(
            LicensePayrollEffect.objects
            .select_for_update()
            .select_related(
                'license__employee__person',
                'license__personnel_action',
            )
            .filter(
                license__is_active=True,
                license__personnel_action__is_registered=True,
                labor_regime='CT',
            ).filter(
                Q(employer_covered_days__gt=0)
                | Q(days_to_discount__gt=0)
            ).filter(pending_effects | reported_effects)
        )
        if not effects:
            return JsonResponse(
                {'success': False, 'message': 'No existen subsidios pendientes para este corte.'},
                status=404,
            )

        rows = []
        calculated_at = timezone.now()
        for effect in effects:
            license_instance = effect.license
            if not effect.subsidy_reported:
                effect.estimated_discount_amount = _subsidy_amount(effect)
                effect.save(update_fields=['estimated_discount_amount'])
            person = license_instance.employee.person
            license_month = effect.license_month or license_instance.start_date.month
            license_year = effect.license_year or license_instance.start_date.year
            rows.append({
                'document': person.document_number or '',
                'name': f'{person.last_name} {person.first_name}'.strip(),
                'month': (
                    f'{LICENSE_MONTH_NAMES[license_month]} '
                    f'{license_year}'
                ),
                'days': effect.employer_covered_days + effect.days_to_discount,
                'amount': effect.estimated_discount_amount,
            })
            if not effect.subsidy_reported:
                LicensePayrollEffect.objects.filter(pk=effect.pk).update(
                    subsidy_reported=True,
                    subsidy_reported_at=calculated_at,
                    target_year=year,
                    target_month=month,
                )

        rows.sort(key=lambda row: (row['name'].lower(), row['month']))
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Subsidios'
        sheet.append([f'Reporte de Subsidios - Corte al {cutoff_end:%d/%m/%Y}'])
        sheet.append([
            'Cédula', 'Apellidos y nombres', 'Mes de licencia',
            'Días subsidio', 'Valor calculado'
        ])
        for row in rows:
            sheet.append([
                row['document'],
                row['name'],
                row['month'],
                row['days'],
                float(row['amount']),
            ])
        sheet.append([])
        sheet.append([
            '', 'TOTAL', '',
            sum(row['days'] for row in rows),
            float(sum((row['amount'] for row in rows), Decimal('0.00')))
        ])
        sheet.append([])
        sheet.append(['', f'Elaborado por: {request.user.get_full_name() or request.user.username}'])
        sheet.merge_cells('A1:E1')
        sheet['A1'].font = Font(bold=True, size=14)
        sheet['A1'].alignment = Alignment(horizontal='center')
        for cell in sheet[2]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='1F4E78')
        for cell in sheet['E'][2:]:
            cell.number_format = '$#,##0.00'
        for column, width in {'A': 16, 'B': 42, 'C': 18, 'D': 16, 'E': 18}.items():
            sheet.column_dimensions[column].width = width

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="Reporte_Subsidios_{year}_{month:02d}.xlsx"'
        )
        return response


class MedicalLicenseCreateView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        form = MedicalLicenseForm()
        html = render_to_string(
            'licenses/modals/modal_license_form.html',
            {'form': form},
            request=request
        )
        return JsonResponse({'success': True, 'html': html})

    def post(self, request, *args, **kwargs):
        form = MedicalLicenseForm(request.POST)
        if form.is_valid():
            license_instance = form.save(commit=False)
            if hasattr(request, 'user') and request.user.is_authenticated:
                license_instance.created_by = request.user
            license_instance.save()
            form.save(commit=True)

            licenses = MedicalLicense.objects.select_related(
                'employee__person',
                'license_type',
                'substitute_assignment__substitute_employee'
            ).filter(is_active=True)[:15]

            html_table = render_to_string(
                'licenses/partials/partial_license_table.html',
                {'licenses': licenses},
                request=request
            )

            return JsonResponse({
                'success': True,
                'status': 'success',
                'message': 'Licencia médica registrada correctamente.',
                'html': html_table
            })

        errors = {field: [str(err) for err in errs] for field, errs in form.errors.items()}
        return JsonResponse({
            'success': False,
            'status': 'error',
            'message': 'Existen inconsistencias en los campos ingresados.',
            'errors': errors
        }, status=400)


class MedicalLicenseActionModalView(LoginRequiredMixin, View):
    def get(self, request, pk):
        license_instance = get_object_or_404(
            MedicalLicense.objects.select_related('employee__person', 'license_type', 'personnel_action'),
            pk=pk, is_active=True,
            status__in=[
                MedicalLicense.STATUS_DRAFT,
                MedicalLicense.STATUS_SUBMITTED,
                MedicalLicense.STATUS_VALIDATED,
                MedicalLicense.STATUS_ACTION_ISSUED,
            ]
        )
        if not license_instance.personnel_action_id:
            action = create_draft_license_action(license_instance)
            license_instance.personnel_action = action
            license_instance.status = MedicalLicense.STATUS_ACTION_ISSUED
            license_instance.save(update_fields=['personnel_action', 'status', 'updated_at'])
            license_instance.refresh_from_db()
        action = license_instance.personnel_action
        _ensure_license_action_movement(action)
        action.authority_1 = license_instance.license_type.default_authority_1 or action.authority_1
        action.authority_2 = license_instance.license_type.default_authority_2
        action.reviewer = license_instance.license_type.default_reviewer
        action.register = license_instance.license_type.default_register
        action.save(update_fields=[
            'authority_1', 'authority_2', 'reviewer', 'register',
        ])
        form = LicensePersonnelActionForm(
            instance=action,
            license_instance=license_instance
        )
        html = render_to_string(
            'licenses/modals/modal_license_action.html',
            {'license': license_instance, 'form': form},
            request=request
        )
        return JsonResponse({'success': True, 'html': html})


class MedicalLicenseActionSaveView(LoginRequiredMixin, View):
    @transaction.atomic
    def post(self, request, pk):
        license_instance = get_object_or_404(
            MedicalLicense.objects.select_for_update().select_related('employee', 'license_type'),
            pk=pk, is_active=True
        )
        if license_instance.status not in [
            MedicalLicense.STATUS_DRAFT,
            MedicalLicense.STATUS_SUBMITTED,
            MedicalLicense.STATUS_VALIDATED,
            MedicalLicense.STATUS_ACTION_ISSUED,
        ]:
            return JsonResponse({'success': False, 'message': 'La licencia no puede generar una acción.'}, status=400)
        if not license_instance.personnel_action_id:
            action = create_draft_license_action(license_instance)
            license_instance.personnel_action = action
            license_instance.status = MedicalLicense.STATUS_ACTION_ISSUED
            license_instance.save(update_fields=['personnel_action', 'status', 'updated_at'])
            license_instance.refresh_from_db()
        action = license_instance.personnel_action
        form = LicensePersonnelActionForm(
            request.POST, instance=action,
            license_instance=license_instance
        )
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors, 'message': 'Revise los campos de la acción.'},
                                status=400)
        action = form.save(commit=False)
        action.authority_1 = license_instance.license_type.default_authority_1 or action.authority_1
        action.authority_2 = license_instance.license_type.default_authority_2
        action.reviewer = license_instance.license_type.default_reviewer
        action.register = license_instance.license_type.default_register
        action.save()
        _ensure_license_action_movement(action)
        license_instance.status = MedicalLicense.STATUS_ACTION_ISSUED
        license_instance.save(update_fields=['status', 'updated_at'])
        license_instance.start_date = form.cleaned_data['date_from']
        license_instance.end_date = form.cleaned_data['date_to']
        license_instance.updated_by = request.user
        license_instance.save(update_fields=['start_date', 'end_date', 'updated_by', 'updated_at', 'total_days'])

        mode = form.cleaned_data.get('schedule_mode')
        if mode and mode != 'FULL_DAY':
            LicenseSchedule.objects.update_or_create(
                license=license_instance,
                defaults={
                    'modality': LicenseSchedule.MODALITY_SHIFT_OVERRIDE if mode == 'CUSTOM' else mode if mode in {
                        LicenseSchedule.MODALITY_ENTRY_DELAY,
                        LicenseSchedule.MODALITY_EXIT_EARLY,
                        LicenseSchedule.MODALITY_LUNCH,
                    } else LicenseSchedule.MODALITY_REDUCTION_HOURS,
                    'custom_entry_time': form.cleaned_data.get('custom_entry_time'),
                    'custom_exit_time': form.cleaned_data.get('custom_exit_time'),
                    'reduction_hours': 2,
                    'is_biometric_exempt': True,
                }
            )
        else:
            LicenseSchedule.objects.filter(license=license_instance).delete()
        return JsonResponse({'success': True, 'message': 'Acción de personal actualizada correctamente.'})


class MedicalLicenseReturnReceptionView(LoginRequiredMixin, View):
    @transaction.atomic
    def post(self, request, pk):
        license_instance = get_object_or_404(MedicalLicense, pk=pk, is_active=True)
        return_observation = request.POST.get('return_observation', '').strip()
        if not return_observation:
            return JsonResponse({'success': False, 'message': 'Debe indicar el motivo de la devolución.'}, status=400)
        reception = license_instance.reception
        if not reception:
            return JsonResponse({'success': False, 'message': 'La licencia no tiene recepción de origen.'}, status=400)
        license_instance.status = MedicalLicense.STATUS_CANCELLED
        license_instance.is_active = False
        license_instance.updated_by = request.user
        license_instance.save(update_fields=['status', 'is_active', 'updated_by', 'updated_at'])
        reception.status = LicenseReception.STATUS_APPROVED
        reception.observations = (
                (reception.observations or '')
                + f'\n[DEVUELTA A RECEPCIÓN {timezone.now():%d/%m/%Y %H:%M}] '
                  f'Motivo: {return_observation}'
        )
        reception.save(update_fields=['status', 'observations'])
        return JsonResponse({'success': True, 'message': 'La licencia fue devuelta a recepción.'})


class MedicalLicenseReturnReceptionModalView(LoginRequiredMixin, View):
    def get(self, request, pk):
        license_instance = get_object_or_404(
            MedicalLicense.objects.select_related('employee__person', 'license_type', 'reception'),
            pk=pk, is_active=True
        )
        html = render_to_string(
            'licenses/modals/modal_return_reception.html',
            {'license': license_instance},
            request=request
        )
        return JsonResponse({'success': True, 'html': html})


def get_type_requirements_api(request, type_id):
    """Endpoint AJAX que devuelve los anexos configurados de un tipo de licencia."""
    license_type = get_object_or_404(MedicalLicenseType, pk=type_id)
    # Filtramos anexos activos ordenados por nombre
    requirements = list(
        license_type.requirements.filter(is_active=True).values('id', 'name', 'is_mandatory')
    )
    return JsonResponse({'success': True, 'requirements': requirements})


# ==========================================
# GESTIÓN Y VALIDACIÓN DE RECEPCIÓN
# ==========================================

class LicenseReceptionValidateModalView(LoginRequiredMixin, View):
    """Abre el modal para completar los anexos pendientes de una recepción en estado REGISTRADO."""

    def get(self, request, pk, *args, **kwargs):
        reception = get_object_or_404(
            LicenseReception.objects.select_related('employee__person', 'license_type'),
            pk=pk
        )
        # Obtenemos los checks que están desmarcados (is_checked=False)
        pending_checks = reception.checked_items.filter(is_checked=False).select_related('requirement')

        html = render_to_string(
            'licenses/modals/modal_validate_reception.html',
            {
                'reception': reception,
                'pending_checks': pending_checks
            },
            request=request
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseReceptionValidateSaveView(LoginRequiredMixin, View):
    """Guarda los requisitos recién entregados y actualiza a APROBADO si se completaron todos."""

    @transaction.atomic
    def post(self, request, pk, *args, **kwargs):
        reception = get_object_or_404(LicenseReception, pk=pk)
        newly_checked_ids = [int(i) for i in request.POST.getlist('pending_checked')]

        # Actualizamos los ítems marcados en el modal
        if newly_checked_ids:
            reception.checked_items.filter(id__in=newly_checked_ids).update(is_checked=True)

        # Verificamos si aún queda algún requisito (obligatorio o general) sin marcar
        has_pending = reception.checked_items.filter(is_checked=False).exists()
        if not has_pending:
            reception.status = LicenseReception.STATUS_APPROVED
            reception.save()

        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': 'Requisitos actualizados correctamente.'
        })


class LicenseReceptionDeliverModalView(LoginRequiredMixin, View):
    """Abre el modal para remitir el expediente (Estado APROBADO -> ENTREGADO)."""

    def get(self, request, pk, *args, **kwargs):
        reception = get_object_or_404(
            LicenseReception.objects.select_related('employee__person', 'license_type'),
            pk=pk
        )
        # Usuarios/Analistas receptores de Talento Humano
        users = _human_resources_users()

        html = render_to_string(
            'licenses/modals/modal_deliver_reception.html',
            {
                'reception': reception,
                'users': users
            },
            request=request
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseReceptionBulkDeliverModalView(LoginRequiredMixin, View):
    """Abre el modal para remitir varias recepciones aprobadas."""

    def get(self, request, *args, **kwargs):
        users = _human_resources_users()
        html = render_to_string(
            'licenses/modals/modal_bulk_deliver_reception.html',
            {'users': users},
            request=request
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseReceptionBulkDeliverSaveView(LoginRequiredMixin, View):
    """Remite en una sola operación las recepciones aprobadas seleccionadas."""

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        raw_ids = request.POST.get('reception_ids', '')
        reception_ids = [value for value in raw_ids.split(',') if value.isdigit()]
        delivered_to_id = request.POST.get('delivered_to')
        delivery_observation = request.POST.get('delivery_observation', '').strip()

        if not reception_ids:
            return JsonResponse({'success': False, 'message': 'Seleccione al menos una recepción.'}, status=400)
        if not delivered_to_id:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar el servidor destinatario.'}, status=400)

        dest_user = get_object_or_404(_human_resources_users(), pk=delivered_to_id)
        receptions = list(
            LicenseReception.objects.select_for_update().filter(
                pk__in=reception_ids,
                status=LicenseReception.STATUS_APPROVED
            )
        )
        if len(receptions) != len(set(reception_ids)):
            return JsonResponse({
                'success': False,
                'message': 'Solo se pueden remitir recepciones aprobadas.'
            }, status=400)

        obs_entry = (
            f"\n[ENTREGA {timezone.now().strftime('%d/%m/%Y %H:%M')}] "
            f"Entregado a: {dest_user.get_full_name()}. Obs: {delivery_observation}"
        )
        delivery_batch = uuid.uuid4()
        for reception in receptions:
            reception.status = LicenseReception.STATUS_DELIVERED
            reception.delivery_batch = delivery_batch
            reception.delivered_to = dest_user
            reception.observations = (reception.observations or '') + obs_entry
            reception.save(update_fields=['status', 'delivery_batch', 'delivered_to', 'observations'])
            _ensure_medical_license_from_reception(reception, request.user)

        report_url = reverse('licenses:reception_report')
        report_url += f'?batch={receptions[0].delivery_batch}&delivered_to={dest_user.id}'
        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': f'{len(receptions)} recepción(es) remitida(s) correctamente.',
            'pdf_url': report_url
        })


class LicenseReceptionDetailModalView(LoginRequiredMixin, View):
    """Muestra el detalle de una recepción entregada."""

    def get(self, request, pk, *args, **kwargs):
        reception = get_object_or_404(
            LicenseReception.objects.select_related(
                'employee__person', 'license_type'
            ).prefetch_related('checked_items__requirement'),
            pk=pk
        )
        html = render_to_string(
            'licenses/modals/modal_reception_detail.html',
            {'reception': reception},
            request=request
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseReceptionDeliverSaveView(LoginRequiredMixin, View):
    """Guarda la entrega, cambia el estado a ENTREGADO y retorna la URL para imprimir la acta PDF."""

    @transaction.atomic
    def post(self, request, pk, *args, **kwargs):
        reception = get_object_or_404(LicenseReception, pk=pk)
        delivered_to_id = request.POST.get('delivered_to')
        delivery_observation = request.POST.get('delivery_observation', '').strip()

        if not delivered_to_id:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar el servidor destinatario.'}, status=400)

        dest_user = get_object_or_404(_human_resources_users(), pk=delivered_to_id)

        reception.status = LicenseReception.STATUS_DELIVERED
        reception.delivery_batch = uuid.uuid4()
        reception.delivered_to = dest_user
        # Se guarda el destinatario y notas si existen en el modelo, o en la observación
        obs_entry = f"\n[ENTREGA {timezone.now().strftime('%d/%m/%Y %H:%M')}] Entregado a: {dest_user.get_full_name()}. Obs: {delivery_observation}"
        reception.observations = (reception.observations or '') + obs_entry
        reception.save()
        _ensure_medical_license_from_reception(reception, request.user)

        pdf_url = reverse('licenses:reception_report')
        pdf_url += f'?batch={reception.delivery_batch}&delivered_to={dest_user.id}'

        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': 'Expediente entregado correctamente.',
            'pdf_url': pdf_url
        })


class LicenseReceptionPdfReportView(LoginRequiredMixin, View):
    """Genera el PDF del Acta de Entrega Documental con firma de Entregué y Recibí Conforme."""

    def get(self, request, pk, *args, **kwargs):
        receptions = LicenseReception.objects.select_related(
            'employee__person', 'license_type', 'received_by'
        ).prefetch_related('checked_items__requirement').filter(pk=pk)
        receptions = list(receptions)
        for reception in receptions:
            reception.verified_attachments = ', '.join(
                check.requirement.name
                for check in reception.checked_items.all()
                if check.is_checked
            )

        html_string = render_to_string('licenses/reports/pdf_reception_delivery.html', {
            'receptions': receptions,
            'user': request.user,
            'delivered_to': User.objects.filter(
                pk=request.GET.get('delivered_to')
            ).first(),
            'current_date': timezone.now()
        })

        # Si usas weasyprint u otra librería de PDF estándar del sistema:
        try:
            from weasyprint import HTML
            pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Reporte_Recepciones_Entregadas.pdf"'
            return response
        except ImportError:
            # Renderizado directo como HTML imprimible si no se encuentra weasyprint compilado
            return HttpResponse(html_string)


class LicenseReceptionReportView(LoginRequiredMixin, View):
    """Genera el reporte consolidado de recepciones entregadas."""

    def get(self, request, *args, **kwargs):
        reception_ids = [value for value in request.GET.getlist('ids') if value.isdigit()]
        delivery_batch = request.GET.get('batch', '').strip()
        receptions = LicenseReception.objects.select_related(
            'employee__person', 'license_type', 'received_by'
        ).prefetch_related('checked_items__requirement').filter(
            status=LicenseReception.STATUS_DELIVERED
        )
        if reception_ids:
            receptions = receptions.filter(pk__in=reception_ids)
        elif delivery_batch:
            receptions = receptions.filter(delivery_batch=delivery_batch)
        if not request.GET.get('delivered_to') and delivery_batch:
            delivered_to = LicenseReception.objects.filter(
                delivery_batch=delivery_batch
            ).values_list('delivered_to', flat=True).first()
        else:
            delivered_to = request.GET.get('delivered_to')
        receptions = receptions.order_by('employee__person__last_name', 'employee__person__first_name')
        receptions = list(receptions)
        for reception in receptions:
            reception.verified_attachments = ', '.join(
                check.requirement.name
                for check in reception.checked_items.all()
                if check.is_checked
            )
        delivered_to = User.objects.filter(pk=delivered_to).first()
        html_string = render_to_string('licenses/reports/pdf_reception_delivery.html', {
            'receptions': receptions,
            'user': request.user,
            'delivered_to': delivered_to,
            'current_date': timezone.now()
        })
        try:
            from weasyprint import HTML
            pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf_file, content_type='application/pdf')
            response['Content-Disposition'] = 'inline; filename="Reporte_Recepciones_Entregadas.pdf"'
            return response
        except ImportError:
            return HttpResponse(html_string)
