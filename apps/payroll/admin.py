from django.contrib import admin
from .models import Income, Deduction, PayrollPeriod, Payslip, PayrollConstant

@admin.register(PayrollConstant)
class PayrollConstantAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'value')
    search_fields = ('name', 'code')
    # Instrucciones: Crear al menos 'SBU' y 'IESS_PER'

@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    search_fields = ('name', 'code')

@admin.register(Deduction)
class DeductionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'type', 'is_active')
    search_fields = ('name', 'code')

@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('month', 'year', 'start_date', 'end_date', 'is_closed')
    list_filter = ('year', 'is_closed')

@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ('employee', 'period', 'net_pay', 'worked_days')
    list_filter = ('period',)
    search_fields = ('employee__person__name', 'employee__person__lastname')