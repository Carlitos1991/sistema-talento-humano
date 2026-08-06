"""
keycloak_service.py

Servicio de aprovisionamiento perezoso hacia Keycloak.

Se invoca DESPUÉS de que el login local (CustomLoginView) ya validó las
credenciales contra la base de datos de Django. Este módulo NO valida
contraseñas: solo garantiza que la persona que acaba de loguearse localmente
también tenga una cuenta en Keycloak, creándola si hace falta.

Requiere en Keycloak (realm 'municipio' o el que uses):
  1. Un cliente CONFIDENCIAL nuevo, ej. 'sigeth-admin-service', distinto del
     cliente 'sigeth' que usa el login SSO normal.
  2. En ese cliente: pestaña "Settings" -> 'Service Accounts Enabled' = ON.
  3. En ese cliente: pestaña "Service Account Roles" -> asignar, del cliente
     'realm-management', los roles: manage-users, view-users, query-users.
  4. Copiar su Client Secret (pestaña "Credentials") a la variable de entorno
     KEYCLOAK_ADMIN_CLIENT_SECRET.

Settings requeridos (agregar a settings.py):
    KEYCLOAK_ADMIN_CLIENT_ID = os.environ.get('KEYCLOAK_ADMIN_CLIENT_ID', 'sigeth-admin-service')
    KEYCLOAK_ADMIN_CLIENT_SECRET = os.environ.get('KEYCLOAK_ADMIN_CLIENT_SECRET', '')

(Reutiliza KEYCLOAK_URL y REALM que ya existen en tu settings.py actual.)
"""
import logging
import secrets
import string

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 8  # segundos


def _admin_token_url() -> str:
    return f"{settings.KEYCLOAK_URL}/realms/{settings.REALM}/protocol/openid-connect/token"


def _admin_users_url() -> str:
    return f"{settings.KEYCLOAK_URL}/admin/realms/{settings.REALM}/users"


def get_admin_token() -> str:
    """
    Client Credentials Grant contra el cliente de servicio. Retorna un
    access_token con permisos de administración de usuarios sobre el realm.
    """
    resp = requests.post(
        _admin_token_url(),
        data={
            'grant_type': 'client_credentials',
            'client_id': settings.KEYCLOAK_ADMIN_CLIENT_ID,
            'client_secret': settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()['access_token']


def find_keycloak_user_by_document(document_number: str) -> dict | None:
    """
    Busca por el atributo personalizado 'document_number' (la cédula), NO por
    username, porque el username local (cédula, ver CreateUserFromLoginView)
    y el username generado en Keycloak (inicial+apellido, ver auth.py) tienen
    formatos distintos y no son comparables directamente.

    Devuelve la representación del usuario de Keycloak (dict) o None.
    """
    token = get_admin_token()
    resp = requests.get(
        _admin_users_url(),
        headers={'Authorization': f'Bearer {token}'},
        params={'q': f'document_number:{document_number}'},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json()
    return results[0] if results else None


def _generate_temp_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + '!@#$%'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def create_keycloak_user(*, username: str, email: str, first_name: str,
                         last_name: str, document_number: str,
                         password: str | None = None,
                         temporary: bool = True) -> tuple[str | None, str]:
    """
    Crea el usuario en Keycloak.

    - Si `password` no se especifica, se genera una contraseña ALEATORIA
      temporal (comportamiento original, pensado para el aprovisionamiento
      perezoso desde ensure_keycloak_account, donde el usuario ya entró por
      otro medio y esta cuenta de Keycloak es "de respaldo").
    - Si se pasa `password` explícito (ej. la cédula, para el registro vía
      CreateUserFromLoginView), se usa esa. En ese caso normalmente querrás
      temporary=False, porque KeycloakPasswordBackend usa el grant
      'password' (ROPC), y Keycloak RECHAZA ese grant si la cuenta tiene
      una acción pendiente como UPDATE_PASSWORD.
    - Si temporary=True, se agrega requiredActions=['UPDATE_PASSWORD']: la
      próxima vez que esa persona autentique DIRECTAMENTE contra Keycloak
      (flujo SSO real por redirect), Keycloak la obligará a cambiarla.

    Devuelve (keycloak_user_id, password_usada). keycloak_user_id puede ser
    None si Keycloak no devolvió el header Location esperado.
    """
    token = get_admin_token()
    final_password = password if password is not None else _generate_temp_password()

    payload = {
        'username': username,
        'email': email,
        'firstName': first_name,
        'lastName': last_name,
        'enabled': True,
        'emailVerified': True,
        'attributes': {
            'document_number': [document_number],
            'locale': ['es']
        },
        'credentials': [{
            'type': 'password',
            'value': final_password,
            'temporary': temporary,
        }],
    }
    if temporary:
        payload['requiredActions'] = ['UPDATE_PASSWORD']

    resp = requests.post(
        _admin_users_url(),
        headers={'Authorization': f'Bearer {token}'},
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    if resp.status_code == 409:
        raise ValueError(
            f"Ya existe un usuario en Keycloak con username='{username}' o email='{email}' "
            f"(pero sin document_number='{document_number}' coincidente: revisar manualmente)."
        )
    resp.raise_for_status()

    location = resp.headers.get('Location', '')
    keycloak_user_id = location.rstrip('/').split('/')[-1] if location else None

    return keycloak_user_id, final_password


def set_keycloak_password(keycloak_user_id: str, new_password: str, *, temporary: bool = False) -> None:
    """
    Restablece la contraseña de un usuario en Keycloak vía Admin API
    (endpoint PUT /admin/realms/{realm}/users/{id}/reset-password).

    Si temporary=True, Keycloak marcará la contraseña como temporal y
    exigirá cambio en el próximo login DIRECTO contra Keycloak (SSO real).
    Como el login vía KeycloakPasswordBackend usa el grant 'password', una
    contraseña temporal hará que Keycloak RECHACE ese login hasta que el
    usuario la cambie por el flujo hospedado de Keycloak; por eso, para
    mantener "el mismo login" funcionando de inmediato, usa temporary=False
    salvo que tengas pensado un flujo de cambio de contraseña aparte.
    """
    token = get_admin_token()
    resp = requests.put(
        f"{_admin_users_url()}/{keycloak_user_id}/reset-password",
        headers={'Authorization': f'Bearer {token}'},
        json={'type': 'password', 'value': new_password, 'temporary': temporary},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()


def reset_password_by_document(document_number: str, new_password: str) -> dict:
    """
    Punto de entrada para "recuperar contraseña": busca al usuario en
    Keycloak por su document_number (cédula) y le restablece la
    contraseña ahí. Keycloak es la fuente de verdad; la BD local de
    Django NO se toca.

    Retorna {'status': 'ok'} | {'status': 'not_found'} | {'status': 'error', 'reason': str}
    """
    try:
        existing = find_keycloak_user_by_document(document_number)
    except Exception:
        logger.exception(
            "[KEYCLOAK][RESET] Error consultando Keycloak para document_number=%s", document_number,
        )
        return {'status': 'error', 'reason': 'no se pudo consultar Keycloak'}

    if not existing:
        logger.warning(
            "[KEYCLOAK][RESET] No existe usuario en Keycloak para document_number=%s", document_number,
        )
        return {'status': 'not_found'}

    try:
        set_keycloak_password(existing['id'], new_password, temporary=False)
    except Exception:
        logger.exception(
            "[KEYCLOAK][RESET] Error restableciendo password en Keycloak para document_number=%s",
            document_number,
        )
        return {'status': 'error', 'reason': 'no se pudo restablecer la contraseña en Keycloak'}

    logger.info("[KEYCLOAK][RESET] Password restablecido en Keycloak para document_number=%s", document_number)
    return {'status': 'ok', 'keycloak_user_id': existing['id']}


def verify_keycloak_password(username: str, password: str) -> bool:
    """
    Confirma que `password` es la contraseña ACTUAL del usuario en
    Keycloak, usando el mismo grant 'password' (ROPC) que usa
    KeycloakPasswordBackend para el login. Se usa antes de permitir un
    cambio de contraseña, para no dejar que cualquiera con la sesión
    abierta (o un token robado) cambie la clave sin saber la actual.
    """
    try:
        resp = requests.post(
            settings.OIDC_OP_TOKEN_ENDPOINT,
            data={
                'grant_type': 'password',
                'client_id': settings.OIDC_RP_CLIENT_ID,
                'client_secret': settings.OIDC_RP_CLIENT_SECRET,
                'username': username,
                'password': password,
                'scope': 'openid',
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        logger.exception(
            "[KEYCLOAK][CAMBIO_PASSWORD] No se pudo contactar a Keycloak para verificar la contraseña actual.")
        return False

    return resp.status_code == 200


def change_password_by_document(document_number: str, current_password: str,
                                username: str, new_password: str) -> dict:
    """
    Punto de entrada para "Cambiar contraseña" (usuario YA autenticado en
    el sistema, cambiando su propia clave por gusto).

    1. Verifica `current_password` contra Keycloak (ROPC) — si no coincide,
       no se cambia nada.
    2. Si coincide, busca al usuario en Keycloak por document_number y le
       actualiza la contraseña ahí (Admin API), no temporal.

    Keycloak sigue siendo la única fuente de verdad; la BD local de Django
    no guarda la contraseña nueva (debe quedar/seguir "unusable").

    Retorna:
        {'status': 'ok'}
        {'status': 'invalid_current_password'}
        {'status': 'not_found'}
        {'status': 'error', 'reason': str}
    """
    if not verify_keycloak_password(username, current_password):
        return {'status': 'invalid_current_password'}

    try:
        existing = find_keycloak_user_by_document(document_number)
    except Exception:
        logger.exception(
            "[KEYCLOAK][CAMBIO_PASSWORD] Error consultando Keycloak para document_number=%s", document_number,
        )
        return {'status': 'error', 'reason': 'no se pudo consultar Keycloak'}

    if not existing:
        logger.warning(
            "[KEYCLOAK][CAMBIO_PASSWORD] No existe usuario en Keycloak para document_number=%s", document_number,
        )
        return {'status': 'not_found'}

    try:
        set_keycloak_password(existing['id'], new_password, temporary=False)
    except Exception:
        logger.exception(
            "[KEYCLOAK][CAMBIO_PASSWORD] Error actualizando password en Keycloak para document_number=%s",
            document_number,
        )
        return {'status': 'error', 'reason': 'no se pudo actualizar la contraseña en Keycloak'}

    logger.info(
        "[KEYCLOAK][CAMBIO_PASSWORD] Password actualizado en Keycloak para document_number=%s", document_number,
    )
    return {'status': 'ok'}


def ensure_keycloak_account(person, django_user, plain_password: str | None = None) -> dict:
    """
    Punto de entrada principal, llamado DESPUÉS de un login local exitoso
    (ver CustomLoginView.form_valid).

    Nunca lanza excepciones hacia la vista: si Keycloak no responde o falla,
    se registra en logs y el login local sigue funcionando con normalidad.

    Si se recibe `plain_password` (la contraseña que el usuario acaba de
    escribir en el form), la cuenta se crea en Keycloak con el MISMO
    username local (django_user.username) y ESA MISMA contraseña, no
    temporal. Así, la próxima vez que esta persona intente loguearse,
    KeycloakPasswordBackend (ROPC) la valida directamente y ya no depende
    del respaldo local (ModelBackend).

    Si no se recibe `plain_password` (por compatibilidad con otros
    llamadores), se conserva el comportamiento anterior: username generado
    (`generate_keycloak_username`) + contraseña aleatoria temporal. OJO: en
    ese caso la cuenta creada NO podrá loguearse vía KeycloakPasswordBackend
    hasta que alguien la resetee manualmente (queda pensada solo para el
    flujo SSO por redirect).

    Retorna un dict informativo:
        {'status': 'skipped'|'exists'|'created'|'error', ...}
    """
    document_number = getattr(person, 'document_number', None)
    if not document_number:
        logger.warning(
            "[KEYCLOAK][PROVISION] Person id=%s sin document_number; "
            "no se puede verificar/crear en Keycloak.", getattr(person, 'id', None)
        )
        return {'status': 'skipped', 'reason': 'sin document_number'}

    try:
        existing = find_keycloak_user_by_document(document_number)
    except Exception:
        logger.exception(
            "[KEYCLOAK][PROVISION] Error consultando Keycloak para document_number=%s",
            document_number,
        )
        return {'status': 'error', 'reason': 'no se pudo consultar Keycloak'}

    if existing:
        logger.info(
            "[KEYCLOAK][PROVISION] Ya existe en Keycloak (id=%s) para document_number=%s",
            existing.get('id'), document_number,
        )
        return {'status': 'exists', 'keycloak_user': existing}

    try:
        if plain_password:
            # Camino nuevo: mismo username local + misma contraseña que el
            # usuario ya conoce, sin acción pendiente, para login inmediato.
            keycloak_username = django_user.username
            keycloak_user_id, _ = create_keycloak_user(
                username=keycloak_username,
                email=django_user.email or '',
                first_name=django_user.first_name,
                last_name=django_user.last_name,
                document_number=document_number,
                password=plain_password,
                temporary=False,
            )
            temp_password = None
        else:
            # Camino legado: username generado + password aleatoria temporal
            # (pensado para el flujo SSO por redirect, no para ROPC).
            from .auth import generate_keycloak_username
            keycloak_username = generate_keycloak_username(django_user.first_name, django_user.last_name)

            keycloak_user_id, temp_password = create_keycloak_user(
                username=keycloak_username,
                email=django_user.email or '',
                first_name=django_user.first_name,
                last_name=django_user.last_name,
                document_number=document_number,
            )
    except Exception:
        logger.exception(
            "[KEYCLOAK][PROVISION] Error creando usuario en Keycloak para document_number=%s",
            document_number,
        )
        return {'status': 'error', 'reason': 'no se pudo crear en Keycloak'}

    logger.info(
        "[KEYCLOAK][PROVISION] Usuario creado en Keycloak id=%s para document_number=%s",
        keycloak_user_id, document_number,
    )
    return {
        'status': 'created',
        'keycloak_user_id': keycloak_user_id,
        'temp_password': temp_password,
    }

def find_keycloak_user_by_username(username: str) -> dict | None:
    """
    Busca al usuario en Keycloak por su username exacto.
    Devuelve la representación del usuario de Keycloak (dict) o None.
    """
    token = get_admin_token()
    resp = requests.get(
        _admin_users_url(),
        headers={'Authorization': f'Bearer {token}'},
        params={
            'username': username,
            'exact': True  # Clave para evitar coincidencias parciales
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json()
    return results[0] if results else None


def send_keycloak_reset_password_email(keycloak_user_id: str, redirect_uri: str) -> None:
    """
    Solicita a Keycloak que envíe su propio correo de restablecimiento de contraseña.
    Se envía la cabecera de idioma para forzar el correo en español.
    """
    token = get_admin_token()

    params = {
        'client_id': settings.OIDC_RP_CLIENT_ID,
        'redirect_uri': redirect_uri
    }

    # Inyectamos Accept-Language para forzar la respuesta y el correo en español
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept-Language': 'es,es-ES;q=0.9,en;q=0.8'
    }

    resp = requests.put(
        f"{_admin_users_url()}/{keycloak_user_id}/execute-actions-email",
        headers=headers,
        params=params,
        json=['UPDATE_PASSWORD'],
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()