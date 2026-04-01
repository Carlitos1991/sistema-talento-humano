"""
Management command para limpiar sesiones expiradas (>12 horas sin actividad)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from security.models import UserSession


class Command(BaseCommand):
    help = 'Limpia sesiones que no han tenido actividad en más de 12 horas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=12,
            help='Número de horas de inactividad para considerar una sesión expirada (default: 12)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se eliminaría sin hacerlo realmente'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']
        
        threshold = timezone.now() - timedelta(hours=hours)
        
        expired_sessions = UserSession.objects.filter(last_activity__lt=threshold)
        count = expired_sessions.count()
        
        if dry_run:
            self.stdout.write(f'Se eliminarían {count} sesiones expiradas (>  {hours} horas)')
            for session in expired_sessions:
                print(f'  - {session.user.username}: última actividad {session.last_activity}')
        else:
            expired_sessions.delete()
            self.stdout.write(
                self.style.SUCCESS(f'Se eliminaron {count} sesiones expiradas')
            )
