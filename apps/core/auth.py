"""
Backends de autenticación y utilidades OIDC/Keycloak para SIGETH.
"""
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
    """Construye la URL de cierre de sesión RP-Initiated Logout en Keycloak."""
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
    """Valida credenciales directamente contra Keycloak mediante grant_type=password."""

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
            logger.info(
                "[KEYCLOAK][LOGIN] Rechazado por Keycloak para username=%s (status=%s)",
                username,
                token_resp.status_code,
            )
            return None

        user_model = get_user_model()
        try:
            user = user_model.objects.get(username__iexact=username)
        except user_model.DoesNotExist:
            logger.warning(
                "[KEYCLOAK][LOGIN] Keycloak validó a '%s' pero no existe usuario local.",
                username,
            )
            return None
        except user_model.MultipleObjectsReturned:
            logger.error(
                "[KEYCLOAK][LOGIN] Múltiples usuarios locales coinciden con username='%s'.",
                username,
            )
            return None

        if not self.user_can_authenticate(user):
            return None

        return user


def generate_keycloak_username(first_name: str, last_name: str) -> str:
    """Genera el username institucional: inicial primer nombre + primer apellido + inicial segundo apellido."""
    first_names = (first_name or '').strip().split()
    last_names = (last_name or '').strip().split()

    first_name_initial = first_names[0][0].lower() if first_names else ''
    first_surname = last_names[0].lower() if last_names else ''
    second_surname_initial = last_names[1][0].lower() if len(last_names) > 1 else ''

    return f"{first_name_initial}{first_surname}{second_surname_initial}"


class KeycloakOIDCBackend(OIDCAuthenticationBackend):
    """Backend de autenticación federada OIDC con aprovisionamiento local."""

    def filter_users_by_claims(self, claims):
        username = claims.get('preferred_username')
        if not username:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(username__iexact=username)

    def create_user(self, claims):
        email = claims.get('email', '')
        document_number = claims.get('document_number', '')

        person = Person.objects.filter(
            document_number=document_number
        ).select_related('employee_profile__employment_status').first()

        if not person:
            raise Exception('No se encontró una persona registrada con esa cédula en la institución.')

        employee_profile = getattr(person, 'employee_profile', None)
        if not employee_profile or not employee_profile.is_active:
            raise Exception('Para crear usuario debe estar registrado como empleado o trabajador de la institución.')

        employment_code = (getattr(getattr(employee_profile, 'employment_status', None), 'code', '') or '').upper()
        if employment_code not in {'EMPLEADO', 'TRABAJADOR'}:
            raise Exception('Solo se pueden crear usuarios para registros con estado laboral EMPLEADO o TRABAJADOR.')

        generated_username = generate_keycloak_username(person.first_name, person.last_name)

        user = super().create_user(claims)
        user.username = generated_username
        user.email = email
        user.first_name = person.first_name
        user.last_name = person.last_name
        user.save()

        person.user = user
        person.save(update_fields=['user', 'updated_at'])

        normal_group, _ = Group.objects.get_or_create(name='USUARIO_NORMAL')
        user.groups.add(normal_group)

        content_type = ContentType.objects.get_for_model(Group)
        dashboard_perm, _ = Permission.objects.get_or_create(
            codename='dashboard_empleado',
            content_type=content_type,
            defaults={'name': 'Acceso dashboard empleado'},
        )
        user.user_permissions.add(dashboard_perm)

        return user

    def update_user(self, user, claims):
        user.email = claims.get('email', user.email)
        user.save(update_fields=['email'])
        return user
