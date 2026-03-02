from django.shortcuts import redirect
from django.urls import reverse


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

        # Intentar resolver la URL de login, fallback a la configuración directa
        try:
            login_url_resolved = reverse('core:login')
        except:
            login_url_resolved = '/login/'  # Fallback genérico si falla el reverse

        # 1. Rutas PÚBLICAS (Lista Blanca)
        # Aquí definimos qué partes del sistema no requieren usuario/contraseña
        public_paths = [
            login_url_resolved,  # La página de login
            '/admin/',  # El admin de Django (tiene su propio login)
            '/static/',  # Archivos CSS/JS
            '/media/',  # Archivos subidos
            '/biometric/adms/',  # Tu ruta antigua (opcional)
            '/iclock/',  # <--- ¡IMPORTANTE! Esta es la ruta que usa el ZKTeco
        ]

        # 2. Verificar si la petición actual empieza con alguna ruta pública
        # El startswith permite que '/iclock/cdata', '/iclock/getrequest', etc., pasen.
        is_public = any(path.startswith(p) for p in public_paths)

        # 3. Si no es pública y no está autenticado, enviarlo al login
        if not is_public and not request.user.is_authenticated:
            return redirect(login_url_resolved)

        # 4. Lógica de Cambio de Contraseña Obligatorio
        if request.user.is_authenticated:
            if getattr(request.user, 'must_change_password', False):
                # Evitar bucle infinito y permitir estáticos
                if not path.startswith('/security/change-password/') and not path.startswith('/static/'):
                    return redirect('/security/change-password/?force=1')

        return self.get_response(request)
