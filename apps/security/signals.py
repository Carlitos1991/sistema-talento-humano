from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone
from .models import UserSession
import logging

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Obtiene la IP del cliente considerando proxies"""
    # Intentar múltiples fuentes de IP
    ip = None
    
    # Método 1: X-Forwarded-For (si está detrás de proxy/load balancer)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    
    # Método 2: X-Real-IP (some proxies)
    if not ip:
        ip = request.META.get('HTTP_X_REAL_IP')
    
    # Método 3: REMOTE_ADDR (directo o tras proxy simple)
    if not ip:
        ip = request.META.get('REMOTE_ADDR')
    
    # LimPiar la IP
    if ip:
        ip = ip.strip()
    
    logger.info(f"IP capturada: {ip} (X-Forwarded-For: {x_forwarded_for})")
    
    return ip

def get_user_agent(request):
    """Obtiene el User Agent del cliente"""
    return request.META.get('HTTP_USER_AGENT', '')

@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """
    Registra la sesión del usuario con IP cuando inicia sesión.
    """
    try:
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        try:
            session_key = request.session.session_key
        except Exception:
            session_key = None
        
        # Validar que ip_address no sea vacío
        if not ip_address or ip_address.strip() == '':
            ip_address = 'No disponible'
        
        # Crear o actualizar la sesión usando solo el usuario como clave
        session_obj, created = UserSession.objects.update_or_create(
            user=user,
            defaults={
                'ip_address': ip_address,
                'session_key': session_key,
                'user_agent': user_agent,
            }
        )
        
        logger.info(f"UserSession {'creada' if created else 'actualizada'} para {user.username}: IP={ip_address}")
        
    except Exception as e:
        logger.error(f"Error en user_logged_in_handler: {str(e)}")

@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """
    Elimina la sesión cuando el usuario cierra sesión.
    """
    session_key = request.session.session_key
    UserSession.objects.filter(user=user, session_key=session_key).delete()
