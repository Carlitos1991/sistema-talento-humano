from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=17, null=True, blank=True, verbose_name='Dirección MAC')
    session_key = models.CharField(max_length=40, null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True, verbose_name='User Agent')
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} - {self.ip_address}'

    @property
    def is_session_active(self):
        """Verifica si la sesión está activa (menos de 12 horas sin actividad)"""
        SESSION_TIMEOUT = 12  # horas
        timeout_threshold = timezone.now() - timedelta(hours=SESSION_TIMEOUT)
        return self.last_activity >= timeout_threshold

    class Meta:
        verbose_name = 'Sesión de Usuario'
        verbose_name_plural = 'Sesiones de Usuarios'
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', '-last_activity']),
        ]
