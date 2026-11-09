from django.contrib.auth.mixins import LoginRequiredMixin
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
from datetime import datetime

# Importación desde otras apps raíz del sys.path
from employee.models import Employee
from core.models import User
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
    LicenseSchedule
)
from .services import apply_validation_effects


def _ensure_medical_license_from_reception(reception, user):
    """Create the management record once a physical reception is delivered."""
    if hasattr(reception, 'medical_license') and reception.medical_license:
        return reception.medical_license

    start_date = reception.license_start_date or reception.reception_date.date()
    end_date = reception.license_end_date or start_date
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


# ==========================================
# 1. GESTIÓN DE TIPOS DE LICENCIAS
# ==========================================

class LicenseTypeListView(LoginRequiredMixin, ListView):
    model = MedicalLicenseType
    template_name = 'licenses/type_list.html'
    context_object_name = 'types'
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
        context['stats'] = {
            'total': full_qs.count(),
            'registered': full_qs.filter(status=LicenseReception.STATUS_REGISTERED).count(),
            'approved': full_qs.filter(status=LicenseReception.STATUS_APPROVED).count(),
            'delivered': full_qs.filter(status=LicenseReception.STATUS_DELIVERED).count(),
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
        end_date_raw = request.POST.get('license_end_date')
        checked_req_ids = [int(i) for i in request.POST.getlist('requirements_checked')]

        employee = get_object_or_404(Employee, pk=employee_id)
        license_type = get_object_or_404(MedicalLicenseType, pk=license_type_id)
        try:
            license_start_date = datetime.strptime(start_date_raw, '%Y-%m-%d').date() if start_date_raw else None
            license_end_date = datetime.strptime(end_date_raw, '%Y-%m-%d').date() if end_date_raw else None
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Las fechas de la licencia no son válidas.'}, status=400)
        if license_start_date and license_end_date and license_end_date < license_start_date:
            return JsonResponse({'success': False, 'message': 'La fecha fin no puede ser anterior a la fecha inicio.'}, status=400)

        # 1. Crear cabecera inicial
        reception = LicenseReception.objects.create(
            employee=employee,
            license_type=license_type,
            received_by=request.user,
            license_start_date=license_start_date,
            license_end_date=license_end_date,
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
        employees = Employee.objects.select_related('person').filter(is_active=True)
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

class MedicalLicenseListView(LoginRequiredMixin, ListView):
    model = MedicalLicense
    template_name = 'licenses/license_list.html'
    context_object_name = 'licenses'
    paginate_by = 15

    def get_queryset(self):
        qs = MedicalLicense.objects.select_related(
            'employee__person',
            'license_type',
            'substitute_assignment__substitute_employee'
        ).filter(is_active=True)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(employee__first_name__icontains=q) |
                Q(employee__last_name__icontains=q) |
                Q(employee__identification_number__icontains=q) |
                Q(substitute_assignment__substitute_employee__first_name__icontains=q) |
                Q(substitute_assignment__substitute_employee__last_name__icontains=q) |
                Q(medical_certificate_number__icontains=q) |
                Q(diagnosis__icontains=q)
            )

        license_type_id = self.request.GET.get('license_type', '').strip()
        if license_type_id:
            qs = qs.filter(license_type_id=license_type_id)

        legalized = self.request.GET.get('is_legalized', '').strip()
        if legalized in ['true', '1', 'True']:
            qs = qs.filter(status__in=[MedicalLicense.STATUS_VALIDATED, MedicalLicense.STATUS_ACTION_ISSUED])
        elif legalized in ['false', '0', 'False']:
            qs = qs.filter(status__in=[MedicalLicense.STATUS_DRAFT, MedicalLicense.STATUS_SUBMITTED])

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['license_types'] = MedicalLicenseType.objects.filter(is_active=True)
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_type'] = self.request.GET.get('license_type', '').strip()
        context['selected_legalized'] = self.request.GET.get('is_legalized', '').strip()

        active_qs = MedicalLicense.objects.filter(is_active=True)
        context['total_licenses'] = active_qs.count()
        context['total_substitutes'] = active_qs.filter(substitute_assignment__isnull=False).count()
        context['total_legalized'] = active_qs.filter(
            status__in=[MedicalLicense.STATUS_VALIDATED, MedicalLicense.STATUS_ACTION_ISSUED]
        ).count()
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
            pk=pk, is_active=True, status__in=[MedicalLicense.STATUS_VALIDATED, MedicalLicense.STATUS_ACTION_ISSUED]
        )
        if not license_instance.personnel_action_id:
            apply_validation_effects(license_instance)
            license_instance.refresh_from_db()
        form = LicensePersonnelActionForm(
            instance=license_instance.personnel_action,
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
        if license_instance.status not in [MedicalLicense.STATUS_VALIDATED, MedicalLicense.STATUS_ACTION_ISSUED]:
            return JsonResponse({'success': False, 'message': 'La licencia debe estar convalidada.'}, status=400)
        if not license_instance.personnel_action_id:
            apply_validation_effects(license_instance)
            license_instance.refresh_from_db()
        form = LicensePersonnelActionForm(
            request.POST, instance=license_instance.personnel_action,
            license_instance=license_instance
        )
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors, 'message': 'Revise los campos de la acción.'}, status=400)
        action = form.save(commit=False)
        action.save()
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
        apply_validation_effects(license_instance)
        return JsonResponse({'success': True, 'message': 'Acción de personal actualizada correctamente.'})


class MedicalLicenseReturnReceptionView(LoginRequiredMixin, View):
    @transaction.atomic
    def post(self, request, pk):
        license_instance = get_object_or_404(MedicalLicense, pk=pk, is_active=True)
        reception = license_instance.reception
        if not reception:
            return JsonResponse({'success': False, 'message': 'La licencia no tiene recepción de origen.'}, status=400)
        license_instance.status = MedicalLicense.STATUS_CANCELLED
        license_instance.is_active = False
        license_instance.updated_by = request.user
        license_instance.save(update_fields=['status', 'is_active', 'updated_by', 'updated_at'])
        reception.status = LicenseReception.STATUS_APPROVED
        reception.observations = (reception.observations or '') + f'\n[DEVUELTA A RECEPCIÓN {timezone.now():%d/%m/%Y %H:%M}]'
        reception.save(update_fields=['status', 'observations'])
        return JsonResponse({'success': True, 'message': 'La licencia fue devuelta a recepción.'})


class MedicalLicenseLegalizeModalView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        try:
            license_instance = MedicalLicense.objects.select_related('employee').get(pk=pk, is_active=True)
        except MedicalLicense.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Licencia no encontrada.'}, status=404)

        html = render_to_string(
            'licenses/modals/modal_legalize_confirm.html',
            {'license': license_instance},
            request=request
        )
        return JsonResponse({'success': True, 'html': html})


class MedicalLicenseLegalizeView(LoginRequiredMixin, View):
    @transaction.atomic
    def post(self, request, pk, *args, **kwargs):
        try:
            license_instance = MedicalLicense.objects.get(pk=pk, is_active=True)
        except MedicalLicense.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Licencia médica no encontrada.'}, status=404)

        if license_instance.is_legalized:
            return JsonResponse({
                'success': False,
                'message': 'Esta licencia médica ya se encuentra legalizada.'
            }, status=400)

        license_instance.status = MedicalLicense.STATUS_VALIDATED
        license_instance.convalidation_date = timezone.now()
        if hasattr(request, 'user') and request.user.is_authenticated:
            license_instance.convalidated_by = request.user
            license_instance.updated_by = request.user
        license_instance.save()
        apply_validation_effects(license_instance)

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
            'message': 'La licencia médica ha sido convalidada exitosamente.',
            'html': html_table
        })


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
        users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')

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
        users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
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

        dest_user = get_object_or_404(User, pk=delivered_to_id, is_active=True)
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
        for reception in receptions:
            reception.status = LicenseReception.STATUS_DELIVERED
            reception.observations = (reception.observations or '') + obs_entry
            reception.save(update_fields=['status', 'observations'])
            _ensure_medical_license_from_reception(reception, request.user)

        report_url = reverse('licenses:reception_report')
        report_url += '?' + '&'.join(f'ids={reception.id}' for reception in receptions)
        report_url += f'&delivered_to={dest_user.id}'
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
            pk=pk,
            status=LicenseReception.STATUS_DELIVERED
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

        dest_user = get_object_or_404(User, pk=delivered_to_id)

        reception.status = LicenseReception.STATUS_DELIVERED
        # Se guarda el destinatario y notas si existen en el modelo, o en la observación
        obs_entry = f"\n[ENTREGA {timezone.now().strftime('%d/%m/%Y %H:%M')}] Entregado a: {dest_user.get_full_name()}. Obs: {delivery_observation}"
        reception.observations = (reception.observations or '') + obs_entry
        reception.save()
        _ensure_medical_license_from_reception(reception, request.user)

        pdf_url = reverse('licenses:reception_pdf_report', kwargs={'pk': reception.pk})
        pdf_url += f'?delivered_to={dest_user.id}'

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
        receptions = LicenseReception.objects.select_related(
            'employee__person', 'license_type', 'received_by'
        ).prefetch_related('checked_items__requirement').filter(
            status=LicenseReception.STATUS_DELIVERED
        )
        if reception_ids:
            receptions = receptions.filter(pk__in=reception_ids)
        receptions = receptions.order_by('employee__person__last_name', 'employee__person__first_name')
        delivered_to = User.objects.filter(pk=request.GET.get('delivered_to')).first()
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
