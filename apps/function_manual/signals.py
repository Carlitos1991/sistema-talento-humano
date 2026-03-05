from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import JobActivity


@receiver(post_save, sender=JobActivity)
def update_profile_points_on_activity_save(sender, instance, created, **kwargs):
    """
    Cuando se guarda una actividad, actualiza el total_activity_points del perfil.
    """
    if instance.profile:
        instance.profile.update_total_activity_points()


@receiver(post_delete, sender=JobActivity)
def update_profile_points_on_activity_delete(sender, instance, **kwargs):
    """
    Cuando se elimina una actividad, actualiza el total_activity_points del perfil.
    """
    if instance.profile:
        instance.profile.update_total_activity_points()
