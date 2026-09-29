from django.urls import path
from . import views

app_name = 'schedule'

urlpatterns = [
    # -------------------------------------------------------------
    # 1. GESTIÓN DE HORARIOS INSTITUCIONALES (SCHEDULE)
    # -------------------------------------------------------------
    path('list/', views.ScheduleListView.as_view(), name='schedule_list'),
    path('modal/form/', views.ScheduleModalFormView.as_view(), name='schedule_modal_create'),
    path('modal/form/<int:pk>/', views.ScheduleModalFormView.as_view(), name='schedule_modal_update'),
    path('create/', views.ScheduleCreateView.as_view(), name='schedule_create'),
    path('update/<int:pk>/', views.ScheduleUpdateView.as_view(), name='schedule_update'),
    path('history/<int:pk>/', views.ScheduleHistoryAPIView.as_view(), name='schedule_history_api'),
    path('activate/<int:pk>/', views.ScheduleActivateView.as_view(), name='schedule_activate'),
    path('deactivate/<int:pk>/', views.ScheduleDeactivateView.as_view(), name='schedule_deactivate'),

    # -------------------------------------------------------------
    # 2. ASIGNACIÓN DE HORARIOS A EMPLEADOS
    # -------------------------------------------------------------
    path('assignment/', views.EmployeeScheduleAssignmentListView.as_view(), name='assignment_list'),
    path('assignment/partial-table/', views.EmployeeScheduleAssignmentTablePartialView.as_view(),
         name='assignment_partial_table'),
    path('assignment/history/<int:employee_id>/', views.EmployeeScheduleHistoryAPIView.as_view(),
         name='employee_schedule_history_api'),
    path('assignment/change-modal/<int:employee_id>/', views.EmployeeScheduleChangeModalView.as_view(),
         name='employee_schedule_change_modal'),
    path('assignment/<int:employee_id>/', views.EmployeeScheduleAssignView.as_view(), name='employee_schedule_assign'),

    # -------------------------------------------------------------
    # 3. FERIADOS Y OBSERVACIONES (REQUERIDO POR EL SIDEBAR)
    # -------------------------------------------------------------
    path('observations/', views.ObservationListView.as_view(), name='observation_list'),
    path('observations/partial-table/', views.ObservationTablePartialView.as_view(), name='observation_partial_table'),
    path('observations/create/', views.ObservationCreateView.as_view(), name='observation_create'),
    path('observations/update/<int:pk>/', views.ObservationUpdateView.as_view(), name='observation_update'),
    path('observations/detail/<int:pk>/', views.ObservationDetailAPIView.as_view(), name='observation_detail_api'),
    path('observations/toggle-status/<int:pk>/', views.ObservationToggleStatusView.as_view(),
         name='observation_toggle_status'),
    path('observations/modal/form/', views.ObservationModalFormView.as_view(), name='observation_modal_create'),
    path('observations/modal/form/<int:pk>/', views.ObservationModalFormView.as_view(),
         name='observation_modal_update'),
]
