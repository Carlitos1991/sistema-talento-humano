from django.urls import path
from .views import PeriodListView, PeriodCreateView, GeneratePayrollView, ConstantListView, ConstantCreateView, \
    ConstantUpdateView, ConstantDeleteView, PayrollListView, PayslipListView, PayslipDetailView

app_name = 'payroll'

urlpatterns = [
    # Periodos y Generación
    path('periods/', PeriodListView.as_view(), name='period_list'),
    path('periods/create/', PeriodCreateView.as_view(), name='period_create'),
    path('generate/', GeneratePayrollView.as_view(), name='generate'),

    # Constantes (CRUD)
    path('constants/', ConstantListView.as_view(), name='constant_list'),
    path('constants/create/', ConstantCreateView.as_view(), name='constant_create'),
    path('constants/update/<int:pk>/', ConstantUpdateView.as_view(), name='constant_update'),
    path('constants/delete/<int:pk>/', ConstantDeleteView.as_view(), name='constant_delete'),
    path('payslips/list/', PayrollListView.as_view(), name='payslip_list'),
    path('payslips/', PayslipListView.as_view(), name='payslip_list'),
    path('payslips/detail/<int:pk>/', PayslipDetailView.as_view(), name='payslip_detail'),
]
