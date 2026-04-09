from .models import PersonAuditLog


PERSON_AUDIT_SECTIONS = {
    'personal': 'Datos personales',
    'institutional': 'Datos institucionales',
    'economic': 'Datos económicos',
    'budget': 'Partida presupuestaria',
    'contracts': 'Historia laboral',
    'permissions': 'Permisos',
    'actions': 'Acciones de personal',
    'sanctions': 'Sanciones',
    'vacations': 'Vacaciones',
    'payments': 'Roles de pago',
    'curriculum': 'Curriculum',
    'photo': 'Foto',
}


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_person_audit(request, person, action, section='', details=''):
    if not request.user.is_authenticated:
        return None

    return PersonAuditLog.objects.create(
        person=person,
        user=request.user,
        action=action,
        section=section or '',
        details=details or '',
        ip_address=get_client_ip(request),
    )
