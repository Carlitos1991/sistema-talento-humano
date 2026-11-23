import base64
import mimetypes
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape

from budget.models import BudgetAssignmentHistory, BudgetLine, BudgetModificationHistory
from core.models import CatalogItem, SystemConfiguration, User
from employee.models import InstitutionalData
from institution.models import AdministrativeUnit
from personnel_actions.models import ActionMovement, ActionType, PersonnelAction
from schedule.models import EmployeeScheduleHistory
from .models import (
    ContractTemplate,
    ContractTemplateSection,
    ContractType,
    History,
    ManagementPeriod,
)


def clean_text_accents(text):
    if not text:
        return ''
    return (
        unicodedata.normalize('NFKD', str(text))
        .encode('ascii', 'ignore')
        .decode('utf-8')
        .strip()
        .lower()
    )


def build_user_full_name(user):
    if not user:
        return ''
    try:
        person = getattr(user, 'person', None)
        if person and (person.full_name or '').strip():
            return person.full_name.strip().upper()
    except Exception:
        pass

    full_name = (user.get_full_name() or '').strip()
    if full_name:
        return full_name.upper()
    return (user.username or '').strip().upper()


def is_action_contract_type(contract_type):
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


class HistoricalContractService:
    @staticmethod
    @transaction.atomic
    def create_historical_period(form, user):
        status_finalized = CatalogItem.objects.get(
            catalog__code='STATUS_CONTRACT',
            code='FINALIZADO'
        )

        period = form.save(commit=False)
        period.is_historical = True
        period.budget_line = None
        period.status = status_finalized
        period.manual_position = (period.manual_position or '').strip().upper()
        period.created_by = user
        period.updated_by = user

        custom_doc = (form.cleaned_data.get('document_number_input') or '').strip().upper()
        if custom_doc:
            period.document_number = custom_doc

        period.full_clean()
        period.save()

        # Sincronizar fecha de ingreso si no existe o si este contrato histórico es más antiguo
        if period.employee and period.start_date:
            inst_data, _ = InstitutionalData.objects.get_or_create(employee=period.employee)
            if not inst_data.entry_date or period.start_date < inst_data.entry_date:
                inst_data.entry_date = period.start_date
                inst_data.save(update_fields=['entry_date'])

        History.objects.create(
            employee=period.employee,
            contract=period,
            user_register=user.get_full_name() or user.username,
            type='REGISTRO_HISTORICO',
            reason=(
                f'REGISTRO HISTÓRICO '
                f'({period.start_date.strftime("%d/%m/%Y")} - {period.end_date.strftime("%d/%m/%Y")})'
            ),
            historical_position=period.manual_position,
            historical_salary=period.manual_remuneration,
        )
        return period


class ContractTemplateService:
    """
    Gestiona plantillas simples con editor enriquecido (base.html) y variables genéricas.
    """

    GENERIC_VARIABLES = [
        {'placeholder': '[FULL_NAME]', 'label': 'Nombres y apellidos completos'},
        {'placeholder': '[FIRST_NAME]', 'label': 'Nombres'},
        {'placeholder': '[LAST_NAME]', 'label': 'Apellidos'},
        {'placeholder': '[DOCUMENT_NUMBER]', 'label': 'Número de cédula'},
        {'placeholder': '[DOC_NUMBER]', 'label': 'Número de contrato / documento'},
        {'placeholder': '[POSITION]', 'label': 'Cargo'},
        {'placeholder': '[REMUNERATION]', 'label': 'Remuneración'},
        {'placeholder': '[UNIT]', 'label': 'Unidad administrativa'},
        {'placeholder': '[WORKPLACE]', 'label': 'Lugar de trabajo'},
        {'placeholder': '[SCHEDULE]', 'label': 'Horario'},
        {'placeholder': '[START_DATE]', 'label': 'Fecha de inicio (dd/mm/aaaa)'},
        {'placeholder': '[END_DATE]', 'label': 'Fecha de fin (dd/mm/aaaa o INDEFINIDO)'},
        {'placeholder': '[CONTRACT_TYPE]', 'label': 'Modalidad contractual'},
        {'placeholder': '[LABOR_REGIME]', 'label': 'Régimen laboral'},
        {'placeholder': '[TODAY]', 'label': 'Fecha actual (dd/mm/aaaa)'},
        {'placeholder': '[YEAR]', 'label': 'Año actual'},
    ]

    @staticmethod
    def sanitize_rich_html(raw_html):
        html = (raw_html or '').strip()
        if not html:
            return ''
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'\son\w+\s*=\s*(["\']).*?\1', '', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'javascript:', '', html, flags=re.IGNORECASE)
        return html

    @staticmethod
    def get_editor_body_html(template):
        sections = list(template.sections.filter(is_active=True).order_by('order'))
        if not sections:
            return ''
        if len(sections) == 1 and '<' in (sections[0].content or ''):
            return sections[0].content or ''

        # Compatibilidad con plantillas previas divididas en párrafos/títulos
        blocks = []
        for sec in sections:
            text = escape((sec.content or '').strip()).replace('\n', '<br>')
            if not text:
                continue
            if sec.section_type == 'TITLE':
                blocks.append(f'<h4>{text}</h4>')
            else:
                blocks.append(f'<p>{text}</p>')
        return ''.join(blocks)

    @classmethod
    @transaction.atomic
    def save_editor_body_html(cls, template, raw_html, user):
        clean_html = cls.sanitize_rich_html(raw_html)
        first_section = template.sections.filter(is_active=True).order_by('order').first()

        if first_section:
            first_section.section_type = 'PARAGRAPH'
            first_section.content = clean_html
            first_section.order = 0
            first_section.updated_by = user
            first_section.save(update_fields=['section_type', 'content', 'order', 'updated_by', 'updated_at'])
            template.sections.filter(is_active=True).exclude(pk=first_section.pk).delete()
            return first_section

        return ContractTemplateSection.objects.create(
            template=template,
            section_type='PARAGRAPH',
            content=clean_html,
            order=0,
            created_by=user,
            updated_by=user,
        )

    @staticmethod
    def ensure_action_template_sections(template, user):
        existing_sections = list(template.sections.filter(is_active=True).order_by('order'))
        if len(existing_sections) >= 6:
            return existing_sections[:6]

        for index in range(len(existing_sections), 6):
            ContractTemplateSection.objects.create(
                template=template,
                section_type='PARAGRAPH',
                content='',
                order=index,
                created_by=user,
                updated_by=user,
            )
        return list(template.sections.filter(is_active=True).order_by('order'))[:6]

    @staticmethod
    def get_action_template_preview_data(template):
        sections = list(template.sections.filter(is_active=True).order_by('order'))
        raw_values = [(sections[i].content or '').strip() if len(sections) > i else '' for i in range(6)]

        action_type = None
        if raw_values[0].isdigit():
            action_type = ActionType.objects.filter(pk=int(raw_values[0]), is_active=True).first()

        user_ids = [int(val) for val in raw_values[1:] if val.isdigit()]
        users_map = User.objects.filter(pk__in=user_ids, is_active=True).in_bulk()

        def resolve_user_name(raw_id):
            if not raw_id or not raw_id.isdigit():
                return 'Pendiente'
            u = users_map.get(int(raw_id))
            return build_user_full_name(u) if u else 'Pendiente'

        return {
            'action_type': action_type.name if action_type else 'Pendiente',
            'authority_1': resolve_user_name(raw_values[1]),
            'authority_2': resolve_user_name(raw_values[2]),
            'reviewer': resolve_user_name(raw_values[3]),
            'elaboration': resolve_user_name(raw_values[4]),
            'register': resolve_user_name(raw_values[5]),
        }

    @staticmethod
    def build_replacements(period):
        today = timezone.now().date()
        person = period.employee.person
        category_label = (
            'ACCIÓN DE PERSONAL'
            if period.contract_type.contract_type_category == ContractType.TYPE_ACCION_PERSONAL
            else 'CONTRATO'
        )
        elaboration_date = (
            period.elaboration_date.strftime('%d/%m/%Y')
            if getattr(period, 'elaboration_date', None)
            else '-'
        )
        configuration = SystemConfiguration.get_current()
        authority_name = (getattr(configuration, 'max_authority_name', '') or '').strip().upper()

        return {
            '[FULL_NAME]': person.full_name or '-',
            '[EMPLOYEE_FULL_NAME]': person.full_name or '-',
            '[FIRST_NAME]': person.first_name or '-',
            '[LAST_NAME]': person.last_name or '-',
            '[DOCUMENT_NUMBER]': person.document_number or '-',
            '[DOC_NUMBER]': period.document_number or '-',
            '[CONTRACT_TYPE]': period.contract_type.name or '-',
            '[DOCUMENT_CATEGORY]': category_label,
            '[LABOR_REGIME]': period.contract_type.labor_regime.name or '-',
            '[POSITION]': period.display_position or '-',
            '[REMUNERATION]': f'{period.display_remuneration:.2f}' if period.display_remuneration is not None else '-',
            '[UNIT]': period.administrative_unit.name if period.administrative_unit else '-',
            '[WORKPLACE]': period.workplace or '-',
            '[SCHEDULE]': period.schedule.name if period.schedule else '-',
            '[START_DATE]': period.start_date.strftime('%d/%m/%Y') if period.start_date else '-',
            '[END_DATE]': period.end_date.strftime('%d/%m/%Y') if period.end_date else 'INDEFINIDO',
            '[TODAY]': today.strftime('%d/%m/%Y'),
            '[today]': today.strftime('%d/%m/%Y'),
            '[YEAR]': str(today.year),
            '[ACTION_ISSUE_DATE]': elaboration_date,
            '[ACTION_EFFECTIVE_FROM]': period.start_date.strftime('%d/%m/%Y') if period.start_date else '-',
            '[ACTION_EFFECTIVE_TO]': period.end_date.strftime('%d/%m/%Y') if period.end_date else '-',
            '[MOTIVATION]': period.action_motivation or '-',
            '[EXPLANATION]': period.action_explanation or '-',
            '[ACTION_EXPLANATION_HEADER]': 'Se hace constar la siguiente acción de personal:',
            '[PREPARED_BY]': build_user_full_name(period.created_by),
            '[AUTHORITY_1]': authority_name,
        }

    @classmethod
    def render_template_body(cls, template, replacements):
        raw_html = cls.get_editor_body_html(template)
        if not raw_html:
            return ''

        # Si el contenido no tiene etiquetas HTML (texto plano antiguo), lo escapamos y formateamos
        if '<' not in raw_html:
            rendered = escape(raw_html)
            for placeholder, value in replacements.items():
                rendered = rendered.replace(placeholder, escape(str(value)))
            rendered = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', rendered, flags=re.DOTALL)
            rendered = re.sub(r'__(.+?)__', r'<u>\1</u>', rendered, flags=re.DOTALL)
            return f'<p>{rendered.replace(chr(10), "<br>")}</p>'

        rendered = cls.sanitize_rich_html(raw_html)
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, escape(str(value)))
        return rendered


class ManagementPeriodService:
    """Orquesta creación, legalización, finalización e impresión de inicios de gestión."""

    @staticmethod
    def _sync_employee_entry_date(employee, start_date):
        if not employee or not start_date:
            return
        inst_data, _ = InstitutionalData.objects.get_or_create(employee=employee)
        if not inst_data.entry_date or start_date < inst_data.entry_date or not employee.is_active:
            inst_data.entry_date = start_date
            inst_data.save(update_fields=['entry_date'])

    @staticmethod
    def _should_auto_create_personnel_action(contract_type):
        if not contract_type:
            return False
        contract_category = (contract_type.contract_type_category or '').upper()
        if contract_category != ContractType.TYPE_ACCION_PERSONAL:
            return False
        contract_code = (contract_type.code or '').upper()
        contract_name = (contract_type.name or '').upper()
        if 'NOMBRAMIENTO' in contract_code or 'NOMBRAMIENTO' in contract_name:
            return False
        return True

    @staticmethod
    def _generate_personnel_action_number(reference_date):
        year = reference_date.year if reference_date else timezone.now().year
        max_sequence = 0
        existing_numbers = PersonnelAction.objects.filter(number__endswith=f'-{year}').values_list('number', flat=True)
        for number in existing_numbers:
            sequence_str = (number or '').split('-')[0]
            if sequence_str.isdigit():
                max_sequence = max(max_sequence, int(sequence_str))
        return f'{max_sequence + 1:04d}-{year}'

    @classmethod
    def _create_linked_personnel_action(cls, period, user):
        if period.personnel_action_id or not cls._should_auto_create_personnel_action(period.contract_type):
            return None

        contract_type = period.contract_type
        contract_code = (contract_type.code or '').upper().strip()
        contract_name = (contract_type.name or '').upper().strip()
        normalized_code = re.sub(r'[^A-Z0-9]+', '_', contract_code).strip('_')[:20]

        action_type = ActionType.objects.filter(is_active=True).filter(
            Q(code__iexact=contract_code)
            | Q(name__iexact=contract_name)
            | Q(code__iexact=normalized_code)
        ).first()

        template = ContractTemplate.objects.filter(contract_type=contract_type, is_active=True).first()
        sections = list(template.sections.filter(is_active=True).order_by('order')[:6]) if template else []

        if sections and (sections[0].content or '').strip().isdigit():
            tpl_action_type = ActionType.objects.filter(
                pk=int(sections[0].content.strip()),
                is_active=True
            ).first()
            action_type = tpl_action_type or action_type

        if not action_type:
            raise ValidationError({
                'contract_type': 'No existe un tipo de acción activo que coincida con esta modalidad.'
            })

        active_users = list(User.objects.filter(is_active=True).order_by('username')[:2])
        if not active_users:
            raise ValidationError({
                'personnel_action': 'Debe existir al menos un usuario activo para generar la acción de personal.'
            })

        default_auth_1 = active_users[0]
        default_auth_2 = active_users[1] if len(active_users) > 1 else None

        def pick_signer(idx, fallback):
            if len(sections) <= idx:
                return fallback
            raw_val = (sections[idx].content or '').strip()
            if not raw_val.isdigit():
                return fallback
            return User.objects.filter(pk=int(raw_val), is_active=True).first() or fallback

        auth_1 = pick_signer(1, default_auth_1)
        auth_2 = pick_signer(2, default_auth_2)
        reviewer = pick_signer(3, auth_2 or auth_1)
        elaboration = pick_signer(4, user or auth_1)
        register = pick_signer(5, user or auth_1)

        action = PersonnelAction.objects.create(
            employee=period.employee,
            action_type=action_type,
            number=cls._generate_personnel_action_number(period.elaboration_date or period.start_date),
            motivation=period.action_motivation or contract_type.name,
            date_issue=period.elaboration_date or period.start_date,
            date_effective=period.start_date,
            explanation=period.action_explanation or period.job_functions or '',
            authority_1=auth_1,
            authority_2=auth_2,
            reviewer=reviewer,
            elaboration=elaboration,
            register=register,
            created_by=user,
        )

        ActionMovement.objects.create(
            personnel_action=action,
            previous_unit=None,
            previous_position=None,
            previous_remuneration=0,
            previous_budget_line=None,
            new_unit=period.administrative_unit,
            new_position=(
                period.budget_line.position_item
                if period.budget_line and period.budget_line.position_item
                else None
            ),
            new_remuneration=period.display_remuneration or 0,
            new_budget_line=period.budget_line,
            location_text=period.workplace or '',
        )

        period.personnel_action = action
        period.save(update_fields=['personnel_action'])
        return action

    @classmethod
    @transaction.atomic
    def create_period(cls, form, user):
        status_initial = CatalogItem.objects.get(
            catalog__code='STATUS_CONTRACT',
            code='SIN_FIRMAR'
        )

        period = form.save(commit=False)
        contract_type = period.contract_type
        employee = period.employee

        is_professional_service = (contract_type.code or '').upper() == 'SERVICIOS_PROFESIONALES'
        is_action_document = contract_type.contract_type_category == ContractType.TYPE_ACCION_PERSONAL

        budget_line = None if is_professional_service else employee.current_budget_line.first()
        if not is_professional_service and not budget_line:
            raise ValidationError({
                'budget_line': 'La persona no tiene una partida presupuestaria asignada. Asigne una partida antes de continuar.'
            })

        period.budget_line = budget_line
        period.status = status_initial
        period.created_by = user
        period.updated_by = user
        period.manual_position = (period.manual_position or '').strip().upper() or None
        period.action_motivation = (period.action_motivation or '').strip().upper() or None
        period.action_explanation = (period.action_explanation or '').strip() or None

        if is_action_document:
            period.schedule = None
            period.workplace = None
            period.job_functions = ''
            period.institutional_need_memo = None
            period.budget_certification = None
        else:
            period.workplace = (period.workplace or '').strip().upper() or None
            period.job_functions = (period.job_functions or '').strip()
            period.institutional_need_memo = (period.institutional_need_memo or '').strip().upper() or None
            period.budget_certification = (period.budget_certification or '').strip().upper() or None

        period.full_clean()
        period.save()

        # Actualizar fecha de ingreso en InstitutionalData
        cls._sync_employee_entry_date(employee, period.start_date)

        # Vincular Acción de Personal si corresponde
        cls._create_linked_personnel_action(period, user)

        # Marcar como jefe inmediato si se indicó
        if form.cleaned_data.get('is_boss'):
            employee.is_boss = True
            employee.save(update_fields=['is_boss'])
            if period.administrative_unit_id:
                AdministrativeUnit.objects.filter(pk=period.administrative_unit_id).update(boss=employee)

        return period

    @classmethod
    @transaction.atomic
    def sign_period(cls, period, user):
        status_signed = CatalogItem.objects.get(
            catalog__code='STATUS_CONTRACT',
            code='FIRMADO'
        )
        period.status = status_signed
        period.updated_by = user
        period.save(update_fields=['status', 'updated_by', 'updated_at'])

        regime = period.contract_type.labor_regime.code
        ctype = period.contract_type.code
        new_status = 'EMPLEADO'
        if regime == 'CT':
            new_status = 'TRABAJADOR'
        elif regime == 'LOSEP':
            if 'OCASIONAL' in ctype:
                new_status = 'CONTRATADO'
            elif 'PROFESIONAL' in ctype:
                new_status = 'PROFESIONAL'

        period.employee.set_status(new_status)
        if not period.employee.is_active:
            period.employee.is_active = True
            period.employee.save(update_fields=['is_active'])

        inst_data, _ = InstitutionalData.objects.get_or_create(employee=period.employee)
        fields_to_update = []
        if not inst_data.original_budget_line and period.budget_line:
            inst_data.original_budget_line = period.budget_line
            fields_to_update.append('original_budget_line')
        if not inst_data.entry_date and period.start_date:
            inst_data.entry_date = period.start_date
            fields_to_update.append('entry_date')
        if fields_to_update:
            inst_data.save(update_fields=fields_to_update)

        is_action_document = period.contract_type.contract_type_category == ContractType.TYPE_ACCION_PERSONAL
        History.objects.create(
            employee=period.employee,
            contract=period,
            user_register=user.get_full_name() or user.username,
            type='FIRMA',
            reason='ACCIÓN LEGALIZADA' if is_action_document else 'CONTRATO FIRMADO',
            historical_position=period.display_position,
            historical_salary=period.display_remuneration,
        )

        if period.schedule_id:
            EmployeeScheduleHistory.objects.create(
                employee=period.employee,
                schedule=period.schedule,
                start_date=period.start_date,
                end_date=period.end_date,
                reason='Asignación de Horario',
                is_current=True,
                created_by=user,
            )

        if is_action_document and period.personnel_action_id and not period.personnel_action.is_registered:
            period.personnel_action.is_registered = True
            period.personnel_action.save(update_fields=['is_registered'])

        return period

    @staticmethod
    @transaction.atomic
    def terminate_period(period, form, user):
        reason = form.cleaned_data['reason'].strip()
        end_date = form.cleaned_data['end_date']

        if period.start_date and end_date < period.start_date:
            raise ValidationError({'end_date': 'La fecha fin no puede ser menor al inicio.'})

        end_status = CatalogItem.objects.get(catalog__code='STATUS_CONTRACT', code='FINALIZADO')
        libre_status = CatalogItem.objects.get(catalog__code='BUDGET_STATUS', code='LIBRE')

        period.status = end_status
        period.end_date = end_date
        period.updated_by = user
        period.save(update_fields=['status', 'end_date', 'updated_by', 'updated_at'])

        current_status = period.employee.employment_status.code
        if current_status.startswith('EX'):
            exit_status = current_status
        else:
            mapping = {
                'EMPLEADO': 'EX_EMPLEADO',
                'TRABAJADOR': 'EX_TRABAJADOR',
                'CONTRATADO': 'EX_EMPLEADO',
                'PROFESIONAL': 'EX_PROFESIONAL',
            }
            exit_status = mapping.get(current_status, 'PERSONA')

        period.employee.set_status(exit_status)
        period.employee.is_active = False
        period.employee.save(update_fields=['employment_status', 'is_active'])

        budget_line = period.budget_line or BudgetLine.objects.filter(current_employee=period.employee).first()
        if budget_line:
            assignment_history = BudgetAssignmentHistory.objects.filter(
                budget_line=budget_line,
                employee=period.employee,
                is_current=True,
            ).first()
            if assignment_history:
                assignment_history.end_date = end_date
                assignment_history.is_current = False
                assignment_history.observation = f'Fin de gestión: {reason}'
                assignment_history.save()

            budget_line.status_item = libre_status
            budget_line.current_employee = None
            budget_line.save(modified_by=user)

            BudgetModificationHistory.objects.create(
                budget_line=budget_line,
                modified_by=user,
                modification_type='RELEASE',
                field_name='Estado y Ocupante',
                old_value=f'Ocupada por {period.employee.person.full_name}',
                new_value='LIBRE / VACANTE',
                reason=f'Terminación de contrato {period.document_number}: {reason}',
            )

        History.objects.create(
            employee=period.employee,
            contract=period,
            user_register=user.get_full_name() or user.username,
            type='TERMINACIÓN',
            reason=reason,
            historical_position=period.display_position,
            historical_salary=period.display_remuneration,
        )
        return period, bool(budget_line)

    @staticmethod
    def get_letterhead_data_uri(request):
        configuration = SystemConfiguration.get_current()
        if configuration is None:
            configuration = (
                SystemConfiguration.objects.filter(letterhead__isnull=False)
                .exclude(letterhead='')
                .order_by('-effective_date')
                .first()
            )
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


class ContractExportService:
    """Unifica contratos/nombramientos con encargos/subrogaciones para el reporte Excel."""

    @staticmethod
    def get_unified_export_rows(periods_queryset, filters):
        unit_id = (filters.get('unit') or '').strip()
        date_from = (filters.get('date_from') or '').strip()
        date_to = (filters.get('date_to') or '').strip()
        q = (filters.get('q') or '').strip()
        raw_document_numbers = (filters.get('document_numbers') or '').strip()

        equivalent_unit_ids = []
        unit_display_name = 'N/A'
        if unit_id:
            selected_unit = AdministrativeUnit.objects.filter(pk=unit_id).first()
            if selected_unit:
                unit_display_name = selected_unit.name
                clean_target = clean_text_accents(selected_unit.name)
                all_units = AdministrativeUnit.objects.values_list('id', 'name')
                equivalent_unit_ids = [
                    u_id for u_id, u_name in all_units
                    if clean_text_accents(u_name) == clean_target
                ]
                if int(unit_id) not in equivalent_unit_ids:
                    equivalent_unit_ids.append(int(unit_id))
            else:
                try:
                    equivalent_unit_ids = [int(unit_id)]
                except ValueError:
                    equivalent_unit_ids = []

        export_rows = []
        for p in periods_queryset:
            person = getattr(getattr(p, 'employee', None), 'person', None)
            regime_name = (
                p.contract_type.labor_regime.name
                if p.contract_type and p.contract_type.labor_regime
                else '-'
            )
            export_rows.append({
                'cedula': person.document_number if person else '',
                'apellidos': person.last_name if person else '',
                'nombres': person.first_name if person else '',
                'cargo': p.list_display_position or 'SIN CARGO',
                'remuneracion': f'$ {p.list_display_remuneration}' if p.list_display_remuneration is not None else '-',
                'dependencia': p.administrative_unit.name if p.administrative_unit else unit_display_name,
                'modalidad': p.contract_type.name if p.contract_type else '-',
                'regimen': regime_name,
                'fecha_desde': p.start_date.strftime('%d/%m/%Y') if p.start_date else '',
                'fecha_hasta': p.end_date.strftime('%d/%m/%Y') if p.end_date else 'Indefinido',
                'sort_date': p.start_date or timezone.now().date(),
            })

        if equivalent_unit_ids:
            partidas_unidad_ids = BudgetLine.objects.filter(
                Q(managementperiod__administrative_unit_id__in=equivalent_unit_ids)
                | Q(assignments__employee__area_id__in=equivalent_unit_ids)
            ).distinct().values_list('id', flat=True)

            encargos_qs = BudgetAssignmentHistory.objects.filter(
                budget_line_id__in=partidas_unidad_ids
            ).filter(
                Q(is_acting=True)
                | Q(observation__icontains='encargo')
                | Q(observation__icontains='subrog')
            ).select_related(
                'employee__person',
                'budget_line__position_item',
                'budget_line__regime_item',
            )

            if date_from and date_to:
                encargos_qs = encargos_qs.filter(start_date__lte=date_to).filter(
                    Q(end_date__gte=date_from) | Q(end_date__isnull=True)
                )
            elif date_from:
                encargos_qs = encargos_qs.filter(Q(end_date__gte=date_from) | Q(end_date__isnull=True))
            elif date_to:
                encargos_qs = encargos_qs.filter(start_date__lte=date_to)

            if raw_document_numbers:
                cedulas = [c.strip() for c in raw_document_numbers.split(',') if c.strip()]
                if cedulas:
                    encargos_qs = encargos_qs.filter(employee__person__document_number__in=cedulas)

            if q:
                for token in [t for t in q.split() if t]:
                    encargos_qs = encargos_qs.filter(
                        Q(employee__person__first_name__icontains=token)
                        | Q(employee__person__last_name__icontains=token)
                        | Q(employee__person__document_number__icontains=token)
                        | Q(budget_line__position_item__name__icontains=token)
                    )

            for enc in encargos_qs:
                person = getattr(getattr(enc, 'employee', None), 'person', None)
                cargo_nombre = (
                    enc.budget_line.position_item.name
                    if enc.budget_line and enc.budget_line.position_item
                    else 'SIN CARGO'
                )
                partida_num = (
                    enc.budget_line.number_individual or enc.budget_line.code
                    if enc.budget_line
                    else ''
                )
                remun = (
                    f'$ {enc.budget_line.remuneration}'
                    if enc.budget_line and enc.budget_line.remuneration
                    else '-'
                )
                regimen_enc = (
                    enc.budget_line.regime_item.name
                    if enc.budget_line and enc.budget_line.regime_item
                    else 'LOSEP'
                )

                export_rows.append({
                    'cedula': person.document_number if person else '',
                    'apellidos': person.last_name if person else '',
                    'nombres': person.first_name if person else '',
                    'cargo': f'{cargo_nombre} ({partida_num})' if partida_num else cargo_nombre,
                    'remuneracion': remun,
                    'dependencia': unit_display_name,
                    'modalidad': 'ENCARGO / SUBROGACIÓN',
                    'regimen': regimen_enc,
                    'fecha_desde': enc.start_date.strftime('%d/%m/%Y') if enc.start_date else '',
                    'fecha_hasta': enc.end_date.strftime('%d/%m/%Y') if enc.end_date else 'Indefinido',
                    'sort_date': enc.start_date or timezone.now().date(),
                })

        export_rows.sort(key=lambda r: r['sort_date'], reverse=True)
        return export_rows
