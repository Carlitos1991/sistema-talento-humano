from django.db import OperationalError, ProgrammingError
from django.db.models import Q


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

        roots = list(
            HelpMessage.objects.filter(
                original_message__isnull=True
            ).exclude(
                status__in=[HelpMessage.Status.ATTENDED, HelpMessage.Status.FINALIZED]
            ).filter(
                Q(sender_user=request.user) | Q(recipient_user=request.user)
            ).values_list('id', flat=True)
        )

        pending_count = 0
        if roots:
            thread_messages = HelpMessage.objects.filter(
                Q(id__in=roots) | Q(original_message_id__in=roots)
            ).values('id', 'original_message_id', 'recipient_user_id', 'created_at').order_by('created_at')

            last_recipient_by_root = {}
            for item in thread_messages:
                root_id = item['original_message_id'] or item['id']
                last_recipient_by_root[root_id] = item['recipient_user_id']

            pending_count = sum(1 for _, recipient_id in last_recipient_by_root.items() if recipient_id == request.user.id)

        return {
            'help_messages_show_notifications': pending_count > 0,
            'help_messages_unread_count': pending_count,
            'help_messages_url': 'security:help_message_list'
        }
    except (OperationalError, ProgrammingError, Exception):
        return {
            'help_messages_show_notifications': False,
            'help_messages_unread_count': 0,
            'help_messages_url': ''
        }
