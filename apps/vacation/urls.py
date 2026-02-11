# --- vacation/urls.py ---
from django.urls import path
from . import views

app_name = 'vacation'

urlpatterns = [
    # Solicitudes
    path('requests/', views.VacationRequestListView.as_view(), name='request_list'),
    path('requests/create/', views.VacationCreateView.as_view(), name='request_create'),
    path('requests/create-first/<int:employee_id>/', views.CreateFirstVacationView.as_view(), name='create_first_vacation'),
    path('requests/create-new/<int:employee_id>/', views.CreateNewVacationPeriodView.as_view(), name='create_new_vacation'),
    path('requests/employee/<int:employee_id>/', views.EmployeeVacationDetailView.as_view(), name='employee_vacation_detail'),
    path('requests/create-hour-permit/<int:employee_id>/', views.CreateHourPermitVacationView.as_view(), name='create_hour_permit'),
    path('requests/create-day-permit/<int:employee_id>/', views.CreateDayPermitVacationView.as_view(), name='create_day_permit'),
    path('requests/permit-list/<int:employee_id>/', views.EmployeePermitListView.as_view(), name='permit_list'),
    path('requests/approve-permit/<int:permit_id>/', views.ApprovePermitView.as_view(), name='approve_permit'),
    path('requests/reject-permit/<int:permit_id>/', views.RejectPermitView.as_view(), name='reject_permit'),
    path('requests/cancel-permit/<int:permit_id>/', views.CancelPermitView.as_view(), name='cancel_permit'),
    path('requests/create-liquidation/<int:employee_id>/', views.CreateVacationLiquidationView.as_view(), name='create_liquidation'),
    path('requests/liquidation-list/<int:employee_id>/', views.EmployeeLiquidationListView.as_view(), name='liquidation_list'),
    path('requests/register-liquidation/<int:action_id>/', views.RegisterLiquidationView.as_view(), name='register_liquidation'),
    path('requests/edit-liquidation/<int:action_id>/', views.EditLiquidationView.as_view(), name='edit_liquidation'),
    
    # Historiales
    path('requests/vacation-history/<int:balance_id>/', views.VacationHistoryDetailView.as_view(), name='vacation_history'),
    path('requests/permit-history/<int:balance_id>/', views.PermitHistoryDetailView.as_view(), name='permit_history'),
    
    # Reportes
    path('requests/permit-report-modal/<int:employee_id>/', views.PermitReportModalView.as_view(), name='permit_report_modal'),
    path('requests/permit-report-pdf/<int:employee_id>/', views.PermitReportPDFView.as_view(), name='permit_report_pdf'),
    path('requests/liquidation-print-pdf/<int:action_id>/', views.LiquidationPrintPDFView.as_view(), name='liquidation_print_pdf'),

    # Periodos
    path('periods/', views.PeriodListView.as_view(), name='period_list'),
    path('periods/create/', views.PeriodCreateView.as_view(), name='period_create'),
    path('periods/edit/<int:pk>/', views.PeriodUpdateView.as_view(), name='period_edit'),
]
