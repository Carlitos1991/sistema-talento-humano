"""
Management command para sincronizar sesiones de Django con UserSession
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from security.models import UserSession


User = get_user_model()


class Command(BaseCommand):
    help = 'Sincroniza las sesiones de Django activas con UserSession'

    def handle(self, *args, **options):
        # Obtener todos los usuarios activos
        active_users = User.objects.filter(is_active=True)
        
        created_count = 0
        updated_count = 0
        
        for user in active_users:
            # Crear sesión para cada usuario activo si no existe
            session, created = UserSession.objects.update_or_create(
                user=user,
                defaults={
                    'ip_address': '0.0.0.0',  # Placeholder
                    'last_activity': timezone.now(),
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Se crearon {created_count} sesiones y se actualizaron {updated_count}'
            )
        )
