from django.db import OperationalError, ProgrammingError


def help_messages_notifications(request):
    """Retorna el conteo de mensajes pendientes para el usuario autenticado."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'help_messages_show_notifications': False,
            'help_messages_unread_count': 0,
            'help_messages_url': ''
        }

    try:
        from .models import HelpMessage
        unread_count = HelpMessage.objects.filter(
            recipient_user=request.user,
            status=HelpMessage.Status.SENT
        ).count()

        return {
            'help_messages_show_notifications': unread_count > 0,
            'help_messages_unread_count': unread_count,
            'help_messages_url': 'security:help_message_list'
        }
    except (OperationalError, ProgrammingError, Exception):
        return {
            'help_messages_show_notifications': False,
            'help_messages_unread_count': 0,
            'help_messages_url': ''
        }
