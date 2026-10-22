"""
Módulo de Modelos para Gestión Documental, Trámites y Firma Electrónica (SIGETH).
Define el expediente institucional (Procedure), sus tareas concurrentes,
la trazabilidad inmutable para Contraloría y los documentos generados/escaneados.
"""

import os
from datetime import datetime
from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import BaseModel, CatalogItem
from institution.models import AdministrativeUnit


# ==============================================================================
# 1. PERFIL DE FIRMA ELECTRÓNICA DEL USUARIO (.p12 / .pfx)
# ==============================================================================
def user_signature_path(instance, filename):
    return f'signatures/user_{instance.user_id}/certificate.p12'


class UserSignatureProfile(BaseModel):
    """
    Conserva la ubicación y metadatos del certificado de firma digital del usuario.
    La clave privada se valida y abre exclusivamente en memoria; jamás se guarda la contraseña.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='signature_profile',
        verbose_name="Usuario"
    )
    certificate_file = models.FileField(
        upload_to=user_signature_path,
        verbose_name="Archivo de Certificado (.p12 / .pfx)"
    )
    issuer = models.CharField(max_length=255, blank=True, null=True, verbose_name="Entidad Emisora")
    subject_dn = models.CharField(max_length=255, blank=True, null=True, verbose_name="Titular de la Firma")
    serial_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Serie")
    valid_from = models.DateTimeField(blank=True, null=True, verbose_name="Válido Desde")
    valid_to = models.DateTimeField(blank=True, null=True, verbose_name="Válido Hasta")

    class Meta:
        verbose_name = "Perfil de Firma Electrónica"
        verbose_name_plural = "Perfiles de Firmas Electrónicas"

    def __str__(self):
        return f"Firma de {self.user.get_full_name() or self.user.username}"

    @property
    def file_exists(self):
        return bool(self.certificate_file and os.path.isfile(self.certificate_file.path))

    @property
    def is_expired(self):
        if not self.valid_to:
            return True
        return timezone.now() > self.valid_to


# ==============================================================================
# 2. TIPOS DE DOCUMENTO (CATÁLOGO OFICIAL)
# ==============================================================================
class DocumentType(BaseModel):
    """
    Catálogo de categorías documentales reconocidas (Memorando, Oficio, Informe Técnico).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    code_prefix = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Prefijo para Radicado (Ej: MEM, OFI, INF)"
    )
    is_external = models.BooleanField(
        default=False,
        verbose_name="Aplica para Recepción Externa",
        help_text="Marque esta opción para que el tipo de documento esté disponible en Ventanilla/Recepción."
    )

    class Meta:
        verbose_name = "Tipo de Documento"
        verbose_name_plural = "Tipos de Documentos"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({'Externo' if self.is_external else 'Interno'})"

# ==============================================================================
# 3. EXPEDIENTE / TRÁMITE INSTITUCIONAL (PROCEDURE)
# ==============================================================================
class Procedure(BaseModel):
    """
    Expediente principal que recorre la institución.
    Posee número único institucional, tipo de trámite, estado y semáforo individual.
    """

    class ProcedureType(models.TextChoices):
        RECEPCION = 'RECEPCION', 'Recepción Externa / Ventanilla'
        INTERNO = 'INTERNO', 'Trámite Interno'

    class Priority(models.TextChoices):
        NORMAL = 'NORMAL', 'Normal'
        URGENTE = 'URGENTE', 'Urgente'
        MUY_URGENTE = 'MUY_URGENTE', 'Muy Urgente'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Borrador'
        IN_DESPATCH = 'IN_DESPATCH', 'En Despacho / Secretaría'
        IN_PROCESS = 'IN_PROCESS', 'En Trámite'
        ATTENDED = 'ATTENDED', 'Atendido'
        DISPATCHED = 'DISPATCHED', 'Despachado'
        ARCHIVED = 'ARCHIVED', 'Archivado'

    code = models.CharField(
        max_length=60,
        unique=True,
        db_index=True,
        verbose_name="Número de Radicado / Trámite"
    )
    procedure_type = models.CharField(
        max_length=20,
        choices=ProcedureType.choices,
        default=ProcedureType.RECEPCION,
        verbose_name="Tipo de Trámite"
    )
    category = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='procedures',
        verbose_name="Tipo de Documento Principal"
    )
    subject = models.CharField(max_length=255, verbose_name="Asunto")

    # Datos Remitente Externo (Ventanilla / Ciudadanía)
    external_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Nro. Oficio / Documento Externo"
    )
    external_sender = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Remitente Externo"
    )
    external_id_card = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Cédula / RUC del Solicitante"
    )
    external_email = models.EmailField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Correo Electrónico para Notificación"
    )

    # Estado y Control
    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name="Estado del Trámite"
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
        verbose_name="Prioridad"
    )
    current_unit = models.ForeignKey(
        AdministrativeUnit,
        on_delete=models.PROTECT,
        related_name='held_procedures',
        null=True,
        blank=True,
        verbose_name="Unidad Administrativa Actual"
    )
    limit_date = models.DateTimeField(
        verbose_name="Fecha Límite de Atención",
        null=True,
        blank=True
    )
    closed_at = models.DateTimeField(
        verbose_name="Fecha y Hora de Cierre Definitivo",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Trámite"
        verbose_name_plural = "Trámites"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.subject}"

    @property
    def semaphore_status(self):
        """
        Calcula el semáforo propio del trámite:
        - COMPLETADO (Azul)
        - VENCIDO (Rojo)
        - POR_VENCER (Amarillo, menos del 40% del tiempo disponible)
        - A_TIEMPO (Verde)
        """
        if self.status in [self.Status.ATTENDED, self.Status.DISPATCHED, self.Status.ARCHIVED]:
            return 'COMPLETADO'
        if not self.limit_date:
            return 'A_TIEMPO'

        now = timezone.now()
        if now > self.limit_date:
            return 'VENCIDO'

        total_time = (self.limit_date - self.created_at).total_seconds()
        remaining_time = (self.limit_date - now).total_seconds()

        if total_time > 0 and (remaining_time / total_time) < 0.4:
            return 'POR_VENCER'

        return 'A_TIEMPO'


# ==============================================================================
# 4. TAREAS CONCURRENTES / DELEGACIÓN (PROCEDURE TASK)
# ==============================================================================
class ProcedureTask(BaseModel):
    """
    Representa una asignación activa en el despacho de un funcionario o unidad.
    Soporta bifurcación concurrente (Fork & Join) para tareas compartidas.
    """

    class TaskStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        IN_PROCESS = 'IN_PROCESS', 'En Elaboración'
        UNDER_REVIEW = 'UNDER_REVIEW', 'En Revisión / Visto Bueno'
        RESPONDED = 'RESPONDED', 'Respondido / Elevado'
        RETURNED = 'RETURNED', 'Devuelto con Observaciones'
        CLOSED = 'CLOSED', 'Cerrado'

    procedure = models.ForeignKey(
        Procedure,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name="Trámite Matriz"
    )
    unit = models.ForeignKey(
        AdministrativeUnit,
        on_delete=models.PROTECT,
        related_name='assigned_procedure_tasks',
        verbose_name="Unidad Asignada"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='procedure_tasks',
        null=True,
        blank=True,
        verbose_name="Funcionario Asignado"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='delegated_procedure_tasks',
        verbose_name="Delegado por"
    )
    parent_task = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subtasks',
        verbose_name="Tarea Predecesora"
    )
    is_main_task = models.BooleanField(
        default=True,
        verbose_name="Es Tarea Principal",
        help_text="True si este funcionario consolida la respuesta final; False si es tarea compartida de apoyo."
    )
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
        verbose_name="Estado de la Tarea"
    )
    limit_date = models.DateTimeField(
        verbose_name="Fecha Límite Interna",
        null=True,
        blank=True
    )
    responded_at = models.DateTimeField(
        verbose_name="Fecha de Atención",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Tarea de Trámite"
        verbose_name_plural = "Tareas de Trámites"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.procedure.code} -> {self.unit.name}"

    @property
    def semaphore_status(self):
        if self.status in [self.TaskStatus.RESPONDED, self.TaskStatus.CLOSED]:
            return 'COMPLETADO'
        if not self.limit_date:
            return 'A_TIEMPO'

        now = timezone.now()
        if now > self.limit_date:
            return 'VENCIDO'

        total_time = (self.limit_date - self.created_at).total_seconds()
        remaining_time = (self.limit_date - now).total_seconds()

        if total_time > 0 and (remaining_time / total_time) < 0.4:
            return 'POR_VENCER'

        return 'A_TIEMPO'


# ==============================================================================
# 5. SUMILLAS / DISPOSICIONES FIRMADAS (PROCEDURE SUMILLA)
# ==============================================================================
class ProcedureSumilla(BaseModel):
    """
    Disposición oficial dictada por una autoridad sobre una tarea de trámite.
    Almacena los metadatos de la firma electrónica tras la legalización.
    """
    task = models.OneToOneField(
        ProcedureTask,
        on_delete=models.CASCADE,
        related_name='sumilla',
        verbose_name="Tarea Asociada"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='authored_sumillas',
        verbose_name="Autor de la Disposición"
    )
    instruction = models.CharField(
        max_length=255,
        verbose_name="Tipo de Disposición / Instrucción Clave"
    )
    observation = models.TextField(
        blank=True,
        null=True,
        verbose_name="Texto Detallado de la Sumilla"
    )
    is_signed = models.BooleanField(
        default=False,
        verbose_name="Firmado Electrónicamente"
    )
    signed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha y Hora del Sellado"
    )
    signature_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Metadatos Criptográficos de Firma"
    )

    class Meta:
        verbose_name = "Sumilla de Trámite"
        verbose_name_plural = "Sumillas de Trámites"

    def __str__(self):
        return f"Sumilla #{self.pk} - {self.author.get_full_name()}"


# ==============================================================================
# 6. DOCUMENTOS ASOCIADOS (GENERADOS EN EDITOR O ESCANEADOS)
# ==============================================================================
class Document(BaseModel):
    """
    Documento oficial individual (Oficio escaneado de entrada, Informe Técnico,
    Memorando redactado en editor o resolución final).
    """

    def document_upload_path(self, filename):
        return f'documents/{datetime.now().strftime("%Y/%m")}/{filename}'

    class DocumentStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Borrador'
        UNDER_REVIEW = 'UNDER_REVIEW', 'En Revisión'
        APPROVED = 'APPROVED', 'Aprobado (Listo para Firma)'
        SIGNED = 'SIGNED', 'Firmado Electrónicamente'

    procedure = models.ForeignKey(
        Procedure,
        on_delete=models.CASCADE,
        related_name='documents',
        null=True,
        blank=True,
        verbose_name="Trámite Asociado"
    )
    task = models.ForeignKey(
        ProcedureTask,
        on_delete=models.SET_NULL,
        related_name='documents',
        null=True,
        blank=True,
        verbose_name="Tarea Origen"
    )
    filing_code = models.CharField(
        max_length=60,
        unique=True,
        verbose_name="Número de Radicado del Documento"
    )
    category = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='documents',
        verbose_name="Tipo de Documento"
    )
    subject = models.CharField(max_length=255, verbose_name="Asunto")
    sender_name = models.CharField(max_length=255, verbose_name="Remitente / Responsable")
    recipient_name = models.CharField(max_length=255, verbose_name="Dirigido a")

    # Contenido WYSIWYG
    body_html = models.TextField(
        blank=True,
        null=True,
        verbose_name="Cuerpo del Documento (HTML)"
    )
    doc_status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT,
        verbose_name="Estado del Documento"
    )

    # Archivo PDF (Sellado o escaneado físico)
    file_attachment = models.FileField(
        upload_to=document_upload_path,
        blank=True,
        null=True,
        verbose_name="Archivo Digital (PDF)"
    )
    registration_date = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha de Registro"
    )
    observation = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones"
    )

    # Marcadores de Proceso
    is_entry_document = models.BooleanField(
        default=False,
        verbose_name="Es Documento de Ingreso (Oficio Inicial)"
    )
    is_final_response = models.BooleanField(
        default=False,
        verbose_name="Es Respuesta Definitiva al Solicitante"
    )

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ['-registration_date']

    def __str__(self):
        return f"{self.filing_code} - {self.subject}"

    def delete(self, *args, **kwargs):
        if self.file_attachment and os.path.isfile(self.file_attachment.path):
            try:
                os.remove(self.file_attachment.path)
            except OSError:
                pass
        super().delete(*args, **kwargs)


# ==============================================================================
# 7. HOJA DE RUTA INMUTABLE PARA CONTRALORÍA (PROCEDURE TRACE)
# ==============================================================================
class ProcedureTrace(models.Model):
    """
    Log de auditoría append-only para Contraloría General del Estado.
    Registra cada evento, derivación, firma o proveído sin permitir alteración.
    """

    class TraceAction(models.TextChoices):
        RECEPTION = 'RECEPTION', 'Recepción e Ingreso en Ventanilla'
        PASSED_TO_DESPATCH = 'PASSED_TO_DESPATCH', 'Puesto a Conocimiento de Dirección'
        SUMILLED = 'SUMILLED', 'Sumilla Legalizada con Firma Electrónica'
        DELEGATED = 'DELEGATED', 'Delegado a Dependencia / Técnico'
        RETURNED = 'RETURNED', 'Devuelto con Observaciones'
        REPORT_ATTACHED = 'REPORT_ATTACHED', 'Informe Técnico / Respuesta Adjunta'
        APPROVED = 'APPROVED', 'Visto Bueno / Aprobación de Jefatura'
        FINAL_DISPATCH = 'FINAL_DISPATCH', 'Despacho Final Firmado y Notificado'
        ARCHIVED = 'ARCHIVED', 'Expediente Archivado'

    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE, related_name='traces')
    task = models.ForeignKey('ProcedureTask', on_delete=models.SET_NULL, null=True, blank=True, related_name='traces')
    document = models.ForeignKey('Document', on_delete=models.SET_NULL, null=True, blank=True, related_name='traces',
                                 verbose_name="Documento Adjunto")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,verbose_name="Funcionario Actuante")
    actor_name = models.CharField(max_length=200)
    actor_position = models.CharField(max_length=200, blank=True, null=True)
    unit_name = models.CharField(
        max_length=255,
        verbose_name="Unidad Administrativa"
    )
    action = models.CharField(
        max_length=30,
        choices=TraceAction.choices,
        verbose_name="Acción Realizada"
    )
    observation = models.TextField(
        blank=True,
        null=True,
        verbose_name="Detalle de la Actuación / Proveído"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Fecha y Hora Exacta"
    )

    class Meta:
        verbose_name = "Ruta de Trámite"
        verbose_name_plural = "Rutas de Trámites"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.created_at.strftime('%d/%m/%Y %H:%M:%S')} | {self.actor_name} | {self.get_action_display()}"
