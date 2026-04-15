import base64
import json
import mimetypes
import os
import re
from pathlib import Path
from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Count, Prefetch
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, View

from budget.models import BudgetModificationHistory, BudgetAssignmentHistory
from core.models import CatalogItem
from core.models import SystemConfiguration
from employee.models import Employee
from person.models import Person
from institution.models import AdministrativeUnit
from schedule.models import Schedule
from core.models import User
from personnel_actions.models import ActionType, PersonnelAction
from .forms import LaborRegimeForm, ContractTypeForm
from .models import (
    LaborRegime,
    ContractType,
    ManagementPeriod,
    History,
    ContractTemplate,
    ContractTemplateSection,
)


def _normalize_contract_template_content(content):
    return (content or '').replace('\r\n', '\n').replace('\r', '\n').strip()


def _render_contract_inline_formatting(content):
    raw_text = str(content or '').replace('\r\n', '\n').replace('\r', '\n')
    safe_text = escape(raw_text)
    safe_text = safe_text.replace('\t', '&nbsp;' * 4)
    safe_text = re.sub(r' {2,}', lambda match: '&nbsp;' * len(match.group(0)), safe_text)
    safe_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'__(.+?)__', r'<u>\1</u>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[SIZE_DOWN\](.+?)\[/SIZE_DOWN\]', r'<span style="font-size:0.9em;">\1</span>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[SIZE_UP\](.+?)\[/SIZE_UP\]', r'<span style="font-size:1.1em;">\1</span>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[ALIGN_LEFT\](.+?)\[/ALIGN_LEFT\]', r'<span style="display:block; text-align:left;">\1</span>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[ALIGN_CENTER\](.+?)\[/ALIGN_CENTER\]', r'<span style="display:block; text-align:center;">\1</span>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[ALIGN_RIGHT\](.+?)\[/ALIGN_RIGHT\]', r'<span style="display:block; text-align:right;">\1</span>', safe_text, flags=re.DOTALL)
    return safe_text.replace('\n', '<br>')


def _is_action_template(contract_type):
    if not contract_type:
        return False

    category = (getattr(contract_type, 'contract_type_category', '') or '').upper().strip()
    if category == ContractType.TYPE_ACCION_PERSONAL:
        return True

    haystack = f"{getattr(contract_type, 'code', '') or ''} {getattr(contract_type, 'name', '') or ''}".upper()
    action_tokens = [
        'NOMBR',
        'ACCION DE PERSONAL',
        'ACCION_PERSONAL',
        'ASCENSO',
        'ENCARGO',
        'TRASPASO',
        'SUBROGACION',
        'REASIGN',
    ]
    return any(token in haystack for token in action_tokens)


def _get_contract_today_date():
    return timezone.now().date()


def _build_contract_user_full_name(user):
    if not user:
        return ''

    try:
        person = getattr(user, 'person', None)
        if person:
            full_name = (person.full_name or '').strip()
            if full_name:
                return full_name.upper()
    except Exception:
        pass

    full_name = (user.get_full_name() or '').strip()
    if full_name:
        return full_name.upper()

    return (user.username or '').strip().upper()


def _get_contract_letterhead_resource(request):
    configuration = SystemConfiguration.get_current()
    if configuration is None:
        configuration = SystemConfiguration.objects.filter(letterhead__isnull=False).exclude(letterhead='').order_by('-effective_date').first()

    if not configuration or not configuration.letterhead:
        return ''

    try:
        file_path = Path(configuration.letterhead.path)
        if file_path.exists():
            raw_bytes = file_path.read_bytes()
            mime_type, _ = mimetypes.guess_type(str(file_path))
            mime_type = mime_type or 'image/png'
            encoded = base64.b64encode(raw_bytes).decode('ascii')
            return f'data:{mime_type};base64,{encoded}'
    except Exception:
        pass

    try:
        return request.build_absolute_uri(configuration.letterhead.url)
    except Exception:
        return ''


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


class LaborRegimeTablePartialView(LoginRequiredMixin, View):
    def get(self, request):
        name = request.GET.get('name', '')
        is_active = request.GET.get('is_active', '')
        queryset = LaborRegime.objects.all().order_by('code')

        if name: queryset = queryset.filter(name__icontains=name)
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

        html = render_to_string('contract/partials/partial_labor_regime_table.html', {
            'regimes': queryset
        }, request=request)
        return JsonResponse({'table_html': html, 'stats': stats})


class LaborRegimeDetailAPIView(LoginRequiredMixin, View):
    def get(self, request, pk):
        regime = get_object_or_404(LaborRegime, pk=pk)
        return JsonResponse({
            'success': True,
            'regime': {
                'id': regime.id,
                'code': regime.code,
                'name': regime.name,
                'description': regime.description or '',
                'is_active': regime.is_active
            }
        })


class ContractTypeListView(LoginRequiredMixin, View):
    """
    Retorna los tipos de contrato vinculados a un régimen laboral específico.
    """

    def get(self, request, regime_id):
        regime = get_object_or_404(LaborRegime, pk=regime_id)
        types = regime.contract_types.all().order_by('name')

        data = [{
            'id': t.id,
            'code': t.code,
            'name': t.name,
            'category': t.contract_type_category,
            'category_display': t.get_contract_type_category_display(),
            'is_active': t.is_active
        } for t in types]

        return JsonResponse({'success': True, 'contract_types': data})


class ContractTypeCreateView(LoginRequiredMixin, View):
    """
    Crea un nuevo tipo de contrato vinculado a un régimen.
    Diseñado para ser llamado vía AJAX desde SweetAlert2.
    """

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
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error interno: {str(e)}'
                }, status=500)

        # Enviamos los errores de validación (ej: código duplicado)
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class ContractTypeToggleStatusView(LoginRequiredMixin, View):
    """
    Alterna el estado activo/inactivo de una modalidad.
    """

    def post(self, request, pk):
        instance = get_object_or_404(ContractType, pk=pk)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save()
        return JsonResponse({
            'success': True,
            'message': f'Estado de "{instance.name}" actualizado.'
        })


class LaborRegimeCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Procesa la creación de un nuevo régimen laboral."""
    permission_required = 'contract.add_laborregime'

    def post(self, request):
        form = LaborRegimeForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    instance = form.save(commit=False)
                    instance.created_by = request.user  # Auditoría BaseModel
                    instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Régimen Laboral creado exitosamente.'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error al guardar: {str(e)}'
                }, status=500)

        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class LaborRegimeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Procesa la actualización de un régimen existente."""
    permission_required = 'contract.change_laborregime'

    def post(self, request, pk):
        instance = get_object_or_404(LaborRegime, pk=pk)
        form = LaborRegimeForm(request.POST, instance=instance)

        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_instance = form.save(commit=False)
                    updated_instance.updated_by = request.user  # Auditoría BaseModel
                    updated_instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Régimen Laboral actualizado correctamente.'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error al actualizar: {str(e)}'
                }, status=500)

        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class LaborRegimeToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Alterna el estado is_active (Alta/Baja) de un régimen."""
    permission_required = 'contract.change_laborregime'

    def post(self, request, pk):
        instance = get_object_or_404(LaborRegime, pk=pk)
        # Cambiamos el estado (Toggle logic)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save()

        message = "Régimen activado (Alta)" if instance.is_active else "Régimen desactivado (Baja)"
        return JsonResponse({
            'success': True,
            'message': message
        })


class ContractTypeUpdateView(LoginRequiredMixin, View):
    """
    Actualiza un tipo de contrato existente.
    """

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
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)}, status=500)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ContractTemplateEditorCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    def _seed_action_template_sections(self, template, user):
        existing_sections = list(template.sections.filter(is_active=True).order_by('order'))
        if len(existing_sections) >= 6:
            return

        for index in range(len(existing_sections), 6):
            ContractTemplateSection.objects.create(
                template=template,
                section_type='PARAGRAPH',
                content='',
                order=index,
                created_by=user,
                updated_by=user,
            )

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

        if _is_action_template(contract_type):
            self._seed_action_template_sections(template, request.user)

        return redirect('contract:template_editor_detail', pk=template.pk)


class ContractTemplateEditorDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    def get(self, request, pk):
        template = get_object_or_404(
            ContractTemplate.objects.select_related('contract_type__labor_regime'),
            pk=pk,
        )
        is_action_template = _is_action_template(template.contract_type)
        action_template_fields = []

        if is_action_template:
            if template.sections.filter(is_active=True).count() < 6:
                existing_sections = list(template.sections.filter(is_active=True).order_by('order'))
                for index in range(len(existing_sections), 6):
                    ContractTemplateSection.objects.create(
                        template=template,
                        section_type='PARAGRAPH',
                        content='',
                        order=index,
                        created_by=request.user,
                        updated_by=request.user,
                    )

            sections = list(template.sections.filter(is_active=True).order_by('order'))[:6]
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

        available_mappings = [
            {'placeholder': '[FULL_NAME]', 'label': 'Nombre completo de la persona'},
            {'placeholder': '[DOCUMENT_NUMBER]', 'label': 'Cédula / documento de identidad'},
            {'placeholder': '[DOC_NUMBER]', 'label': 'Número del contrato/acción de personal'},
            {'placeholder': '[CONTRACT_TYPE]', 'label': 'Nombre de la modalidad'},
            {'placeholder': '[DOCUMENT_CATEGORY]', 'label': 'Etiqueta Contrato o Acción de Personal'},
            {'placeholder': '[LABOR_REGIME]', 'label': 'Régimen laboral'},
            {'placeholder': '[POSITION]', 'label': 'Cargo'},
            {'placeholder': '[REMUNERATION]', 'label': 'Remuneración'},
            {'placeholder': '[UNIT]', 'label': 'Unidad administrativa'},
            {'placeholder': '[WORKPLACE]', 'label': 'Lugar de trabajo'},
            {'placeholder': '[SCHEDULE]', 'label': 'Horario'},
            {'placeholder': '[START_DATE]', 'label': 'Fecha de inicio (dd/mm/aaaa)'},
            {'placeholder': '[END_DATE]', 'label': 'Fecha de fin (dd/mm/aaaa o INDEFINIDO)'},
            {'placeholder': '[today]', 'label': 'Fecha actual en español'},
            {'placeholder': '[YEAR]', 'label': 'Año actual'},
            {'placeholder': '[ACTION_ISSUE_DATE]', 'label': 'Fecha de elaboración de acción'},
            {'placeholder': '[ACTION_EFFECTIVE_FROM]', 'label': 'Fecha rige desde'},
            {'placeholder': '[ACTION_EFFECTIVE_TO]', 'label': 'Fecha rige hasta'},
            {'placeholder': '[MOTIVATION]', 'label': 'Motivación de la acción'},
            {'placeholder': '[EXPLANATION]', 'label': 'Explicación de la acción'},
            {'placeholder': '[ACTION_EXPLANATION_HEADER]', 'label': 'Encabezado de explicación de acción'},
            {'placeholder': '[PREPARED_BY]', 'label': 'Usuario que elaboró el documento'},
            {'placeholder': '[AUTHORITY_1]', 'label': 'Máxima autoridad'},
        ]

        context = {
            'template': template,
            'available_mappings': available_mappings,
            'is_action_template': is_action_template,
            'action_template_fields': action_template_fields,
            'action_types': [
                {
                    'id': item.id,
                    'name': item.name,
                }
                for item in _get_action_types_for_template()
            ],
            'authorities': [
                {
                    'id': item.id,
                    'name': item.name,
                    'position': item.position,
                }
                for item in _get_authorities_for_template()
            ],
        }
        template_name = 'contract/template_editor/action_template_editor.html' if is_action_template else 'contract/template_editor/template_editor.html'
        return render(request, template_name, context)


class ContractTemplateEditorOptionsAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    def get(self, request):
        action_types = [
            {
                'id': item.id,
                'name': item.name,
            }
            for item in _get_action_types_for_template()
        ]
        authorities = [
            {
                'id': item.id,
                'name': item.name,
                'position': item.position,
            }
            for item in _get_authorities_for_template()
        ]
        return JsonResponse({
            'success': True,
            'action_types': action_types,
            'authorities': authorities,
        })


def _build_contract_replacements(period):
    today = _get_contract_today_date()
    person = period.employee.person
    category_label = 'ACCIÓN DE PERSONAL' if period.contract_type.contract_type_category == ContractType.TYPE_ACCION_PERSONAL else 'CONTRATO'
    elaboration_date = period.elaboration_date.strftime('%d/%m/%Y') if getattr(period, 'elaboration_date', None) else '-'

    return {
        '[FULL_NAME]': person.full_name or '-',
        '[DOCUMENT_NUMBER]': person.document_number or '-',
        '[DOC_NUMBER]': period.document_number or '-',
        '[CONTRACT_TYPE]': period.contract_type.name or '-',
        '[DOCUMENT_CATEGORY]': category_label,
        '[LABOR_REGIME]': period.contract_type.labor_regime.name or '-',
        '[POSITION]': period.display_position or '-',
        '[REMUNERATION]': str(period.display_remuneration) if period.display_remuneration is not None else '-',
        '[UNIT]': period.administrative_unit.name if period.administrative_unit else '-',
        '[WORKPLACE]': period.workplace or '-',
        '[SCHEDULE]': period.schedule.name if period.schedule else '-',
        '[START_DATE]': period.start_date.strftime('%d/%m/%Y') if period.start_date else '-',
        '[END_DATE]': period.end_date.strftime('%d/%m/%Y') if period.end_date else 'INDEFINIDO',
        '[today]': today.strftime('%d/%m/%Y'),
        '[YEAR]': str(today.year),
        '[ACTION_ISSUE_DATE]': elaboration_date,
        '[ACTION_EFFECTIVE_FROM]': period.start_date.strftime('%d/%m/%Y') if period.start_date else '-',
        '[ACTION_EFFECTIVE_TO]': period.end_date.strftime('%d/%m/%Y') if period.end_date else '-',
        '[MOTIVATION]': period.action_motivation or '-',
        '[EXPLANATION]': period.action_explanation or '-',
        '[ACTION_EXPLANATION_HEADER]': 'Se hace constar la siguiente acción de personal:',
        '[PREPARED_BY]': _build_contract_user_full_name(period.created_by),
        '[AUTHORITY_1]': (getattr(SystemConfiguration.get_current(), 'max_authority_name', '') or '').strip().upper(),
        '[EMPLOYEE_FULL_NAME]': person.full_name or '-',
    }


def _render_contract_sections_html(template, replacements):
    rows = []
    sections = template.sections.filter(is_active=True).order_by('order')
    for section in sections:
        content = section.content or ''
        for placeholder, replacement in replacements.items():
            content = content.replace(placeholder, replacement)

        rendered = _render_contract_inline_formatting(content)
        if section.section_type == 'TITLE':
            rows.append(f'<h4 style="text-align:left; margin-top:0.9rem; margin-bottom:0.35rem; font-size:1rem;">{rendered}</h4>')
        else:
            rows.append(f'<p style="text-align:justify; margin-bottom:0.6rem; line-height:1.42; font-size:0.95rem;">{rendered}</p>')

    return ''.join(rows)


class ContractTemplateSectionCreateAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    @method_decorator(require_http_methods(['POST']))
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(self.permission_required):
            return JsonResponse({'success': False, 'error': 'No tiene permisos para agregar secciones.'}, status=403)
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
        if not request.user.has_perm(self.permission_required):
            return JsonResponse({'success': False, 'error': 'No tiene permisos para editar secciones.'}, status=403)
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
        if not request.user.has_perm(self.permission_required):
            return JsonResponse({'success': False, 'error': 'No tiene permisos para eliminar secciones.'}, status=403)
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
        if not request.user.has_perm(self.permission_required):
            return JsonResponse({'success': False, 'error': 'No tiene permisos para reordenar secciones.'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, template_id):
        template = get_object_or_404(ContractTemplate, pk=template_id)
        try:
            data = json.loads(request.body)
            for item in data.get('sections', []):
                section = ContractTemplateSection.objects.get(pk=item['id'], template=template)
                section.order = item['order']
                section.updated_by = request.user
                section.save(update_fields=['order', 'updated_by', 'updated_at'])
            return JsonResponse({'success': True})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=500)


class ContractTemplatePreviewAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.change_contracttype'

    def get(self, request, template_id):
        try:
            template = get_object_or_404(
                ContractTemplate.objects.select_related('contract_type__labor_regime'),
                pk=template_id,
            )
            is_action_template = _is_action_template(template.contract_type)

            if is_action_template:
                sections = list(template.sections.filter(is_active=True).order_by('order'))
                selected_action_type = ActionType.objects.filter(
                    pk=(sections[0].content or '').strip(),
                    is_active=True,
                ).first() if len(sections) > 0 else None
                selected_authority_1 = User.objects.filter(
                    pk=(sections[1].content or '').strip(),
                    is_active=True,
                ).first() if len(sections) > 1 else None
                selected_authority_2 = User.objects.filter(
                    pk=(sections[2].content or '').strip(),
                    is_active=True,
                ).first() if len(sections) > 2 else None
                selected_reviewer = User.objects.filter(
                    pk=(sections[3].content or '').strip(),
                    is_active=True,
                ).first() if len(sections) > 3 else None
                selected_elaboration = User.objects.filter(
                    pk=(sections[4].content or '').strip(),
                    is_active=True,
                ).first() if len(sections) > 4 else None
                selected_register = User.objects.filter(
                    pk=(sections[5].content or '').strip(),
                    is_active=True,
                ).first() if len(sections) > 5 else None

                preview_html = f'''
                <div style="max-width: 800px; margin: 1rem auto; padding: 2rem; border: 1px solid #ddd; background: white;">
                    <div style="text-align:center; font-weight:bold; margin-bottom:1rem; font-size:1.05rem;">ACCIÓN DE PERSONAL</div>
                    <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 1rem;">
                        <div><strong>Tipo de Acción:</strong><br>{(selected_action_type.name if selected_action_type else 'Pendiente')}</div>
                        <div><strong>Autoridad 1:</strong><br>{(selected_authority_1.name if selected_authority_1 else 'Pendiente')}</div>
                        <div><strong>Autoridad 2:</strong><br>{(selected_authority_2.name if selected_authority_2 else 'Pendiente')}</div>
                        <div><strong>Revisado Por:</strong><br>{(selected_reviewer.name if selected_reviewer else 'Pendiente')}</div>
                        <div><strong>Elaborado Por:</strong><br>{(selected_elaboration.name if selected_elaboration else 'Pendiente')}</div>
                        <div><strong>Registrado Por:</strong><br>{(selected_register.name if selected_register else 'Pendiente')}</div>
                    </div>
                    <p style="margin:0; color:#6b7280; font-size:0.9rem;">Esta plantilla se complementa con los datos que se registran en el paso 3 del inicio de gestión.</p>
                </div>
                '''
                return JsonResponse({'preview': preview_html})

            period = ManagementPeriod.objects.select_related(
                'employee__person',
                'contract_type__labor_regime',
                'administrative_unit',
                'schedule',
                'budget_line__position_item',
            ).filter(contract_type=template.contract_type).order_by('-created_at').first()

            if not period:
                replacements = {
                    '[DOC_NUMBER]': 'PENDIENTE',
                    '[today]': _get_contract_today_date().strftime('%d/%m/%Y'),
                }
            else:
                replacements = _build_contract_replacements(period)

            sections_html = _render_contract_sections_html(template, replacements)
            doc_number = replacements.get('[DOC_NUMBER]', 'PENDIENTE')

            if not sections_html:
                sections_html = '<p style="text-align:justify; margin-bottom:0.6rem; line-height:1.42; font-size:0.95rem;">Agregue párrafos en el editor para visualizar el cuerpo del contrato.</p>'

            preview_html = f'''
            <div style="max-width: 800px; margin: 1rem auto; padding: 2.4rem 2rem 1.4rem; border: 1px solid #ddd; background: white;">
                <div style="text-align:center; font-weight:bold; margin-bottom:1.2rem; font-size:1.08rem;">CONTRATO NRO. {doc_number}</div>
                <div style="text-align:left; margin-bottom:1.1rem; font-size:0.92rem;">Loja, {replacements.get('[today]', '')}</div>
                <div class="template-sections">{sections_html}</div>
            </div>
            '''

            return JsonResponse({'preview': preview_html})
        except Exception:
            fallback_html = f'''
            <div style="max-width: 800px; margin: 1rem auto; padding: 2.4rem 2rem 1.4rem; border: 1px solid #ddd; background: white;">
                <div style="text-align:center; font-weight:bold; margin-bottom:1.2rem; font-size:1.08rem;">CONTRATO NRO. PENDIENTE</div>
                <div style="text-align:left; margin-bottom:1.1rem; font-size:0.92rem;">Loja, {_get_contract_today_date().strftime('%d/%m/%Y')}</div>
                <div class="template-sections">
                    <p style="text-align:justify; margin-bottom:0.6rem; line-height:1.42; font-size:0.95rem;">No fue posible cargar todos los datos de la vista previa. Puede continuar editando la plantilla.</p>
                </div>
            </div>
            '''
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
        replacements = _build_contract_replacements(period)
        is_action_document = period.contract_type.contract_type_category == ContractType.TYPE_ACCION_PERSONAL
        document_label = 'ACCIÓN DE PERSONAL' if is_action_document else 'CONTRATO'

        if template:
            body_html = _render_contract_sections_html(template, replacements)
        elif is_action_document:
            body_html = ''.join([
                f'<p style="margin-bottom:0.4rem;"><strong>FECHA DE ELABORACIÓN:</strong> {replacements.get("[ACTION_ISSUE_DATE]", "-")}</p>',
                f'<p style="margin-bottom:0.4rem;"><strong>RIGE DESDE:</strong> {replacements.get("[ACTION_EFFECTIVE_FROM]", "-")} &nbsp;&nbsp; <strong>HASTA:</strong> {replacements.get("[ACTION_EFFECTIVE_TO]", "-")}</p>',
                '<h4 style="text-align:left; margin-top:0.9rem; margin-bottom:0.35rem; font-size:1rem;">MOTIVACIÓN Y EXPLICACIÓN</h4>',
                f'<p style="text-align:justify; margin-bottom:0.6rem; line-height:1.42; font-size:0.95rem;"><strong>MOTIVACIÓN:</strong> {replacements.get("[MOTIVATION]", "-")}</p>',
                f'<p style="text-align:justify; margin-bottom:0.6rem; line-height:1.42; font-size:0.95rem;">{replacements.get("[EXPLANATION]", "-")}</p>',
            ])
        else:
            body_html = _render_contract_inline_formatting(
                f"Se certifica que {replacements['[FULL_NAME]']} con documento {replacements['[DOCUMENT_NUMBER]']} "
                f"mantiene un vínculo bajo la modalidad {replacements['[CONTRACT_TYPE]']} "
                f"en el régimen {replacements['[LABOR_REGIME]']}, desde {replacements['[START_DATE]']} "
                f"hasta {replacements['[END_DATE]']}."
            )
            body_html = f'<p style="text-align:justify; margin-bottom:0.6rem; line-height:1.42; font-size:0.95rem;">{body_html}</p>'

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
        prepared_by = _build_contract_user_full_name(period.created_by)

        context = {
            'document_label': document_label,
            'document_number': replacements.get('[DOC_NUMBER]', '-'),
            'today': replacements.get('[today]', _get_contract_today_date().strftime('%d/%m/%Y')),
            'city': city,
            'letterhead_path': _get_contract_letterhead_resource(request),
            'authority_name': authority_name,
            'authority_position': authority_position,
            'employee_full_name': employee_full_name,
            'prepared_by': prepared_by,
            'is_pdf': True,
            'body_html': mark_safe(body_html),
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



class ManagementPeriodListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ManagementPeriod
    template_name = 'contract/management_period_list.html'
    permission_required = 'contract.view_managementperiod'
    context_object_name = 'periods'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = ManagementPeriod.objects.filter(is_active=True)

        # Estadísticas dinámicas: realizar en una sola agregación para reducir consultas
        aggs = qs.aggregate(
            total_active=Count('id'),
            count_losep=Count('id', filter=Q(contract_type__labor_regime__code='LOSEP')),
            count_ct=Count('id', filter=Q(contract_type__labor_regime__code='CT'))
        )
        context['total_active'] = aggs.get('total_active', 0)
        context['count_losep'] = aggs.get('count_losep', 0)
        context['count_ct'] = aggs.get('count_ct', 0)

        context['regimes'] = LaborRegime.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                'contract_types',
                queryset=ContractType.objects.filter(is_active=True).order_by('name'),
                to_attr='active_contract_types'
            )
        )
        context['schedules'] = Schedule.objects.filter(is_active=True)
        context['units'] = AdministrativeUnit.objects.filter(is_active=True)

        return context


class ManagementPeriodNotificationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ManagementPeriod
    template_name = 'contract/management_period_notification_list.html'
    permission_required = 'contract.view_managementperiod'
    context_object_name = 'periods'
    paginate_by = 10

    def get_ordering(self):
        sort = (self.request.GET.get('sort') or 'end_date').strip()
        direction = (self.request.GET.get('direction') or 'asc').strip().lower()
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


class ValidateEmployeeAPIView(LoginRequiredMixin, View):
    def get(self, request, doc_number):
        try:
            contract_type_id = request.GET.get('contract_type_id')
            contract_type = ContractType.objects.filter(pk=contract_type_id).first() if contract_type_id else None
            contract_code = (contract_type.code if contract_type else '').upper()
            contract_category = (contract_type.contract_type_category if contract_type else '').upper()
            is_professional_service = contract_code == 'SERVICIOS_PROFESIONALES'

            # 1. Buscar la persona por cédula (incluye ex empleados con persona inactiva)
            person = Person.objects.filter(document_number=doc_number).first()
            if not person:
                return JsonResponse({
                    'success': False,
                    'message': 'Cédula no registrada.'
                })

            # 2. Si existe un empleado activo relacionado, bloquear (no debe ser empleado activo)
            active_employee = Employee.objects.filter(person=person, is_active=True).first()
            if active_employee:
                return JsonResponse({
                    'success': False,
                    'message': 'Atención: la persona ya es un empleado activo.'
                })

            # 3. Buscar un registro de Employee vinculado que tenga una partida presupuestaria asignada
            employees = Employee.objects.filter(person=person).select_related('person').prefetch_related('current_budget_line__position_item')
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

            # 4. Verificar si ya tiene contrato formal activo
            has_active = ManagementPeriod.objects.filter(
                employee=employee_selected, status__code='ACTIVO'
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
                    'requires_manual_compensation': is_professional_service
                },
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class GetAvailableBudgetLinesAPIView(LoginRequiredMixin, View):
    def get(self, request, unit_id):
        # Buscamos partidas que estén LIBRES para esa unidad
        from budget.models import BudgetLine

        # Ajusta este filtro según cómo vinculaste la Unidad con la Partida
        lines = BudgetLine.objects.filter(
            # Ejemplo: Si la partida tiene relación con la unidad o vía actividad
            status_item__code='LIBRE',
            is_active=True
        ).select_related('position_item')

        data = [{
            'id': l.id,
            'number_individual': l.number_individual or l.code,
            'position_name': l.position_item.name if l.position_item else 'SIN CARGO',
            'remuneration': str(l.remuneration)
        } for l in lines]

        return JsonResponse({'success': True, 'lines': data})


class ManagementPeriodTablePartialView(LoginRequiredMixin, View):
    def get(self, request):
        # 1. Filtros
        q = request.GET.get('q', '').strip()
        regime_code_filter = request.GET.get('regime_code', '').strip()
        unit_id = request.GET.get('unit', '')
        status_code = request.GET.get('status_code', '')

        # 2. QuerySet REALMENTE Optimizado
        queryset = ManagementPeriod.objects.select_related(
            'employee__person',
            'budget_line__position_item',
            'contract_type__labor_regime',
            'administrative_unit',
            'status'
        ).order_by('-created_at')

        # 3. Filtros (Igual que antes pero sin evaluar el queryset todavía)
        if q:
            queryset = queryset.filter(
                Q(employee__person__first_name__icontains=q) |
                Q(employee__person__last_name__icontains=q) |
                Q(employee__person__document_number__icontains=q) |
                Q(document_number__icontains=q) |
                Q(manual_position__icontains=q)
            )
        if regime_code_filter:
            queryset = queryset.filter(contract_type__labor_regime__code=regime_code_filter)
        if unit_id:
            queryset = queryset.filter(administrative_unit_id=unit_id)
        if status_code:
            queryset = queryset.filter(status__code=status_code)

        # 4. Paginación de Servidor (Aquí es donde ocurre la magia)
        from django.core.paginator import Paginator, EmptyPage
        page = int(request.GET.get('page', 1))
        page_size = 10  # Mostrar 10 registros por página (consistente con otras tablas)

        paginator = Paginator(queryset, page_size)
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(1)

        # 5. Renderizado (Solo procesará 50 filas, no 6450)
        html = render_to_string(
            'contract/partials/partial_management_period_table.html',
            {'periods': page_obj},
            request=request
        )

        # 6. Estadísticas Dinámicas para las tarjetas superiores
        regimes_stats = LaborRegime.objects.filter(is_active=True).annotate(
            count=Count('contract_types__management_periods',
                        filter=Q(contract_types__management_periods__is_active=True))
        ).values('code', 'name', 'count')
        total_active = ManagementPeriod.objects.filter(is_active=True).count()

        return JsonResponse({
            'success': True,
            'table_html': html,
            'stats': {
                'total': total_active,
                'regimes': list(regimes_stats)
            },
            'pagination': {
                'total': paginator.count,
                'page': page_obj.number,
                'has_next': page_obj.has_next(),
                'has_prev': page_obj.has_previous(),
                'start': page_obj.start_index(),
                'end': page_obj.end_index(),
            }
        })


class ManagementPeriodTerminateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Finaliza un contrato y libera automáticamente la partida presupuestaria.
    """
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        reason = request.POST.get('reason', '').strip()
        end_date_raw = request.POST.get('end_date', '').strip()

        if not reason:
            return JsonResponse({'success': False, 'message': 'El motivo de salida es obligatorio.'}, status=400)
        if not end_date_raw:
            return JsonResponse({'success': False, 'message': 'La fecha fin de gestión es obligatoria.'}, status=400)

        try:
            end_date = datetime.strptime(end_date_raw, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Formato de fecha fin inválido.'}, status=400)

        if period.start_date and end_date < period.start_date:
            return JsonResponse({
                'success': False,
                'message': 'La fecha fin de gestión no puede ser menor a la fecha de inicio.'
            }, status=400)

        release_concept = 'Finalizacion de gestion laboral'

        try:
            with transaction.atomic():
                # 1. Obtener estados
                finalizado_status = CatalogItem.objects.get(catalog__code='STATUS_CONTRACT', code='FINALIZADO')
                libre_status = CatalogItem.objects.get(catalog__code='BUDGET_STATUS', code='LIBRE')
                current_status = period.employee.employment_status.code

                # 2. Finalizar el Periodo
                period.status = finalizado_status
                period.end_date = end_date
                period.updated_by = request.user
                period.save()

                mapping = {
                    'EMPLEADO': 'EX_EMPLEADO',
                    'TRABAJADOR': 'EX_TRABAJADOR',
                    'CONTRATADO': 'EX_EMPLEADO',
                    'PROFESIONAL': 'EX_PROFESIONAL'
                }
                exit_status = mapping.get(current_status, 'PERSONA')
                period.employee.set_status(exit_status)

                # Cambiar is_active del empleado a False
                period.employee.is_active = False
                period.employee.save()

                # 3. Liberar la Partida
                budget_line = period.budget_line
                if not budget_line:
                    return JsonResponse({
                        'success': False,
                        'message': 'El período de gestión no tiene una partida presupuestaria asignada.'
                    }, status=400)

                # 3.1 Cerrar historial de asignación con la misma fecha/observación de finalización
                assignment_history = BudgetAssignmentHistory.objects.filter(
                    budget_line=budget_line,
                    employee=period.employee,
                    is_current=True
                ).first()
                if assignment_history:
                    if assignment_history.start_date and end_date < assignment_history.start_date:
                        return JsonResponse({
                            'success': False,
                            'message': 'La fecha fin no puede ser menor a la fecha de inicio en el historial de partida.'
                        }, status=400)
                    assignment_history.end_date = end_date
                    assignment_history.is_current = False
                    assignment_history.observation = release_concept
                    assignment_history.save()

                budget_line.status_item = libre_status
                budget_line.current_employee = None
                budget_line.save(modified_by=request.user)

                # 4. Registro en historial de contrato
                History.objects.create(
                    employee=period.employee,
                    contract=period,
                    user_register=request.user.get_full_name() or request.user.username,
                    type='TERMINACIÓN',
                    reason=reason
                )

                # 5. Auditoría en historial de partida
                BudgetModificationHistory.objects.create(
                    budget_line=budget_line,
                    modified_by=request.user,
                    modification_type='RELEASE',
                    field_name='Estado y Ocupante',
                    old_value=f"Ocupada por {period.employee.person.full_name}",
                    new_value="LIBRE / VACANTE",
                    reason=release_concept
                )

            return JsonResponse({
                'success': True,
                'message': 'Gestión finalizada, partida liberada y registro guardado en el historial.'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error técnico: {str(e)}'}, status=500)


class ManagementPeriodCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.add_managementperiod'

    def post(self, request):
        data = request.POST
        try:
            with transaction.atomic():
                status_initial = CatalogItem.objects.get(
                    catalog__code='STATUS_CONTRACT', code='SIN_FIRMAR'
                )

                employee = get_object_or_404(Employee, pk=data.get('employee'))
                contract_type = get_object_or_404(ContractType, pk=data.get('contract_type'))
                is_professional_service = (contract_type.code or '').upper() == 'SERVICIOS_PROFESIONALES'
                is_action_document = contract_type.contract_type_category == ContractType.TYPE_ACCION_PERSONAL

                budget_line = None if is_professional_service else employee.current_budget_line.first()

                if not is_professional_service and not budget_line:
                    return JsonResponse({
                        'success': False,
                        'message': 'La persona no tiene una partida presupuestaria asignada. Debe asignarle una partida antes de pasar al tercer paso.'
                    }, status=400)

                manual_position = data.get('manual_position', '').strip().upper()
                manual_remuneration = data.get('manual_remuneration')
                elaboration_date = data.get('elaboration_date') or None
                action_motivation = data.get('action_motivation', '').strip().upper()
                action_explanation = data.get('action_explanation', '').strip()

                if is_action_document and (not elaboration_date or not data.get('start_date') or not action_motivation or not action_explanation):
                    return JsonResponse({
                        'success': False,
                        'message': 'Para ACCIÓN DE PERSONAL debe completar fecha de elaboración, rige desde, motivación y explicación.'
                    }, status=400)

                if is_professional_service and (not manual_position or not manual_remuneration):
                    return JsonResponse({
                        'success': False,
                        'message': 'Para SERVICIOS_PROFESIONALES debe ingresar cargo y remuneración manual.'
                    }, status=400)

                administrative_unit_id = data.get('administrative_unit')
                schedule_id = data.get('schedule') if not is_action_document else None
                workplace = data.get('workplace', '').strip().upper() if not is_action_document else None
                job_functions = data.get('job_functions', '').strip() if not is_action_document else ''
                institutional_need_memo = data.get('institutional_need_memo', '').strip().upper() if not is_action_document else None
                budget_certification = data.get('budget_certification', '').strip().upper() if not is_action_document else None

                if is_action_document and not administrative_unit_id:
                    return JsonResponse({
                        'success': False,
                        'message': 'Para ACCIÓN DE PERSONAL debe seleccionar la unidad administrativa de destino.'
                    }, status=400)

                # Creamos la instancia SIN document_number (el save() lo pondrá)
                period = ManagementPeriod(
                    employee=employee,
                    budget_line=budget_line,
                    contract_type=contract_type,
                    administrative_unit_id=administrative_unit_id,
                    schedule_id=schedule_id,
                    status=status_initial,
                    manual_position=manual_position or None,
                    manual_remuneration=manual_remuneration or None,

                    # Estos campos se mantienen manuales
                    institutional_need_memo=institutional_need_memo,
                    budget_certification=budget_certification,
                    workplace=workplace,
                    job_functions=job_functions,
                    elaboration_date=elaboration_date or None,
                    start_date=data.get('start_date'),
                    end_date=data.get('end_date') if data.get('end_date') else None,
                    action_motivation=action_motivation or None,
                    action_explanation=action_explanation or None,
                    created_by=request.user
                )

                period.full_clean()
                period.save()  # Aquí se dispara la secuencia y el update del Employee

                # Si se solicitó marcar como jefe inmediato, actualizar employee.is_boss y unit.boss
                try:
                    is_boss_flag = data.get('is_boss')
                    is_boss = str(is_boss_flag).lower() in ('1', 'true', 'on', 'yes')
                    if is_boss:
                        try:
                            employee.is_boss = True
                            employee.save(update_fields=['is_boss'])
                        except Exception as e:
                            print(f"No se pudo marcar employee.is_boss=True: {e}")

                        try:
                            unit = AdministrativeUnit.objects.filter(pk=period.administrative_unit_id).first()
                            if unit:
                                unit.boss = employee
                                unit.save(update_fields=['boss'])
                        except Exception as e:
                            print(f"No se pudo actualizar AdministrativeUnit.boss: {e}")
                except Exception:
                    pass

                return JsonResponse({
                    'success': True,
                    'message': f'Gestión {period.document_number} registrada y área del empleado actualizada.'
                })

        except ValidationError as e:
            # Esto le dirá EXACTAMENTE qué campo falla en la consola de PyCharm
            return JsonResponse({'success': False, 'errors': e.message_dict}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ManagementPeriodSignView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Acción para legalizar/firmar el contrato."""
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(
            ManagementPeriod.objects.select_related('contract_type', 'personnel_action', 'employee__person'),
            pk=pk
        )
        try:
            with transaction.atomic():
                status_signed = CatalogItem.objects.get(
                    catalog__code='STATUS_CONTRACT',
                    code='FIRMADO'
                )
                period.status = status_signed
                period.updated_by = request.user
                period.save()
                regime = period.contract_type.labor_regime.code  # LOSEP, CT, etc.
                ctype = period.contract_type.code
                new_status = 'EMPLEADO'
                if regime == 'CT':
                    new_status = 'TRABAJADOR'
                elif regime == 'LOSEP':
                    if 'OCASIONAL' in ctype:
                        new_status = 'CONTRATADO'
                    elif 'PROFESIONAL' in ctype:
                        new_status = 'PROFESIONAL'
                    else:
                        new_status = 'EMPLEADO'
                period.employee.set_status(new_status)

                # Cuando el contrato está FIRMADO, el empleado debe estar activo
                try:
                    if not period.employee.is_active:
                        period.employee.is_active = True
                        period.employee.save(update_fields=['is_active'])
                except Exception as e:
                    print(f"No se pudo activar employee tras firma (id={getattr(period.employee,'id',None)}): {e}")

                # --- REGISTRO EN HISTORIAL DE CONTRATO ---
                is_action_document = period.contract_type.contract_type_category == ContractType.TYPE_ACCION_PERSONAL
                History.objects.create(
                    employee=period.employee,
                    contract=period,
                    user_register=request.user.get_full_name() or request.user.username,
                    type='FIRMA',
                    reason='ACCIÓN LEGALIZADA' if is_action_document else 'CONTRATO FIRMADO'
                )

                # --- REGISTRO EN HISTORIAL DE HORARIOS ---
                if period.schedule_id:
                    from schedule.models import EmployeeScheduleHistory
                    EmployeeScheduleHistory.objects.create(
                        employee=period.employee,
                        schedule=period.schedule,
                        start_date=period.start_date,
                        end_date=period.end_date,
                        reason='Asignación de Horario',
                        is_current=True,
                        created_by=request.user
                    )

                if is_action_document and period.personnel_action_id and not period.personnel_action.is_registered:
                    period.personnel_action.is_registered = True
                    period.personnel_action.save(update_fields=['is_registered'])

            return JsonResponse({
                'success': True,
                'message': 'La acción ha sido legalizada y registrada.' if is_action_document else 'El contrato ha sido legalizado y registrado en el historial.'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ManagementPeriodDetailAPIView(LoginRequiredMixin, View):
    """Retorna el JSON con todos los datos para el Expediente y el formulario de edición"""

    def get(self, request, pk):
        p = get_object_or_404(ManagementPeriod, pk=pk)
        return JsonResponse({
            'success': True,
            'period': {
                'id': p.id,
                'signed_document_url': p.signed_document.url if p.signed_document else None,
                'document_number': p.document_number,
                'employee_name': p.employee.person.full_name,
                'employee_photo': p.employee.person.photo.url if p.employee.person.photo else None,
                'status_name': p.status.name,
                'status_code': p.status.code,
                'budget_line_number': (p.budget_line.number_individual or p.budget_line.code) if p.budget_line else 'SIN PARTIDA',
                'position_name': p.display_position,
                'remuneration': str(p.display_remuneration) if p.display_remuneration is not None else '-',
                'unit_name': p.administrative_unit.name if p.administrative_unit else '',
                'institutional_need_memo': p.institutional_need_memo or '',
                'budget_certification': p.budget_certification or '',
                'elaboration_date': p.elaboration_date.isoformat() if p.elaboration_date else '',
                'elaboration_date_formatted': p.elaboration_date.strftime('%d/%m/%Y') if p.elaboration_date else '',
                'start_date': p.start_date.isoformat() if p.start_date else '',  # Formato YYYY-MM-DD para el input date
                'start_date_formatted': p.start_date.strftime('%d/%m/%Y') if p.start_date else '',
                'end_date': p.end_date.isoformat() if p.end_date else '',
                'end_date_formatted': p.end_date.strftime('%d/%m/%Y') if p.end_date else 'INDEFINIDO',
                'schedule_id': p.schedule.id if p.schedule else '',
                'schedule_name': p.schedule.name if p.schedule else '',
                'workplace': p.workplace or '',
                'contract_type_name': p.contract_type.name,
                'contract_type_category': p.contract_type.contract_type_category,
                'personnel_action_id': p.personnel_action_id,
                'personnel_action_pdf_url': (
                    reverse('personnel_actions:action_pdf', args=[p.personnel_action_id])
                    if p.personnel_action_id else ''
                ),
                'job_functions': p.job_functions or '',
                'action_motivation': p.action_motivation or '',
                'action_explanation': p.action_explanation or '',
            }
        })


class ManagementPeriodPartialUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Procesa la actualización de campos específicos desde el SweetAlert del Expediente"""
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        if period.status.code != 'SIN_FIRMAR':
            return JsonResponse({
                'success': False,
                'message': 'Error de Integridad: No es posible editar un contrato ya firmado o finalizado.'
            }, status=403)
        data = request.POST
        try:
            with transaction.atomic():
                # Actualización de campos permitidos
                doc = data.get('doc')
                if doc is not None and str(doc).strip():
                    period.document_number = str(doc).strip().upper()
                period.workplace = data.get('workplace', '').strip().upper()
                period.institutional_need_memo = data.get('memo', '').strip().upper()
                period.budget_certification = data.get('cert', '').strip().upper()
                period.start_date = data.get('start')
                period.end_date = data.get('end') if data.get('end') else None
                period.schedule_id = data.get('schedule')
                period.job_functions = data.get('functions', '').strip()

                period.updated_by = request.user
                period.full_clean()
                period.save()

                return JsonResponse({'success': True, 'message': 'Expediente actualizado correctamente.'})
        except ValidationError as e:
            return JsonResponse({'success': False, 'message': 'Error de validación: ' + str(e.message_dict)},
                                status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ManagementPeriodUploadDocView(LoginRequiredMixin, View):
    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        file = request.FILES.get('contract_file')

        if not file:
            return JsonResponse({'success': False, 'message': 'No se seleccionó ningún archivo.'}, status=400)

        # 1. Validaciones de Seguridad
        if not file.name.lower().endswith('.pdf'):
            return JsonResponse({'success': False, 'message': 'Solo se permiten archivos PDF.'}, status=400)

        if file.size > 2 * 1024 * 1024:  # 2MB
            return JsonResponse({'success': False, 'message': 'El archivo excede el límite de 2MB.'}, status=400)

        try:
            # 2. Guardar archivo (Django maneja la ruta vía upload_to definido en el modelo)
            # Si ya existe uno, eliminamos el anterior para no dejar basura en el server
            if period.signed_document:
                if os.path.isfile(period.signed_document.path):
                    os.remove(period.signed_document.path)

            period.signed_document = file
            period.updated_by = request.user
            period.save()

            return JsonResponse({
                'success': True,
                'message': 'Documento legalizado cargado correctamente.',
                'file_url': period.signed_document.url
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ManagementPeriodDeleteDocView(LoginRequiredMixin, View):
    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        try:
            if period.signed_document:
                # Eliminación física
                if os.path.isfile(period.signed_document.path):
                    os.remove(period.signed_document.path)

                period.signed_document = None
                period.save()
                return JsonResponse({'success': True, 'message': 'Documento eliminado del expediente.'})
            return JsonResponse({'success': False, 'message': 'No hay documento para eliminar.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
