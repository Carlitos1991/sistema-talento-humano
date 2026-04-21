import os
from datetime import datetime
from django.db import models
from django.conf import settings


class DocumentType(models.Model):
    name = models.CharField(max_length=50, verbose_name='Nombre')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Tipo de Documento'
        verbose_name_plural = 'Tipos de Documentos'
        ordering = ['name']

    def __str__(self):
        return self.name


class Document(models.Model):
    # Genera rutas tipo: documents/2023/10/archivo.pdf
    def document_upload_path(self, filename):
        return f'documents/{datetime.now().strftime("%Y/%m")}/{filename}'

    filing_code = models.CharField(
        max_length=50, unique=True, verbose_name='Nro. Archivo/Radicado',
        help_text="Identificador único del documento"
    )
    category = models.ForeignKey(
        DocumentType, on_delete=models.PROTECT, related_name='documents',
        verbose_name='Tipo de Registro'
    )
    subject = models.CharField(max_length=255, verbose_name="Asunto")

    # "responsible" del modelo anterior (quien firma/envía)
    sender_name = models.CharField(max_length=255, verbose_name="Remitente / Responsable", blank=True, null=True)

    # "target_person" del modelo anterior
    recipient_name = models.CharField(max_length=255, verbose_name="Dirigido a", blank=True, null=True)

    file_attachment = models.FileField(
        upload_to=document_upload_path, verbose_name='Archivo Digital',
        blank=True, null=True
    )

    registration_date = models.DateTimeField(default=datetime.now, verbose_name="Fecha de Registro")
    observation = models.TextField(verbose_name='Observaciones', blank=True, null=True)

    # Control de estado lógico
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='documents_created',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='Creado por'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='documents_updated',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='Última edición por'
    )

    class Meta:
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
        ordering = ['-registration_date']

    def __str__(self):
        return f"{self.filing_code} - {self.subject}"

    def delete(self, *args, **kwargs):
        # Opcional: Borrar archivo físico al borrar registro
        if self.file_attachment:
            if os.path.isfile(self.file_attachment.path):
                os.remove(self.file_attachment.path)
        super().delete(*args, **kwargs)