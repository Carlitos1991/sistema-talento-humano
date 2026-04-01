"""
Management command para llenar last_activity en sesiones existentes
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from security.models import UserSession


class Command(BaseCommand):
    help = 'Llena last_activity con created_at para sesiones sin última actividad registrada'

    def handle(self, *args, **options):
        # Encontrar sesiones con last_activity NULL o vacío
        sessions_to_update = UserSession.objects.filter(
            last_activity__isnull=True
        )
        
        count = 0
        for session in sessions_to_update:
            # Si tiene created_at, usar eso; si no, usar now()
            if session.created_at:
                session.last_activity = session.created_at
            else:
                session.last_activity = timezone.now()
            session.save()
            count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Se actualizaron {count} sesiones con last_activity'
            )
        )
