from django.contrib import admin

from .models import EmployeeArchiveAccessLog
from .models import EmployeeArchiveDocument
from .models import EmployeeArchiveLoan
from .models import EmployeeArchiveLoanLog
from .models import EmployeeArchiveNotification
from .models import EmployeeArchiveScanTask
from .models import EmployeeArchiveVersion
from .models import EmployeeDocumentType


@admin.register(EmployeeDocumentType)
class EmployeeDocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_required', 'has_expiration', 'max_size_mb', 'is_active')
    list_filter = ('is_required', 'has_expiration', 'is_active')
    search_fields = ('name', 'code')


@admin.register(EmployeeArchiveDocument)
class EmployeeArchiveDocumentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'document_type', 'status', 'is_active', 'created_at')
    list_filter = ('status', 'is_active', 'document_type')
    search_fields = ('employee__person__first_name', 'employee__person__last_name', 'employee__person__document_number')


@admin.register(EmployeeArchiveVersion)
class EmployeeArchiveVersionAdmin(admin.ModelAdmin):
    list_display = ('archive', 'version_number', 'is_current', 'uploaded_by', 'created_at')
    list_filter = ('is_current',)
    search_fields = ('archive__employee__person__first_name', 'archive__employee__person__last_name')


@admin.register(EmployeeArchiveLoan)
class EmployeeArchiveLoanAdmin(admin.ModelAdmin):
    list_display = ('expediente_number', 'employee', 'borrower_user', 'status', 'requested_at', 'delivered_at', 'returned_at')
    list_filter = ('status', 'requested_at')
    search_fields = ('expediente_number', 'employee__person__first_name', 'employee__person__last_name', 'borrower_user__username')


@admin.register(EmployeeArchiveLoanLog)
class EmployeeArchiveLoanLogAdmin(admin.ModelAdmin):
    list_display = ('loan', 'action', 'actor', 'ip_address', 'created_at')
    list_filter = ('action',)
    search_fields = ('loan__expediente_number', 'actor__username', 'observation')


@admin.register(EmployeeArchiveNotification)
class EmployeeArchiveNotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'title', 'is_read', 'created_at', 'read_at')
    list_filter = ('is_read',)
    search_fields = ('recipient__username', 'title', 'message')


@admin.register(EmployeeArchiveAccessLog)
class EmployeeArchiveAccessLogAdmin(admin.ModelAdmin):
    list_display = ('employee', 'user', 'action', 'ip_address', 'created_at')
    list_filter = ('action',)
    search_fields = ('employee__person__first_name', 'employee__person__last_name', 'user__username')


@admin.register(EmployeeArchiveScanTask)
class EmployeeArchiveScanTaskAdmin(admin.ModelAdmin):
    list_display = ('employee', 'source_type', 'source_reference', 'document_type', 'is_scanned', 'source_date', 'scanned_at')
    list_filter = ('source_type', 'is_scanned', 'document_type')
    search_fields = ('employee__person__first_name', 'employee__person__last_name', 'source_reference', 'title')
