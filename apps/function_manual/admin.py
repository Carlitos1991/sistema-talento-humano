from django.contrib import admin
from .models import (
    ManualCatalog, ManualCatalogItem, OccupationalMatrix,
    JobProfile, JobActivity, Competency, ProfileCompetency
)


@admin.register(ManualCatalog)
class ManualCatalogAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at']
    search_fields = ['name', 'code']
    list_filter = ['is_active']


@admin.register(ManualCatalogItem)
class ManualCatalogItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'catalog', 'order', 'is_active']
    search_fields = ['name', 'code']
    list_filter = ['catalog', 'is_active']


@admin.register(OccupationalMatrix)
class OccupationalMatrixAdmin(admin.ModelAdmin):
    list_display = ['occupational_group', 'grade', 'remuneration', 'required_role', 'is_active']
    search_fields = ['occupational_group']
    list_filter = ['is_active', 'required_role']


@admin.register(JobProfile)
class JobProfileAdmin(admin.ModelAdmin):
    list_display = ['specific_job_title', 'administrative_unit', 'is_active', 'created_at']
    search_fields = ['specific_job_title', 'position_code']
    list_filter = ['is_active']


@admin.register(Competency)
class CompetencyAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'suggested_level', 'is_active', 'created_at']
    search_fields = ['name']
    list_filter = ['type', 'is_active']


@admin.register(JobActivity)
class JobActivityAdmin(admin.ModelAdmin):
    list_display = ['profile', 'description_short', 'action_verb', 'created_at']
    search_fields = ['description']
    list_filter = ['profile']

    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Descripción'


@admin.register(ProfileCompetency)
class ProfileCompetencyAdmin(admin.ModelAdmin):
    list_display = ['profile', 'competency', 'observable_behavior_short']
    search_fields = ['profile__specific_job_title', 'competency__name']
    list_filter = ['profile', 'competency__type']

    def observable_behavior_short(self, obj):
        return obj.observable_behavior[:50] + '...' if len(obj.observable_behavior) > 50 else obj.observable_behavior
    observable_behavior_short.short_description = 'Comportamiento Observable'
