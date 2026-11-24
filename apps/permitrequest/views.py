import json
import logging
import re

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from employee.models import Employee
from institution.models import AdministrativeUnit
from .forms import PermitTypeForm
from .models import PermitRequest, PermitType
from .services import (
    BinnacleService,
    PermitQueryService,
    PermitSecurityService,
    PermitWorkflowService,
    build_approved_permits_summary,
)

logger = logging.getLogger(__name__)


class AjaxPartialResponseMixin:
    """Renders partial HTML inside a JSON response for AJAX list filtering."""
    partial_template_name = None

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)
            return JsonResponse({'success': True, 'html': html})
        return super().render_to_response(context, **response_kwargs)


class PermitTypeListView(LoginRequiredMixin, PermissionRequiredMixin, AjaxPartialResponseMixin, ListView):
    model = PermitType
    template_name = 'permissions/permissions_type_list.html'
    partial_template_name = 'permissions/partials/partial_permissions_type_list.html'
    context_object_name = 'types'
    permission_required = 'permitrequest.view_permittype'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().filter(parent__isnull=True)
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(name__icontains=query) | queryset.filter(description__icontains=query)
        return queryset.order_by('name')


class PermitTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'permissions/modals/modal_permissions_type_form.html'
    success_url = reverse_lazy('permissions:permit_type_list')
    permission_required = 'permitrequest.add_permittype'

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.template_name, self.get_context_data(form=form), request=request)
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Tipo de permiso creado correctamente.'})
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class PermitTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'permissions/modals/modal_permissions_type_form.html'
    success_url = reverse_lazy('permissions:permit_type_list')
    permission_required = 'permitrequest.change_permittype'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.template_name, self.get_context_data(form=form), request=request)
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Tipo de permiso actualizado correctamente.'})
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class PermitTypeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = PermitType
    success_url = reverse_lazy('permissions:permit_type_list')
    permission_required = 'permitrequest.delete_permittype'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Tipo de permiso eliminado correctamente.'})
        return super().delete(request, *args, **kwargs)


class PermitTypeToggleView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.change_permittype'

    def post(self, request, pk):
        permit_type = get_object_or_404(PermitType, pk=pk)
        permit_type.is_active = not permit_type.is_active
        permit_type.save(update_fields=['is_active'])
        status_label = 'activado' if permit_type.is_active else 'desactivado'
        return JsonResponse({
            'success': True,
            'message': f'Tipo de permiso "{permit_type.name}" {status_label} correctamente.'
        })


class PermitTypeSubItemsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.view_permittype'

    def get(self, request, pk):
        parent = get_object_or_404(PermitType, pk=pk)
        items = PermitType.objects.filter(parent=parent).order_by('name')
        html = render_to_string(
            'permissions/modals/modal_permissions_subtype_list.html',
            {'parent': parent, 'items': items},
            request=request
        )
        return HttpResponse(html)


@login_required
@permission_required('permitrequest.view_permittype', raise_exception=True)
@require_GET
def permit_type_detail_options(request, pk):
    """Returns configuration flags for dynamic Select2/form validation in server-rendered forms."""
    permit_type = get_object_or_404(PermitType, pk=pk)
    return JsonResponse({
        'id': permit_type.id,
        'name': permit_type.name,
        'affects_vacation': permit_type.affects_vacation,
        'requires_attachment': permit_type.requires_attachment,
        'needs_justification': permit_type.needs_justification,
    })


@login_required
@permission_required('permitrequest.view_permittype', raise_exception=True)
@require_GET
def permit_subtype_options(request, parent_id):
    """Returns active child options for cascading Select2 dropdowns."""
    subtypes = PermitType.objects.filter(
        parent_id=parent_id,
        is_active=True
    ).values('id', 'name', 'needs_justification', 'requires_attachment')
    return JsonResponse({'success': True, 'subtypes': list(subtypes)})


class EmployeePermitListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Employee
    template_name = 'permissions/employee_permit_list.html'
    context_object_name = 'employees'
    permission_required = 'permitrequest.view_permitrequest'
    paginate_by = 10

    def get_queryset(self):
        queryset = Employee.objects.filter(is_active=True).select_related('person', 'area', 'employment_status')
        query = self.request.GET.get('q', '').strip()
        if query:
            for token in [t for t in query.split() if t]:
                queryset = queryset.filter(
                    person__first_name__icontains=token
                ) | queryset.filter(
                    person__last_name__icontains=token
                ) | queryset.filter(
                    person__document_number__icontains=token
                )
        return queryset.order_by('person__last_name', 'person__first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employees_data'] = PermitQueryService.attach_active_budgets(context['employees'])
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('permissions/partials/partial_employee_list.html', context, request=self.request)
            page_obj = context.get('page_obj')
            pagination = {
                'start_index': page_obj.start_index() if page_obj else 0,
                'end_index': page_obj.end_index() if page_obj else 0,
                'total_count': page_obj.paginator.count if page_obj else 0,
                'current_page': page_obj.number if page_obj else 1,
                'total_pages': page_obj.paginator.num_pages if page_obj else 1,
                'has_previous': page_obj.has_previous() if page_obj else False,
                'has_next': page_obj.has_next() if page_obj else False,
            }
            return JsonResponse({'success': True, 'html': html, 'pagination': pagination})
        return super().render_to_response(context, **response_kwargs)


class EmployeePermitHistoryView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.view_permitrequest'

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)
        permits = PermitRequest.objects.filter(
            employee=employee
        ).exclude(status__in=['CANCELED', 'INACTIVE']).select_related('permit_type').order_by('-start_date')

        html = render_to_string(
            'permissions/modals/modal_employee_permit_history.html',
            {'employee': employee, 'permits': permits},
            request=request
        )
        return HttpResponse(html)


class GeneratePermitFormView(LoginRequiredMixin, View):
    def get(self, request):
        employee_id = re.sub(r'[^0-9]', '', str(request.GET.get('employee') or ''))
        if not employee_id:
            return JsonResponse({'success': False, 'message': 'ID de empleado inválido.'}, status=400)

        employee = get_object_or_404(Employee, pk=int(employee_id))
        if not PermitSecurityService.can_generate_for_employee(request.user, employee):
            raise PermissionDenied('No tiene permisos para generar permisos.')

        parent_types = PermitType.objects.filter(is_active=True, parent__isnull=True).order_by('name')
        html = render_to_string(
            'permissions/modals/modal_generate_permit_form.html',
            {'employee': employee, 'parent_types': parent_types},
            request=request
        )
        return HttpResponse(html)

    def post(self, request):
        employee_id = re.sub(r'[^0-9]', '', str(request.POST.get('employee') or ''))
        if not employee_id:
            return JsonResponse({'success': False, 'message': 'ID de empleado inválido.'}, status=400)

        employee = get_object_or_404(Employee, pk=int(employee_id))
        if not PermitSecurityService.can_generate_for_employee(request.user, employee):
            raise PermissionDenied('No tiene permisos para generar permisos.')

        try:
            PermitWorkflowService.create_permit_request(request.user, employee, request.POST, request.FILES)
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Permiso generado correctamente.'})
            return redirect('permissions:permit_employee_list')
        except ValidationError as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            return JsonResponse({'success': False, 'message': msg}, status=400)


class PermitAdminListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PermitRequest
    template_name = 'permissions/permit_list.html'
    partial_template_name = 'permissions/partials/partial_permit_table.html'
    context_object_name = 'permits'
    permission_required = 'permitrequest.view_permitrequest'
    paginate_by = 10

    def get_queryset(self):
        return PermitQueryService.get_filtered_admin_permits(
            self.request.GET,
            self.request.session.get('permit_document_numbers', [])
        )

    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('export') == 'true':
            html = render_to_string(self.partial_template_name, {'permits': self.get_queryset()}, request=request)
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)
            page_obj = context.get('page_obj')
            paginator = context.get('paginator')
            pagination = {
                'start_index': page_obj.start_index() if page_obj and paginator and paginator.count else 0,
                'end_index': page_obj.end_index() if page_obj and paginator and paginator.count else 0,
                'total_count': paginator.count if paginator else 0,
                'page': page_obj.number if page_obj else 1,
                'total_pages': paginator.num_pages if paginator else 1,
                'has_previous': bool(page_obj and page_obj.has_previous()),
                'has_next': bool(page_obj and page_obj.has_next()),
            }
            return JsonResponse({
                'success': True,
                'html': html,
                'pagination': pagination,
                'summary': context.get('summary', {}),  # <-- AGREGAR ESTO
            })
        return super().render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        default_from, default_to = PermitQueryService.get_current_month_bounds()
        context['summary'] = build_approved_permits_summary(self.object_list)
        context['summary_json'] = json.dumps(context['summary'])

        context['areas'] = AdministrativeUnit.objects.filter(is_active=True).order_by('name')
        context['permit_types'] = PermitType.objects.filter(parent__isnull=True, is_active=True).order_by('name')
        context['permit_subtypes'] = PermitType.objects.filter(
            is_active=True, parent__isnull=False
        ).select_related('parent').order_by('parent__name', 'name')
        context['status_choices'] = PermitRequest.STATUS_CHOICES

        context['current_filters'] = {
            'q': (self.request.GET.get('q') or '').strip(),
            'area': (self.request.GET.get('area') or '').strip(),
            'permit_type': (self.request.GET.get('permit_type') or '').strip(),
            'permit_subtype': (self.request.GET.get('permit_subtype') or '').strip(),
            'status': (self.request.GET.get('status') or '').strip(),
            'date_from': (self.request.GET.get('date_from') or default_from.isoformat()).strip(),
            'date_to': (self.request.GET.get('date_to') or default_to.isoformat()).strip(),
            'document_numbers': (self.request.GET.get('document_numbers') or '').strip(),
            'sort_field': self.request.GET.get('sort_field', 'start_date'),
            'sort_dir': self.request.GET.get('sort_dir', 'desc'),
        }

        all_permits = PermitRequest.objects.all()
        context['total'] = all_permits.count()
        context['pendientes'] = all_permits.filter(status='REQUESTED').count()
        context['aprobados'] = all_permits.filter(status='APPROVED').count()
        context['rechazados'] = all_permits.filter(status='REJECTED').count()
        return context


class PermitApprovedSummaryModalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Renderiza el modal independiente con el resumen de permisos aprobados según filtros."""
    permission_required = 'permitrequest.view_permitrequest'

    def get(self, request):
        filtered_qs = PermitQueryService.get_filtered_admin_permits(
            request.GET,
            request.session.get('permit_document_numbers', [])
        )
        summary = build_approved_permits_summary(filtered_qs)
        html = render_to_string(
            'permissions/modals/modal_permit_summary.html',
            {'summary': summary},
            request=request
        )
        return HttpResponse(html)


class PermitDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.view_permitrequest'

    def get(self, request, pk):
        permit = get_object_or_404(
            PermitRequest.objects.select_related('employee__person', 'permit_type', 'created_by', 'response_by'),
            pk=pk
        )
        template = (
            'permissions/modals/modal_permit_detail.html'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest'
            else 'permissions/reports/permit_detail_public.html'
        )
        return HttpResponse(render_to_string(template, {'permit': permit}, request=request))


class PublicPermitValidationView(View):
    """Public QR validation endpoint protected by cryptographic signing token."""

    def get(self, request, token):
        try:
            permit_id = PermitSecurityService.parse_public_token(token)
        except (signing.BadSignature, ValueError, TypeError):
            raise Http404('Código de validación inválido.')

        permit = get_object_or_404(
            PermitRequest.objects.select_related('employee__person', 'permit_type', 'created_by', 'response_by'),
            pk=permit_id,
            status='APPROVED'
        )
        html = render_to_string('permissions/reports/permit_detail_public.html', {'permit': permit}, request=request)
        return HttpResponse(html)


class PermitResponseView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.change_permitrequest'

    def get(self, request, pk, action):
        permit = get_object_or_404(PermitRequest, pk=pk)
        if permit.status != 'REQUESTED':
            return JsonResponse({'success': False, 'message': 'Este permiso ya fue procesado.'}, status=400)

        default_message = 'Se acepta el permiso' if action == 'approve' else ''
        html = render_to_string(
            'permissions/modals/modal_permit_response.html',
            {'permit': permit, 'action': action, 'default_message': default_message},
            request=request
        )
        return HttpResponse(html)

    def post(self, request, pk, action):
        permit = get_object_or_404(PermitRequest, pk=pk)
        try:
            PermitWorkflowService.process_permit_response(
                request.user, permit, action, request.POST.get('response_note', '')
            )
            msg = 'Permiso aprobado correctamente.' if action == 'approve' else 'Permiso rechazado correctamente.'
            return JsonResponse({
                'success': True,
                'message': msg,
                'status': permit.status,
                'response_note': permit.response_note or ''
            })
        except ValidationError as exc:
            return JsonResponse({'success': False, 'message': exc.message}, status=400)


class PermitInsistView(LoginRequiredMixin, View):
    def get(self, request, pk):
        permit = get_object_or_404(PermitRequest.objects.select_related('employee__person', 'permit_type'), pk=pk)
        if not PermitSecurityService.can_insist_permit(request.user, permit):
            raise PermissionDenied('No tiene permisos para insistir esta solicitud.')

        html = render_to_string('permissions/modals/modal_permit_insist.html', {'permit': permit}, request=request)
        return HttpResponse(html)

    def post(self, request, pk):
        permit = get_object_or_404(PermitRequest.objects.select_related('employee__person'), pk=pk)
        if not PermitSecurityService.can_insist_permit(request.user, permit):
            raise PermissionDenied('No tiene permisos para insistir esta solicitud.')

        try:
            PermitWorkflowService.insist_permit(request.user, permit, request.POST.get('insist_message', ''))
            return JsonResponse({
                'success': True,
                'message': 'La solicitud fue insistida y enviada nuevamente para revisión.'
            })
        except ValidationError as exc:
            return JsonResponse({'success': False, 'message': exc.message}, status=400)


class PermitReportView(LoginRequiredMixin, View):
    def get(self, request, pk):
        permit = get_object_or_404(
            PermitRequest.objects.select_related('employee__person', 'permit_type', 'response_by'),
            pk=pk
        )
        if not PermitSecurityService.can_view_report(request.user, permit):
            raise PermissionDenied('Acceso denegado.')

        if permit.status != 'APPROVED':
            return HttpResponse('Solo se pueden imprimir permisos aprobados.', status=400)

        validation_token = PermitSecurityService.build_public_token(permit.id)
        detail_url = request.build_absolute_uri(
            reverse_lazy('permissions:permit_public_validate', kwargs={'token': validation_token})
        )
        qr_base64 = PermitWorkflowService.generate_qr_base64(detail_url)

        html = render_to_string(
            'permissions/reports/permit_report.html',
            {
                'permit': permit,
                'qr_code': qr_base64,
                'detail_url': detail_url,
                'validation_code': f"{validation_token[:10]}...{validation_token[-8:]}"
            },
            request=request
        )
        return HttpResponse(html)


class ParsePermitIdentificationExcelView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.view_permitrequest'

    def post(self, request):
        try:
            unique_ids = PermitWorkflowService.parse_identification_excel(request.FILES.get('identification_file'))
            request.session['permit_document_numbers'] = unique_ids
            request.session.modified = True
            return JsonResponse({
                'success': True,
                'count': len(unique_ids),
                'message': f'Se cargaron {len(unique_ids)} cédula(s) correctamente.'
            })
        except ValidationError as exc:
            return JsonResponse({'success': False, 'message': exc.message}, status=400)


# ==========================================
# VISTAS: BITÁCORAS (BINNACLES)
# ==========================================

class BinnacleRegisterView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.add_permitrequest'

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)
        html = render_to_string(
            'permissions/modals/modal_binnacle_register.html',
            {'employee_id': employee.id, 'employee_name': employee.person.full_name},
            request=request
        )
        return HttpResponse(html)

    def post(self, request, employee_id):
        employee = get_object_or_404(Employee, pk=employee_id)
        try:
            created_count = BinnacleService.register_binnacles(
                request.user, employee, request.POST, request.FILES.get('attachment')
            )
            return JsonResponse({
                'success': True,
                'message': f'Se crearon {created_count} bitácora(s) correctamente.'
            })
        except ValidationError as exc:
            return JsonResponse({'success': False, 'message': exc.message}, status=400)


class BinnacleListView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.view_permitrequest'

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee.objects.select_related('person'), pk=employee_id)
        binnacle_type = PermitType.objects.filter(name__icontains='Bitácora').first()
        binnacles = []

        if binnacle_type:
            binnacles = PermitRequest.objects.filter(
                employee=employee,
                permit_type=binnacle_type,
                status__in=['REQUESTED', 'REJECTED']
            ).select_related('created_by').order_by('-start_date', '-start_time')

        html = render_to_string(
            'permissions/modals/modal_binnacle_list.html',
            {'employee': employee, 'employee_name': employee.person.full_name, 'bitacoras': binnacles},
            request=request
        )
        return HttpResponse(html)


class BinnacleHistoryView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Server-rendered modal showing approved binnacle history."""
    permission_required = 'permitrequest.view_permitrequest'

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee.objects.select_related('person'), pk=employee_id)
        binnacle_type = PermitType.objects.filter(name__icontains='Bitácora').first()

        qs = PermitRequest.objects.none()
        if binnacle_type:
            qs = PermitRequest.objects.filter(
                employee=employee,
                permit_type=binnacle_type,
                status='APPROVED'
            ).select_related('response_by', 'created_by', 'updated_by').order_by('-start_date')

        can_edit = (
                request.user.has_perm('permitrequest.can_edit') or
                request.user.has_perm('permitrequest.change_permitrequest') or
                request.user.has_perm('permitrequest.delete_permitrequest')
        )

        html = render_to_string(
            'permissions/modals/modal_binnacle_history.html',
            {
                'bitacoras': qs,
                'employee_name': employee.person.full_name,
                'can_edit': can_edit,
            },
            request=request
        )
        return HttpResponse(html)


class BinnacleApproveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.change_permitrequest'

    def post(self, request):
        payload = json.loads(request.body.decode('utf-8') or '{}')
        ids = [int(i) for i in payload.get('ids', []) if str(i).isdigit()]
        if not ids:
            return JsonResponse({'success': False, 'message': 'No se especificaron bitácoras.'}, status=400)

        updated = PermitRequest.objects.filter(id__in=ids, status='REQUESTED').update(
            status='APPROVED',
            response_by=request.user,
            response_date=timezone.now(),
            response_note='Aprobado masivamente',
            updated_by=request.user
        )
        return JsonResponse({'success': True, 'message': f'Se aprobaron {updated} bitácora(s) correctamente.'})


class BinnacleRejectView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.change_permitrequest'

    def post(self, request):
        payload = json.loads(request.body.decode('utf-8') or '{}')
        ids = [int(i) for i in payload.get('ids', []) if str(i).isdigit()]
        reason = (payload.get('reason') or '').strip()

        if not ids or not reason:
            return JsonResponse({'success': False, 'message': 'Datos incompletos para rechazar.'}, status=400)

        now = timezone.now()
        updated = 0
        for binnacle in PermitRequest.objects.filter(id__in=ids, status='REQUESTED'):
            binnacle.status = 'REJECTED'
            binnacle.response_by = request.user
            binnacle.response_date = now
            binnacle.response_note = PermitWorkflowService.format_history_entry(
                'note-reject', 'Rechazo', reason, binnacle.response_note
            )
            binnacle.updated_by = request.user
            binnacle.save(update_fields=[
                'status', 'response_by', 'response_date', 'response_note', 'updated_by', 'updated_at'
            ])
            updated += 1

        return JsonResponse({'success': True, 'message': f'Se rechazaron {updated} bitácora(s) correctamente.'})


class BinnacleReviewView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.change_permitrequest'

    def post(self, request, pk):
        payload = json.loads(request.body.decode('utf-8') or '{}')
        reason = (payload.get('reason') or '').strip()
        if not reason:
            return JsonResponse({'success': False, 'message': 'Se requiere el motivo.'}, status=400)

        binnacle = get_object_or_404(PermitRequest, pk=pk)
        binnacle.response_note = PermitWorkflowService.format_history_entry(
            'note-modifica', 'Modifica', reason, binnacle.response_note
        )
        binnacle.status = 'REQUESTED'
        binnacle.updated_by = request.user
        binnacle.save(update_fields=['response_note', 'status', 'updated_by', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Motivo añadido. Bitácora marcada como PENDIENTE.'
        })


class BinnacleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.delete_permitrequest'

    def post(self, request):
        payload = json.loads(request.body.decode('utf-8') or '{}')
        ids = [int(i) for i in payload.get('ids', []) if str(i).isdigit()]
        updated = PermitRequest.objects.filter(
            id__in=ids, status__in=['REQUESTED', 'REJECTED']
        ).update(status='CANCELED', updated_by=request.user, updated_at=timezone.now())

        return JsonResponse({'success': True, 'message': f'Se anularon {updated} bitácora(s) correctamente.'})


class BinnacleEditView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'permitrequest.change_permitrequest'

    def post(self, request, pk):
        binnacle = get_object_or_404(PermitRequest, pk=pk, status__in=['REQUESTED', 'REJECTED'])
        try:
            BinnacleService.update_binnacle(
                user=request.user,
                binnacle=binnacle,
                start_time=request.POST.get('start_time'),
                end_time=request.POST.get('end_time'),
                note=request.POST.get('response_note'),
                attachment=request.FILES.get('justification_file')
            )
            return JsonResponse({'success': True, 'message': 'Bitácora actualizada correctamente.'})
        except ValidationError as exc:
            return JsonResponse({'success': False, 'message': exc.message}, status=400)
