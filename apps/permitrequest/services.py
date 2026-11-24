import base64
import re
from calendar import monthrange
from datetime import date, datetime, time as dtime, timedelta
from io import BytesIO
import os
from collections import defaultdict
import openpyxl
import qrcode
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape
from django.utils.text import slugify

from budget.models import BudgetLine
from employee.models import Employee
from institution.models import AdministrativeUnit
from person.models import Person
from .forms import validate_justification_file
from .models import PermitRequest, PermitType

PERMIT_PUBLIC_TOKEN_SALT = 'permitrequest.public.validation'

PERMIT_ADMIN_SORT_FIELDS = {
    'employee': 'employee__person__last_name',
    'document_number': 'employee__person__document_number',
    'area': 'employee__area__name',
    'permit_type': 'permit_type__name',
    'created_at': 'created_at',
    'start_date': 'start_date',
    'end_date': 'end_date',
    'status': 'status',
}


class PermitSecurityService:
    """Handles token signing and employee-level authorization checks."""

    @staticmethod
    def build_public_token(permit_id: int) -> str:
        return signing.dumps({'permit_id': permit_id}, salt=PERMIT_PUBLIC_TOKEN_SALT)

    @staticmethod
    def parse_public_token(token: str) -> int:
        payload = signing.loads(token, salt=PERMIT_PUBLIC_TOKEN_SALT)
        permit_id = payload.get('permit_id')
        if not permit_id:
            raise signing.BadSignature('Missing permit_id in token payload')
        return int(permit_id)

    @staticmethod
    def resolve_user_employee(user):
        user_person = getattr(user, 'person', None)
        employee_profile = getattr(user_person, 'employee_profile', None) if user_person else None
        if employee_profile:
            return employee_profile

        person_by_doc = Person.objects.filter(
            document_number=user.username
        ).select_related('employee_profile').first()
        if person_by_doc and getattr(person_by_doc, 'employee_profile', None):
            return person_by_doc.employee_profile

        if user.email:
            person_by_email = Person.objects.filter(
                email__iexact=user.email
            ).select_related('employee_profile').first()
            if person_by_email and getattr(person_by_email, 'employee_profile', None):
                return person_by_email.employee_profile

        return None

    @classmethod
    def can_generate_for_employee(cls, user, employee: Employee) -> bool:
        if user.has_perm('permitrequest.add_permitrequest'):
            return True
        request_employee = cls.resolve_user_employee(user)
        return bool(request_employee and request_employee.id == employee.id)

    @classmethod
    def can_view_report(cls, user, permit: PermitRequest) -> bool:
        if user.has_perm('permitrequest.view_permitrequest'):
            return True
        request_employee = cls.resolve_user_employee(user)
        return bool(request_employee and request_employee.id == permit.employee_id)

    @staticmethod
    def can_insist_permit(user, permit: PermitRequest) -> bool:
        if user.has_perm('permitrequest.add_permitrequest'):
            return True
        user_person = getattr(user, 'person', None)
        return bool(user_person and permit.employee.person_id == user_person.id)


class PermitQueryService:
    """Encapsulates complex ORM filtering, sorting, and tree traversal."""

    @staticmethod
    def get_current_month_bounds():
        today = date.today()
        first_day = today.replace(day=1)
        last_day = today.replace(day=monthrange(today.year, today.month)[1])
        return first_day, last_day

    @staticmethod
    def get_unit_tree_ids(root_unit_id) -> list:
        try:
            root_id = int(root_unit_id)
        except (TypeError, ValueError):
            return []

        all_ids = {root_id}
        frontier = [root_id]

        while frontier:
            child_ids = list(
                AdministrativeUnit.objects.filter(
                    parent_id__in=frontier,
                    is_active=True,
                ).values_list('id', flat=True)
            )
            next_frontier = [cid for cid in child_ids if cid not in all_ids]
            if not next_frontier:
                break
            all_ids.update(next_frontier)
            frontier = next_frontier

        return list(all_ids)

    @staticmethod
    def parse_sort_fields(raw_fields: str, raw_dirs: str) -> list:
        sort_fields = [item.strip() for item in (raw_fields or 'created_at').split(',') if item.strip()] or [
            'created_at']
        sort_dirs = [item.strip().lower() for item in (raw_dirs or 'desc').split(',') if item.strip()] or ['desc']

        if len(sort_dirs) < len(sort_fields):
            sort_dirs.extend([sort_dirs[-1]] * (len(sort_fields) - len(sort_dirs)))
        elif len(sort_dirs) > len(sort_fields):
            sort_dirs = sort_dirs[:len(sort_fields)]

        order_by = []
        for index, sort_field in enumerate(sort_fields):
            mapped_field = PERMIT_ADMIN_SORT_FIELDS.get(sort_field)
            if not mapped_field:
                continue

            direction = sort_dirs[index] if index < len(sort_dirs) else 'asc'
            if direction == 'desc' and not mapped_field.startswith('-'):
                mapped_field = f'-{mapped_field}'
            elif direction == 'asc' and mapped_field.startswith('-'):
                mapped_field = mapped_field[1:]

            order_by.append(mapped_field)

        if not order_by:
            order_by = ['-created_at']

        if 'pk' not in {field.lstrip('-') for field in order_by}:
            order_by.append('-pk')

        return order_by

    @classmethod
    def get_filtered_admin_permits(cls, params: dict, session_documents: list):
        queryset = PermitRequest.objects.select_related(
            'employee__person',
            'employee__area',
            'permit_type',
            'permit_type__parent',
        ).filter(permit_type__is_active=True).exclude(status='INACTIVE')

        query = (params.get('q') or '').strip()
        area_id = (params.get('area') or '').strip()
        permit_type_id = (params.get('permit_type') or '').strip()
        permit_subtype_id = (params.get('permit_subtype') or '').strip()
        status = (params.get('status') or '').strip()

        default_from, default_to = cls.get_current_month_bounds()
        date_from = (params.get('date_from') or default_from.isoformat()).strip()
        date_to = (params.get('date_to') or default_to.isoformat()).strip()
        raw_docs = (params.get('document_numbers') or '').strip()

        if raw_docs:
            doc_list = session_documents if raw_docs == 'session' else [
                c.strip() for c in raw_docs.split(',') if c.strip()
            ]
            if doc_list:
                queryset = queryset.filter(employee__person__document_number__in=doc_list)

        if query:
            for token in [t for t in query.split() if t]:
                queryset = queryset.filter(
                    Q(employee__person__first_name__icontains=token) |
                    Q(employee__person__last_name__icontains=token) |
                    Q(employee__person__document_number__icontains=token) |
                    Q(employee__area__name__icontains=token) |
                    Q(permit_type__name__icontains=token)
                )

        if area_id:
            unit_ids = cls.get_unit_tree_ids(area_id)
            queryset = queryset.filter(
                employee__area_id__in=unit_ids if unit_ids else [area_id]
            )

        if permit_type_id:
            queryset = queryset.filter(
                Q(permit_type_id=permit_type_id) | Q(permit_type__parent_id=permit_type_id)
            )

        if permit_subtype_id:
            queryset = queryset.filter(permit_type_id=permit_subtype_id)

        if status:
            queryset = queryset.filter(status=status)

        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)

        if date_to:
            queryset = queryset.filter(start_date__lte=date_to)

        order_by = cls.parse_sort_fields(params.get('sort_field'), params.get('sort_dir'))
        return queryset.order_by(*order_by)

    @staticmethod
    def attach_active_budgets(employees) -> list:
        employee_ids = [emp.id for emp in employees]
        budgets_dict = {}
        if employee_ids:
            budgets = BudgetLine.objects.filter(
                current_employee_id__in=employee_ids,
                is_active=True
            ).select_related('position_item')
            budgets_dict = {b.current_employee_id: b for b in budgets}

        return [{'employee': emp, 'budget': budgets_dict.get(emp.id)} for emp in employees]


class PermitWorkflowService:
    """Manages permit creation, approval, rejection, insistence, and QR generation."""

    @staticmethod
    def format_history_entry(css_class: str, label: str, message: str, existing_note: str = '') -> str:
        sanitized_msg = escape(message.strip())
        entry_html = f'<span class="note-label {css_class}">{label}: {sanitized_msg}</span>'
        return f'{entry_html}\n\n{existing_note}' if existing_note else entry_html

    @staticmethod
    def create_permit_request(user, employee: Employee, post_data: dict, files: dict) -> PermitRequest:
        permit_type_id = post_data.get('permit_subtype') or post_data.get('permit_type')
        if not permit_type_id:
            raise ValidationError('Debe seleccionar un tipo de permiso.')

        permit_type = PermitType.objects.filter(pk=permit_type_id, is_active=True).first()
        if not permit_type:
            raise ValidationError('El tipo de permiso seleccionado no es válido.')

        justification_file = files.get('justification_file')
        if permit_type.requires_attachment and not justification_file:
            raise ValidationError('Este tipo de permiso requiere adjuntar un archivo PDF.')

        if justification_file:
            validate_justification_file(justification_file)

        permit = PermitRequest(
            employee=employee,
            permit_type=permit_type,
            start_date=post_data.get('start_date'),
            start_time=post_data.get('start_time') or None,
            end_date=post_data.get('end_date') or None,
            end_time=post_data.get('end_time') or None,
            days=int(post_data.get('days') or 0),
            hours=int(post_data.get('hours') or 0),
            minutes=int(post_data.get('minutes') or 0),
            response_note=post_data.get('reason', '').strip(),
            justification_file=justification_file,
            created_by=user,
            updated_by=user,
            status='REQUESTED'
        )
        permit.full_clean()
        permit.save()
        return permit

    @classmethod
    def process_permit_response(cls, user, permit: PermitRequest, action: str, note: str) -> PermitRequest:
        if permit.status != 'REQUESTED':
            raise ValidationError('Este permiso ya fue procesado.')

        clean_note = (note or '').strip()
        if action == 'approve':
            permit.status = 'APPROVED'
            clean_note = clean_note or 'Se acepta el permiso'
            entry = cls.format_history_entry('note-justifica', 'Aprobación', clean_note, permit.response_note)
        elif action == 'reject':
            if not clean_note:
                raise ValidationError('Debe ingresar el motivo de la negativa.')
            permit.status = 'REJECTED'
            entry = cls.format_history_entry('note-reject', 'Rechazo', clean_note, permit.response_note)
        else:
            raise ValidationError('Acción no válida.')

        permit.response_note = entry
        permit.response_date = timezone.now()
        permit.response_by = user
        permit.updated_by = user
        permit.save(update_fields=[
            'status', 'response_note', 'response_date', 'response_by', 'updated_by', 'updated_at'
        ])
        return permit

    @staticmethod
    def insist_permit(user, permit: PermitRequest, insist_message: str) -> PermitRequest:
        if permit.status != 'REJECTED':
            raise ValidationError('Solo se puede insistir en permisos rechazados.')

        clean_msg = (insist_message or '').strip()
        if not clean_msg:
            raise ValidationError('Debe escribir un mensaje para insistir la solicitud.')

        now = timezone.localtime(timezone.now())
        user_full_name = user.get_full_name().strip() or user.username
        insist_note = f"INSISTENCIA ({now.strftime('%d/%m/%Y %H:%M')}) por {escape(user_full_name)}: {escape(clean_msg)}"

        permit.response_note = f"{permit.response_note}\n\n{insist_note}" if permit.response_note else insist_note
        permit.status = 'REQUESTED'
        permit.response_date = None
        permit.response_by = None
        permit.updated_by = user
        permit.save(update_fields=[
            'status', 'response_note', 'response_date', 'response_by', 'updated_by', 'updated_at'
        ])
        return permit

    @staticmethod
    def generate_qr_base64(validation_url: str) -> str:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(validation_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    @staticmethod
    def parse_identification_excel(excel_file) -> list:
        if not excel_file:
            raise ValidationError('No se proporcionó ningún archivo Excel.')

        if excel_file.size > 1 * 1024 * 1024:
            raise ValidationError('El archivo supera el tamaño máximo permitido de 1 MB.')

        if not (excel_file.name.endswith('.xlsx') or excel_file.name.endswith('.xls')):
            raise ValidationError('El archivo debe tener formato .xlsx o .xls.')

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
        unique_ids = list(dict.fromkeys(identifications))
        if not unique_ids:
            raise ValidationError('No se encontraron cédulas válidas (9 a 13 dígitos) en el archivo.')

        return unique_ids


class BinnacleService:
    """Manages binnacle (bitácora) creation, overlap validation, and batch transitions."""

    SPANISH_MONTHS = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
        5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
        9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }

    @staticmethod
    def get_or_create_binnacle_type() -> PermitType:
        binnacle_type = PermitType.objects.filter(name__icontains='Bitácora').first()
        if not binnacle_type:
            binnacle_type = PermitType.objects.create(
                name='Bitácora',
                needs_justification=True,
                affects_vacation=False,
                requires_attachment=False
            )
        return binnacle_type

    @staticmethod
    def _combine_datetime(target_date: date, target_time) -> datetime:
        if not target_time:
            return datetime.combine(target_date, dtime.min)
        if isinstance(target_time, str):
            fmt = '%H:%M:%S' if len(target_time.strip()) > 5 else '%H:%M'
            parsed_time = datetime.strptime(target_time.strip(), fmt).time()
            return datetime.combine(target_date, parsed_time)
        return datetime.combine(target_date, target_time)

    @classmethod
    def check_overlap(cls, employee: Employee, binnacle_type: PermitType, start_date: date,
                      end_date: date, start_time, end_time, exclude_pk: int = None):
        new_start = cls._combine_datetime(start_date, start_time)
        new_end = cls._combine_datetime(end_date or start_date, end_time)

        qs = PermitRequest.objects.filter(
            employee=employee,
            permit_type=binnacle_type,
            status='APPROVED',
            start_date__lte=end_date or start_date,
            end_date__gte=start_date
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)

        for existing in qs:
            ex_start = cls._combine_datetime(existing.start_date, existing.start_time)
            ex_end = cls._combine_datetime(existing.end_date or existing.start_date, existing.end_time)
            if new_start < ex_end and ex_start < new_end:
                month_name = cls.SPANISH_MONTHS.get(existing.start_date.month, '')
                date_str = f"{existing.start_date.day} de {month_name} de {existing.start_date.year}"
                time_str = existing.start_time.strftime('%H:%M') if existing.start_time else ''
                raise ValidationError(
                    f"Existe una bitácora aprobada el {date_str} desde las {time_str}."
                )

    @classmethod
    @transaction.atomic
    def register_binnacles(cls, user, employee: Employee, post_data: dict, attachment=None) -> int:
        if attachment:
            validate_justification_file(attachment)

        start_date_str = post_data.get('start_date')
        if not start_date_str:
            raise ValidationError('Debe ingresar la fecha de inicio.')

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        num_days = int(post_data.get('num_days', 1))
        justification = (post_data.get('justification') or '').strip()

        if not justification:
            raise ValidationError('Debe ingresar la justificación.')

        shifts = [
            (
                post_data.get('first_start', '').strip(),
                post_data.get('first_end', '').strip(),
                post_data.get('first_crosses_midnight') == 'on'
            ),
            (
                post_data.get('second_start', '').strip(),
                post_data.get('second_end', '').strip(),
                post_data.get('second_crosses_midnight') == 'on'
            )
        ]

        valid_shifts = [(s, e, cross) for s, e, cross in shifts if s and e]
        if not valid_shifts:
            raise ValidationError('Debe ingresar al menos una jornada completa.')

        binnacle_type = cls.get_or_create_binnacle_type()
        saved_path = None
        if attachment:
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            employee_slug = slugify(employee.person.full_name)
            file_path = os.path.join('permits', 'bitacoras', f"bitacora_{employee_slug}_{timestamp}.pdf")
            saved_path = default_storage.save(file_path, attachment)

        creation_note = PermitWorkflowService.format_history_entry('note-creation', 'Creación', justification)
        created_count = 0

        for day_offset in range(num_days):
            current_date = start_date + timedelta(days=day_offset)
            for shift_start, shift_end, crosses_midnight in valid_shifts:
                end_date = current_date + timedelta(days=1) if crosses_midnight else current_date
                cls.check_overlap(employee, binnacle_type, current_date, end_date, shift_start, shift_end)

                PermitRequest.objects.create(
                    employee=employee,
                    permit_type=binnacle_type,
                    start_date=current_date,
                    end_date=end_date,
                    start_time=shift_start,
                    end_time=shift_end,
                    justification_file=saved_path,
                    response_note=creation_note,
                    status='REQUESTED',
                    created_by=user,
                    updated_by=user
                )
                created_count += 1

        return created_count

    @classmethod
    def update_binnacle(cls, user, binnacle: PermitRequest, start_time: str, end_time: str,
                        note: str = None, attachment=None) -> PermitRequest:
        if attachment:
            validate_justification_file(attachment)

        candidate_start = start_time if start_time is not None else binnacle.start_time
        candidate_end = end_time if end_time is not None else binnacle.end_time

        cls.check_overlap(
            binnacle.employee,
            binnacle.permit_type,
            binnacle.start_date,
            binnacle.end_date or binnacle.start_date,
            candidate_start,
            candidate_end,
            exclude_pk=binnacle.pk
        )

        was_rejected = binnacle.status == 'REJECTED'
        save_fields = ['updated_by', 'updated_at']

        if start_time is not None:
            binnacle.start_time = start_time or None
            save_fields.append('start_time')
        if end_time is not None:
            binnacle.end_time = end_time or None
            save_fields.append('end_time')
        if note is not None and note.strip():
            css_cls = 'note-justifica' if was_rejected else 'note-modifica'
            label = 'Justifica' if was_rejected else 'Modifica'
            binnacle.response_note = PermitWorkflowService.format_history_entry(
                css_cls, label, note, binnacle.response_note
            )
            save_fields.append('response_note')
        if attachment:
            binnacle.justification_file = attachment
            save_fields.append('justification_file')

        if was_rejected:
            binnacle.status = 'REQUESTED'
            binnacle.response_by = None
            binnacle.response_date = None
            save_fields.extend(['status', 'response_by', 'response_date'])

        binnacle.updated_by = user
        binnacle.save(update_fields=save_fields)
        return binnacle


def build_approved_permits_summary(queryset):
    """
    Calcula el resumen de tiempo de permisos APROBADOS agrupado por empleado y tipo de permiso.
    Regla: 8 horas (480 minutos) equivalen a 1 día. Los estados distintos a APPROVED no suman.
    """
    approved_qs = queryset.filter(status='APPROVED').select_related(
        'employee__person', 'permit_type'
    )

    grouped = defaultdict(lambda: {
        'employee_name': '',
        'document_number': '',
        'permit_type': '',
        'approved_count': 0,
        'total_minutes': 0,
    })

    grand_total_minutes = 0
    grand_approved_count = 0

    for permit in approved_qs:
        mins = ((permit.days or 0) * 480) + ((permit.hours or 0) * 60) + (permit.minutes or 0)
        key = (permit.employee_id, permit.permit_type_id)

        item = grouped[key]
        item['employee_name'] = permit.employee.person.full_name
        item['document_number'] = permit.employee.person.document_number or '--'
        item['permit_type'] = permit.permit_type.name
        item['approved_count'] += 1
        item['total_minutes'] += mins

        grand_total_minutes += mins
        grand_approved_count += 1

    def format_duration(total_mins):
        days = total_mins // 480
        rem = total_mins % 480
        hours = rem // 60
        minutes = rem % 60
        return {
            'days': days,
            'hours': hours,
            'minutes': minutes,
            'formatted': f"{days}d {hours}h {minutes}m"
        }

    items = []
    for data in sorted(grouped.values(), key=lambda x: (x['employee_name'], x['permit_type'])):
        dur = format_duration(data['total_minutes'])
        items.append({
            'employee_name': data['employee_name'],
            'document_number': data['document_number'],
            'permit_type': data['permit_type'],
            'approved_count': data['approved_count'],
            **dur,
        })

    return {
        'items': items,
        'total_approved_count': grand_approved_count,
        'grand_total': format_duration(grand_total_minutes),
    }
