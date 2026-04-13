from django.contrib import admin

from .models import AttendanceRegistry, BiometricCommand, BiometricDevice, BiometricLoad, OfflineAttendanceRegistry


@admin.register(BiometricDevice)
class BiometricDeviceAdmin(admin.ModelAdmin):
	list_display = ('name', 'ip_address', 'port', 'location', 'serial_number', 'is_active')
	search_fields = ('name', 'ip_address', 'location', 'serial_number')
	list_filter = ('is_active',)


@admin.register(BiometricLoad)
class BiometricLoadAdmin(admin.ModelAdmin):
	list_display = ('biometric', 'load_type', 'num_records', 'created_at')
	search_fields = ('biometric__name', 'reason', 'load_type')
	list_filter = ('load_type', 'created_at')


@admin.register(AttendanceRegistry)
class AttendanceRegistryAdmin(admin.ModelAdmin):
	list_display = ('employee', 'employee_id_bio', 'registry_date', 'biometric_load')
	search_fields = ('employee__person__first_name', 'employee__person__last_name', 'employee_id_bio')
	list_filter = ('registry_date',)


@admin.register(OfflineAttendanceRegistry)
class OfflineAttendanceRegistryAdmin(admin.ModelAdmin):
	list_display = ('employee', 'punch_type', 'captured_at', 'sync_status', 'source', 'accuracy_m')
	search_fields = ('employee__person__first_name', 'employee__person__last_name', 'offline_uuid')
	list_filter = ('punch_type', 'sync_status', 'source', 'captured_at')
	readonly_fields = ('offline_uuid', 'created_at', 'updated_at')


@admin.register(BiometricCommand)
class BiometricCommandAdmin(admin.ModelAdmin):
	list_display = ('device', 'command', 'status', 'execution_time')
	search_fields = ('device__name', 'command', 'return_value')
	list_filter = ('status', 'execution_time')
