from django.contrib import admin
from .models import Authority, SystemConfiguration


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ['institution_name', 'city', 'effective_date', 'is_active']
    list_filter = ['is_active', 'city', 'effective_date']
    search_fields = ['institution_name', 'city', 'institution_ruc', 'institution_email']
    ordering = ['-effective_date']

    fieldsets = (
        ('Información institucional', {
            'fields': ('institution_name', 'city', 'institution_ruc', 'institution_address', 'institution_phone', 'institution_email')
        }),
        ('Autoridades', {
            'fields': ('max_authority_name', 'max_authority_position', 'talento_humano_authority_name', 'talento_humano_authority_position')
        }),
        ('Membretes y logo', {
            'fields': ('letterhead', 'logo')
        }),
        ('Vigencia', {
            'fields': ('effective_date', 'is_active')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'created_by', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Authority)
class AuthorityAdmin(admin.ModelAdmin):
    list_display = ['name', 'position', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'position']
    ordering = ['name']
