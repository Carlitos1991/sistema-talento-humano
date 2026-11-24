from django.urls import path
from . import views

app_name = 'permissions'

urlpatterns = [
    # Configuración
    path('types/', views.PermitTypeListView.as_view(), name='permit_type_list'),
    path('types/create/', views.PermitTypeCreateView.as_view(), name='permit_type_create'),
    path('types/update/<int:pk>/', views.PermitTypeUpdateView.as_view(), name='permit_type_update'),
    path('types/delete/<int:pk>/', views.PermitTypeDeleteView.as_view(), name='permit_type_delete'),
    path('types/toggle/<int:pk>/', views.PermitTypeToggleView.as_view(), name='permit_type_toggle'),
    path('types/<int:pk>/subitems/', views.PermitTypeSubItemsView.as_view(), name='permit_type_subitems'),
    path('types/<int:pk>/options/', views.permit_type_detail_options, name='permit_type_options'),
    path('types/<int:parent_id>/subtypes/', views.permit_subtype_options, name='permit_subtype_options'),

    # Permisos - Empleados
    path('employees/', views.EmployeePermitListView.as_view(), name='permit_employee_list'),
    path('employees/<int:employee_id>/history/', views.EmployeePermitHistoryView.as_view(),
         name='permit_employee_history'),
    path('requests/generate/', views.GeneratePermitFormView.as_view(), name='generate_permit_form'),
    path('requests/create/', views.GeneratePermitFormView.as_view(), name='permit_create'),
    path('admin/approved-summary/', views.PermitApprovedSummaryModalView.as_view(), name='permit_approved_summary'),

    # Administración
    path('admin/', views.PermitAdminListView.as_view(), name='permit_admin'),
    path('admin/<int:pk>/detail/', views.PermitDetailView.as_view(), name='permit_detail'),
    path('admin/<int:pk>/report/', views.PermitReportView.as_view(), name='permit_report'),
    path('admin/<int:pk>/insist/', views.PermitInsistView.as_view(), name='permit_insist'),
    path('admin/<int:pk>/<str:action>/', views.PermitResponseView.as_view(), name='permit_response'),
    path('admin/parse-identifications/', views.ParsePermitIdentificationExcelView.as_view(),
         name='parse_permit_identifications'),
    path('validate/<str:token>/', views.PublicPermitValidationView.as_view(), name='permit_public_validate'),

    # Bitácoras
    path('bitacora/register/<int:employee_id>/', views.BinnacleRegisterView.as_view(), name='bitacora_register'),
    path('bitacora/list/<int:employee_id>/', views.BinnacleListView.as_view(), name='bitacora_list'),
    path('bitacora/history/<int:employee_id>/', views.BinnacleHistoryView.as_view(), name='bitacora_history'),
    path('bitacora/approve/', views.BinnacleApproveView.as_view(), name='bitacora_approve'),
    path('bitacora/reject/', views.BinnacleRejectView.as_view(), name='bitacora_reject'),
    path('bitacora/delete/', views.BinnacleDeleteView.as_view(), name='bitacora_delete'),
    path('bitacora/edit/<int:pk>/', views.BinnacleEditView.as_view(), name='bitacora_edit'),
    path('bitacora/review/<int:pk>/', views.BinnacleReviewView.as_view(), name='bitacora_review'),
]
