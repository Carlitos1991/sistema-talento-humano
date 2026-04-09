from django.core.management.base import BaseCommand
from sanctions.models import NotificationTemplate, SanctionNotificationType, TemplateSection
from contract.models import LaborRegime
from django.db import IntegrityError


class Command(BaseCommand):
    help = 'Crea templates dinámicos para todas las combinaciones de SanctionNotificationType + LaborRegime'

    def handle(self, *args, **options):
        notification_types = SanctionNotificationType.objects.filter(is_active=True)
        labor_regimes = LaborRegime.objects.filter(is_active=True)
        
        created = 0
        already_exist = 0
        
        for notif_type in notification_types:
            for regime in labor_regimes:
                try:
                    template, was_created = NotificationTemplate.objects.get_or_create(
                        notification_type=notif_type,
                        labor_regime=regime,
                        defaults={'is_active': True}
                    )
                    
                    if was_created:
                        # Crear una sección de ejemplo por defecto
                        TemplateSection.objects.create(
                            template=template,
                            section_type='PARAGRAPH',
                            content=f'[Aquí irá el contenido de la notificación para {notif_type.name} en régimen {regime.name}]',
                            order=0,
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f"✓ Creado: {notif_type.name} - {regime.name}")
                        )
                        created += 1
                    else:
                        already_exist += 1
                except IntegrityError:
                    already_exist += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n{created} templates creados'))
        self.stdout.write(self.style.WARNING(f'{already_exist} templates ya existentes'))
