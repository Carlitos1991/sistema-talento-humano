import re
from django.utils import timezone

STOP_WORDS = {'DE', 'DEL', 'LA', 'LAS', 'LOS', 'EL', 'Y', 'E', 'EN', 'POR', 'PARA'}


def get_clean_acronym(text):
    """
    Extrae la primera letra de las palabras significativas ignorando conectores.
    Ejemplo: 'Dirección de Tecnologías de la Información' -> 'DTI'
    'Coordinación de Desarrollo de Software' -> 'CDS'
    """
    if not text:
        return ''
    clean_text = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]', ' ', text).upper()
    words = [w for w in clean_text.split() if w not in STOP_WORDS]
    return ''.join([w[0] for w in words])


def get_user_name_initials(user):
    """
    Obtiene las iniciales de los nombres y apellidos del funcionario.
    Ejemplo: 'Carlos Isrrael Chacha Guaman' -> 'CICG'
    """
    person = getattr(user, 'person', None)
    if person:
        full = f"{person.first_name or ''} {person.last_name or ''}".strip()
    else:
        full = user.get_full_name() or user.username

    clean = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]', ' ', full).upper()
    parts = clean.split()
    return ''.join([p[0] for p in parts]) if parts else 'USR'


def generate_document_filing_code(unit, user, doc_type, is_personal=False):
    """
    Construye la codificación:
    Dirección: ML - DT - 2026 - 0001 - M
    Personal:  ML - DT - CDS - CICG - 2026 - 0001 - M
    """
    from .models import Document
    year = timezone.now().year
    type_suffix = doc_type.code_prefix or get_clean_acronym(doc_type.name)[:1]

    # Recorrer jerarquía ascendente hasta la raíz
    hierarchy = []
    curr = unit
    while curr:
        hierarchy.insert(0, curr)
        curr = curr.parent

    # Acrónimos organizacionales
    unit_acronyms = [get_clean_acronym(u.name) for u in hierarchy if get_clean_acronym(u.name)]

    parts = ['ML']
    if is_personal:
        parts.extend(unit_acronyms)
        parts.append(get_user_name_initials(user))
    else:
        # Nivel de la unidad seleccionada
        parts.extend(unit_acronyms)

    base_prefix = '-'.join(parts) + f"-{year}-"

    # Secuencial del año para ese prefijo exacto
    count = Document.objects.filter(
        filing_code__startswith=base_prefix,
        registration_date__year=year
    ).count() + 1

    return f"{base_prefix}{count:04d}-{type_suffix}"