from django.contrib import admin
from .models import SanctionType, Sanction


@admin.register(SanctionType)
class SanctionTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'requires_attachment']
    list_filter = ['is_active']
    search_fields = ['name']
    ordering = ['name']


@admin.register(Sanction)
class SanctionAdmin(admin.ModelAdmin):
    list_display = [
        'get_sanction_number', 'employee', 'sanction_type', 
        'severity', 'sanction_date', 'status', 'created_by'
    ]
    list_filter = ['status', 'severity', 'sanction_type', 'sanction_date']
    search_fields = [
        'personnel_action__number',
        'employee__person__first_name',
        'employee__person__last_name',
        'employee__person__document_number'
    ]
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    date_hierarchy = 'sanction_date'
    ordering = ['-sanction_date', '-created_at']
    
    fieldsets = (
        ('Información General', {
            'fields': ('employee', 'sanction_type', 'severity')
        }),
        ('Detalles de la Sanción', {
            'fields': ('description', 'legal_basis', 'attachment_file')
        }),
        ('Fechas', {
            'fields': ('incident_date', 'sanction_date', 'start_date', 'end_date', 'days')
        }),
        ('Estado y Observaciones', {
            'fields': ('status', 'observations')
        }),
        ('Acción de Personal', {
            'fields': ('personnel_action',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_sanction_number(self, obj):
        return obj.personnel_action.number if obj.personnel_action else 'N/A'
    get_sanction_number.short_description = 'Número de Acción'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
