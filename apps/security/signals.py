from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone
from .models import UserSession

@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """
    Handles the user logged in signal.
    """
    session_key = request.session.session_key
    ip_address = request.META.get('REMOTE_ADDR')
    UserSession.objects.get_or_create(
        user=user,
        ip_address=ip_address,
        session_key=session_key
    )

@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """
    Handles the user logged out signal.
    """
    session_key = request.session.session_key
    UserSession.objects.filter(user=user, session_key=session_key).delete()
