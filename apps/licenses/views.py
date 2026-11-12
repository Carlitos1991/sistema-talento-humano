from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from contract.models import ManagementPeriod
from core.models import User
from employee.models import Employee
from .forms import (
    LicensePersonnelActionForm,
    LicenseReceptionForm,
    LicenseTypeForm,
    LicenseTypeRequirementForm,
    MedicalLicenseForm,
)
from .models import (
    LicenseReception,
    MedicalLicense,
    MedicalLicenseType,
)
from .services import (
    create_license_reception,
    deliver_receptions_batch,
    generate_subsidy_excel_report,
    get_human_resources_users,
    get_reception_statistics,
    prepare_license_action_modal,
    render_reception_delivery_document,
    return_license_to_reception,
    save_license_personnel_action,
    validate_reception_requirements,
)


# ==========================================
# 1. LICENSE TYPES MANAGEMENT
# ==========================================

class LicenseTypeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
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
            'default_register',
        )
        query = self.request.GET.get('q', '').strip()
        show_inactive = self.request.GET.get('show_inactive') == 'true'

        qs = qs.filter(is_active=not show_inactive)
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query))
        return qs.order_by('name')

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html_table = render_to_string(
                'licenses/partials/partial_type_table.html', context, request=self.request
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


class LicenseTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = MedicalLicenseType
    form_class = LicenseTypeForm
    template_name = 'licenses/modals/modal_type_form.html'
    success_url = reverse_lazy('licenses:type_list')
    permission_required = 'licenses.add_medicallicensetype'
    raise_exception = True

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
                'message': f'Tipo de Licencia "{self.object.name}" creado correctamente.',
            })
        return redirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor corrija los errores en el formulario.',
                'errors': errors_data,
            }, status=400)
        return super().form_invalid(form)


class LicenseTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = MedicalLicenseType
    form_class = LicenseTypeForm
    template_name = 'licenses/modals/modal_type_form.html'
    success_url = reverse_lazy('licenses:type_list')
    permission_required = 'licenses.change_medicallicensetype'
    raise_exception = True

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
                'message': f'Tipo de Licencia "{self.object.name}" actualizado correctamente.',
            })
        return redirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors_data = {field: errors[0] for field, errors in form.errors.items()}
            return JsonResponse({
                'status': 'error',
                'success': False,
                'message': 'Por favor corrija los errores en el formulario.',
                'errors': errors_data,
            }, status=400)
        return super().form_invalid(form)


# ==========================================
# 2. REQUIREMENTS QUICK CREATION
# ==========================================

class RequirementCreateModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.add_licensetyperequirement'
    raise_exception = True

    def get(self, request, *args, **kwargs):
        form = LicenseTypeRequirementForm()
        html = render_to_string(
            'licenses/modals/modal_requirement_form.html', {'form': form}, request=request
        )
        return JsonResponse({'success': True, 'html': html})


class RequirementSaveAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.add_licensetyperequirement'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        form = LicenseTypeRequirementForm(request.POST)
        if form.is_valid():
            req_obj = form.save()
            return JsonResponse({
                'success': True,
                'status': 'success',
                'message': 'Requisito creado correctamente.',
                'requirement': {'id': req_obj.id, 'name': req_obj.name},
            })
        errors = {field: [str(err) for err in errs] for field, errs in form.errors.items()}
        return JsonResponse({'success': False, 'status': 'error', 'errors': errors}, status=400)


class LicenseTypeRequirementsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.view_medicallicensetype'
    raise_exception = True

    def get(self, request, type_id, *args, **kwargs):
        license_type = get_object_or_404(MedicalLicenseType, pk=type_id)
        requirements = list(
            license_type.requirements.filter(is_active=True).values('id', 'name', 'is_mandatory')
        )
        return JsonResponse({'success': True, 'requirements': requirements})


# ==========================================
# 3. DOCUMENT RECEPTION & INSPECTION
# ==========================================

class LicenseReceptionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LicenseReception
    template_name = 'licenses/reception_list.html'
    permission_required = 'licenses.view_licensereception'
    raise_exception = True
    context_object_name = 'receptions'
    paginate_by = 10

    def get_queryset(self):
        qs = LicenseReception.objects.select_related(
            'employee__person', 'license_type', 'received_by'
        ).prefetch_related('checked_items__requirement')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(employee__person__first_name__icontains=q)
                | Q(employee__person__last_name__icontains=q)
                | Q(employee__person__document_number__icontains=q)
            )

        status = self.request.GET.get('status', '').strip()
        if status == LicenseReception.STATUS_CANCELLED:
            qs = qs.filter(status=status)
        elif status and status != 'all':
            qs = qs.filter(status=status).exclude(status=LicenseReception.STATUS_CANCELLED)
        else:
            qs = qs.exclude(status=LicenseReception.STATUS_CANCELLED)

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
        context['stats'] = get_reception_statistics()
        context['license_types'] = MedicalLicenseType.objects.filter(is_active=True)
        context['reception_statuses'] = LicenseReception.STATUS_CHOICES
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html_table = render_to_string(
                'licenses/partials/partial_reception_table.html', context, request=self.request
            )
            return JsonResponse({
                'success': True,
                'html': html_table,
                'stats': context.get('stats', {}),
            })
        return super().render_to_response(context, **response_kwargs)


class LicenseReceptionCreateModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.add_licensereception'
    raise_exception = True

    def get(self, request, *args, **kwargs):
        employees = Employee.objects.select_related('person').filter(
            is_active=True
        ).order_by('person__last_name', 'person__first_name')
        license_types = MedicalLicenseType.objects.filter(is_active=True)
        html = render_to_string(
            'licenses/modals/modal_reception_form.html',
            {'employees': employees, 'license_types': license_types},
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseReceptionSaveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.add_licensereception'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        form = LicenseReceptionForm(request.POST)
        if not form.is_valid():
            errors = {field: errs[0] for field, errs in form.errors.items()}
            return JsonResponse({
                'success': False,
                'message': 'Complete todos los campos obligatorios marcados con *.',
                'errors': errors,
            }, status=400)

        payload = {
            'employee_id': form.cleaned_data['employee'],
            'license_type_id': form.cleaned_data['license_type'],
            'license_start_date': form.cleaned_data['license_start_date'],
            'license_days': form.cleaned_data['license_days'],
            'supporting_document': form.cleaned_data['supporting_document'].strip(),
            'observations': form.cleaned_data.get('observations', ''),
            'checked_req_ids': [int(i) for i in request.POST.getlist('requirements_checked') if i.isdigit()],
        }

        with transaction.atomic():
            recent_threshold = timezone.now() - timedelta(seconds=10)
            duplicate_exists = LicenseReception.objects.select_for_update().filter(
                employee_id=payload['employee_id'],
                license_type_id=payload['license_type_id'],
                license_start_date=payload['license_start_date'],
                reception_date__gte=recent_threshold,
            ).exclude(status=LicenseReception.STATUS_CANCELLED).exists()

            if not duplicate_exists:
                create_license_reception(payload, request.user)

        receptions = (
            LicenseReception.objects.select_related('employee__person', 'license_type', 'received_by')
            .prefetch_related('checked_items__requirement')
            .exclude(status=LicenseReception.STATUS_CANCELLED)
            .order_by('-id')[:10]
        )
        html_table = render_to_string(
            'licenses/partials/partial_reception_table.html',
            {'receptions': receptions},
            request=request,
        )
        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': 'Registro de recepción guardado correctamente.',
            'html': html_table,
            'stats': get_reception_statistics(),
        })


class LicenseReceptionToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_licensereception'
    raise_exception = True

    def post(self, request, pk, *args, **kwargs):
        reception = get_object_or_404(LicenseReception, pk=pk)
        target_status = request.POST.get('status', '')

        if target_status == LicenseReception.STATUS_DELIVERED:
            reception.status = LicenseReception.STATUS_DELIVERED
            msg = f'La recepción #REC-{reception.id} ha sido remitida (Estado: Entregado).'
        elif target_status == LicenseReception.STATUS_CANCELLED:
            reception.status = LicenseReception.STATUS_CANCELLED
            msg = f'La recepción #REC-{reception.id} ha sido dada de baja.'
        else:
            return JsonResponse({'success': False, 'message': 'Estado no válido.'}, status=400)

        reception.save(update_fields=['status'])
        receptions = (
            LicenseReception.objects.select_related('employee__person', 'license_type', 'received_by')
            .prefetch_related('checked_items__requirement')
            .exclude(status=LicenseReception.STATUS_CANCELLED)
            .order_by('-id')[:10]
        )
        html_table = render_to_string(
            'licenses/partials/partial_reception_table.html',
            {'receptions': receptions},
            request=request,
        )
        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': msg,
            'html': html_table,
            'stats': get_reception_statistics(),
        })


class LicenseReceptionValidateModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_licensereception'
    raise_exception = True

    def get(self, request, pk, *args, **kwargs):
        reception = get_object_or_404(
            LicenseReception.objects.select_related('employee__person', 'license_type'), pk=pk
        )
        pending_checks = reception.checked_items.filter(is_checked=False).select_related('requirement')
        html = render_to_string(
            'licenses/modals/modal_validate_reception.html',
            {'reception': reception, 'pending_checks': pending_checks},
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseReceptionValidateSaveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_licensereception'
    raise_exception = True

    def post(self, request, pk, *args, **kwargs):
        newly_checked_ids = [int(i) for i in request.POST.getlist('pending_checked') if i.isdigit()]
        validate_reception_requirements(pk, newly_checked_ids)
        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': 'Requisitos actualizados correctamente.',
            'stats': get_reception_statistics(),
        })


class LicenseReceptionDeliverModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_licensereception'
    raise_exception = True

    def get(self, request, pk, *args, **kwargs):
        reception = get_object_or_404(
            LicenseReception.objects.select_related('employee__person', 'license_type'), pk=pk
        )
        html = render_to_string(
            'licenses/modals/modal_deliver_reception.html',
            {'reception': reception, 'users': get_human_resources_users()},
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseReceptionDeliverSaveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_licensereception'
    raise_exception = True

    def post(self, request, pk, *args, **kwargs):
        delivered_to_id = request.POST.get('delivered_to')
        observation = request.POST.get('delivery_observation', '').strip()
        if not delivered_to_id:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar el servidor destinatario.'}, status=400)

        try:
            batch_uuid, dest_user, _ = deliver_receptions_batch(
                [str(pk)], delivered_to_id, observation, request.user
            )
        except ValueError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=400)

        pdf_url = f"{reverse('licenses:reception_report')}?batch={batch_uuid}&delivered_to={dest_user.id}"
        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': 'Expediente entregado correctamente.',
            'pdf_url': pdf_url,
        })


class LicenseReceptionBulkDeliverModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_licensereception'
    raise_exception = True

    def get(self, request, *args, **kwargs):
        html = render_to_string(
            'licenses/modals/modal_bulk_deliver_reception.html',
            {'users': get_human_resources_users()},
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseReceptionBulkDeliverSaveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_licensereception'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        raw_ids = request.POST.get('reception_ids', '')
        reception_ids = [val for val in raw_ids.split(',') if val.isdigit()]
        delivered_to_id = request.POST.get('delivered_to')
        observation = request.POST.get('delivery_observation', '').strip()

        if not reception_ids:
            return JsonResponse({'success': False, 'message': 'Seleccione al menos una recepción.'}, status=400)
        if not delivered_to_id:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar el servidor destinatario.'}, status=400)

        try:
            batch_uuid, dest_user, count = deliver_receptions_batch(
                reception_ids, delivered_to_id, observation, request.user
            )
        except ValueError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=400)

        report_url = f"{reverse('licenses:reception_report')}?batch={batch_uuid}&delivered_to={dest_user.id}"
        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': f'{count} recepción(es) remitida(s) correctamente.',
            'pdf_url': report_url,
        })


class LicenseReceptionDetailModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.view_licensereception'
    raise_exception = True

    def get(self, request, pk, *args, **kwargs):
        reception = get_object_or_404(
            LicenseReception.objects.select_related('employee__person', 'license_type')
            .prefetch_related('checked_items__requirement'),
            pk=pk,
        )
        html = render_to_string(
            'licenses/modals/modal_reception_detail.html',
            {'reception': reception},
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseReceptionPdfReportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.view_licensereception'
    raise_exception = True

    def get(self, request, pk, *args, **kwargs):
        receptions = (
            LicenseReception.objects.select_related('employee__person', 'license_type', 'received_by')
            .prefetch_related('checked_items__requirement')
            .filter(pk=pk)
        )
        delivered_to = User.objects.filter(pk=request.GET.get('delivered_to')).first()
        content, content_type = render_reception_delivery_document(
            receptions, request.user, delivered_to, request.build_absolute_uri('/')
        )
        response = HttpResponse(content, content_type=content_type)
        if content_type == 'application/pdf':
            response['Content-Disposition'] = 'inline; filename="Reporte_Recepcion.pdf"'
        return response


class LicenseReceptionReportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.view_licensereception'
    raise_exception = True

    def get(self, request, *args, **kwargs):
        reception_ids = [val for val in request.GET.getlist('ids') if val.isdigit()]
        delivery_batch = request.GET.get('batch', '').strip()

        receptions = (
            LicenseReception.objects.select_related('employee__person', 'license_type', 'received_by')
            .prefetch_related('checked_items__requirement')
            .filter(status=LicenseReception.STATUS_DELIVERED)
        )
        if reception_ids:
            receptions = receptions.filter(pk__in=reception_ids)
        elif delivery_batch:
            receptions = receptions.filter(delivery_batch=delivery_batch)

        delivered_to_id = request.GET.get('delivered_to')
        if not delivered_to_id and delivery_batch:
            delivered_to_id = (
                LicenseReception.objects.filter(delivery_batch=delivery_batch)
                .values_list('delivered_to', flat=True)
                .first()
            )

        receptions = receptions.order_by('employee__person__last_name', 'employee__person__first_name')
        delivered_to = User.objects.filter(pk=delivered_to_id).first()

        content, content_type = render_reception_delivery_document(
            receptions, request.user, delivered_to, request.build_absolute_uri('/')
        )
        response = HttpResponse(content, content_type=content_type)
        if content_type == 'application/pdf':
            response['Content-Disposition'] = 'inline; filename="Reporte_Recepciones_Entregadas.pdf"'
        return response


# ==========================================
# 4. MEDICAL LICENSES MANAGEMENT
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

    def _apply_user_scope(self, qs):
        if self._is_global_admin():
            return qs
        user = self.request.user
        scope_filter = (
                Q(reception__delivered_to=user)
                | Q(reception__received_by=user)
                | Q(created_by=user)
                | Q(employee__person__user=user)
                | Q(employee__person__document_number=user.username)
        )
        return qs.filter(scope_filter).distinct()

    def get_queryset(self):
        qs = (
            MedicalLicense.objects.select_related(
                'employee__person',
                'license_type',
                'personnel_action',
                'substitute_assignment__substitute_employee',
            )
            .prefetch_related('payroll_effects')
            .filter(is_active=True)
        )
        qs = self._apply_user_scope(qs)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(employee__person__first_name__icontains=q)
                | Q(employee__person__last_name__icontains=q)
                | Q(employee__person__document_number__icontains=q)
                | Q(medical_certificate_number__icontains=q)
                | Q(diagnosis__icontains=q)
            )

        license_type_id = self.request.GET.get('license_type', '').strip()
        if license_type_id:
            qs = qs.filter(license_type_id=license_type_id)

        legalized = self.request.GET.get('is_legalized', '').strip()
        if legalized == 'registered':
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
            qs = qs.filter(status__in=[MedicalLicense.STATUS_DRAFT, MedicalLicense.STATUS_SUBMITTED])

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['license_types'] = MedicalLicenseType.objects.filter(is_active=True)
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_type'] = self.request.GET.get('license_type', '').strip()
        context['selected_legalized'] = self.request.GET.get('is_legalized', '').strip()

        for license_instance in context['licenses']:
            period = (
                ManagementPeriod.objects.select_related('contract_type__labor_regime')
                .filter(employee=license_instance.employee, start_date__lte=license_instance.start_date)
                .order_by('-start_date')
                .first()
            )
            regime = period.contract_type.labor_regime if period and period.contract_type else None
            license_instance.labor_regime_display = regime.code if regime else 'N/D'
            license_instance.subsidy_total = sum(
                (effect.estimated_discount_amount for effect in license_instance.payroll_effects.all()),
                Decimal('0.00'),
            )

        active_qs = self._apply_user_scope(MedicalLicense.objects.filter(is_active=True))
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
                'licenses/partials/partial_license_table.html', context, request=self.request
            )
            return JsonResponse({'success': True, 'html': html})
        return super().render_to_response(context, **response_kwargs)


class MedicalLicenseCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.add_medicallicense'
    raise_exception = True

    def get(self, request, *args, **kwargs):
        form = MedicalLicenseForm()
        html = render_to_string(
            'licenses/modals/modal_license_form.html', {'form': form}, request=request
        )
        return JsonResponse({'success': True, 'html': html})

    def post(self, request, *args, **kwargs):
        form = MedicalLicenseForm(request.POST)
        if form.is_valid():
            license_instance = form.save(commit=False)
            license_instance.created_by = request.user
            license_instance.save()
            form.save(commit=True)

            licenses = MedicalLicense.objects.select_related(
                'employee__person', 'license_type', 'substitute_assignment__substitute_employee'
            ).filter(is_active=True)[:10]

            html_table = render_to_string(
                'licenses/partials/partial_license_table.html',
                {'licenses': licenses},
                request=request,
            )
            return JsonResponse({
                'success': True,
                'status': 'success',
                'message': 'Licencia médica registrada correctamente.',
                'html': html_table,
            })

        errors = {field: [str(err) for err in errs] for field, errs in form.errors.items()}
        return JsonResponse({
            'success': False,
            'status': 'error',
            'message': 'Existen inconsistencias en los campos ingresados.',
            'errors': errors,
        }, status=400)


class MedicalLicenseActionModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_medicallicense'
    raise_exception = True

    def get(self, request, pk):
        license_instance, action = prepare_license_action_modal(pk, actor_user=request.user)
        form = LicensePersonnelActionForm(instance=action, license_instance=license_instance)
        html = render_to_string(
            'licenses/modals/modal_license_action.html',
            {'license': license_instance, 'form': form},
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})


class MedicalLicenseActionSaveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_medicallicense'
    raise_exception = True

    def post(self, request, pk):
        license_instance, action = prepare_license_action_modal(pk, actor_user=request.user)
        form = LicensePersonnelActionForm(
            request.POST, instance=action, license_instance=license_instance
        )
        if not form.is_valid():
            return JsonResponse(
                {'success': False, 'errors': form.errors, 'message': 'Revise los campos de la acción.'},
                status=400,
            )
        save_license_personnel_action(license_instance, form, request.user)
        return JsonResponse({'success': True, 'message': 'Acción de personal actualizada correctamente.'})


class MedicalLicenseReturnReceptionModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_medicallicense'
    raise_exception = True

    def get(self, request, pk):
        license_instance = get_object_or_404(
            MedicalLicense.objects.select_related('employee__person', 'license_type', 'reception'),
            pk=pk,
            is_active=True,
        )
        html = render_to_string(
            'licenses/modals/modal_return_reception.html',
            {'license': license_instance},
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})


class MedicalLicenseReturnReceptionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.change_medicallicense'
    raise_exception = True

    def post(self, request, pk):
        reason = request.POST.get('return_observation', '').strip()
        if not reason:
            return JsonResponse({'success': False, 'message': 'Debe indicar el motivo de la devolución.'}, status=400)
        try:
            return_license_to_reception(pk, reason, request.user)
        except ValueError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=400)

        return JsonResponse({'success': True, 'message': 'La licencia fue devuelta a recepción.'})


class LicenseSubsidyReportModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.view_medicallicense'
    raise_exception = True

    def get(self, request):
        html = render_to_string(
            'licenses/modals/modal_subsidy_report.html',
            {'current_month': timezone.now().date().strftime('%Y-%m')},
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})


class LicenseSubsidyReportExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'licenses.view_medicallicense'
    raise_exception = True

    def post(self, request):
        period = (request.POST.get('period') or '').strip()
        try:
            year, month = (int(value) for value in period.split('-', 1))
            if not (1 <= month <= 12):
                raise ValueError
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': 'Seleccione un mes válido.'}, status=400)

        try:
            excel_bytes = generate_subsidy_excel_report(year, month, request.user)
        except LookupError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=404)

        response = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="Reporte_Subsidios_{year}_{month:02d}.xlsx"'
        )
        return response
