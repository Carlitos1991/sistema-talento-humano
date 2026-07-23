from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class KeycloakOIDCBackend(OIDCAuthenticationBackend):
    def create_user(self, claims):
        """Se ejecuta la primera vez que un usuario de Keycloak entra al sistema"""
        # Crea el usuario base usando el username/email provisto por Keycloak
        user = super().create_user(claims)

        # Sincronizamos los datos del token con tu modelo personalizado
        user.first_name = claims.get('given_name', '')
        user.last_name = claims.get('family_name', '')

        # Mapeo de campos personalizados si tu compañero los incluyó en el token
        user.custom_name = f"{user.first_name} {user.last_name}".strip()
        user.custom_position = claims.get('position', '')  # Si viene del LDAP/Keycloak

        user.save()
        return user

    def update_user(self, user, claims):
        """Se ejecuta en cada inicio de sesión posterior para mantener los datos actualizados"""
        user.first_name = claims.get('given_name', '')
        user.last_name = claims.get('family_name', '')

        # Actualizas el cargo por si cambió en la institución
        if 'position' in claims:
            user.custom_position = claims.get('position', '')

        user.save()
        return user