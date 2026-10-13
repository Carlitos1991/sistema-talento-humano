# --- vacation/urls.py ---
from django.urls import path
from . import views

app_name = 'vacation'

urlpatterns = [
    # Solicitudes
    path('requests/', views.VacationRequestListView.as_view(), name='request_list'),
    path('requests/create/', views.VacationCreateView.as_view(), name='request_create'),
    path('requests/create-first/<int:employee_id>/', views.CreateFirstVacationView.as_view(),
         name='create_first_vacation'),
    path('requests/create-new/<int:employee_id>/', views.CreateNewVacationPeriodView.as_view(),
         name='create_new_vacation'),
    path('requests/employee/<int:employee_id>/', views.EmployeeVacationDetailView.as_view(),
         name='employee_vacation_detail'),
    path('requests/create-hour-permit/<int:employee_id>/', views.CreateHourPermitVacationView.as_view(),
         name='create_hour_permit'),
    path('requests/create-day-permit/<int:employee_id>/', views.CreateDayPermitVacationView.as_view(),
         name='create_day_permit'),
    path('requests/permit-list/<int:employee_id>/', views.EmployeePermitListView.as_view(), name='permit_list'),
    path('requests/approve-permit/<int:permit_id>/', views.ApprovePermitView.as_view(), name='approve_permit'),
    path('requests/reject-permit/<int:permit_id>/', views.RejectPermitView.as_view(), name='reject_permit'),
    path('requests/cancel-permit/<int:permit_id>/', views.CancelPermitView.as_view(), name='cancel_permit'),
    path('requests/create-liquidation/<int:employee_id>/', views.CreateVacationLiquidationView.as_view(),
         name='create_liquidation'),
    path('requests/liquidation-list/<int:employee_id>/', views.EmployeeLiquidationListView.as_view(),
         name='liquidation_list'),
    path('requests/register-liquidation/<int:action_id>/', views.RegisterLiquidationView.as_view(),
         name='register_liquidation'),
    path('requests/edit-liquidation/<int:action_id>/', views.EditLiquidationView.as_view(), name='edit_liquidation'),

    # Historiales
    path('requests/vacation-history/<int:balance_id>/', views.VacationHistoryDetailView.as_view(),
         name='vacation_history'),
    path('requests/permit-history/<int:balance_id>/', views.PermitHistoryDetailView.as_view(), name='permit_history'),

    # Reportes
    path('requests/permit-report-modal/<int:employee_id>/', views.PermitReportModalView.as_view(),
         name='permit_report_modal'),
    path('requests/permit-report-pdf/<int:employee_id>/', views.PermitReportPDFView.as_view(),
         name='permit_report_pdf'),
    path('requests/liquidation-print-pdf/<int:action_id>/', views.LiquidationPrintPDFView.as_view(),
         name='liquidation_print_pdf'),

    # Periodos
    path('periods/', views.PeriodListView.as_view(), name='period_list'),
    path('periods/create/', views.PeriodCreateView.as_view(), name='period_create'),
    path('periods/edit/<int:pk>/', views.PeriodUpdateView.as_view(), name='period_edit'),
    # Cronograma Anual
    path('schedule/', views.VacationSchedulePlanListView.as_view(), name='schedule_plan_list'),
    path('schedule/create/', views.VacationSchedulePlanCreateModalView.as_view(), name='schedule_plan_create'),
    path('schedule/<int:plan_id>/', views.VacationScheduleDetailView.as_view(), name='schedule_detail'),
    path('schedule/<int:plan_id>/add-item/', views.VacationScheduleItemCreateModalView.as_view(),
         name='schedule_item_create'),
    path('schedule/item/<int:item_id>/delete/', views.VacationScheduleItemDeleteView.as_view(),
         name='schedule_item_delete'),
    path('schedule/toggle-status/<int:pk>/', views.VacationSchedulePlanToggleStatusView.as_view(),
         name='schedule_plan_toggle_status'),
    path('schedule/edit/<int:pk>/', views.VacationSchedulePlanUpdateModalView.as_view(), name='schedule_plan_edit'),
    path('schedule/<int:plan_id>/drop-modal/<int:employee_id>/<int:month>/',
         views.VacationScheduleDropModalView.as_view(), name='schedule_drop_modal'),
    path('schedule/<int:plan_id>/drop-save/<int:employee_id>/', views.VacationScheduleDropSaveView.as_view(),
         name='schedule_drop_save'),
    path('schedule/<int:plan_id>/export-excel/', views.VacationScheduleExcelExportView.as_view(),
         name='schedule_export_excel'),
    path('schedule/<int:plan_id>/export-pdf/', views.VacationSchedulePdfExportView.as_view(),
         name='schedule_export_pdf'),
    path('schedule/<int:plan_id>/consolidated-modal/', views.VacationScheduleConsolidatedModalView.as_view(),
         name='schedule_consolidated_modal'),
    path('schedule/<int:plan_id>/consolidated-export/', views.VacationScheduleConsolidatedExportView.as_view(),
         name='schedule_consolidated_export'),
    path('schedule/approve/<int:pk>/', views.VacationScheduleApprovePlanView.as_view(), name='schedule_plan_approve'),
    path('schedule/api/user-search/', views.UserSearchSelect2View.as_view(), name='schedule_user_search'),
    path('schedule/<int:plan_id>/unit-report-modal/', views.VacationScheduleUnitReportModalView.as_view(),
         name='schedule_unit_report_modal'),
    path('schedule/sub-units/<int:parent_id>/', views.SubUnitsAjaxView.as_view(), name='schedule_sub_units_ajax'),
    path('schedule/<int:plan_id>/unit-report-pdf/', views.VacationScheduleUnitReportPDFView.as_view(),
         name='schedule_unit_report_pdf'),
]
