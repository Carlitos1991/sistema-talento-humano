from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class SIGETHSecurityMiddleware:
    """
    Middleware global de seguridad.
    Controla que solo usuarios autenticados accedan al sistema,
    pero deja puertas abiertas para el hardware (ADMS).
    También registra la actividad de cada usuario.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Actualizar última actividad del usuario si está autenticado
        if request.user.is_authenticated:
            try:
                from security.models import UserSession
                
                # Obtener IP del cliente (mejorado)
                ip_address = None
                
                # Intenta obtner de X-Forwarded-For (proxy/load balancer)
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(',')[0].strip()
                
                # Si no, intenta X-Real-IP
                if not ip_address:
                    ip_address = request.META.get('HTTP_X_REAL_IP', '').strip()
                
                # Si no, usa REMOTE_ADDR
                if not ip_address:
                    ip_address = request.META.get('REMOTE_ADDR', '').strip()
                
                # Obtener session_key
                try:
                    session_key = request.session.session_key
                except Exception:
                    session_key = None
                
                # Actualizar o crear sesión usando SOLO el usuario como clave
                if ip_address:  # Solo actualizar si tenemos IP válida
                    UserSession.objects.update_or_create(
                        user=request.user,
                        defaults={
                            'ip_address': ip_address,
                            'session_key': session_key,
                            'last_activity': timezone.now(),
                        }
                    )
                else:
                    # Si no hay IP, solo actualizar last_activity
                    UserSession.objects.filter(user=request.user).update(
                        last_activity=timezone.now(),
                        session_key=session_key
                    )
            except Exception as e:
                pass  # Silenciar errores en la actualización de actividad

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
            '/favicon.ico',  # Permitir favicon sin autenticación
            '/static/',  # Archivos CSS/JS
            '/media/',  # Archivos subidos
            '/biometric/adms/',  # Tu ruta antigua (opcional)
            '/iclock/',  # <--- ¡IMPORTANTE! Esta es la ruta que usa el ZKTeco
            '/payroll/payslips/validate/',  # Validación pública de roles de pago mediante QR
            '/permissions/validate/',  # Validación pública de permisos mediante QR
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
