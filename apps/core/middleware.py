# apps/core/middleware.py
from django.shortcuts import redirect
from django.conf import settings
from django.urls import resolve, reverse


class SIGETHSecurityMiddleware:
    """
    Middleware global de seguridad.
    Controla que solo usuarios autenticados accedan al sistema,
    pero deja puertas abiertas para el hardware (ADMS).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        try:
            login_path = settings.LOGIN_URL if settings.LOGIN_URL.startswith('/') else reverse(settings.LOGIN_URL)
        except Exception:
            login_path = settings.LOGIN_URL
        # 1. Rutas que el biométrico y el público pueden usar sin estar logueados
        # Ajustado a tus URLs actuales
        public_paths = [
            login_path,
            settings.LOGIN_URL,  # también aceptar el nombre por si acaso
            '/admin/',
            '/static/',
            '/media/',
            '/biometric/adms/',
        ]

        # 2. Verificar si la petición es para una ruta pública
        is_public = any(path.startswith(p) for p in public_paths)

        # 3. Si no es pública y no está autenticado, enviarlo al login
        if not is_public and not request.user.is_authenticated:
            # Usamos reverse para obtener la URL del nombre 'core:login' definido en tu settings
            return redirect(settings.LOGIN_URL)

        # 4. Lógica de Cambio de Contraseña Obligatorio (Si la necesitas)
        if request.user.is_authenticated:
            # Solo si tu modelo de Usuario tiene este campo
            if getattr(request.user, 'must_change_password', False):
                # Evitar bucle infinito si ya está intentando cambiarla
                if not path.startswith('/security/change-password/') and not path.startswith('/static/'):
                    return redirect('/security/change-password/?force=1')

        return self.get_response(request)