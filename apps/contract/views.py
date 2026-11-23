import json
import os
import re
from datetime import datetime, timedelta

import openpyxl
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import CharField, Prefetch, Q
from django.db.models.functions import Coalesce, Lower
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, View

from budget.models import BudgetLine
from core.models import SystemConfiguration, User
from employee.models import Employee
from institution.models import AdministrativeUnit
from person.models import Person
from personnel_actions.models import ActionType
from schedule.models import Schedule
from .forms import (
    ContractTypeForm,
    HistoricalManagementPeriodForm,
    LaborRegimeForm,
    ManagementPeriodCreateForm,
    ManagementPeriodPartialUpdateForm,
    ManagementPeriodTerminateForm,
)
from .models import (
    ContractTemplate,
    ContractTemplateSection,
    ContractType,
    History,
    LaborRegime,
    ManagementPeriod,
)
from .services import (
    ContractExportService,
    ContractTemplateService,
    HistoricalContractService,
    ManagementPeriodService,
    build_user_full_name,
    clean_text_accents,
    is_action_contract_type,
)

PERIOD_SORT_FIELDS = {
    'document_number': 'employee__person__document_number',
    'last_name': 'employee__person__last_name',
    'first_name': 'employee__person__first_name',
    'position': 'position_sort_name',
    'remuneration': 'budget_line__remuneration',
    'unit': 'administrative_unit__name',
    'contract_type': 'contract_type__name',
    'regime': 'contract_type__labor_regime__name',
    'start_date': 'start_date',
    'end_date': 'end_date',
    'status': 'status__name',
}


def _normalize_contract_template_content(content):
    return (content or '').replace('\r\n', '\n').replace('\r', '\n').strip()


def _parse_period_sort(request):
    sort_field = (request.GET.get('sort_field') or 'created_at').strip()
    sort_dir = (request.GET.get('sort_dir') or 'desc').strip().lower()
    mapped_field = PERIOD_SORT_FIELDS.get(sort_field, 'created_at')

    if sort_dir == 'desc':
        return [f'-{mapped_field}', '-pk']
    return [mapped_field, 'pk']


def _get_action_types_for_template():
    action_types = ActionType.objects.filter(is_active=True).order_by('name')
    if action_types.exists():
        return action_types
    return ActionType.objects.order_by('name')


def _get_authorities_for_template():
    return User.objects.filter(is_active=True).order_by('username')


class LaborRegimeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LaborRegime
    template_name = 'contract/labor_regime_list.html'
    permission_required = 'contract.view_laborregime'
    context_object_name = 'regimes'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = LaborRegime.objects.all()
        context['stats_total'] = qs.count()
        context['stats_active'] = qs.filter(is_active=True).count()
        context['stats_inactive'] = qs.filter(is_active=False).count()
        return context


class LaborRegimeTablePartialView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.view_laborregime'

    def get(self, request):
        name = request.GET.get('name', '').strip()
        is_active = request.GET.get('is_active', '').strip()
        queryset = LaborRegime.objects.all().order_by('code')

        if name:
            queryset = queryset.filter(Q(name__icontains=name) | Q(code__icontains=name))
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)

        all_qs = LaborRegime.objects.all()
        stats = {
            'total': all_qs.count(),
            'active': all_qs.filter(is_active=True).count(),
            'inactive': all_qs.filter(is_active=False).count(),
        }

        html = render_to_string(
            'contract/partials/partial_labor_regime_table.html',
            {'regimes': queryset},
            request=request,
        )
        return JsonResponse({'table_html': html, 'stats': stats})


class LaborRegimeDetailAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.view_laborregime'

    def get(self, request, pk):
        regime = get_object_or_404(LaborRegime, pk=pk)
        return JsonResponse({
            'success': True,
            'regime': {
                'id': regime.id,
                'code': regime.code,
                'name': regime.name,
                'description': regime.description or '',
                'is_active': regime.is_active,
            }
        })


class LaborRegimeCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.add_laborregime'

    def post(self, request):
        form = LaborRegimeForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    instance = form.save(commit=False)
                    instance.created_by = request.user
                    instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Régimen Laboral creado exitosamente.'
                })
            except Exception as exc:
                return JsonResponse({
                    'success': False,
                    'message': f'Error al guardar: {str(exc)}'
                }, status=500)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class LaborRegimeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_laborregime'

    def post(self, request, pk):
        instance = get_object_or_404(LaborRegime, pk=pk)
        form = LaborRegimeForm(request.POST, instance=instance)

        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_instance = form.save(commit=False)
                    updated_instance.updated_by = request.user
                    updated_instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Régimen Laboral actualizado correctamente.'
                })
            except Exception as exc:
                return JsonResponse({
                    'success': False,
                    'message': f'Error al actualizar: {str(exc)}'
                }, status=500)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class LaborRegimeToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_laborregime'

    def post(self, request, pk):
        instance = get_object_or_404(LaborRegime, pk=pk)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save(update_fields=['is_active', 'updated_by', 'updated_at'])

        message = 'Régimen activado (Alta)' if instance.is_active else 'Régimen desactivado (Baja)'
        return JsonResponse({'success': True, 'message': message})


class ContractTypeListView(LoginRequiredMixin, View):
    """Lista las modalidades contractuales asociadas a un régimen renderizando su parcial HTML."""

    def get(self, request, regime_id):
        regime = get_object_or_404(LaborRegime, pk=regime_id)
        contract_types = ContractType.objects.filter(labor_regime=regime).order_by('name')
        table_html = render_to_string(
            'contract/partials/partial_contract_type_table.html',
            {'contract_types': contract_types, 'regime': regime},
            request=request,
        )
        return JsonResponse({
            'success': True,
            'regime_name': regime.name,
            'table_html': table_html,
        })


class ContractTypeCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.add_contracttype'

    def post(self, request):
        form = ContractTypeForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    instance = form.save(commit=False)
                    instance.created_by = request.user
                    instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Modalidad laboral registrada con éxito.'
                })
            except Exception as exc:
                return JsonResponse({
                    'success': False,
                    'message': f'Error interno: {str(exc)}'
                }, status=500)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ContractTypeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    def post(self, request, pk):
        instance = get_object_or_404(ContractType, pk=pk)
        form = ContractTypeForm(request.POST, instance=instance)
        if form.is_valid():
            try:
                with transaction.atomic():
                    instance = form.save(commit=False)
                    instance.updated_by = request.user
                    instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Modalidad actualizada correctamente.'
                })
            except Exception as exc:
                return JsonResponse({'success': False, 'message': str(exc)}, status=500)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ContractTypeToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    def post(self, request, pk):
        instance = get_object_or_404(ContractType, pk=pk)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        return JsonResponse({
            'success': True,
            'message': f'Estado de "{instance.name}" actualizado.'
        })


class ContractTemplateEditorCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    def get(self, request, contract_type_id):
        contract_type = get_object_or_404(ContractType, pk=contract_type_id)
        template, _ = ContractTemplate.objects.get_or_create(
            contract_type=contract_type,
            defaults={
                'created_by': request.user,
                'updated_by': request.user,
            },
        )

        if template.created_by is None:
            template.created_by = request.user
        template.updated_by = request.user
        template.save(update_fields=['created_by', 'updated_by', 'updated_at'])

        if is_action_contract_type(contract_type):
            ContractTemplateService.ensure_action_template_sections(template, request.user)

        return redirect('contract:template_editor_detail', pk=template.pk)


class ContractTemplateEditorDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    def get(self, request, pk):
        template = get_object_or_404(
            ContractTemplate.objects.select_related('contract_type__labor_regime'),
            pk=pk,
        )
        is_action_template = is_action_contract_type(template.contract_type)
        action_template_fields = []
        editor_body_html = ''

        if is_action_template:
            sections = ContractTemplateService.ensure_action_template_sections(template, request.user)
            field_specs = [
                ('action_type', 'Tipo de Acción'),
                ('authority_1', 'Autoridad 1'),
                ('authority_2', 'Autoridad 2'),
                ('reviewer', 'Revisado Por'),
                ('elaboration', 'Elaborado Por'),
                ('register', 'Registrado Por'),
            ]
            action_template_fields = [
                {
                    'id': sections[index].id if len(sections) > index else None,
                    'key': key,
                    'label': label,
                    'value': sections[index].content if len(sections) > index else '',
                    'original': sections[index].content if len(sections) > index else '',
                    'type': 'select2',
                }
                for index, (key, label) in enumerate(field_specs)
            ]
        else:
            editor_body_html = ContractTemplateService.get_editor_body_html(template)

        context = {
            'template': template,
            'available_mappings': ContractTemplateService.GENERIC_VARIABLES,
            'editor_body_html': editor_body_html,
            'is_action_template': is_action_template,
            'action_template_fields': action_template_fields,
            'action_types': [
                {'id': item.id, 'name': item.name}
                for item in _get_action_types_for_template()
            ],
            'authorities': [
                {'id': item.id, 'name': item.name, 'position': item.position}
                for item in _get_authorities_for_template()
            ],
        }
        template_name = (
            'contract/template_editor/action_template_editor.html'
            if is_action_template
            else 'contract/template_editor/template_editor.html'
        )
        return render(request, template_name, context)


class ContractTemplateEditorOptionsAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    def get(self, request):
        return JsonResponse({
            'success': True,
            'action_types': [
                {'id': item.id, 'name': item.name}
                for item in _get_action_types_for_template()
            ],
            'authorities': [
                {'id': item.id, 'name': item.name, 'position': item.position}
                for item in _get_authorities_for_template()
            ],
        })


class ContractTemplateSaveBodyAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Guarda el contenido enriquecido del editor WYSIWYG de base.html para la plantilla."""
    permission_required = 'contract.change_contracttype'

    @method_decorator(require_http_methods(['POST']))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, template_id):
        template = get_object_or_404(ContractTemplate, pk=template_id)
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                raw_html = data.get('content', '')
            else:
                raw_html = request.POST.get('content', '')

            section = ContractTemplateService.save_editor_body_html(template, raw_html, request.user)
            return JsonResponse({
                'success': True,
                'message': 'Plantilla contractual guardada correctamente.',
                'section_id': section.id,
            })
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
        except Exception as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=500)


class ContractTemplateSectionCreateAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    @method_decorator(require_http_methods(['POST']))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, template_id):
        template = get_object_or_404(ContractTemplate, pk=template_id)
        try:
            data = json.loads(request.body)
            content = _normalize_contract_template_content(data.get('content', ''))
            section_type = data.get('section_type', 'PARAGRAPH')
            order = data.get('order', 0)

            if not content:
                return JsonResponse({'error': 'El contenido no puede estar vacío'}, status=400)
            if section_type not in ['PARAGRAPH', 'TITLE']:
                return JsonResponse({'error': 'Tipo de sección inválido'}, status=400)

            section = ContractTemplateSection.objects.create(
                template=template,
                section_type=section_type,
                content=content,
                order=order,
                created_by=request.user,
                updated_by=request.user,
            )

            return JsonResponse({
                'success': True,
                'section': {
                    'id': section.id,
                    'section_type': section.get_section_type_display(),
                    'section_type_code': section.section_type,
                    'content': section.content,
                    'order': section.order,
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)


class ContractTemplateSectionUpdateAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    @method_decorator(require_http_methods(['POST']))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, section_id):
        section = get_object_or_404(ContractTemplateSection, pk=section_id)
        try:
            data = json.loads(request.body)
            section.content = _normalize_contract_template_content(data.get('content', section.content))
            section.section_type = data.get('section_type', section.section_type)
            section.order = data.get('order', section.order)
            section.updated_by = request.user
            section.save()

            return JsonResponse({
                'success': True,
                'section': {
                    'id': section.id,
                    'section_type': section.get_section_type_display(),
                    'section_type_code': section.section_type,
                    'content': section.content,
                    'order': section.order,
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)


class ContractTemplateSectionDeleteAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    @method_decorator(require_http_methods(['POST']))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, section_id):
        section = get_object_or_404(ContractTemplateSection, pk=section_id)
        deleted_id = section.id
        section.delete()
        return JsonResponse({'success': True, 'deleted_id': deleted_id})


class ContractTemplateSectionReorderAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    @method_decorator(require_http_methods(['POST']))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, template_id):
        template = get_object_or_404(ContractTemplate, pk=template_id)
        try:
            data = json.loads(request.body)
            for item in data.get('sections', []):
                ContractTemplateSection.objects.filter(
                    pk=item['id'],
                    template=template
                ).update(order=item['order'], updated_by=request.user)
            return JsonResponse({'success': True})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)


class ContractTemplatePreviewAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'
    template_name = 'contract/partials/template_preview_sheet.html'

    def get(self, request, template_id):
        today_str = timezone.now().date().strftime('%d/%m/%Y')
        try:
            template = get_object_or_404(
                ContractTemplate.objects.select_related('contract_type__labor_regime'),
                pk=template_id,
            )
            is_action_template = is_action_contract_type(template.contract_type)

            if is_action_template:
                action_data = ContractTemplateService.get_action_template_preview_data(template)
                preview_html = render_to_string(
                    self.template_name,
                    {
                        'is_action_template': True,
                        'action_data': action_data,
                    },
                    request=request,
                )
                return JsonResponse({'preview': preview_html})

            period = (
                ManagementPeriod.objects.select_related(
                    'employee__person',
                    'contract_type__labor_regime',
                    'administrative_unit',
                    'schedule',
                    'budget_line__position_item',
                )
                .filter(contract_type=template.contract_type)
                .order_by('-created_at')
                .first()
            )

            if not period:
                replacements = {
                    '[DOC_NUMBER]': 'PENDIENTE',
                    '[TODAY]': today_str,
                    '[today]': today_str,
                }
            else:
                replacements = ContractTemplateService.build_replacements(period)

            sections_html = ContractTemplateService.render_template_body(template, replacements)
            preview_html = render_to_string(
                self.template_name,
                {
                    'is_action_template': False,
                    'doc_number': replacements.get('[DOC_NUMBER]', 'PENDIENTE'),
                    'today_str': replacements.get('[TODAY]', today_str),
                    'sections_html': sections_html,
                },
                request=request,
            )
            return JsonResponse({'preview': preview_html})
        except Exception:
            fallback_html = render_to_string(
                self.template_name,
                {
                    'is_action_template': False,
                    'doc_number': 'PENDIENTE',
                    'today_str': today_str,
                    'sections_html': '',
                    'empty_message': 'No fue posible cargar todos los datos de la vista previa. Puede continuar editando la plantilla.',
                },
                request=request,
            )
            return JsonResponse({'preview': fallback_html})


class ManagementPeriodPrintView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.view_managementperiod'

    def get(self, request, pk):
        period = get_object_or_404(
            ManagementPeriod.objects.select_related(
                'employee__person',
                'contract_type__labor_regime',
                'administrative_unit',
                'schedule',
                'budget_line__position_item',
                'created_by',
                'personnel_action',
            ),
            pk=pk,
        )

        if period.contract_type.contract_type_category == ContractType.TYPE_ACCION_PERSONAL and period.personnel_action_id:
            return redirect('personnel_actions:action_pdf', pk=period.personnel_action_id)

        template = ContractTemplate.objects.filter(contract_type=period.contract_type, is_active=True).first()
        replacements = ContractTemplateService.build_replacements(period)
        is_action_document = period.contract_type.contract_type_category == ContractType.TYPE_ACCION_PERSONAL
        document_label = 'ACCIÓN DE PERSONAL' if is_action_document else 'CONTRATO'

        if (period.custom_document_body or '').strip():
            body_html = ContractTemplateService.sanitize_rich_html(period.custom_document_body)
            for placeholder, value in replacements.items():
                body_html = body_html.replace(placeholder, str(value))
        else:
            body_html = ContractTemplateService.render_template_body(template, replacements) if template else ''

        configuration = SystemConfiguration.get_current()
        authority_name = ''
        authority_position = ''
        city = 'Loja'
        if configuration:
            authority_name = (configuration.max_authority_name or '').strip().upper()
            authority_position = (configuration.max_authority_position or '').strip().upper()
            city = (configuration.city or 'Loja').strip()

        employee_person = getattr(period.employee, 'person', None)
        employee_full_name = (employee_person.full_name or '').strip().upper() if employee_person else ''

        context = {
            'document_label': document_label,
            'document_number': replacements.get('[DOC_NUMBER]', '-'),
            'today': replacements.get('[TODAY]', timezone.now().date().strftime('%d/%m/%Y')),
            'city': city,
            'letterhead_path': ManagementPeriodService.get_letterhead_data_uri(request),
            'authority_name': authority_name,
            'authority_position': authority_position,
            'employee_full_name': employee_full_name,
            'prepared_by': build_user_full_name(period.created_by),
            'is_pdf': True,
            'is_action_document': is_action_document,
            'replacements': replacements,
            'body_html': body_html,
        }

        try:
            from weasyprint import HTML

            html_string = render_to_string(
                'contract/reports/printable_management_document.html',
                context,
                request=request,
            )
            pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            safe_doc = str(replacements.get('[DOC_NUMBER]', period.pk)).replace(' ', '_').replace('/', '-')
            file_prefix = 'AccionPersonal' if is_action_document else 'Contrato'
            response['Content-Disposition'] = f'inline; filename="{file_prefix}_{safe_doc}.pdf"'
            return response
        except Exception:
            return HttpResponse('Error al generar el PDF del contrato', status=500)


class ManagementPeriodEditContentView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_managementperiod'

    def get(self, request, pk):
        period = get_object_or_404(
            ManagementPeriod.objects.select_related(
                'employee__person',
                'contract_type__labor_regime',
                'administrative_unit',
                'schedule',
                'budget_line__position_item',
                'status',
            ),
            pk=pk,
        )
        if period.status.code != 'SIN_FIRMAR':
            return redirect('contract:period_list')

        template = ContractTemplate.objects.filter(contract_type=period.contract_type, is_active=True).first()
        replacements = ContractTemplateService.build_replacements(period)

        if (period.custom_document_body or '').strip():
            editor_body_html = ContractTemplateService.sanitize_rich_html(period.custom_document_body)
        elif template:
            editor_body_html = ContractTemplateService.render_template_body(template, replacements)
        else:
            editor_body_html = ''

        return render(request, 'contract/template_editor/period_document_editor.html', {
            'period': period,
            'editor_body_html': editor_body_html,
            'available_mappings': ContractTemplateService.GENERIC_VARIABLES,
            'doc_number': replacements.get('[DOC_NUMBER]', period.document_number),
        })

    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        if period.status.code != 'SIN_FIRMAR':
            return JsonResponse({
                'success': False,
                'error': 'No se puede editar un contrato ya firmado o finalizado.'
            }, status=403)

        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            raw_html = data.get('content', '')
            period.custom_document_body = ContractTemplateService.sanitize_rich_html(raw_html)
            period.updated_by = request.user
            period.save(update_fields=['custom_document_body', 'updated_by', 'updated_at'])
            return JsonResponse({
                'success': True,
                'message': f'Contenido del contrato {period.document_number} actualizado.'
            })
        except Exception as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=500)


class ManagementPeriodNotificationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ManagementPeriod
    template_name = 'contract/management_period_notification_list.html'
    permission_required = 'contract.view_managementperiod'
    context_object_name = 'periods'
    paginate_by = 10

    def get_ordering(self):
        sort = (self.request.GET.get('sort_field') or self.request.GET.get('sort') or 'end_date').strip()
        direction = (self.request.GET.get('sort_dir') or self.request.GET.get('direction') or 'asc').strip().lower()
        allowed = {
            'last_name': 'employee__person__last_name',
            'document': 'employee__person__document_number',
            'contract_type': 'contract_type__name',
            'regime': 'contract_type__labor_regime__name',
            'position': 'budget_line__position_item__name',
            'start_date': 'start_date',
            'end_date': 'end_date',
        }
        field = allowed.get(sort, 'end_date')
        return f'-{field}' if direction == 'desc' else field

    def get_queryset(self):
        today = timezone.now().date()
        deadline = today + timedelta(days=20)
        q = (self.request.GET.get('q') or '').strip()

        queryset = ManagementPeriod.objects.filter(
            is_active=True,
            end_date__isnull=False,
            end_date__gte=today,
            end_date__lte=deadline,
        ).select_related(
            'employee__person',
            'contract_type__labor_regime',
            'budget_line__position_item',
        )

        if q:
            queryset = queryset.filter(
                Q(employee__person__first_name__icontains=q)
                | Q(employee__person__last_name__icontains=q)
                | Q(employee__person__document_number__icontains=q)
                | Q(contract_type__name__icontains=q)
                | Q(contract_type__labor_regime__name__icontains=q)
                | Q(budget_line__position_item__name__icontains=q)
                | Q(manual_position__icontains=q)
                | Q(document_number__icontains=q)
            )

        return queryset.order_by(self.get_ordering(), 'employee__person__last_name', 'employee__person__first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        deadline = today + timedelta(days=20)
        context['q'] = (self.request.GET.get('q') or '').strip()
        context['current_sort'] = (self.request.GET.get('sort') or 'end_date').strip()
        context['current_direction'] = (self.request.GET.get('direction') or 'asc').strip().lower()
        context['window_start'] = today
        context['window_end'] = deadline
        return context


class ValidateEmployeeAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.add_managementperiod'

    def get(self, request, doc_number):
        try:
            contract_type_id = request.GET.get('contract_type_id')
            contract_type = ContractType.objects.filter(pk=contract_type_id).first() if contract_type_id else None
            contract_code = (contract_type.code if contract_type else '').upper()
            contract_category = (contract_type.contract_type_category if contract_type else '').upper()
            is_professional_service = contract_code == 'SERVICIOS_PROFESIONALES'

            person = Person.objects.filter(document_number=doc_number).first()
            if not person:
                return JsonResponse({'success': False, 'message': 'Cédula no registrada.'})

            active_employee = Employee.objects.filter(person=person, is_active=True).first()
            if active_employee:
                return JsonResponse({
                    'success': False,
                    'message': 'Atención: la persona ya es un empleado activo.'
                })

            employees = Employee.objects.filter(person=person).select_related('person').prefetch_related(
                'current_budget_line__position_item'
            )
            employee_candidate = employees.first()
            employee_with_line = None
            budget_line = None
            for emp in employees:
                bl = emp.current_budget_line.first()
                if bl:
                    employee_with_line = emp
                    budget_line = bl
                    break

            employee_selected = employee_with_line or employee_candidate
            if not employee_selected:
                return JsonResponse({
                    'success': False,
                    'message': 'Bloqueo: La persona no tiene un registro de empleado para generar gestión laboral.'
                })

            if not is_professional_service and (not employee_with_line or not budget_line):
                return JsonResponse({
                    'success': False,
                    'message': 'Bloqueo: La persona no tiene una partida presupuestaria asignada. Asigne una partida antes de continuar.'
                })

            has_active = ManagementPeriod.objects.filter(
                employee=employee_selected,
                status__code='ACTIVO'
            ).exists()

            if has_active:
                return JsonResponse({
                    'success': False,
                    'message': 'Atención: La persona ya posee un Inicio de Gestión (Contrato) vigente.'
                })

            return JsonResponse({
                'success': True,
                'employee': {
                    'id': employee_selected.id,
                    'full_name': person.full_name,
                    'photo': person.photo.url if person.photo else None,
                    'budget_line': ({
                                        'id': budget_line.id,
                                        'number': budget_line.number_individual or budget_line.code,
                                        'position': budget_line.position_item.name if budget_line.position_item else 'SIN CARGO'
                                    } if budget_line else None),
                    'contract_type_category': contract_category or ContractType.TYPE_CONTRATO,
                    'requires_manual_compensation': is_professional_service,
                },
            })
        except Exception as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=500)


class GetAvailableBudgetLinesAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.view_managementperiod'

    def get(self, request, unit_id):
        lines = BudgetLine.objects.filter(
            status_item__code='LIBRE',
            is_active=True
        ).select_related('position_item')

        data = [{
            'id': line.id,
            'number_individual': line.number_individual or line.code,
            'position_name': line.position_item.name if line.position_item else 'SIN CARGO',
            'remuneration': str(line.remuneration),
        } for line in lines]

        return JsonResponse({'success': True, 'lines': data})


class JSONResponseMixin:
    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)
            page_obj = context.get('page_obj')
            paginator = context.get('paginator')
            pagination_data = {
                'start_index': page_obj.start_index() if page_obj and paginator and paginator.count else 0,
                'end_index': page_obj.end_index() if page_obj and paginator and paginator.count else 0,
                'total_count': paginator.count if paginator else 0,
                'page': page_obj.number if page_obj else 1,
                'total_pages': paginator.num_pages if paginator else 1,
                'has_previous': bool(page_obj and page_obj.has_previous()),
                'has_next': bool(page_obj and page_obj.has_next()),
            }
            return JsonResponse({'success': True, 'html': html, 'pagination': pagination_data})
        return super().render_to_response(context, **response_kwargs)


class ManagementPeriodListView(LoginRequiredMixin, PermissionRequiredMixin, JSONResponseMixin, ListView):
    model = ManagementPeriod
    template_name = 'contract/management_period_list.html'
    partial_template_name = 'contract/partials/partial_management_period_table.html'
    export_template_name = 'contract/partials/partial_management_period_export.html'
    permission_required = 'contract.view_managementperiod'
    context_object_name = 'periods'
    paginate_by = 10

    def get_paginate_by(self, queryset):
        if self.request.GET.get('export') == 'true':
            return None
        return self.paginate_by

    def get(self, request, *args, **kwargs):
        if request.GET.get('export') == 'true':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            context['export_rows'] = ContractExportService.get_unified_export_rows(
                self.object_list,
                context['current_filters']
            )
            return render(request, self.export_template_name, context)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = (
            ManagementPeriod.objects.select_related(
                'employee__person',
                'budget_line__position_item',
                'contract_type__labor_regime',
                'administrative_unit',
                'status',
            )
            .prefetch_related('history_set')
            .annotate(
                position_sort_name=Lower(
                    Coalesce(
                        'budget_line__position_item__name',
                        'manual_position',
                        output_field=CharField(),
                    )
                ),
                employee_sort_name=Lower('employee__person__last_name'),
            )
        )

        q = (self.request.GET.get('q') or '').strip()
        regime_code = (self.request.GET.get('regime_code') or '').strip()
        unit_id = (self.request.GET.get('unit') or '').strip()
        status_code = (self.request.GET.get('status_code') or '').strip()
        date_from = (self.request.GET.get('date_from') or '').strip()
        date_to = (self.request.GET.get('date_to') or '').strip()
        raw_document_numbers = (self.request.GET.get('document_numbers') or '').strip()

        if raw_document_numbers:
            cedulas = [c.strip() for c in raw_document_numbers.split(',') if c.strip()]
            if cedulas:
                queryset = queryset.filter(employee__person__document_number__in=cedulas)

        if q:
            for token in [t for t in q.split() if t]:
                queryset = queryset.filter(
                    Q(employee__person__first_name__icontains=token)
                    | Q(employee__person__last_name__icontains=token)
                    | Q(employee__person__document_number__icontains=token)
                    | Q(document_number__icontains=token)
                    | Q(manual_position__icontains=token)
                    | Q(budget_line__position_item__name__icontains=token)
                )

        if regime_code:
            queryset = queryset.filter(contract_type__labor_regime__code=regime_code)

        if unit_id:
            try:
                selected_unit = AdministrativeUnit.objects.filter(pk=unit_id).first()
                if selected_unit:
                    clean_target = clean_text_accents(selected_unit.name)
                    all_units = AdministrativeUnit.objects.values_list('id', 'name')
                    equivalent_ids = [
                        u_id for u_id, u_name in all_units
                        if clean_text_accents(u_name) == clean_target
                    ]
                    if int(unit_id) not in equivalent_ids:
                        equivalent_ids.append(int(unit_id))
                    queryset = queryset.filter(administrative_unit_id__in=equivalent_ids)
                else:
                    queryset = queryset.filter(administrative_unit_id=unit_id)
            except Exception:
                queryset = queryset.filter(administrative_unit_id=unit_id)

        if status_code:
            queryset = queryset.filter(status__code=status_code)

        if date_from and date_to:
            queryset = queryset.filter(start_date__lte=date_to).filter(
                Q(end_date__gte=date_from) | Q(end_date__isnull=True)
            )
        elif date_from:
            queryset = queryset.filter(Q(end_date__gte=date_from) | Q(end_date__isnull=True))
        elif date_to:
            queryset = queryset.filter(start_date__lte=date_to)

        if not self.request.GET.get('sort_field'):
            return queryset.order_by('-start_date', '-pk')

        return queryset.order_by(*_parse_period_sort(self.request))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        schedules_qs = Schedule.objects.filter(is_active=True)
        context['regimes'] = LaborRegime.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                'contract_types',
                queryset=ContractType.objects.filter(is_active=True).order_by('name'),
                to_attr='active_contract_types'
            )
        )
        context['schedules'] = schedules_qs
        context['schedules_json'] = [
            {'id': s.id, 'name': s.name}
            for s in schedules_qs
        ]
        context['units'] = AdministrativeUnit.objects.filter(is_active=True).order_by('name')

        context['current_filters'] = {
            'q': (self.request.GET.get('q') or '').strip(),
            'unit': (self.request.GET.get('unit') or '').strip(),
            'regime_code': (self.request.GET.get('regime_code') or '').strip(),
            'status_code': (self.request.GET.get('status_code') or '').strip(),
            'date_from': (self.request.GET.get('date_from') or '').strip(),
            'date_to': (self.request.GET.get('date_to') or '').strip(),
            'document_numbers': (self.request.GET.get('document_numbers') or '').strip(),
            'sort_field': self.request.GET.get('sort_field', 'start_date'),
            'sort_dir': self.request.GET.get('sort_dir', 'desc'),
        }
        return context


class ManagementPeriodTerminateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        form = ManagementPeriodTerminateForm(request.POST)

        if not form.is_valid():
            first_error = next(iter(form.errors.values()))[0]
            return JsonResponse({'success': False, 'message': first_error}, status=400)

        try:
            _, released = ManagementPeriodService.terminate_period(period, form, request.user)
            suffix = ' Partida liberada.' if released else ' (No se detectó partida vinculada)'
            return JsonResponse({
                'success': True,
                'message': f'Gestión finalizada correctamente.{suffix}'
            })
        except ValidationError as exc:
            first_error = next(iter(exc.message_dict.values()))[0]
            return JsonResponse({'success': False, 'message': first_error}, status=400)
        except Exception as exc:
            return JsonResponse({'success': False, 'message': f'Error técnico: {str(exc)}'}, status=500)


class ManagementPeriodCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.add_managementperiod'

    def post(self, request):
        form = ManagementPeriodCreateForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        try:
            period = ManagementPeriodService.create_period(form, request.user)
            return JsonResponse({
                'success': True,
                'message': f'Gestión {period.document_number} registrada y área del empleado actualizada.'
            })
        except ValidationError as exc:
            return JsonResponse({'success': False, 'errors': exc.message_dict}, status=400)
        except Exception as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=500)


class ManagementPeriodSignView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(
            ManagementPeriod.objects.select_related('contract_type__labor_regime', 'personnel_action',
                                                    'employee__person'),
            pk=pk
        )
        try:
            ManagementPeriodService.sign_period(period, request.user)
            is_action = period.contract_type.contract_type_category == ContractType.TYPE_ACCION_PERSONAL
            return JsonResponse({
                'success': True,
                'message': (
                    'La acción ha sido legalizada y registrada.'
                    if is_action
                    else 'El contrato ha sido legalizado y registrado en el historial.'
                )
            })
        except Exception as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=500)


class ManagementPeriodDetailAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.view_managementperiod'

    def get(self, request, pk):
        period = get_object_or_404(
            ManagementPeriod.objects.select_related(
                'budget_line__position_item',
                'employee__person',
                'administrative_unit',
                'status',
                'contract_type',
                'schedule',
            ),
            pk=pk
        )

        hist_record = History.objects.filter(contract=period).first()
        has_budget_line = period.budget_line is not None

        if has_budget_line:
            cargo_final = period.budget_line.position_item.name if period.budget_line.position_item else 'SIN CARGO'
            sueldo_final = period.budget_line.remuneration
            codigo_banner = period.budget_line.number_individual or period.budget_line.code
        elif hist_record:
            cargo_final = hist_record.historical_position
            sueldo_final = hist_record.historical_salary
            codigo_banner = 'DATOS DE MIGRACIÓN'
        else:
            cargo_final = period.manual_position or 'SIN CARGO REGISTRADO'
            sueldo_final = period.manual_remuneration
            codigo_banner = 'S/P (REGISTRO MANUAL)'

        return JsonResponse({
            'success': True,
            'period': {
                'id': period.id,
                'has_budget_line': has_budget_line,
                'signed_document_url': period.signed_document.url if period.signed_document else None,
                'document_number': period.document_number,
                'employee_name': period.employee.person.full_name,
                'employee_photo': period.employee.person.photo.url if period.employee.person.photo else None,
                'status_name': period.status.name,
                'status_code': period.status.code,
                'budget_line_number': codigo_banner,
                'position_name': cargo_final,
                'remuneration': f'$ {sueldo_final}' if sueldo_final else 'No definida',
                'unit_name': period.administrative_unit.name if period.administrative_unit else 'N/A',
                'start_date_formatted': period.start_date.strftime('%d/%m/%Y') if period.start_date else '',
                'end_date_formatted': period.end_date.strftime('%d/%m/%Y') if period.end_date else 'INDEFINIDO',
                'schedule_name': period.schedule.name if period.schedule else 'SIN HORARIO',
                'workplace': period.workplace or 'N/A',
                'contract_type_name': period.contract_type.name,
                'contract_type_category': period.contract_type.contract_type_category,
                'job_functions': period.job_functions or '',
                'action_motivation': period.action_motivation or '',
                'action_explanation': period.action_explanation or '',
            }
        })


class ManagementPeriodPartialUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        if period.status.code != 'SIN_FIRMAR':
            return JsonResponse({
                'success': False,
                'message': 'Error de Integridad: No es posible editar un contrato ya firmado o finalizado.'
            }, status=403)

        form = ManagementPeriodPartialUpdateForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'success': False, 'message': 'Error de validación: ' + str(form.errors)}, status=400)

        cleaned = form.cleaned_data
        try:
            with transaction.atomic():
                if cleaned.get('doc') and cleaned['doc'].strip():
                    period.document_number = cleaned['doc'].strip().upper()
                period.workplace = (cleaned.get('workplace') or '').strip().upper()
                period.institutional_need_memo = (cleaned.get('memo') or '').strip().upper()
                period.budget_certification = (cleaned.get('cert') or '').strip().upper()
                period.start_date = cleaned['start']
                period.end_date = cleaned.get('end')
                if cleaned.get('schedule'):
                    period.schedule = cleaned['schedule']
                period.job_functions = (cleaned.get('functions') or '').strip()
                period.updated_by = request.user
                period.full_clean()
                period.save()

            return JsonResponse({'success': True, 'message': 'Expediente actualizado correctamente.'})
        except ValidationError as exc:
            return JsonResponse({'success': False, 'message': 'Error de validación: ' + str(exc.message_dict)},
                                status=400)
        except Exception as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=500)


class ManagementPeriodUploadDocView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        file = request.FILES.get('contract_file')

        if not file:
            return JsonResponse({'success': False, 'message': 'No se seleccionó ningún archivo.'}, status=400)

        if not file.name.lower().endswith('.pdf'):
            return JsonResponse({'success': False, 'message': 'Solo se permiten archivos PDF.'}, status=400)

        if file.size > 2 * 1024 * 1024:
            return JsonResponse({'success': False, 'message': 'El archivo excede el límite de 2MB.'}, status=400)

        try:
            if period.signed_document and os.path.isfile(period.signed_document.path):
                os.remove(period.signed_document.path)

            period.signed_document = file
            period.updated_by = request.user
            period.save(update_fields=['signed_document', 'updated_by', 'updated_at'])

            return JsonResponse({
                'success': True,
                'message': 'Documento legalizado cargado correctamente.',
                'file_url': period.signed_document.url,
            })
        except Exception as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=500)


class ManagementPeriodDeleteDocView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        try:
            if period.signed_document:
                if os.path.isfile(period.signed_document.path):
                    os.remove(period.signed_document.path)

                period.signed_document = None
                period.updated_by = request.user
                period.save(update_fields=['signed_document', 'updated_by', 'updated_at'])
                return JsonResponse({'success': True, 'message': 'Documento eliminado del expediente.'})
            return JsonResponse({'success': False, 'message': 'No hay documento para eliminar.'})
        except Exception as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=500)


class ParseManagementPeriodIdentificationExcelView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.view_managementperiod'

    def post(self, request, *args, **kwargs):
        excel_file = request.FILES.get('identification_file')
        if not excel_file:
            return JsonResponse({'success': False, 'message': 'No se proporciono ningun archivo Excel.'}, status=400)

        if excel_file.size > 1 * 1024 * 1024:
            return JsonResponse(
                {'success': False, 'message': 'El archivo supera el limite maximo permitido de 1 MB.'},
                status=400,
            )

        if not (excel_file.name.endswith('.xlsx') or excel_file.name.endswith('.xls')):
            return JsonResponse(
                {'success': False, 'message': 'El archivo debe tener formato .xlsx o .xls.'},
                status=400,
            )

        try:
            workbook = openpyxl.load_workbook(excel_file, read_only=True, data_only=True)
            first_sheet = workbook.active
            identifications = []

            for row in first_sheet.iter_rows(values_only=True):
                if not row:
                    continue
                for cell_value in row:
                    if cell_value is not None:
                        clean_val = re.sub(r'[^0-9]', '', str(cell_value).strip())
                        if 9 <= len(clean_val) <= 13:
                            identifications.append(clean_val)

            workbook.close()
            unique_identifications = list(dict.fromkeys(identifications))

            if not unique_identifications:
                return JsonResponse({
                    'success': False,
                    'message': 'No se encontraron cedulas validas (9 a 13 digitos) en el archivo.',
                }, status=400)

            return JsonResponse({
                'success': True,
                'count': len(unique_identifications),
                'document_numbers': unique_identifications,
                'message': f'Se cargaron {len(unique_identifications)} cedula(s) correctamente.',
            })
        except Exception as exc:
            return JsonResponse({'success': False, 'message': f'Error al procesar el archivo: {str(exc)}'}, status=500)


class HistoricalManagementPeriodCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.add_managementperiod'
    template_name = 'contract/modals/modal_historical_period_form.html'

    def get(self, request):
        form = HistoricalManagementPeriodForm()
        html = render_to_string(self.template_name, {'form': form}, request=request)
        return JsonResponse({'success': True, 'html': html})

    def post(self, request):
        form = HistoricalManagementPeriodForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                period = HistoricalContractService.create_historical_period(form, request.user)
                return JsonResponse({
                    'success': True,
                    'message': f'Contrato histórico {period.document_number} registrado correctamente.',
                })
            except Exception as exc:
                return JsonResponse({'success': False, 'message': str(exc)}, status=500)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class HistoricalEmployeeSearchAPIView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()
        if len(term) < 3:
            return JsonResponse({'results': []})

        qs = Employee.objects.select_related('person', 'employment_status')
        for token in term.split():
            qs = qs.filter(
                Q(person__document_number__icontains=token)
                | Q(person__last_name__icontains=token)
                | Q(person__first_name__icontains=token)
            )

        results = []
        for emp in qs.order_by('person__last_name', 'person__first_name')[:25]:
            person = emp.person
            status_label = f" ({emp.employment_status.name})" if getattr(emp, 'employment_status', None) else ''
            results.append({
                'id': emp.id,
                'text': f"{person.document_number} - {person.last_name} {person.first_name}{status_label}",
            })
        return JsonResponse({'results': results})
