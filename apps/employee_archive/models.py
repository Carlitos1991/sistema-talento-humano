import os
import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import BaseModel
from core.models import User
from employee.models import Employee


ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf'}

PREDEFINED_ARCHIVE_TYPES = [
    {
        'code': 'EXPEDIENTE_INICIAL',
        'name': 'Expediente Inicial',
        'description': 'Documentos iniciales de ingreso del empleado.',
        'is_required': True,
        'has_expiration': False,
        'max_size_mb': 10,
    },
    {
        'code': 'ACCIONES_PERSONAL',
        'name': 'Acciones de Personal',
        'description': 'Acciones de personal para digitalizacion y resguardo.',
        'is_required': True,
        'has_expiration': False,
        'max_size_mb': 10,
    },
    {
        'code': 'CONTRATOS',
        'name': 'Contratos',
        'description': 'Contratos y adendas del empleado para digitalizacion y resguardo.',
        'is_required': True,
        'has_expiration': False,
        'max_size_mb': 10,
    },
]


def _safe_segment(value, fallback):
    text = str(value or '').strip()
    if not text:
        return fallback
    return re.sub(r'[^A-Za-z0-9_-]+', '_', text)


def employee_archive_upload_path(instance, filename):
    employee = getattr(instance.archive, 'employee', None)
    person = getattr(employee, 'person', None)

    cedula = _safe_segment(getattr(person, 'document_number', None), f'empleado_{employee.id if employee else "sin_empleado"}')
    document_type = getattr(instance.archive, 'document_type', None)
    type_code = _safe_segment(getattr(document_type, 'code', None), 'general')
    clean_filename = os.path.basename(filename)

    return f'employee_archive/{cedula}/{type_code.lower()}/{clean_filename}'


def ensure_predefined_document_types():
    type_map = {}
    for type_data in PREDEFINED_ARCHIVE_TYPES:
        desired_code = type_data['code']
        desired_name = type_data['name']

        code_item = EmployeeDocumentType.objects.filter(code=desired_code).first()
        name_item = EmployeeDocumentType.objects.filter(name=desired_name).first()

        # Si existen dos registros distintos (uno por código y otro por nombre),
        # preservamos el registro por código y renombramos el de nombre para evitar colisión.
        if code_item and name_item and code_item.pk != name_item.pk:
            legacy_name = f"{name_item.name} LEGACY {name_item.pk}"
            name_item.name = legacy_name[:120]
            name_item.save(update_fields=['name'])

        item = code_item or name_item
        if item:
            item.code = desired_code
            item.name = desired_name
            item.description = type_data['description']
            item.is_required = type_data['is_required']
            item.has_expiration = type_data['has_expiration']
            item.max_size_mb = type_data['max_size_mb']
            item.is_active = True
            item.save()
        else:
            item = EmployeeDocumentType.objects.create(
                code=desired_code,
                name=desired_name,
                description=type_data['description'],
                is_required=type_data['is_required'],
                has_expiration=type_data['has_expiration'],
                max_size_mb=type_data['max_size_mb'],
                is_active=True,
            )
        type_map[item.code] = item
    return type_map


class EmployeeDocumentType(BaseModel):
    code = models.CharField(max_length=50, unique=True, verbose_name='Codigo')
    name = models.CharField(max_length=120, unique=True, verbose_name='Nombre')
    description = models.TextField(blank=True, null=True, verbose_name='Descripcion')
    is_required = models.BooleanField(default=False, verbose_name='Requisito de ingreso')
    has_expiration = models.BooleanField(default=False, verbose_name='Requiere fecha de caducidad')
    max_size_mb = models.PositiveIntegerField(default=10, verbose_name='Tamano maximo (MB)')

    class Meta:
        verbose_name = 'Tipo de Documento de Empleado'
        verbose_name_plural = 'Tipos de Documentos de Empleado'
        ordering = ['name']

    def __str__(self):
        return self.name


class EmployeeArchiveDocument(BaseModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        VERIFIED = 'VERIFIED', 'Verificado'
        OBSERVED = 'OBSERVED', 'Observado'

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='archive_documents',
        verbose_name='Empleado'
    )
    document_type = models.ForeignKey(
        EmployeeDocumentType,
        on_delete=models.PROTECT,
        related_name='employee_documents',
        verbose_name='Tipo de Documento'
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Estado'
    )
    notes = models.TextField(blank=True, null=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Documento de Archivo Digital'
        verbose_name_plural = 'Documentos de Archivo Digital'
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'document_type'],
                name='unique_employee_document_type_archive'
            )
        ]
        ordering = ['employee__person__last_name', 'document_type__name']

    def __str__(self):
        return f'{self.employee} - {self.document_type}'


class EmployeeArchiveVersion(BaseModel):
    archive = models.ForeignKey(
        EmployeeArchiveDocument,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='Documento Archivo'
    )
    version_number = models.PositiveIntegerField(default=1, verbose_name='Version')
    file = models.FileField(upload_to=employee_archive_upload_path, verbose_name='Archivo PDF')
    issue_date = models.DateField(blank=True, null=True, verbose_name='Fecha de emision')
    expiration_date = models.DateField(blank=True, null=True, verbose_name='Fecha de caducidad')
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='uploaded_archive_versions',
        verbose_name='Subido por'
    )
    observations = models.TextField(blank=True, null=True, verbose_name='Observaciones')
    is_current = models.BooleanField(default=True, verbose_name='Version vigente')

    class Meta:
        verbose_name = 'Version de Documento'
        verbose_name_plural = 'Versiones de Documento'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['archive', 'version_number'],
                name='unique_archive_version_number'
            ),
            models.UniqueConstraint(
                fields=['archive'],
                condition=Q(is_current=True),
                name='unique_current_version_per_archive'
            )
        ]

    def __str__(self):
        return f'{self.archive} v{self.version_number}'

    def clean(self):
        if not self.file:
            return

        if not self.archive_id and not hasattr(self, 'archive'):
            return

        lower_name = self.file.name.lower()
        if not any(lower_name.endswith(ext) for ext in ALLOWED_DOCUMENT_EXTENSIONS):
            raise ValidationError({'file': 'Solo se permiten archivos PDF.'})

        max_size = self.archive.document_type.max_size_mb * 1024 * 1024
        if self.file.size > max_size:
            raise ValidationError({
                'file': f'El archivo excede el tamano maximo permitido de {self.archive.document_type.max_size_mb} MB.'
            })

        if self.archive.document_type.has_expiration and not self.expiration_date:
            raise ValidationError({'expiration_date': 'Este tipo de documento requiere fecha de caducidad.'})

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if creating:
            last_version = self.archive.versions.order_by('-version_number').first()
            next_version = (last_version.version_number + 1) if last_version else 1
            if not self.version_number or self.version_number <= 0 or self.version_number == 1:
                self.version_number = next_version

            self.archive.versions.filter(is_current=True).update(is_current=False)
            self.is_current = True

        self.full_clean()
        super().save(*args, **kwargs)


class EmployeeArchiveLoan(BaseModel):
    class Status(models.TextChoices):
        REQUESTED = 'REQUESTED', 'Solicitado'
        ON_LOAN = 'ON_LOAN', 'En prestamo'
        RETURN_REPORTED = 'RETURN_REPORTED', 'Devolucion reportada'
        RETURN_VALIDATED = 'RETURN_VALIDATED', 'Devuelto'

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='archive_loans',
        verbose_name='Empleado'
    )
    expediente_number = models.CharField(max_length=50, verbose_name='Numero de expediente')
    borrower_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='archive_loans_as_borrower',
        verbose_name='Usuario que tiene el expediente'
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='archive_loans_requested',
        verbose_name='Solicitado por'
    )
    delivered_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='archive_loans_delivered',
        verbose_name='Entregado por',
        blank=True,
        null=True
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED, verbose_name='Estado')
    requested_at = models.DateTimeField(default=timezone.now, verbose_name='Fecha de solicitud')
    delivered_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de entrega')
    return_reported_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de reporte de devolucion')
    returned_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de devolucion validada')
    request_observation = models.TextField(blank=True, null=True, verbose_name='Observacion de solicitud')
    delivery_observation = models.TextField(blank=True, null=True, verbose_name='Observacion de entrega')
    return_observation = models.TextField(blank=True, null=True, verbose_name='Observacion de devolucion')
    validation_observation = models.TextField(blank=True, null=True, verbose_name='Observacion de validacion')

    class Meta:
        verbose_name = 'Prestamo de Expediente Fisico'
        verbose_name_plural = 'Prestamos de Expediente Fisico'
        ordering = ['-requested_at']
        permissions = [
            ('can_manage_archive_loans', 'Puede gestionar prestamos de archivo'),
            ('can_validate_archive_returns', 'Puede validar devoluciones de archivo'),
            ('can_create_archive_manual_loan', 'Puede registrar prestamos manuales de archivo'),
        ]

    def __str__(self):
        return f'{self.expediente_number} - {self.borrower_user.username} ({self.get_status_display()})'


class EmployeeArchiveLoanLog(models.Model):
    loan = models.ForeignKey(
        EmployeeArchiveLoan,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='Prestamo'
    )
    action = models.CharField(max_length=60, verbose_name='Accion')
    observation = models.TextField(blank=True, null=True, verbose_name='Observacion')
    actor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='archive_loan_logs',
        verbose_name='Usuario'
    )
    ip_address = models.CharField(max_length=64, blank=True, null=True, verbose_name='IP')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')

    class Meta:
        verbose_name = 'Bitacora de Prestamo de Expediente'
        verbose_name_plural = 'Bitacora de Prestamos de Expediente'
        ordering = ['-created_at']


class EmployeeArchiveNotification(models.Model):
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='employee_archive_notifications',
        verbose_name='Destinatario'
    )
    title = models.CharField(max_length=180, verbose_name='Titulo')
    message = models.TextField(verbose_name='Mensaje')
    url = models.CharField(max_length=255, blank=True, null=True, verbose_name='URL destino')
    is_read = models.BooleanField(default=False, verbose_name='Leida')
    read_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de lectura')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creacion')

    class Meta:
        verbose_name = 'Notificacion de Archivo Digital'
        verbose_name_plural = 'Notificaciones de Archivo Digital'
        ordering = ['-created_at']


class EmployeeArchiveAccessLog(models.Model):
    class Action(models.TextChoices):
        VIEW_EMPLOYEE_ARCHIVE = 'VIEW_EMPLOYEE_ARCHIVE', 'Visualizo archivo digital del empleado'
        VIEW_PDF = 'VIEW_PDF', 'Visualizo PDF'
        UPLOAD_PDF = 'UPLOAD_PDF', 'Subio PDF'

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='employee_archive_access_logs',
        verbose_name='Usuario'
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='archive_access_logs',
        verbose_name='Empleado'
    )
    archive_document = models.ForeignKey(
        EmployeeArchiveDocument,
        on_delete=models.SET_NULL,
        related_name='access_logs',
        blank=True,
        null=True,
        verbose_name='Documento de archivo'
    )
    version = models.ForeignKey(
        EmployeeArchiveVersion,
        on_delete=models.SET_NULL,
        related_name='access_logs',
        blank=True,
        null=True,
        verbose_name='Version'
    )
    action = models.CharField(max_length=40, choices=Action.choices, verbose_name='Accion')
    ip_address = models.CharField(max_length=64, blank=True, null=True, verbose_name='IP')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')

    class Meta:
        verbose_name = 'Auditoria de Archivo Digital'
        verbose_name_plural = 'Auditoria de Archivo Digital'
        ordering = ['-created_at']


class EmployeeArchiveScanTask(BaseModel):
    class SourceType(models.TextChoices):
        INITIAL = 'INITIAL', 'Expediente Inicial'
        CONTRACT = 'CONTRACT', 'Contrato'
        PERSONNEL_ACTION = 'PERSONNEL_ACTION', 'Accion de Personal'

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='archive_scan_tasks',
        verbose_name='Empleado'
    )
    document_type = models.ForeignKey(
        EmployeeDocumentType,
        on_delete=models.PROTECT,
        related_name='scan_tasks',
        verbose_name='Tipo de documento destino'
    )
    source_type = models.CharField(max_length=30, choices=SourceType.choices, verbose_name='Origen')
    source_id = models.PositiveIntegerField(blank=True, null=True, verbose_name='Id del registro origen')
    source_reference = models.CharField(max_length=120, blank=True, null=True, verbose_name='Referencia origen')
    title = models.CharField(max_length=255, verbose_name='Titulo')
    source_date = models.DateField(blank=True, null=True, verbose_name='Fecha del registro origen')
    is_scanned = models.BooleanField(default=False, verbose_name='Digitalizado')
    scanned_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de digitalizacion')
    scanned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='archive_scan_tasks_done',
        blank=True,
        null=True,
        verbose_name='Digitalizado por'
    )
    archive_document = models.ForeignKey(
        EmployeeArchiveDocument,
        on_delete=models.SET_NULL,
        related_name='scan_tasks',
        blank=True,
        null=True,
        verbose_name='Documento de archivo'
    )
    version = models.ForeignKey(
        EmployeeArchiveVersion,
        on_delete=models.SET_NULL,
        related_name='scan_tasks',
        blank=True,
        null=True,
        verbose_name='Version'
    )

    class Meta:
        verbose_name = 'Tarea de Digitalizacion de Archivo'
        verbose_name_plural = 'Tareas de Digitalizacion de Archivo'
        ordering = ['-source_date', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'source_type', 'source_id'],
                condition=Q(source_id__isnull=False),
                name='unique_archive_scan_task_per_source'
            )
        ]

    def __str__(self):
        base_reference = self.source_reference or self.title
        return f'{self.employee} - {base_reference}'
