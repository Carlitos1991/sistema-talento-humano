from django.urls import path
from .views import (
    PeriodListView, PeriodCreateView, GeneratePayrollView,
    GeneratePayrollUIView, GeneratePayrollSelectedView,
    ConstantListView, ConstantCreateView, ConstantUpdateView, ConstantDeleteView,
    PayrollListView, PayslipListView, PayslipDetailView,
    IncomeListView, IncomeCreateView, IncomeUpdateView, DeductionListView, DeductionCreateView, DeductionUpdateView, InstitutionalReportView, MappingListView,
    MappingCreateView, MappingUpdateView, MappingDeleteView
)

app_name = 'payroll'

urlpatterns = [
    # Periodos y Generación
    path('periods/', PeriodListView.as_view(), name='period_list'),
    path('periods/create/', PeriodCreateView.as_view(), name='period_create'),
    path('generate/', GeneratePayrollView.as_view(), name='generate'),
    path('generate/ui/', GeneratePayrollUIView.as_view(), name='generate_ui'),
    path('generate/selected/', GeneratePayrollSelectedView.as_view(), name='generate_selected'),

    # Constantes (CRUD)
    path('constants/', ConstantListView.as_view(), name='constant_list'),
    path('constants/create/', ConstantCreateView.as_view(), name='constant_create'),
    path('constants/update/<int:pk>/', ConstantUpdateView.as_view(), name='constant_update'),
    path('constants/delete/<int:pk>/', ConstantDeleteView.as_view(), name='constant_delete'),
    path('payslips/list/', PayrollListView.as_view(), name='payslip_list'),
    path('payslips/', PayslipListView.as_view(), name='payslip_list'),
    path('payslips/detail/<int:pk>/', PayslipDetailView.as_view(), name='payslip_detail'),
    # Mapeos contables para rubros
    path('incomes/', IncomeListView.as_view(), name='income_list'),
    path('incomes/create/', IncomeCreateView.as_view(), name='income_create'),
    path('incomes/<int:pk>/edit/', IncomeUpdateView.as_view(), name='income_edit'),
    path('deductions/', DeductionListView.as_view(), name='deduction_list'),
    path('deductions/create/', DeductionCreateView.as_view(), name='deduction_create'),
    path('deductions/<int:pk>/edit/', DeductionUpdateView.as_view(), name='deduction_edit'),
    path('reports/institutional/<int:period_id>/', InstitutionalReportView.as_view(), name='report_institutional'),

    # Rutas para el Mapeo Presupuestario
    path('mappings/', MappingListView.as_view(), name='mapping_list'),
    path('mappings/create/', MappingCreateView.as_view(), name='mapping_create'),
    path('mappings/<int:pk>/edit/', MappingUpdateView.as_view(), name='mapping_edit'),
    path('mappings/<int:pk>/delete/', MappingDeleteView.as_view(), name='mapping_delete'),
]
