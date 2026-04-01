from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class HelpMessage(models.Model):
    class Status(models.TextChoices):
        SENT = 'sent', 'Enviado'
        READ = 'read', 'Leído'
        ATTENDED = 'attended', 'Atendido'

    sender_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='help_messages_sent',
        verbose_name='Solicitante'
    )
    recipient_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='help_messages_received',
        verbose_name='Destinatario'
    )
    subject = models.CharField(max_length=255, verbose_name='Asunto')
    detail = models.TextField(verbose_name='Detalle')
    attachment = models.FileField(
        upload_to='help_messages/attachments/',
        null=True,
        blank=True,
        verbose_name='Anexo'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SENT,
        verbose_name='Estado'
    )
    original_message = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name='Mensaje original'
    )
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de lectura')
    attended_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de atención')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='security_helpmessage_created',
        null=True,
        blank=True,
        verbose_name='Creado por'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='security_helpmessage_updated',
        null=True,
        blank=True,
        verbose_name='Actualizado por'
    )

    def __str__(self):
        return f'{self.subject} - {self.sender_user} -> {self.recipient_user}'

    @property
    def sender_name(self):
        person = getattr(self.sender_user, 'person', None)
        if person:
            return person.full_name
        return self.sender_user.get_full_name() or self.sender_user.username

    @property
    def recipient_name(self):
        person = getattr(self.recipient_user, 'person', None)
        if person:
            return person.full_name
        return self.recipient_user.get_full_name() or self.recipient_user.username

    @property
    def status_label(self):
        return self.get_status_display()

    class Meta:
        verbose_name = 'Mensaje de Ayuda'
        verbose_name_plural = 'Mensajes de Ayuda'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient_user', 'status', '-created_at']),
            models.Index(fields=['sender_user', '-created_at']),
        ]


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
