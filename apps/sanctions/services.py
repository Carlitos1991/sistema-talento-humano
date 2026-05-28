from datetime import date
from django.conf import settings
from pypdf import PdfReader, PdfWriter

PLACEHOLDER_KEYS = [
    'EMPLOYEE_FULL_NAME',
    'EMPLOYEE_FIRST_NAME',
    'EMPLOYEE_LAST_NAME',
    'EMPLOYEE_DOCUMENT_NUMBER',
    'EMPLOYEE_POSITION',
    'EMPLOYEE_UNIT',
    'REGIME_CODE',
    'REGIME_NAME',
    'NOTIFICATION_NAME',
    'MONTH_NAME',
    'MONTH_NUMBER',
    'YEAR',
    'REGISTRATION_DATE',
    'AUTHORITY_1_NAME',
    'AUTHORITY_1_POSITION',
    'AUTHORITY_2_NAME',
    'AUTHORITY_2_POSITION',
    'MINUTES_LATE',
    'REGS_WITHOUT_MARK',
    'DAYS_WITHOUT_MARK',
    'OBSERVATIONS',
]


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


def build_notification_replacements(data):
    sequence_code = str(data.get('sequence_code', '') or '')
    user_code = str(data.get('user_code', '') or '')
    registration_date = data.get('registration_date', '')
    minutes_late = data.get('minutes_late')
    regs_without_mark = data.get('regs_without_mark')
    days_without_mark = data.get('days_without_mark')

    minutes_late_text = '0' if minutes_late is None else str(minutes_late)
    regs_without_mark_text = '0' if regs_without_mark is None else str(regs_without_mark)
    days_without_mark_text = '0' if days_without_mark is None else str(days_without_mark)

    replacements = {
        '[FULL_NAME]': data.get('employee_full_name', ''),
        '[NAME]': data.get('employee_first_name', ''),
        '[LAST_NAME]': data.get('employee_last_name', ''),
        '[DOCUMENT_NUMBER]': data.get('employee_document_number', ''),
        '[POSITION]': data.get('employee_position', ''),
        '[UNIT]': data.get('employee_unit', ''),
        '[EMPLOYEE_FULL_NAME]': data.get('employee_full_name', ''),
        '[EMPLOYEE_FIRST_NAME]': data.get('employee_first_name', ''),
        '[EMPLOYEE_LAST_NAME]': data.get('employee_last_name', ''),
        '[EMPLOYEE_DOCUMENT_NUMBER]': data.get('employee_document_number', ''),
        '[EMPLOYEE_POSITION]': data.get('employee_position', ''),
        '[EMPLOYEE_UNIT]': data.get('employee_unit', ''),
        '[REGIME_CODE]': data.get('regime_code', ''),
        '[REGIME_NAME]': data.get('regime_name', ''),
        '[NOTIFICATION_NAME]': data.get('notification_name', ''),
        '[MONTH_NAME]': data.get('month_name', ''),
        '[MONTH_NUMBER]': str(data.get('month_number', '') or ''),
        '[YEAR]': str(data.get('year', '') or ''),
        '[AÑO]': str(data.get('year', '') or ''),
        '[REGISTRATION_DATE]': registration_date,
        '[DATE]': registration_date,
        '[today]': registration_date,
        '[TODAY]': registration_date,
        '[LOCALIDAD]': data.get('location', 'Loja') or 'Loja',
        '[SECUENCIA]': sequence_code,
        '[SECUENCIAL]': sequence_code,
        '[CODIGO]': sequence_code,
        '[CODIGO_USUARIO]': user_code,
        '[AUTHORITY_1_NAME]': data.get('authority_1_name', ''),
        '[AUTHORITY_1_POSITION]': data.get('authority_1_position', ''),
        '[AUTHORITY_2_NAME]': data.get('authority_2_name', ''),
        '[AUTHORITY_2_POSITION]': data.get('authority_2_position', ''),
        '[NOMBRE_AUTORIDAD1]': data.get('authority_1_name', ''),
        '[CARGO_AUTORIDAD1]': data.get('authority_1_position', ''),
        '[NOMBRE_AUTORIDAD2]': data.get('authority_2_name', ''),
        '[CARGO_AUTORIDAD2]': data.get('authority_2_position', ''),
        '[MINUTES_LATE]': minutes_late_text,
        '[MINUTOS]': minutes_late_text,
        '[REGS_WITHOUT_MARK]': regs_without_mark_text,
        '[DAYS_WITHOUT_MARK]': days_without_mark_text,
        '[DIAS_SIN_MARCAR]': days_without_mark_text,
        '[OBSERVATIONS]': data.get('observations', ''),
    }
    return replacements


def build_replacements_from_mappings(data, mappings):
    base = build_notification_replacements(data)
    dynamic_replacements = {}

    for mapping in mappings:
        source_value = data.get(mapping.source_key, '')
        dynamic_replacements[mapping.placeholder] = str(source_value or '')

    base.update(dynamic_replacements)
    return base


def _get_nested_value(data, path):
    current = data
    for part in path.split('.'):
        if current is None:
            return ''
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, '')
    return current if current is not None else ''


def _split_expression(expression):
    parts = []
    current = []
    quote = None

    for char in expression:
        if char in ('"', "'"):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            current.append(char)
            continue

        if char == '+' and quote is None:
            token = ''.join(current).strip()
            if token:
                parts.append(token)
            current = []
            continue

        current.append(char)

    token = ''.join(current).strip()
    if token:
        parts.append(token)
    return parts


def evaluate_mapping_expression(expression, data):
    expression = (expression or '').strip()
    if not expression:
        return ''

    if expression.lower() == 'today':
        return _format_spanish_date(date.today())

    if expression.lower().startswith('today:'):
        date_format = expression.split(':', 1)[1].strip() or '%d/%m/%Y'
        return date.today().strftime(date_format)

    value_parts = []
    for token in _split_expression(expression):
        if token.startswith(('"', "'")) and token.endswith(('"', "'")) and len(token) >= 2:
            value_parts.append(token[1:-1])
            continue
        if token.lower() == 'today':
            value_parts.append(_format_spanish_date(date.today()))
            continue
        if token.lower().startswith('today:'):
            date_format = token.split(':', 1)[1].strip() or '%d/%m/%Y'
            value_parts.append(date.today().strftime(date_format))
            continue
        value_parts.append(str(_get_nested_value(data, token)).strip())

    return ''.join(value_parts)


def build_replacements_from_global_mappings(data, mappings):
    replacements = build_notification_replacements(data)
    for mapping in mappings:
        replacements[mapping.placeholder] = evaluate_mapping_expression(mapping.expression, data)
    return replacements


