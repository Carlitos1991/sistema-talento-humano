from django.db import OperationalError, ProgrammingError
from django.db.models import Q
from django.db.models.functions import Coalesce


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
                Q(sender_user=request.user) | Q(recipient_user=request.user)
            ).annotate(
                root_id=Coalesce('original_message_id', 'id')
            ).values_list('root_id', flat=True).distinct()
        )

        pending_count = 0
        if roots:
            root_status_map = {
                item['id']: item['status']
                for item in HelpMessage.objects.filter(id__in=roots).values('id', 'status')
            }

            thread_messages = HelpMessage.objects.filter(
                Q(id__in=roots) | Q(original_message_id__in=roots)
            ).values('id', 'original_message_id', 'recipient_user_id', 'created_at').order_by('created_at')

            last_recipient_by_root = {}
            for item in thread_messages:
                root_id = item['original_message_id'] or item['id']
                last_recipient_by_root[root_id] = item['recipient_user_id']

            pending_count = sum(
                1
                for root_id, recipient_id in last_recipient_by_root.items()
                if recipient_id == request.user.id and root_status_map.get(root_id) != HelpMessage.Status.FINALIZED
            )

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
