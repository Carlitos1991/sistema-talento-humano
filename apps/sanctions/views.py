import base64
import html
import json
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from django.db.models import Case, When, Value, IntegerField
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.html import escape
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView

from budget.models import BudgetLine
from contract.models import LaborRegime
from contract.models import ManagementPeriod
from core.models import SystemConfiguration
from core.models import User
from employee.models import Employee
from personnel_actions.models import PersonnelAction, ActionType
from .forms import SanctionNotificationForm, SanctionNotificationTypeForm, SanctionTypeForm, SanctionForm, MONTH_CHOICES
from .models import NotificationTemplate, TemplateSection, SanctionNotification, SanctionNotificationMapping, \
    SanctionNotificationType, SanctionNotificationTypeRegime, SanctionType, Sanction, SanctionAssignment
from .services import build_notification_replacements, build_replacements_from_global_mappings


# --- MIXIN FOR AJAX SEARCH (Hybrid) ---
class JSONResponseMixin:
    """
    Mixin to handle AJAX responses in ListViews (Dynamic search).
    If it's AJAX, renders only the partial table and returns it in JSON.
    """

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)
            return JsonResponse({'html': html})
        return super().render_to_response(context, **response_kwargs)


def _notification_type_modal_context(notification_type=None, form=None):
    active_regimes = list(LaborRegime.objects.filter(is_active=True).order_by('name'))
    links = {}
    if notification_type and notification_type.pk:
        notification_type = SanctionNotificationType.objects.prefetch_related(
            'regime_templates__labor_regime'
        ).get(pk=notification_type.pk)
        links = {link.labor_regime_id: link for link in notification_type.regime_templates.all()}

    regime_rows = []
    for regime in active_regimes:
        regime_rows.append({
            'regime': regime,
            'link': links.get(regime.id),
            'selected': regime.id in links,
        })

    return {
        'form': form or SanctionNotificationTypeForm(instance=notification_type),
        'notification_type': notification_type,
        'regime_rows': regime_rows,
        'selected_regime_ids': [row['regime'].id for row in regime_rows if row['selected']],
    }


def _parse_regime_ids(raw_regime_ids):
    parsed_ids = []
    for regime_id in raw_regime_ids:
        try:
            parsed_ids.append(int(regime_id))
        except (TypeError, ValueError):
            continue
    return parsed_ids


def _sync_notification_type_regimes(notification_type, selected_regime_ids):
    active_links = {link.labor_regime_id: link for link in notification_type.regime_templates.all()}
    selected_ids = set(_parse_regime_ids(selected_regime_ids))

    for regime_id in selected_ids:
        link = active_links.pop(regime_id, None)

        if link is None:
            SanctionNotificationTypeRegime.objects.create(
                notification_type=notification_type,
                labor_regime_id=regime_id,
            )

    for link in active_links.values():
        link.delete()


def _get_employee_current_regime_context(employee):
    period = ManagementPeriod.objects.select_related(
        'contract_type__labor_regime',
        'budget_line__regime_item',
        'budget_line__position_item',
        'administrative_unit',
    ).filter(employee=employee).order_by('-is_active', '-end_date', '-start_date', '-created_at').first()

    regime = None
    position_name = ''
    unit_name = ''

    if period and period.contract_type and period.contract_type.labor_regime:
        regime = period.contract_type.labor_regime
        if period.budget_line and period.budget_line.position_item:
            position_name = period.budget_line.position_item.name
        elif period.manual_position:
            position_name = period.manual_position
        if period.administrative_unit:
            unit_name = period.administrative_unit.name

    if regime is None:
        budget_line = employee.current_budget_line.select_related('regime_item', 'position_item').first()
        if budget_line:
            regime = budget_line.regime_item
            if budget_line.position_item:
                position_name = budget_line.position_item.name
        if not unit_name and employee.area:
            unit_name = employee.area.name

    return {
        'regime': regime,
        'position_name': position_name,
        'unit_name': unit_name,
    }


def _get_compatible_notification_types(regime):
    if not regime:
        return SanctionNotificationType.objects.none()
    return SanctionNotificationType.objects.filter(
        is_active=True,
        regime_templates__labor_regime=regime,
    ).prefetch_related('regime_templates__labor_regime').distinct().order_by('name')


def _get_next_notification_sequence():
    last_sequence = SanctionNotification.objects.order_by('-sequence_number').values_list('sequence_number',
                                                                                          flat=True).first() or 0
    return last_sequence + 1


def _format_spanish_date(date_value):
    months = {
        1: 'enero',
        2: 'febrero',
        3: 'marzo',
        4: 'abril',
        5: 'mayo',
        6: 'junio',
        7: 'julio',
        8: 'agosto',
        9: 'septiembre',
        10: 'octubre',
        11: 'noviembre',
        12: 'diciembre',
    }
    if not date_value:
        return ''
    return f"{date_value.day:02d} de {months.get(date_value.month, '')} de {date_value.year}"


def _first_token(value):
    parts = str(value or '').strip().split()
    return parts[0] if parts else ''


def _build_user_code(user):
    person = getattr(user, 'person', None)
    first_name_token = ''
    last_name_token = ''

    if person:
        first_name_token = _first_token(person.first_name)
        last_name_token = _first_token(person.last_name)
    else:
        full_name = user.get_full_name() or user.username or ''
        parts = full_name.split()
        if parts:
            first_name_token = parts[0]
            if len(parts) >= 3:
                last_name_token = parts[-2]
            elif len(parts) > 1:
                last_name_token = parts[1]
            else:
                last_name_token = parts[0]

    first_code = ''.join(char for char in first_name_token if char.isalpha())[:2].upper()
    last_code = ''.join(char for char in last_name_token if char.isalpha())[:2].upper()
    return f'{first_code}{last_code}'


def _can_generate_notification(user):
    return user.has_perm('sanctions.add_sanctionnotification') or user.has_perm('sanctions.add_sanction')


def _build_notification_data_context(employee, regime_context, notification_type, form):
    person = employee.person
    person_context = SimpleNamespace(
        first_name=person.first_name or '',
        last_name=person.last_name or '',
        name=person.first_name or '',
        lastname=person.last_name or '',
        full_name=person.full_name or '',
        document_number=person.document_number or '',
    )

    return {
        'employee': employee,
        'person': person_context,
        'regime': SimpleNamespace(
            code=regime_context['regime'].code if regime_context['regime'] else '',
            name=regime_context['regime'].name if regime_context['regime'] else '',
        ),
        'employee_full_name': person.full_name or '',
        'employee_first_name': person.first_name or '',
        'employee_last_name': person.last_name or '',
        'employee_document_number': person.document_number or '',
        'employee_position': regime_context['position_name'] or 'Sin cargo asignado',
        'employee_unit': regime_context['unit_name'] or 'Sin unidad asignada',
        'regime_code': regime_context['regime'].code if regime_context['regime'] else '',
        'regime_name': regime_context['regime'].name if regime_context['regime'] else '',
        'notification_name': notification_type.name,
        'sequence_number': form.initial.get('sequence_number', 0),
        'sequence_code': form.initial.get('sequence_code', '0000'),
        'user_code': form.initial.get('user_code', ''),
        'month_name': dict(form.fields['month'].choices).get(int(form.cleaned_data['month']), ''),
        'month_number': form.cleaned_data['month'],
        'year': form.cleaned_data['year'],
        'registration_date': _format_spanish_date(form.cleaned_data['registration_date']),
        'authority_1_name': form.cleaned_data['authority_1'].name,
        'authority_1_position': form.cleaned_data['authority_1'].position,
        'authority_2_name': form.cleaned_data['authority_2'].name if form.cleaned_data.get('authority_2') else '',
        'authority_2_position': form.cleaned_data['authority_2'].position if form.cleaned_data.get(
            'authority_2') else '',
        'authority_1': form.cleaned_data['authority_1'],
        'authority_2': form.cleaned_data.get('authority_2'),
        'minutes_late': form.cleaned_data.get('minutes_late') or 0,
        'regs_without_mark': form.cleaned_data.get('regs_without_mark') or 0,
        'observations': form.cleaned_data.get('observations') or '',
    }


def _get_notification_city():
    current = SystemConfiguration.get_current()
    return (current.city if current and current.city else 'Loja').strip()


def _render_inline_formatting(content):
    """
    Render básico de texto enriquecido seguro:
    - **texto** => negrita
    - *texto* => cursiva
    - __texto__ => subrayado
    - saltos de línea => <br>
    """
    raw_text = str(content or '').replace('\r\n', '\n').replace('\r', '\n')
    safe_text = html.escape(raw_text)

    # Preserva tabulaciones y secuencias de espacios para firmas y bloques manuales.
    safe_text = safe_text.replace('\t', '&nbsp;' * 4)
    safe_text = re.sub(r' {2,}', lambda m: '&nbsp;' * len(m.group(0)), safe_text)

    safe_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'__(.+?)__', r'<u>\1</u>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[SIZE_DOWN\](.+?)\[/SIZE_DOWN\]', r'<span style="font-size:0.9em;">\1</span>', safe_text,
                       flags=re.DOTALL)
    safe_text = re.sub(r'\[SIZE_UP\](.+?)\[/SIZE_UP\]', r'<span style="font-size:1.1em;">\1</span>', safe_text,
                       flags=re.DOTALL)
    safe_text = re.sub(r'\[ALIGN_LEFT\](.+?)\[/ALIGN_LEFT\]',
                       r'<span style="display:block; text-align:left;">\1</span>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[ALIGN_CENTER\](.+?)\[/ALIGN_CENTER\]',
                       r'<span style="display:block; text-align:center;">\1</span>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[ALIGN_RIGHT\](.+?)\[/ALIGN_RIGHT\]',
                       r'<span style="display:block; text-align:right;">\1</span>', safe_text, flags=re.DOTALL)
    return safe_text.replace('\n', '<br>')


def _normalize_template_section_content(content):
    """
    Normaliza texto del editor cuando llega con secuencias escapadas literales
    (ej. "\\u000A", "\\n", "\\t") para persistir contenido legible.
    """
    text = str(content or '')
    text = text.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\r', '\n').replace('\\t', '\t')
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
    return text.strip()


def _get_letterhead_resource(request):
    configuration = SystemConfiguration.get_current()
    if configuration is None:
        configuration = SystemConfiguration.objects.filter(letterhead__isnull=False).exclude(letterhead='').order_by(
            '-effective_date').first()

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


def _build_notification_render_context(employee, regime_context, notification_type, form, request, sequence_number=None,
                                       user_code=None):
    sequence_number = sequence_number or _get_next_notification_sequence()
    user_code = user_code or _build_user_code(request.user)

    form.initial['sequence_number'] = sequence_number
    form.initial['sequence_code'] = f'{sequence_number:04d}'
    form.initial['user_code'] = user_code

    city = _get_notification_city()
    base_context = _build_notification_data_context(employee, regime_context, notification_type, form)
    base_context['location'] = city

    dynamic_template = NotificationTemplate.objects.filter(
        notification_type=notification_type,
        labor_regime=regime_context['regime'],
        is_active=True,
    ).first()

    global_mappings = SanctionNotificationMapping.objects.filter(is_active=True).order_by('order', 'label')
    replacements = build_replacements_from_global_mappings(base_context, global_mappings)
    replacements.update(build_notification_replacements(base_context))

    sections = []
    if dynamic_template:
        for section in dynamic_template.sections.filter(is_active=True).order_by('order'):
            content = section.content or ''
            for placeholder, replacement in replacements.items():
                content = content.replace(placeholder, str(replacement or ''))
            sections.append({
                'type': section.section_type,
                'content': content,
                'content_html': _render_inline_formatting(content),
            })

    full_code = f'{sequence_number:04d}-{(regime_context["regime"].code or "").upper()}-{form.cleaned_data["year"]}-{user_code}'

    return {
        'header_code': full_code,
        'city': city,
        'registration_date': _format_spanish_date(form.cleaned_data['registration_date']),
        'sections': sections,
        'letterhead_path': _get_letterhead_resource(request),
        'has_dynamic_template': bool(dynamic_template and sections),
    }


def _build_notification_form_like_object(notification):
    return SimpleNamespace(
        cleaned_data={
            'month': notification.month,
            'year': notification.year,
            'registration_date': notification.registration_date,
            'authority_1': notification.authority_1,
            'authority_2': notification.authority_2,
            'minutes_late': notification.minutes_late or 0,
            'regs_without_mark': notification.regs_without_mark or 0,
            'observations': notification.observations or '',
        },
        initial={
            'sequence_number': notification.sequence_number,
            'sequence_code': notification.sequential_code,
            'user_code': notification.user_code,
        },
        fields={
            'month': SimpleNamespace(choices=MONTH_CHOICES),
        },
    )


def _build_notification_render_context_from_record(notification, request):
    regime_context = _get_employee_current_regime_context(notification.employee)
    regime_context['regime'] = notification.labor_regime
    fake_form = _build_notification_form_like_object(notification)
    return _build_notification_render_context(
        notification.employee,
        regime_context,
        notification.notification_type,
        fake_form,
        request,
        sequence_number=notification.sequence_number,
        user_code=notification.user_code,
    )


class SanctionNotificationTypeListView(LoginRequiredMixin, PermissionRequiredMixin, JSONResponseMixin, ListView):
    model = SanctionNotificationType
    template_name = 'sanctions/notification_type_list.html'
    partial_template_name = 'sanctions/partials/partial_notification_type_list.html'
    context_object_name = 'types'
    permission_required = 'sanctions.view_sanctionnotificationtype'
    paginate_by = 10

    def get_queryset(self):
        queryset = SanctionNotificationType.objects.prefetch_related(
            'regime_templates__labor_regime',
            'dynamic_templates__labor_regime'
        )
        query = self.request.GET.get('q', '')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(regime_templates__labor_regime__name__icontains=query)
                | Q(regime_templates__labor_regime__code__icontains=query)
            ).distinct()
        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        for notification_type in context.get('types', []):
            templates_by_regime = {
                template.labor_regime_id: template
                for template in notification_type.dynamic_templates.all()
            }
            notification_type.template_regime_items = []

            for link in notification_type.regime_templates.all():
                template = templates_by_regime.get(link.labor_regime_id)
                notification_type.template_regime_items.append({
                    'regime_id': link.labor_regime_id,
                    'regime_code': link.labor_regime.code,
                    'regime_name': link.labor_regime.name,
                    'has_template': template is not None,
                    'template_id': template.id if template else '',
                    'edit_url': reverse('sanctions:template_editor_detail', args=[template.id]) if template else '',
                    'create_url': reverse('sanctions:template_editor_create',
                                          args=[notification_type.id, link.labor_regime_id]),
                })

        return context

    def render_to_response(self, context, **response_kwargs):
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


class SanctionNotificationTypeCreateView(LoginRequiredMixin, View):
    permission_required = 'sanctions.add_sanctionnotificationtype'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(self.permission_required):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para crear tipos de notificación'},
                                    status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        context = _notification_type_modal_context()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('sanctions/modals/modal_notification_type_form.html', context, request=request)
            return HttpResponse(html)
        return JsonResponse({'success': False, 'message': 'Solicitud inválida'}, status=400)

    def post(self, request, *args, **kwargs):
        form = SanctionNotificationTypeForm(request.POST)
        selected_regime_ids = _parse_regime_ids(request.POST.getlist('regime_ids', []))
        active_regime_ids = set(LaborRegime.objects.filter(is_active=True).values_list('id', flat=True))

        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        if not selected_regime_ids:
            return JsonResponse(
                {'success': False, 'errors': {'regime_ids': ['Debe seleccionar al menos un régimen laboral.']}},
                status=400)

        invalid_ids = [regime_id for regime_id in selected_regime_ids if regime_id not in active_regime_ids]
        if invalid_ids:
            return JsonResponse(
                {'success': False, 'errors': {'regime_ids': ['Uno o más regímenes seleccionados no están activos.']}},
                status=400)

        with transaction.atomic():
            notification_type = form.save(commit=False)
            notification_type.created_by = request.user
            notification_type.updated_by = request.user
            notification_type.save()
            _sync_notification_type_regimes(notification_type, selected_regime_ids)

        return JsonResponse({'success': True, 'message': 'Tipo de notificación creado correctamente.'})


class SanctionNotificationTypeUpdateView(LoginRequiredMixin, View):
    permission_required = 'sanctions.change_sanctionnotificationtype'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(self.permission_required):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'success': False, 'message': 'No tiene permisos para modificar tipos de notificación'}, status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, pk):
        return get_object_or_404(SanctionNotificationType, pk=pk)

    def get(self, request, pk, *args, **kwargs):
        notification_type = self.get_object(pk)
        context = _notification_type_modal_context(notification_type=notification_type)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('sanctions/modals/modal_notification_type_form.html', context, request=request)
            return HttpResponse(html)
        return JsonResponse({'success': False, 'message': 'Solicitud inválida'}, status=400)

    def post(self, request, pk, *args, **kwargs):
        notification_type = self.get_object(pk)
        form = SanctionNotificationTypeForm(request.POST, instance=notification_type)
        selected_regime_ids = _parse_regime_ids(request.POST.getlist('regime_ids', []))
        active_regime_ids = set(LaborRegime.objects.filter(is_active=True).values_list('id', flat=True))

        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        if not selected_regime_ids:
            return JsonResponse(
                {'success': False, 'errors': {'regime_ids': ['Debe seleccionar al menos un régimen laboral.']}},
                status=400)

        invalid_ids = [regime_id for regime_id in selected_regime_ids if regime_id not in active_regime_ids]
        if invalid_ids:
            return JsonResponse(
                {'success': False, 'errors': {'regime_ids': ['Uno o más regímenes seleccionados no están activos.']}},
                status=400)

        with transaction.atomic():
            notification_type = form.save(commit=False)
            notification_type.updated_by = request.user
            notification_type.save()
            _sync_notification_type_regimes(notification_type, selected_regime_ids)

        return JsonResponse({'success': True, 'message': 'Tipo de notificación actualizado correctamente.'})


class SanctionNotificationTypeToggleView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sanctions.change_sanctionnotificationtype'

    def post(self, request, pk):
        notification_type = get_object_or_404(SanctionNotificationType, pk=pk)
        notification_type.toggle_status()
        status = 'activado' if notification_type.is_active else 'desactivado'
        return JsonResponse({
            'success': True,
            'message': f'Tipo de notificación {status} correctamente.',
            'is_active': notification_type.is_active,
        })


class GenerateSanctionNotificationView(LoginRequiredMixin, View):
    permission_required = 'sanctions.add_sanctionnotification'

    def dispatch(self, request, *args, **kwargs):
        if not _can_generate_notification(request.user):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para generar notificaciones'},
                                    status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        employee_id = request.GET.get('employee_id')
        notification_id = request.GET.get('notification_id')
        notification = None

        if notification_id:
            notification = get_object_or_404(
                SanctionNotification.objects.select_related('employee__person', 'notification_type', 'labor_regime',
                                                            'authority_1', 'authority_2'),
                pk=notification_id,
            )
            employee = notification.employee
        else:
            employee = get_object_or_404(Employee, pk=employee_id)

        regime_context = _get_employee_current_regime_context(employee)
        compatible_notification_types = _get_compatible_notification_types(regime_context['regime'])
        if notification and notification.notification_type_id:
            compatible_ids = list(compatible_notification_types.values_list('pk', flat=True))
            if notification.notification_type_id not in compatible_ids:
                compatible_ids.append(notification.notification_type_id)
            compatible_notification_types = SanctionNotificationType.objects.filter(pk__in=compatible_ids).order_by(
                'name')
        authorities = User.objects.filter(is_active=True).order_by('username')

        next_sequence = _get_next_notification_sequence()
        default_notification_type = compatible_notification_types.first()
        default_authority = authorities.first()

        if notification:
            form = SanctionNotificationForm(
                instance=notification,
                notification_types=compatible_notification_types,
                authorities=authorities,
                initial={
                    'sequence_number': notification.sequence_number,
                    'sequence_code': notification.sequential_code,
                    'user_code': notification.user_code,
                },
            )
        else:
            form = SanctionNotificationForm(
                notification_types=compatible_notification_types,
                authorities=authorities,
                initial={
                    'registration_date': timezone.now().date(),
                    'year': timezone.now().year,
                    'month': timezone.now().month,
                    'sequence_number': next_sequence,
                    'sequence_code': f'{next_sequence:04d}',
                    'user_code': _build_user_code(request.user),
                    'notification_type': default_notification_type.pk if default_notification_type else None,
                    'authority_1': default_authority.pk if default_authority else None,
                },
            )

        context = {
            'form': form,
            'employee': employee,
            'regime_context': regime_context,
            'notification_types': compatible_notification_types,
            'authorities': authorities,
            'month_name': dict(form.fields['month'].choices).get(form.initial.get('month') or timezone.now().month, ''),
            'notification': notification,
            'is_edit': notification is not None,
        }

        html = render_to_string(
            'sanctions/modals/modal_generate_notification_form.html',
            context,
            request=request,
        )
        return HttpResponse(html)

    def post(self, request):
        employee_id = request.POST.get('employee_id')
        notification_id = request.POST.get('notification_id')
        notification = None

        if notification_id:
            notification = get_object_or_404(SanctionNotification, pk=notification_id)
            employee = notification.employee
        else:
            employee = get_object_or_404(Employee, pk=employee_id)

        regime_context = _get_employee_current_regime_context(employee)
        if not regime_context['regime']:
            return JsonResponse({
                'success': False,
                'errors': {'employee_id': ['No se pudo detectar un régimen laboral vigente para este empleado.']},
            }, status=400)
        compatible_notification_types = _get_compatible_notification_types(regime_context['regime'])
        authorities = User.objects.filter(is_active=True).order_by('username')

        form = SanctionNotificationForm(
            request.POST,
            instance=notification,
            notification_types=compatible_notification_types,
            authorities=authorities,
        )

        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        notification_type = form.cleaned_data['notification_type']
        regime_template = notification_type.regime_templates.filter(
            labor_regime=regime_context['regime']).select_related('labor_regime').first()
        if not regime_template:
            regime_template = SanctionNotificationTypeRegime.objects.create(
                notification_type=notification_type,
                labor_regime=regime_context['regime'],
            )

        dynamic_template = NotificationTemplate.objects.filter(
            notification_type=notification_type,
            labor_regime=regime_context['regime'],
            is_active=True,
        ).first()

        city = _get_notification_city()

        has_dynamic_template = bool(dynamic_template and dynamic_template.sections.filter(is_active=True).exists())

        if not has_dynamic_template:
            return JsonResponse({
                'success': False,
                'errors': {
                    'notification_type': ['No existe template dinámico con secciones activas para el régimen actual.']}
            }, status=400)

        if notification is None:
            next_sequence = _get_next_notification_sequence()
            user_code = _build_user_code(request.user)
            notification = SanctionNotification(
                employee=employee,
                sequence_number=next_sequence,
                user_code=user_code,
                created_by=request.user,
            )

        notification.employee = employee
        notification.notification_type = notification_type
        notification.regime_template = regime_template
        notification.labor_regime = regime_context['regime']
        notification.month = form.cleaned_data['month']
        notification.year = form.cleaned_data['year']
        notification.registration_date = form.cleaned_data['registration_date']
        notification.authority_1 = form.cleaned_data['authority_1']
        notification.authority_2 = form.cleaned_data.get('authority_2') or None
        notification.minutes_late = form.cleaned_data.get('minutes_late') or 0
        notification.regs_without_mark = form.cleaned_data.get('regs_without_mark') or 0
        notification.observations = form.cleaned_data.get('observations') or ''
        notification.updated_by = request.user
        notification.save()

        message = 'Notificación actualizada correctamente.' if notification_id else 'Notificación registrada correctamente. La vista previa queda disponible en pantalla.'

        return JsonResponse({
            'success': True,
            'message': message,
        })


class SanctionNotificationPreviewView(LoginRequiredMixin, View):
    permission_required = 'sanctions.add_sanctionnotification'

    def dispatch(self, request, *args, **kwargs):
        if not _can_generate_notification(request.user):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para generar notificaciones'},
                                    status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        employee_id = request.GET.get('employee_id')
        employee = get_object_or_404(Employee, pk=employee_id)
        regime_context = _get_employee_current_regime_context(employee)
        compatible_notification_types = _get_compatible_notification_types(regime_context['regime'])
        authorities = User.objects.filter(is_active=True).order_by('username')

        next_sequence = _get_next_notification_sequence()
        default_notification_type = compatible_notification_types.first()
        default_authority = authorities.first()

        query_data = request.GET.copy()

        form = SanctionNotificationForm(
            query_data,
            notification_types=compatible_notification_types,
            authorities=authorities,
            initial={
                'registration_date': timezone.now().date(),
                'year': timezone.now().year,
                'month': timezone.now().month,
                'sequence_number': next_sequence,
                'sequence_code': f'{next_sequence:04d}',
                'user_code': _build_user_code(request.user),
                'notification_type': default_notification_type.pk if default_notification_type else None,
                'authority_1': default_authority.pk if default_authority else None,
            },
        )

        context = {
            'employee': employee,
            'regime_context': regime_context,
            'form': form,
            'is_ready': form.is_valid() and bool(regime_context['regime']) and bool(
                form.cleaned_data.get('notification_type')),
        }

        if context['is_ready']:
            render_context = _build_notification_render_context(
                employee,
                regime_context,
                form.cleaned_data['notification_type'],
                form,
                request,
                sequence_number=next_sequence,
                user_code=form.initial.get('user_code') or _build_user_code(request.user),
            )
            context.update(render_context)

        html = render_to_string('sanctions/preview/notification_preview.html', context, request=request)
        return HttpResponse(html)


class SanctionNotificationListView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sanctions.view_sanctionnotification'

    def has_permission(self):
        return self.request.user.has_perm('sanctions.view_sanctionnotification') or _can_generate_notification(
            self.request.user)

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.has_perm('sanctions.view_sanctionnotification') or _can_generate_notification(
                request.user)):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para ver notificaciones'},
                                    status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        employee_id = request.GET.get('employee_id')
        notifications = SanctionNotification.objects.select_related(
            'employee__person',
            'notification_type',
            'labor_regime',
            'authority_1',
            'authority_2',
            'created_by',
        )

        filtered_employee = None
        if employee_id:
            notifications = notifications.filter(employee_id=employee_id)
            filtered_employee = get_object_or_404(Employee.objects.select_related('person'), pk=employee_id)

        notifications = notifications.order_by('-sequence_number', '-created_at')[:30]

        context = {
            'notifications': notifications,
            'filtered_employee': filtered_employee,
        }
        html = render_to_string('sanctions/modals/modal_notification_list.html', context, request=request)
        return HttpResponse(html)


class SanctionNotificationPdfView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sanctions.view_sanctionnotification'

    def get(self, request, pk):
        notification = get_object_or_404(
            SanctionNotification.objects.select_related(
                'employee__person',
                'notification_type',
                'labor_regime',
                'authority_1',
                'authority_2',
            ),
            pk=pk,
        )

        try:
            from weasyprint import HTML
            pdf_context = _build_notification_render_context_from_record(notification, request)
            html_string = render_to_string('sanctions/pdf/notification_document.html', pdf_context, request=request)
            pdf_bytes = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            filename = f'Notificacion_{notification.sequential_code}_{notification.employee.person.full_name.replace(" ", "_")}.pdf'
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
        except Exception:
            return HttpResponse('Error al generar el PDF', status=500)


class SanctionNotificationTypeHelpView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.has_perm('sanctions.view_sanctionnotificationmapping') or request.user.has_perm(
                'sanctions.view_sanctionnotificationtype')):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para ver la guía'}, status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        mappings = SanctionNotificationMapping.objects.filter(is_active=True).order_by('order', 'label')
        context = {
            'mappings': mappings,
        }
        html = render_to_string('sanctions/modals/modal_notification_type_help.html', context, request=request)
        return HttpResponse(html)


class SanctionNotificationTypePreviewView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sanctions.view_sanctionnotificationtype'

    def get(self, request, pk):
        notification_type = get_object_or_404(
            SanctionNotificationType.objects.prefetch_related('regime_templates__labor_regime'),
            pk=pk,
        )

        preview_rows = []
        for link in notification_type.regime_templates.all():
            preview_rows.append({
                'link': link,
            })

        context = {
            'notification_type': notification_type,
            'preview_rows': preview_rows,
        }

        html = render_to_string('sanctions/modals/modal_notification_type_preview.html', context, request=request)
        return HttpResponse(html)


def _template_editor_render_inline_formatting(content):
    raw_text = str(content or '').replace('\r\n', '\n').replace('\r', '\n')
    safe_text = escape(raw_text)
    safe_text = safe_text.replace('\t', '&nbsp;' * 4)
    safe_text = re.sub(r' {2,}', lambda match: '&nbsp;' * len(match.group(0)), safe_text)
    safe_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'__(.+?)__', r'<u>\1</u>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[SIZE_DOWN\](.+?)\[/SIZE_DOWN\]', r'<span style="font-size:0.9em;">\1</span>', safe_text,
                       flags=re.DOTALL)
    safe_text = re.sub(r'\[SIZE_UP\](.+?)\[/SIZE_UP\]', r'<span style="font-size:1.1em;">\1</span>', safe_text,
                       flags=re.DOTALL)
    safe_text = re.sub(r'\[ALIGN_LEFT\](.+?)\[/ALIGN_LEFT\]',
                       r'<span style="display:block; text-align:left;">\1</span>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[ALIGN_CENTER\](.+?)\[/ALIGN_CENTER\]',
                       r'<span style="display:block; text-align:center;">\1</span>', safe_text, flags=re.DOTALL)
    safe_text = re.sub(r'\[ALIGN_RIGHT\](.+?)\[/ALIGN_RIGHT\]',
                       r'<span style="display:block; text-align:right;">\1</span>', safe_text, flags=re.DOTALL)
    return safe_text.replace('\n', '<br>')


class TemplateEditorDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = NotificationTemplate
    template_name = 'sanctions/template_editor/template_editor.html'
    permission_required = 'sanctions.change_notificationtemplate'
    context_object_name = 'template'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object
        context['available_mappings'] = list(
            SanctionNotificationMapping.objects.filter(is_active=True)
            .order_by('order', 'label')
            .values('placeholder', 'label')
        )
        context['header_format'] = f'NOTIFICACIÓN Nº [SECUENCIA]-{template.labor_regime.code}-[AÑO]-[CODIGO_USUARIO]'
        context['location'] = 'Loja'
        context['date_format'] = '[today]'
        return context


class TemplateEditorCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sanctions.add_notificationtemplate'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(self.permission_required):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para crear templates.'},
                                    status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, type_id, regime_id):
        notification_type = get_object_or_404(SanctionNotificationType, pk=type_id)
        labor_regime = get_object_or_404(LaborRegime, pk=regime_id)

        template, _ = NotificationTemplate.objects.get_or_create(
            notification_type=notification_type,
            labor_regime=labor_regime,
            defaults={
                'created_by': request.user,
                'updated_by': request.user,
            },
        )

        if template.created_by is None:
            template.created_by = request.user
        template.updated_by = request.user
        template.save(update_fields=['created_by', 'updated_by', 'updated_at'])

        return redirect('sanctions:template_editor_detail', pk=template.pk)


class TemplateSectionCreateAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sanctions.add_templatesection'

    @method_decorator(require_http_methods(['POST']))
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(self.permission_required):
            return JsonResponse({'success': False, 'error': 'No tiene permisos para agregar secciones.'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, template_id):
        template = get_object_or_404(NotificationTemplate, id=template_id)

        try:
            data = json.loads(request.body)
            section_type = data.get('section_type')
            content = _normalize_template_section_content(data.get('content', ''))
            order = data.get('order', 0)

            if not content:
                return JsonResponse({'error': 'El contenido no puede estar vacío'}, status=400)

            if section_type not in ['PARAGRAPH', 'TITLE']:
                return JsonResponse({'error': 'Tipo de sección inválido'}, status=400)

            section = TemplateSection.objects.create(
                template=template,
                section_type=section_type,
                content=content,
                order=order,
                created_by=request.user,
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
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class TemplateSectionUpdateAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sanctions.change_templatesection'

    @method_decorator(require_http_methods(['POST']))
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(self.permission_required):
            return JsonResponse({'success': False, 'error': 'No tiene permisos para editar secciones.'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, section_id):
        section = get_object_or_404(TemplateSection, id=section_id)

        try:
            data = json.loads(request.body)
            section.content = _normalize_template_section_content(data.get('content', section.content))
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
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class TemplateSectionDeleteAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sanctions.delete_templatesection'

    @method_decorator(require_http_methods(['POST']))
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(self.permission_required):
            return JsonResponse({'success': False, 'error': 'No tiene permisos para eliminar secciones.'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, section_id):
        section = get_object_or_404(TemplateSection, id=section_id)
        deleted_id = section.id

        try:
            section.delete()
            return JsonResponse({'success': True, 'deleted_id': deleted_id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class TemplateSectionReorderAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sanctions.change_templatesection'

    @method_decorator(require_http_methods(['POST']))
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(self.permission_required):
            return JsonResponse({'success': False, 'error': 'No tiene permisos para reordenar secciones.'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, template_id):
        template = get_object_or_404(NotificationTemplate, id=template_id)

        try:
            data = json.loads(request.body)
            sections_data = data.get('sections', [])

            for item in sections_data:
                section = TemplateSection.objects.get(id=item['id'], template=template)
                section.order = item['order']
                section.updated_by = request.user
                section.save()

            return JsonResponse({'success': True})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class TemplatePreviewAjaxView(LoginRequiredMixin, View):
    def get(self, request, template_id):
        template = get_object_or_404(NotificationTemplate, id=template_id)
        employee_id = request.GET.get('employee_id')

        if not employee_id:
            employee = Employee.objects.first()
            if not employee:
                return JsonResponse({'preview': '<p>No hay empleados registrados</p>'})
        else:
            employee = get_object_or_404(Employee, id=employee_id)

        try:
            data = {
                'employee': employee,
                'person': employee.person if hasattr(employee, 'person') else SimpleNamespace(
                    first_name='Juan',
                    last_name='Pérez',
                    document_number='1234567890'
                ),
                'labor_regime': template.labor_regime,
                'sequence_code': '0001',
                'sequence_number': '0001',
                'year': datetime.now().year,
                'registration_date': _format_spanish_date(datetime.now().date()),
                'today': _format_spanish_date(datetime.now().date()),
                'location': 'Loja',
                'user_code': 'JUPE',
                'created_by': SimpleNamespace(person=SimpleNamespace(
                    first_name='Juan', last_name='Pérez'
                ))
            }

            replacements = build_notification_replacements(data)
            regime_code = template.labor_regime.code
            header = f'NOTIFICACIÓN Nº {replacements.get("[SECUENCIA]", "0001")}-{regime_code}-{replacements.get("[AÑO]", datetime.now().year)}-{replacements.get("[CODIGO_USUARIO]", "XXXX")}';
            location_date = f'{replacements.get("[LOCALIDAD]", "Loja")}, {replacements.get("[today]", _format_spanish_date(datetime.now().date()))}'

            sections_html = ''
            for section in template.sections.filter(is_active=True).order_by('order'):
                content = section.content
                for placeholder, replacement in replacements.items():
                    content = content.replace(placeholder, replacement)

                if section.section_type == 'PARAGRAPH':
                    sections_html += f'<p style="text-align: justify; margin-bottom: 0.6rem; line-height: 1.42; font-size: 0.95rem;">{_template_editor_render_inline_formatting(content)}</p>'
                else:
                    sections_html += f'<h4 style="text-align: left; margin-top: 0.9rem; margin-bottom: 0.35rem; font-size: 1rem;">{_template_editor_render_inline_formatting(content)}</h4>'

            preview_html = f'''
            <div style="max-width: 800px; margin: 1rem auto; padding: 2.4rem 2rem 1.4rem; border: 1px solid #ddd; background: white;">
                <div style="text-align: center; font-weight: bold; margin-bottom: 1.2rem; font-size: 1.08rem;">
                    {header}
                </div>
                <div style="text-align: left; margin-bottom: 1.1rem; font-size: 0.92rem;">
                    {location_date}
                </div>
                <div class="template-sections">
                    {sections_html}
                </div>
            </div>
            '''

            return JsonResponse({'preview': preview_html})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# ==========================================
# VIEWS: SANCTION TYPES (Configuration)
# ==========================================

class SanctionTypeListView(LoginRequiredMixin, PermissionRequiredMixin, JSONResponseMixin, ListView):
    model = SanctionType
    template_name = 'sanctions/sanctions_type_list.html'
    partial_template_name = 'sanctions/partials/partial_sanctions_type_list.html'
    context_object_name = 'types'
    permission_required = 'sanctions.view_sanctiontype'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')

        if query:
            queryset = queryset.filter(Q(name__icontains=query))

        return queryset

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)

            # Get pagination information
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


class SanctionTypeCreateView(LoginRequiredMixin, CreateView):
    model = SanctionType
    form_class = SanctionTypeForm
    template_name = 'sanctions/modals/modal_sanctions_type_form.html'
    success_url = reverse_lazy('sanctions:sanction_type_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('sanctions.add_sanctiontype'):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para crear tipos de sanción'},
                                    status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            context = self.get_context_data(form=form)
            html = render_to_string(self.template_name, context, request=request)
            return HttpResponse(html)
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Tipo de sanción creado correctamente.'})
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class SanctionTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = SanctionType
    form_class = SanctionTypeForm
    template_name = 'sanctions/modals/modal_sanctions_type_form.html'
    success_url = reverse_lazy('sanctions:sanction_type_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('sanctions.change_sanctiontype'):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'No tiene permisos para modificar tipos de sanción'},
                                    status=403)
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            context = self.get_context_data(form=form)
            html = render_to_string(self.template_name, context, request=request)
            return HttpResponse(html)
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Tipo de sanción actualizado correctamente.'})
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        return super().form_invalid(form)


class SanctionTypeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = SanctionType
    success_url = reverse_lazy('sanctions:sanction_type_list')
    permission_required = 'sanctions.delete_sanctiontype'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Eliminado correctamente.'})
        return super().delete(request, *args, **kwargs)


class SanctionTypeToggleView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Toggle active status of sanction type"""
    permission_required = 'sanctions.change_sanctiontype'

    def post(self, request, pk):
        sanction_type = get_object_or_404(SanctionType, pk=pk)
        sanction_type.is_active = not sanction_type.is_active
        sanction_type.save()

        status = "activado" if sanction_type.is_active else "desactivado"
        return JsonResponse({
            'success': True,
            'message': f'Tipo de sanción {status} correctamente.',
            'is_active': sanction_type.is_active
        })


# ==========================================
# VIEWS: EMPLOYEE LIST TO GENERATE SANCTIONS
# ==========================================

class EmployeeSanctionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Vista para listar empleados activos y gestionar sus sanciones/notificaciones"""
    model = Employee
    template_name = 'sanctions/employee_sanction_list.html'
    context_object_name = 'employees'
    permission_required = 'sanctions.view_sanction'
    paginate_by = 10

    def get_queryset(self):
        queryset = Employee.objects.filter(is_active=True).select_related(
            'person', 'area', 'employment_status'
        )
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(person__first_name__icontains=query) |
                Q(person__last_name__icontains=query) |
                Q(person__document_number__icontains=query)
            )
        return queryset.order_by('person__last_name', 'person__first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # --- 1. LÓGICA PESTAÑA EMPLEADOS (Presupuestos) ---
        employee_ids = [emp.id for emp in context['employees']]
        budgets_dict = {}
        if employee_ids:
            budgets = BudgetLine.objects.filter(
                current_employee_id__in=employee_ids, is_active=True
            ).select_related('position_item')
            for budget in budgets:
                budgets_dict[budget.current_employee_id] = budget

        employees_with_budget = []
        for employee in context['employees']:
            employees_with_budget.append({
                'employee': employee,
                'budget': budgets_dict.get(employee.id)
            })
        context['employees_data'] = employees_with_budget

        # --- 2. LÓGICA PESTAÑA NOTIFICACIONES (CORREGIDA) ---
        notifications_q = self.request.GET.get('notifications_q', '').strip()
        selected_month = self.request.GET.get('notifications_month', '')
        selected_year = self.request.GET.get('notifications_year', '')
        status_filter = self.request.GET.get('status_filter', 'GENERADO')

        # Si no hay búsqueda ni filtros, mostramos por defecto el mes/año actual
        # o el de la última notificación registrada
        if not any([notifications_q, selected_month, selected_year]):
            last_notif = SanctionNotification.objects.order_by('-year', '-month').first()
            if last_notif:
                selected_month = str(last_notif.month)
                selected_year = str(last_notif.year)
            else:
                selected_month = str(timezone.now().month)
                selected_year = str(timezone.now().year)

        # Definir QuerySet Base de Notificaciones (para stats)
        base_notifications_qs = SanctionNotification.objects.select_related(
            'employee__person', 'notification_type', 'labor_regime'
        )

        # Aplicar filtros de mes/año a la base para stats
        if selected_month:
            base_notifications_qs = base_notifications_qs.filter(month=selected_month)
        if selected_year:
            base_notifications_qs = base_notifications_qs.filter(year=selected_year)

        # Calcular stats por estado
        stats_data = {}
        total_notif_count = 0
        for status_choice, label in SanctionNotification._meta.get_field('status').choices:
            count = base_notifications_qs.filter(status=status_choice).count()
            total_notif_count += count
            stats_data[status_choice] = {
                'label': label,
                'count': count,
                'status_code': status_choice
            }

        # Construir stats cards CON TOTAL AL FINAL
        stats_cards = []
        status_colors = {
            'GENERADO': {'class': 'color-two', 'icon': 'fa-clipboard'},
            'EN_PROCESO': {'class': 'color-three', 'icon': 'fa-hourglass-half'},
            'SANCIONADO': {'class': 'color-four', 'icon': 'fa-gavel'},
            'ARCHIVADO': {'class': 'color-five', 'icon': 'fa-folder-open'},
        }

        for status_choice, data in stats_data.items():
            color_info = status_colors.get(status_choice, {'class': 'color-secondary', 'icon': 'fa-circle'})
            stats_cards.append({
                'label': data['label'],
                'count': data['count'],
                'filter_val': status_choice,
                'icon': color_info['icon'],
                'class': color_info['class']
            })

        # Agregar TOTAL al final
        stats_cards.append({
            'label': 'TOTAL',
            'count': total_notif_count,
            'filter_val': 'all',
            'icon': 'fa-file-lines',
            'class': 'color-one'
        })

        # QuerySet filtrado con status
        notifications_qs = SanctionNotification.objects.select_related(
            'employee__person', 'notification_type', 'labor_regime'
        ).annotate(
            status_priority=Case(
                When(status='GENERADO', then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        )

        # Aplicar Filtro de búsqueda COD/EMP si existe
        if notifications_q:
            notifications_qs = notifications_qs.filter(
                Q(sequence_number__icontains=notifications_q) |
                Q(employee__person__first_name__icontains=notifications_q) |
                Q(employee__person__last_name__icontains=notifications_q) |
                Q(employee__person__document_number__icontains=notifications_q)
            )

        # Aplicar Filtros de Fecha si existen
        if selected_month:
            notifications_qs = notifications_qs.filter(month=selected_month)
        if selected_year:
            notifications_qs = notifications_qs.filter(year=selected_year)

        # Aplicar filtro de estado (por defecto GENERADO)
        if status_filter and status_filter != 'all':
            notifications_qs = notifications_qs.filter(status=status_filter)

        notifications_qs = notifications_qs.order_by('status_priority', '-sequence_number', '-created_at')

        # Paginación manual para la segunda pestaña
        notif_paginator = Paginator(notifications_qs, 10)
        notif_page_num = self.request.GET.get('notifications_page', 1)
        try:
            notifications_page = notif_paginator.page(notif_page_num)
        except (EmptyPage, PageNotAnInteger):
            notifications_page = notif_paginator.page(1)

        # Actualizar contexto
        context.update({
            'latest_notifications_page_obj': notifications_page,
            'notifications_q': notifications_q,
            'notification_month_choices': MONTH_CHOICES[1:],
            'selected_notifications_month': selected_month,
            'selected_notifications_year': selected_year,
            'stats_cards_notifications': stats_cards,
            'current_status_filter': status_filter,
        })
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Si la petición viene de la pestaña notificaciones
            if self.request.GET.get('section') == 'notifications':
                html = render_to_string(
                    'sanctions/partials/partial_latest_notification_list.html',
                    context, request=self.request
                )
                page_obj = context.get('latest_notifications_page_obj')
                stats = context.get('stats_cards_notifications', [])
            else:
                # Si viene de la pestaña empleados
                html = render_to_string(
                    'sanctions/partials/partial_employee_list.html',
                    context, request=self.request
                )
                page_obj = context.get('page_obj')
                stats = []

            # Construir info de paginación para JS
            pagination_data = {
                'start_index': page_obj.start_index() if page_obj.object_list else 0,
                'end_index': page_obj.end_index() if page_obj.object_list else 0,
                'total_count': page_obj.paginator.count,
                'current_page': page_obj.number,
                'total_pages': page_obj.paginator.num_pages,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
            }
            return JsonResponse({'html': html, 'pagination': pagination_data, 'stats': stats})

        return super().render_to_response(context, **response_kwargs)


class SanctionHistoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = SanctionNotification
    template_name = 'sanctions/sanction_history.html'
    partial_template_name = 'sanctions/partials/partial_assignments_table.html'
    context_object_name = 'notifications'
    permission_required = 'sanctions.view_sanctionnotification'
    paginate_by = 10

    def _get_base_queryset(self):
        """
        Define la visibilidad base:
        - Admin (is_staff): Ve todo.
        - Usuario común: Solo ve lo que tiene o tuvo asignado (vía assignment_history).
        """
        queryset = SanctionNotification.objects.select_related(
            'employee__person',
            'notification_type',
            'labor_regime',
            'authority_1',
            'authority_2',
            'created_by',
        )

        if not self.request.user.is_staff:
            # CORRECCIÓN: Usamos 'assignment_history' que es el related_name del modelo
            queryset = queryset.filter(assignment_history__assigned_to=self.request.user).distinct()

        return queryset

    def get_queryset(self):
        queryset = self._get_base_queryset()

        # 1. Estado inicial por defecto: 'EN_PROCESO'
        status_filter = self.request.GET.get('status_filter', 'EN_PROCESO')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        # 2. Otros filtros de búsqueda
        month = self.request.GET.get('notifications_month')
        year = self.request.GET.get('notifications_year')
        search_q = self.request.GET.get('search_q', '').strip()

        if month and month.isdigit():
            queryset = queryset.filter(month=int(month))
        if year and year.isdigit():
            queryset = queryset.filter(year=int(year))

        if search_q:
            queryset = queryset.filter(
                Q(employee__person__first_name__icontains=search_q) |
                Q(employee__person__last_name__icontains=search_q) |
                Q(employee__person__document_number__icontains=search_q)
            )

        return queryset.order_by('-updated_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Mantener filtros en la UI
        month = self.request.GET.get('notifications_month')
        year = self.request.GET.get('notifications_year')

        if not month or not year:
            last_notif = SanctionNotification.objects.order_by('-year', '-month').first()
            month = month or (str(last_notif.month) if last_notif else str(timezone.now().month))
            year = year or (str(last_notif.year) if last_notif else str(timezone.now().year))

        # LÓGICA DE STATS CON ORDEN PERSONALIZADO
        base_qs = self._get_base_queryset()  # Respeta el filtro assigned_to

        stats_data = {}
        total_count = 0
        for status, label in SanctionNotification.STATUS_CHOICES:
            count = base_qs.filter(status=status).count()
            total_count += count
            stats_data[status] = {'label': label, 'count': count}

        # Orden solicitado: EN_PROCESO -> ARCHIVADO -> SANCIONADO -> GENERADO
        desired_order = ['EN_PROCESO', 'ARCHIVADO', 'SANCIONADO', 'GENERADO']
        status_colors = {
            'GENERADO': {'class': 'color-two', 'icon': 'fa-clipboard'},
            'EN_PROCESO': {'class': 'color-three', 'icon': 'fa-hourglass-half'},
            'SANCIONADO': {'class': 'color-four', 'icon': 'fa-gavel'},
            'ARCHIVADO': {'class': 'color-five', 'icon': 'fa-folder-open'},
        }

        stats_cards = []
        for status_key in desired_order:
            if status_key in stats_data:
                info = stats_data[status_key]
                color = status_colors.get(status_key, {'class': 'color-secondary', 'icon': 'fa-circle'})
                stats_cards.append({
                    'label': info['label'],
                    'count': info['count'],
                    'filter_val': status_key,
                    'icon': color['icon'],
                    'class': color['class']
                })

        # TOTAL al final
        stats_cards.append({
            'label': 'TOTAL',
            'count': total_count,
            'filter_val': 'all',
            'icon': 'fa-file-lines',
            'class': 'color-one'
        })

        context.update({
            'stats_cards': stats_cards,
            'notification_month_choices': MONTH_CHOICES[1:],
            'selected_notifications_month': month,
            'selected_notifications_year': year,
            'current_status_filter': self.request.GET.get('status_filter', 'EN_PROCESO')
        })
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(self.partial_template_name, context, request=self.request)
            page_obj = context.get('page_obj')
            pagination_data = {
                'start_index': page_obj.start_index() if page_obj.object_list else 0,
                'end_index': page_obj.end_index() if page_obj.object_list else 0,
                'total_count': page_obj.paginator.count,
                'current_page': page_obj.number,
                'total_pages': page_obj.paginator.num_pages,
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
            }
            return JsonResponse({'html': html, 'pagination': pagination_data, 'stats': context.get('stats_cards', [])})
        return super().render_to_response(context, **response_kwargs)


# ==========================================
# VIEWS: SANCTION CREATION AND MANAGEMENT
# ==========================================

class GenerateSanctionFormView(LoginRequiredMixin, View):
    """View to generate a sanction for a specific employee"""

    def get(self, request):
        employee_id = request.GET.get('employee_id')
        employee = get_object_or_404(Employee, pk=employee_id)

        form = SanctionForm(initial={'employee': employee})
        authorities = User.objects.filter(is_active=True).order_by('username')

        context = {
            'form': form,
            'employee': employee,
            'authorities': authorities
        }

        html = render_to_string(
            'sanctions/modals/modal_generate_sanction_form.html',
            context,
            request=request
        )
        return HttpResponse(html)

    def post(self, request):
        form = SanctionForm(request.POST, request.FILES)
        notification_id = request.POST.get('notification_id')

        if form.is_valid():
            try:
                with transaction.atomic():
                    sanction = form.save(commit=False)
                    sanction.created_by = request.user

                    # 1. Obtener el tipo de sanción y sus firmas predefinidas
                    st_type = form.cleaned_data['sanction_type']

                    # 2. Lógica de Acción de Personal
                    try:
                        action_type = ActionType.objects.get(code='SANCIONES')
                    except ActionType.DoesNotExist:
                        return JsonResponse(
                            {'success': False, 'message': 'Error: El tipo de acción "SANCIONES" no existe.'},
                            status=400)

                    year = datetime.now().year
                    last_action = PersonnelAction.objects.filter(number__endswith=f'-{year}').order_by(
                        '-created_at').first()
                    new_num = 1
                    if last_action:
                        try:
                            new_num = int(last_action.number.split('-')[0]) + 1
                        except:
                            pass

                    action_number = f'{new_num:04d}-{year}'

                    # 3. Crear Acción de Personal con firmas AUTOMÁTICAS
                    personnel_action = PersonnelAction.objects.create(
                        employee=sanction.employee,
                        action_type=action_type,
                        number=action_number,
                        explanation=sanction.description,
                        motivation=sanction.legal_basis or 'Sanción disciplinaria según normativa vigente',
                        date_issue=sanction.incident_date,
                        date_effective=sanction.sanction_date,

                        # ASIGNACIÓN AUTOMÁTICA DESDE EL TIPO
                        authority_1=st_type.authority_1,
                        authority_2=st_type.authority_2,
                        reviewer=st_type.reviewer,
                        register=st_type.register,
                        elaboration=request.user,  # Automatizado con el usuario actual

                        created_by=request.user
                    )

                    sanction.personnel_action = personnel_action
                    sanction.save()

                    # E. SI VIENE DE LA BANDEJA: Cerramos la notificación
                    if notification_id:
                        notif = SanctionNotification.objects.filter(pk=notification_id).first()
                        if notif:
                            notif.status = 'SANCIONADO'
                            notif.save()

                            curr = notif.current_assignment
                            if curr:
                                # Ya no sale error porque 'sanction' ya existe arriba
                                curr.complete_assignment(sanction_obj=sanction)

                return JsonResponse({'success': True, 'message': f'Sanción registrada con éxito: {action_number}'})


            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error técnico: {str(e)}'}, status=500)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class SanctionAdminListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """View to list and manage all sanctions"""
    model = Sanction
    template_name = 'sanctions/sanction_admin_list.html'
    context_object_name = 'sanctions'
    permission_required = 'sanctions.view_sanction'
    paginate_by = 15

    def get_queryset(self):
        queryset = Sanction.objects.select_related(
            'employee__person',
            'sanction_type',
            'created_by'
        )

        # Filter by employee_id if provided in URL
        employee_id = self.kwargs.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        # Filter by search query
        query = self.request.GET.get('q', '').strip()
        if query:
            # If filtering by employee, search by date or number
            if employee_id:
                # Try to parse as date (dd/mm/yyyy or yyyy-mm-dd)
                date_query = None
                try:
                    # Try dd/mm/yyyy format
                    from datetime import datetime
                    if '/' in query:
                        date_query = datetime.strptime(query, '%d/%m/%Y').date()
                    elif '-' in query and len(query) == 10:
                        date_query = datetime.strptime(query, '%Y-%m-%d').date()
                except:
                    pass

                if date_query:
                    queryset = queryset.filter(
                        Q(sanction_date=date_query) |
                        Q(incident_date=date_query)
                    )
                else:
                    # Search by number or other text fields
                    queryset = queryset.filter(
                        Q(personnel_action__number__icontains=query) |
                        Q(sanction_type__name__icontains=query)
                    )
            else:
                # Otherwise, search by employee info, number, and type
                queryset = queryset.filter(
                    Q(personnel_action__number__icontains=query) |
                    Q(employee__person__first_name__icontains=query) |
                    Q(employee__person__last_name__icontains=query) |
                    Q(employee__person__document_number__icontains=query) |
                    Q(sanction_type__name__icontains=query)
                )

        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filter by severity
        severity = self.request.GET.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)

        return queryset.order_by('-sanction_date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add employee info if filtering by employee
        employee_id = self.kwargs.get('employee_id')
        if employee_id:
            try:
                from employee.models import Employee
                context['filtered_employee'] = Employee.objects.select_related('person').get(pk=employee_id)
            except Employee.DoesNotExist:
                context['filtered_employee'] = None

        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'sanctions/partials/partial_sanction_admin_table.html',
                context,
                request=self.request
            )

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


class SanctionDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to show sanction details"""
    permission_required = 'sanctions.view_sanction'

    def get(self, request, pk):
        sanction = get_object_or_404(
            Sanction.objects.select_related(
                'employee__person',
                'sanction_type',
                'personnel_action',
                'created_by'
            ),
            pk=pk
        )

        context = {'sanction': sanction}

        html = render_to_string(
            'sanctions/modals/modal_sanction_detail.html',
            context,
            request=request
        )
        return HttpResponse(html)


class SanctionUpdateStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to update sanction status"""
    permission_required = 'sanctions.change_sanction'

    def post(self, request, pk):
        sanction = get_object_or_404(Sanction, pk=pk)
        new_status = request.POST.get('status')

        if new_status in dict(Sanction.STATUS_CHOICES):
            sanction.status = new_status
            sanction.updated_by = request.user
            sanction.save()

            return JsonResponse({
                'success': True,
                'message': 'Estado de sanción actualizado correctamente.'
            })

        return JsonResponse({
            'success': False,
            'message': 'Estado no válido.'
        }, status=400)


class EditSanctionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to edit an existing sanction"""
    permission_required = 'sanctions.change_sanction'

    def get(self, request, pk):
        sanction = get_object_or_404(
            Sanction.objects.select_related('employee__person', 'personnel_action'),
            pk=pk
        )

        # Check if sanction is already registered
        if sanction.personnel_action and sanction.personnel_action.is_registered:
            return HttpResponse(
                '<div class="alert alert-warning" style="padding: 20px; text-align: center;">'
                '<i class="fas fa-exclamation-triangle" style="font-size: 3rem; color: #f59e0b;"></i>'
                '<p style="margin-top: 1rem; font-size: 1.1rem; color: #92400e;">Esta sanción ya está registrada y no puede ser editada.</p>'
                '</div>',
                status=403
            )

        form = SanctionForm(instance=sanction)
        authorities = User.objects.filter(is_active=True).order_by('username')

        # Get current authorities from PersonnelAction
        selected_authorities = {}
        if sanction.personnel_action:
            if sanction.personnel_action.authority_1:
                selected_authorities['authority_1'] = sanction.personnel_action.authority_1.id
            if sanction.personnel_action.authority_2:
                selected_authorities['authority_2'] = sanction.personnel_action.authority_2.id
            if sanction.personnel_action.reviewer:
                selected_authorities['reviewer'] = sanction.personnel_action.reviewer.id
            if sanction.personnel_action.elaboration:
                selected_authorities['elaboration'] = sanction.personnel_action.elaboration.id
            if sanction.personnel_action.register:
                selected_authorities['register'] = sanction.personnel_action.register.id

        context = {
            'form': form,
            'employee': sanction.employee,
            'authorities': authorities,
            'sanction': sanction,
            'selected_authorities': selected_authorities,
            'is_edit': True
        }

        html = render_to_string(
            'sanctions/modals/modal_generate_sanction_form.html',
            context,
            request=request
        )
        return HttpResponse(html)

    def post(self, request, pk):
        sanction = get_object_or_404(Sanction.objects.select_related('personnel_action'), pk=pk)

        # Check if sanction is already registered
        if sanction.personnel_action and sanction.personnel_action.is_registered:
            return JsonResponse({
                'success': False,
                'message': 'Esta sanción ya está registrada y no puede ser editada.'
            }, status=403)

        form = SanctionForm(request.POST, request.FILES, instance=sanction)

        if form.is_valid():
            sanction = form.save(commit=False)
            sanction.updated_by = request.user

            # Update PersonnelAction if exists
            if sanction.personnel_action:
                personnel_action = sanction.personnel_action
                personnel_action.explanation = sanction.description
                personnel_action.motivation = sanction.legal_basis or 'Sanción disciplinaria según LOSEP'
                personnel_action.date_issue = sanction.incident_date
                personnel_action.date_effective = sanction.sanction_date

                # Update authorities from POST
                authority_1_id = request.POST.get('authority_1')
                authority_2_id = request.POST.get('authority_2')
                reviewer_id = request.POST.get('reviewer')
                elaboration_id = request.POST.get('elaboration')
                register_id = request.POST.get('register')

                if authority_1_id:
                    personnel_action.authority_1 = User.objects.get(pk=authority_1_id)
                if authority_2_id:
                    personnel_action.authority_2 = User.objects.get(pk=authority_2_id)
                if reviewer_id:
                    personnel_action.reviewer = User.objects.get(pk=reviewer_id)
                personnel_action.elaboration = personnel_action.elaboration or request.user
                if register_id:
                    personnel_action.register = User.objects.get(pk=register_id)

                personnel_action.save()

            sanction.save()

            return JsonResponse({
                'success': True,
                'message': 'Sanción actualizada correctamente.'
            })

        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class RegisterSanctionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to register a sanction (mark PersonnelAction as registered)"""
    permission_required = 'sanctions.change_sanction'

    def post(self, request, pk):
        from django.utils import timezone

        sanction = get_object_or_404(Sanction.objects.select_related('personnel_action'), pk=pk)

        if not sanction.personnel_action:
            return JsonResponse({
                'success': False,
                'message': 'Esta sanción no tiene una acción de personal asociada.'
            }, status=400)

        if sanction.personnel_action.is_registered:
            return JsonResponse({
                'success': False,
                'message': 'Esta sanción ya está registrada.'
            }, status=400)

        # Update PersonnelAction
        personnel_action = sanction.personnel_action
        personnel_action.is_registered = True
        personnel_action.registration_date = timezone.now().date()
        personnel_action.save()

        # Update sanction status to ACTIVE
        sanction.status = 'ACTIVE'
        sanction.updated_by = request.user
        sanction.save()

        return JsonResponse({
            'success': True,
            'message': 'Sanción registrada correctamente.'
        })


class SanctionPDFView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """View to generate sanction PDF report"""
    permission_required = 'sanctions.view_sanction'

    def get(self, request, pk):
        from django.template.loader import get_template
        from xhtml2pdf import pisa
        from io import BytesIO
        import datetime as dt
        from django.conf import settings
        import os

        sanction = get_object_or_404(
            Sanction.objects.select_related(
                'employee__person__document_type',
                'employee__area',
                'sanction_type',
                'personnel_action__authority_1',
                'personnel_action__authority_2',
                'personnel_action__reviewer',
                'personnel_action__elaboration',
                'personnel_action__register',
                'created_by'
            ),
            pk=pk
        )

        # Get budget info
        from budget.models import BudgetLine
        budget = None
        try:
            budget = BudgetLine.objects.select_related('position_item').only(
                'id', 'current_employee', 'position_item__name', 'number_individual',
                'remuneration', 'status_item__name'
            ).get(current_employee=sanction.employee.pk)
        except BudgetLine.DoesNotExist:
            pass

        # Render template
        template = get_template('sanctions/reports/sanction_pdf.html')
        html = template.render({
            'sanction': sanction,
            'employee': sanction.employee,
            'budget': budget,
            'today': dt.datetime.now()
        })

        # Link callback for static files
        def link_callback(uri, rel):
            if uri.startswith(settings.STATIC_URL):
                path = uri.replace(settings.STATIC_URL, '')
                if settings.STATICFILES_DIRS:
                    static_root = settings.STATICFILES_DIRS[0]
                else:
                    static_root = settings.STATIC_ROOT or os.path.join(settings.BASE_DIR, 'static')
                return os.path.join(static_root, path)
            return uri

        # Generate PDF
        response = HttpResponse(content_type='application/pdf')
        filename = f'Sancion_{sanction.employee.person.full_name.replace(" ", "_")}_{sanction.personnel_action.number.replace("/", "-") if sanction.personnel_action else sanction.pk}.pdf'
        response['Content-Disposition'] = f'inline; filename="{filename}"'

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


class SanctionNotificationToggleResponseView(LoginRequiredMixin, View):
    """Actualiza el campo has_responded vía AJAX"""

    def post(self, request, pk):
        notification = get_object_or_404(SanctionNotification, pk=pk)
        notification.has_responded = not notification.has_responded
        notification.save()
        return JsonResponse({
            'success': True,
            'has_responded': notification.has_responded,
            'label': 'Sí' if notification.has_responded else 'No'
        })


class AssignNotificationView(LoginRequiredMixin, View):
    def post(self, request, notification_id):
        new_user_id = request.POST.get('user_id')
        obs = request.POST.get('observation')

        with transaction.atomic():
            notification = get_object_or_404(SanctionNotification, pk=notification_id)
            new_user = get_object_or_404(User, pk=new_user_id)

            # 1. Cerramos la asignación actual
            current_assignment = SanctionAssignment.objects.filter(
                notification=notification, is_current=True
            ).first()

            if current_assignment:
                current_assignment.complete_assignment()

            # 2. Creamos la nueva asignación
            SanctionAssignment.objects.create(
                notification=notification,
                assigned_to=new_user,
                assigned_by=request.user,
                observation=obs
            )

            # 3. Opcional: Cambiar el estado de la notificación
            notification.status = 'EN_PROCESO'
            notification.save()

        return JsonResponse({'success': True, 'message': f'Trámite asignado a {new_user.get_full_name()}'})


class AssignNotificationAjaxView(LoginRequiredMixin, View):
    def get(self, request):
        ids_str = request.GET.get('ids', '')
        notification_ids = [id for id in ids_str.split(',') if id]

        if not notification_ids:
            return HttpResponse("<div class='p-4'>No se seleccionaron registros.</div>", status=400)

        context = {
            'notification_ids': ','.join(notification_ids),
            'count': len(notification_ids),
        }
        html = render_to_string('sanctions/modals/modal_assign_notification.html', context, request=request)
        return HttpResponse(html)

    def post(self, request, pk=None):
        # Obtenemos los IDs del campo oculto del formulario
        ids_raw = request.POST.get('notification_ids', '')
        notification_ids = [id for id in ids_raw.split(',') if id]
        user_to_id = request.POST.get('assigned_to')
        observation = request.POST.get('observation')

        if not notification_ids:
            return JsonResponse({'success': False, 'message': 'No hay notificaciones seleccionadas.'}, status=400)
        if not user_to_id:
            return JsonResponse({'success': False, 'message': 'Debe seleccionar un responsable.'}, status=400)

        try:
            with transaction.atomic():
                notifications = SanctionNotification.objects.filter(id__in=notification_ids)

                for notification in notifications:
                    # 1. Finalizar asignación actual
                    SanctionAssignment.objects.filter(notification=notification, is_current=True).update(
                        is_current=False,
                        end_date=timezone.now()
                    )

                    # 2. Crear nueva asignación
                    SanctionAssignment.objects.create(
                        notification=notification,
                        assigned_to_id=user_to_id,
                        assigned_by=request.user,
                        observation=observation,
                        is_current=True
                    )

                    # 3. Cambiar estado
                    notification.status = 'EN_PROCESO'
                    notification.save()

            return JsonResponse({
                'success': True,
                'message': f'Se han asignado {len(notification_ids)} notificaciones correctamente.'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class UserSearchAjaxView(LoginRequiredMixin, View):
    def get(self, request):
        q = request.GET.get('q', '')
        users = User.objects.filter(is_active=True).filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(username__icontains=q)
        ).distinct()

        results = [
            {
                "id": user.id,
                "text": f"{user.get_full_name()} ({user.username})"  # Select2 espera 'text'
            } for user in users[:15]
        ]
        return JsonResponse({"results": results})


class ReturnNotificationView(LoginRequiredMixin, View):
    """Devuelve el trámite al asignador original y cambia estado a GENERADO"""

    def post(self, request, pk):
        with transaction.atomic():
            notification = get_object_or_404(SanctionNotification, pk=pk)
            current_assign = notification.current_assignment

            if not current_assign:
                return JsonResponse({'success': False, 'message': 'No hay una asignación activa.'}, status=400)

            # 1. Finalizar asignación actual
            current_assign.complete_assignment()

            # 2. Crear nueva asignación de vuelta al que lo envió
            SanctionAssignment.objects.create(
                notification=notification,
                assigned_to=current_assign.assigned_by,  # Se devuelve al originador
                assigned_by=request.user,
                observation=f"Trámite devuelto por: {request.user.get_full_name()}",
                is_current=True
            )

            # 3. Cambiar estado a GENERADO (vuelve a la bandeja general)
            notification.status = 'GENERADO'
            notification.save()

        return JsonResponse({'success': True, 'message': 'Trámite devuelto correctamente.'})


class ArchiveNotificationView(LoginRequiredMixin, View):
    """Cambia el estado a ARCHIVADO y guarda el motivo"""

    def post(self, request, pk):
        motivo = request.POST.get('observation', 'Sin motivo especificado')
        with transaction.atomic():
            notification = get_object_or_404(SanctionNotification, pk=pk)

            # Cerrar asignación actual si existe
            current_assign = notification.current_assignment
            if current_assign:
                current_assign.complete_assignment()

            # Actualizar notificación
            notification.status = 'ARCHIVADO'
            fecha_str = timezone.now().strftime('%d/%m/%Y %H:%M')
            nueva_obs = f"--- ARCHIVADO ({fecha_str}) ---\nMotivo: {motivo}\n"
            notification.observations = (notification.observations or "") + nueva_obs
            notification.save()

        return JsonResponse({'success': True, 'message': 'Trámite archivado correctamente.'})


class MassiveReturnNotificationView(LoginRequiredMixin, View):
    """Devuelve múltiples trámites al estado inicial GENERADO"""

    def post(self, request):
        ids_raw = request.POST.get('notification_ids', '')
        notification_ids = [id for id in ids_raw.split(',') if id]

        if not notification_ids:
            return JsonResponse({'success': False, 'message': 'No hay registros seleccionados.'}, status=400)

        try:
            with transaction.atomic():
                notifications = SanctionNotification.objects.filter(id__in=notification_ids)
                for notification in notifications:
                    # 1. Finalizar asignación actual
                    current_assign = notification.current_assignment
                    if current_assign:
                        current_assign.complete_assignment()

                    # 2. Cambiar estado a GENERADO (Estado inicial)
                    notification.status = 'GENERADO'
                    notification.save()

            return JsonResponse({
                'success': True,
                'message': f'Se han devuelto {len(notification_ids)} trámites correctamente.'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ==========================================
# VIEWS: HISTORIAL DE SANCIONES Y ACCIONES
# ==========================================

class SanctionHistoryAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    AJAX view para obtener el historial de sanciones de un empleado.
    Parámetros GET:
    - employee_id: ID del empleado
    """
    permission_required = 'sanctions.view_sanction'

    def get(self, request):
        employee_id = request.GET.get('employee_id')
        if not employee_id:
            return JsonResponse({'success': False, 'message': 'Employee ID required'}, status=400)

        try:
            employee = get_object_or_404(Employee.objects.select_related('person'), pk=employee_id)
        except Employee.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Employee not found'}, status=404)

        # Obtener todas las sanciones del empleado
        sanctions = Sanction.objects.filter(
            employee=employee
        ).select_related(
            'sanction_type', 'personnel_action'
        ).order_by('-sanction_date', '-created_at')

        context = {
            'sanctions': sanctions,
            'employee': employee,
            'total_count': sanctions.count(),
        }

        html = render_to_string(
            'sanctions/modals/modal_sanction_history_table.html',
            context,
            request=request
        )

        return JsonResponse({'success': True, 'html': html})


class ActionsHistoryAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    AJAX view para obtener el historial de acciones de personal de tipo SANCIONES de un empleado.
    Parámetros GET:
    - employee_id: ID del empleado
    """
    permission_required = 'sanctions.view_sanction'

    def get(self, request):
        employee_id = request.GET.get('employee_id')
        if not employee_id:
            return JsonResponse({'success': False, 'message': 'Employee ID required'}, status=400)

        try:
            employee = get_object_or_404(Employee.objects.select_related('person'), pk=employee_id)
        except Employee.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Employee not found'}, status=404)

        # Obtener el tipo de acción "SANCIONES"
        try:
            sanction_action_type = ActionType.objects.get(code='SANCIONES')
        except ActionType.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'El tipo de acción "SANCIONES" no está configurado'
            }, status=400)

        # Obtener todas las acciones de personal de tipo SANCIONES para este empleado
        actions = PersonnelAction.objects.filter(
            employee=employee,
            action_type=sanction_action_type
        ).select_related(
            'authority_1',
            'authority_2',
            'reviewer',
            'elaboration',
            'register'
        ).order_by('-date_issue', '-created_at')

        context = {
            'actions': actions,
            'employee': employee,
            'total_count': actions.count(),
        }

        html = render_to_string(
            'sanctions/modals/modal_actions_history_table.html',
            context,
            request=request
        )

        return JsonResponse({'success': True, 'html': html})
