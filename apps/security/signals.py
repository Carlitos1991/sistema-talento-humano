from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone
from .models import UserSession

def get_client_ip(request):
    """Obtiene la IP del cliente considerando proxies"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_user_agent(request):
    """Obtiene el User Agent del cliente"""
    return request.META.get('HTTP_USER_AGENT', '')

@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """
    Registra la sesión del usuario con IP cuando inicia sesión.
    """
    session_key = request.session.session_key
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    # Crear o actualizar la sesión con los datos más nuevos
    UserSession.objects.update_or_create(
        user=user,
        session_key=session_key,
        defaults={
            'ip_address': ip_address,
            'user_agent': user_agent,
        }
    )

@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """
    Elimina la sesión cuando el usuario cierra sesión.
    """
    session_key = request.session.session_key
    UserSession.objects.filter(user=user, session_key=session_key).delete()
