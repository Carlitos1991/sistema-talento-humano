from django.contrib import admin
from .models import (
    SanctionNotification, SanctionNotificationMapping, SanctionNotificationType, 
    SanctionNotificationTypeMapping, SanctionNotificationTypeRegime, SanctionType, 
    Sanction, NotificationTemplate, TemplateSection
)


class SanctionNotificationTypeRegimeInline(admin.TabularInline):
    model = SanctionNotificationTypeRegime
    extra = 0


class SanctionNotificationTypeMappingInline(admin.TabularInline):
    model = SanctionNotificationTypeMapping
    extra = 0


@admin.register(SanctionType)
class SanctionTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'requires_attachment']
    list_filter = ['is_active']
    search_fields = ['name']
    ordering = ['name']


@admin.register(SanctionNotificationType)
class SanctionNotificationTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'regime_count', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'description', 'regime_templates__labor_regime__name', 'regime_templates__labor_regime__code']
    inlines = [SanctionNotificationTypeRegimeInline, SanctionNotificationTypeMappingInline]
    ordering = ['name']

    def regime_count(self, obj):
        return obj.regime_templates.count()
    regime_count.short_description = 'Regímenes'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SanctionNotificationMapping)
class SanctionNotificationMappingAdmin(admin.ModelAdmin):
    list_display = ['placeholder', 'label', 'expression', 'is_active', 'order', 'created_at']
    list_filter = ['is_active']
    search_fields = ['placeholder', 'label', 'expression', 'description']
    ordering = ['order', 'label']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SanctionNotification)
class SanctionNotificationAdmin(admin.ModelAdmin):
    list_display = ['sequence_number', 'user_code', 'employee', 'notification_type', 'labor_regime', 'month', 'year', 'registration_date', 'created_by']
    list_filter = ['notification_type', 'labor_regime', 'month', 'year', 'registration_date']
    search_fields = ['employee__person__first_name', 'employee__person__last_name', 'employee__person__document_number', 'notification_type__name', 'user_code']
    readonly_fields = ['sequence_number', 'user_code', 'created_at', 'updated_at', 'created_by', 'updated_by']
    exclude = ['generated_docx', 'generated_pdf']
    ordering = ['-registration_date', '-created_at']


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


class TemplateSectionInline(admin.TabularInline):
    model = TemplateSection
    extra = 1
    fields = ['section_type', 'content', 'order', 'is_active']
    ordering = ['order']


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['notification_type', 'labor_regime', 'section_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'labor_regime', 'notification_type']
    search_fields = ['notification_type__name', 'labor_regime__name', 'labor_regime__code']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    inlines = [TemplateSectionInline]
    ordering = ['labor_regime__code', 'notification_type__name']

    fieldsets = (
        ('Información General', {
            'fields': ('notification_type', 'labor_regime', 'is_active')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def section_count(self, obj):
        return obj.sections.filter(is_active=True).count()
    section_count.short_description = 'Secciones activas'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TemplateSection)
class TemplateSectionAdmin(admin.ModelAdmin):
    list_display = ['template', 'section_type', 'order', 'is_active', 'preview_content']
    list_filter = ['is_active', 'section_type', 'template__labor_regime']
    search_fields = ['template__notification_type__name', 'template__labor_regime__name', 'content']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    ordering = ['template', 'order']

    fieldsets = (
        ('Información General', {
            'fields': ('template', 'section_type', 'order', 'is_active')
        }),
        ('Contenido', {
            'fields': ('content',),
            'description': 'Puede incluir variables: [FULL_NAME], [POSITION], [today], etc.'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def preview_content(self, obj):
        preview = obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return preview
    preview_content.short_description = 'Contenido (preview)'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
