# auth.py
import logging
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from person.models import Person

logger = logging.getLogger(__name__)


def provider_logout(request):
    """
    Función registrada en settings.OIDC_OP_LOGOUT_URL_METHOD.

    mozilla-django-oidc llama a esta función ANTES de invocar auth.logout(request),
    así que aquí request.session todavía tiene el 'oidc_id_token' (requiere
    settings.OIDC_STORE_ID_TOKEN = True).

    Construye la URL de RP-Initiated Logout de Keycloak. Desde Keycloak 18+ el
    parámetro legacy 'redirect_uri' ya no funciona: hay que enviar
    'id_token_hint' + 'post_logout_redirect_uri'.
    """
    logout_url = settings.OIDC_OP_LOGOUT_ENDPOINT
    id_token = request.session.get('oidc_id_token')

    if id_token:
        params = {
            'id_token_hint': id_token,
            'post_logout_redirect_uri': request.build_absolute_uri(settings.LOGOUT_REDIRECT_URL),
        }
        logout_url = f"{logout_url}?{urlencode(params)}"

    return logout_url


class KeycloakPasswordBackend(ModelBackend):
    """
    Backend de autenticación que valida usuario/contraseña DIRECTAMENTE
    contra Keycloak, usando el grant 'password' (también llamado Resource
    Owner Password Credentials / "Direct Access Grants" en Keycloak).

    Esto permite seguir usando el formulario propio (login.html) sin
    redirigir al usuario a la pantalla de login de Keycloak: el usuario
    escribe usuario/contraseña en nuestro form, y nosotros se lo pasamos
    a Keycloak por detrás para que él haga la validación real.

    A partir de este backend, Keycloak es la ÚNICA fuente de verdad para
    la contraseña. La base de datos local de Django deja de guardar
    contraseñas utilizables para los usuarios gestionados por Keycloak
    (ver CreateUserFromLoginView y ForgotPasswordView, que ahora deben
    dejar el password local "unusable" y operar contra Keycloak).

    REQUISITO EN KEYCLOAK:
      En el cliente `settings.OIDC_RP_CLIENT_ID` (el mismo cliente 'sigeth'
      que ya usas para el flujo SSO por redirect):
        Pestaña "Settings" -> "Direct Access Grants Enabled" = ON

    IMPORTANTE - convención de username:
      Este backend busca al usuario local por `username` exacto (el mismo
      valor que se envía a Keycloak). Para que esto funcione, el username
      local y el username en Keycloak DEBEN ser el mismo string. Si sigues
      usando `generate_keycloak_username()` (inicial+apellido) para las
      cuentas creadas por el flujo SSO, y la cédula para las cuentas
      creadas por CreateUserFromLoginView/ForgotPasswordView, vas a tener
      DOS convenciones distintas y este backend no podrá resolverlas todas
      con el mismo criterio. Revisa el mensaje de acompañamiento.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        try:
            token_resp = requests.post(
                settings.OIDC_OP_TOKEN_ENDPOINT,
                data={
                    'grant_type': 'password',
                    'client_id': settings.OIDC_RP_CLIENT_ID,
                    'client_secret': settings.OIDC_RP_CLIENT_SECRET,
                    'username': username,
                    'password': password,
                    'scope': 'openid',
                },
                timeout=8,
            )
        except requests.RequestException:
            logger.exception("[KEYCLOAK][LOGIN] No se pudo contactar a Keycloak para validar credenciales.")
            return None

        if token_resp.status_code != 200:
            # Credenciales inválidas, usuario deshabilitado, o cuenta con
            # una acción pendiente (ej. UPDATE_PASSWORD) -> Keycloak
            # responde 400/401 y NO autenticamos.
            logger.info(
                "[KEYCLOAK][LOGIN] Rechazado por Keycloak para username=%s (status=%s)",
                username, token_resp.status_code,
            )
            return None

        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(username__iexact=username)
        except UserModel.DoesNotExist:
            logger.warning(
                "[KEYCLOAK][LOGIN] Keycloak validó a '%s' pero no existe usuario local con ese username.",
                username,
            )
            return None
        except UserModel.MultipleObjectsReturned:
            logger.error(
                "[KEYCLOAK][LOGIN] Más de un usuario local coincide con username='%s' (iexact).",
                username,
            )
            return None

        if not self.user_can_authenticate(user):
            return None

        return user


def generate_keycloak_username(first_name: str, last_name: str) -> str:
    """
    Convención única de username para Keycloak: inicial del primer nombre +
    primer apellido + inicial del segundo apellido (ej. 'jrodriguezp').

    Esta es la MISMA regla que antes vivía inline en KeycloakOIDCBackend.create_user.
    Se extrajo aquí para que keycloak_service.py (aprovisionamiento perezoso
    desde el login local) genere usernames con el mismo formato, en vez de
    usar el username local (que es la cédula) y crear una inconsistencia
    entre cuentas creadas por un flujo u otro.

    NOTA: no valida colisiones (dos personas con mismo nombre+apellido
    generarían el mismo username). Ese comportamiento ya existía antes de
    esta extracción; si quieres que se resuelva, hay que agregar una
    verificación de unicidad con sufijo numérico en ambos flujos.
    """
    nombres = (first_name or '').strip().split()
    apellidos = (last_name or '').strip().split()

    inicial_nombre = nombres[0][0].lower() if nombres else ''
    primer_apellido = apellidos[0].lower() if apellidos else ''
    inicial_segundo_apellido = apellidos[1][0].lower() if len(apellidos) > 1 else ''

    return f"{inicial_nombre}{primer_apellido}{inicial_segundo_apellido}"


class KeycloakOIDCBackend(OIDCAuthenticationBackend):

    def filter_users_by_claims(self, claims):
        """
        Sobrescribimos este método para que el algoritmo valide
        por el nuevo username en lugar del email por defecto.
        """
        username = claims.get('preferred_username')
        if not username:
            return self.UserModel.objects.none()
        try:
            return self.UserModel.objects.filter(username__iexact=username)
        except self.UserModel.DoesNotExist:
            return self.UserModel.objects.none()

    def create_user(self, claims):
        """Se ejecuta la primera vez que un usuario autenticado por Keycloak entra al sistema"""

        # Obtenemos el email y el username que envía Keycloak (ej: jrodriguezp)
        keycloak_username = claims.get('preferred_username', '').lower()
        email = claims.get('email', '')

        # IMPORTANTE: Debes enviar la cédula desde Keycloak en un claim personalizado.
        # Ajusta 'document_number' al nombre exacto del claim que configures en tu Realm.
        cedula = claims.get('document_number', '')

        # Validamos en la base de datos de talento humano
        person = Person.objects.filter(
            document_number=cedula
        ).select_related('employee_profile__employment_status').first()

        if not person:
            raise Exception("No se encontró una persona registrada con esa cédula en la institución.")

        employee_profile = getattr(person, 'employee_profile', None)
        if not employee_profile or not employee_profile.is_active:
            raise Exception("Para crear usuario debe estar registrado como empleado o trabajador de la institución.")

        employment_code = (getattr(getattr(employee_profile, 'employment_status', None), 'code', '') or '').upper()
        if employment_code not in ['EMPLEADO', 'TRABAJADOR']:
            raise Exception("Solo se pueden crear usuarios para registros con estado laboral EMPLEADO o TRABAJADOR.")

        # --- LÓGICA DE GENERACIÓN DE USERNAME (compartida con keycloak_service.py) ---
        nuevo_username = generate_keycloak_username(person.first_name, person.last_name)

        # Creación del usuario en Django
        user = super().create_user(claims)
        # Asignamos el username generado (debe coincidir con keycloak_username si Keycloak usa la misma regla)
        user.username = nuevo_username
        user.email = email
        user.first_name = person.first_name
        user.last_name = person.last_name
        user.save()

        # Vinculación del usuario al modelo Person
        person.user = user
        person.save(update_fields=['user', 'updated_at'])

        # Asignación de permisos base
        normal_group, _ = Group.objects.get_or_create(name='USUARIO_NORMAL')
        user.groups.add(normal_group)

        ct = ContentType.objects.get_for_model(Group)
        dashboard_perm, _ = Permission.objects.get_or_create(
            codename='dashboard_empleado',
            content_type=ct,
            defaults={'name': 'Acceso dashboard empleado'}
        )
        user.user_permissions.add(dashboard_perm)

        return user

    def update_user(self, user, claims):
        """Mantiene sincronizado el correo si cambia en Keycloak en futuros logins"""
        user.email = claims.get('email', user.email)
        user.save()
        return user
