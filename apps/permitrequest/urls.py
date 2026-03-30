from django.urls import path
from . import views

app_name = 'permissions'

urlpatterns = [
    # --- Tipos de Permiso (Configuración) ---
    path('types/', views.PermitTypeListView.as_view(), name='type_list'),
    path('types/create/', views.PermitTypeCreateView.as_view(), name='type_create'),
    path('types/update/<int:pk>/', views.PermitTypeUpdateView.as_view(), name='type_update'),
    path('types/delete/<int:pk>/', views.PermitTypeDeleteView.as_view(), name='type_delete'),
    path('types/toggle/<int:pk>/', views.PermitTypeToggleView.as_view(), name='type_toggle'),
    path('types/<int:pk>/subitems/', views.PermitTypeSubItemsView.as_view(), name='type_subitems'),

    # --- Lista de Empleados para Generar Permisos ---
    path('employees/', views.EmployeePermitListView.as_view(), name='employee_list'),
    path('employees/<int:employee_id>/history/', views.EmployeePermitHistoryView.as_view(), name='employee_history'),

    # --- Solicitudes de Permiso (OBSOLETO - usar permit_admin) ---
    # path('requests/', views.PermitRequestListView.as_view(), name='permit_list'),
    path('requests/generate/', views.GeneratePermitFormView.as_view(), name='generate_permit_form'),
    path('requests/create/', views.GeneratePermitFormView.as_view(), name='permit_create'),  # POST para crear permiso
    # path('requests/update/<int:pk>/', views.PermitRequestUpdateView.as_view(), name='permit_update'),
    path('api/type/<int:pk>/', views.permit_type_detail_api, name='api_type_details'),
    
    # --- API para subtipos ---
    path('api/subtypes/<int:parent_id>/', views.get_subtypes_api, name='api_subtypes'),
    
    # --- Administración de Permisos ---
    path('admin/', views.PermitAdminListView.as_view(), name='permit_admin'),
    path('admin/<int:pk>/detail/', views.PermitDetailView.as_view(), name='permit_detail'),
    path('validate/<str:token>/', views.PublicPermitValidationView.as_view(), name='permit_public_validate'),
    path('admin/<int:pk>/report/', views.PermitReportView.as_view(), name='permit_report'),
    path('admin/<int:pk>/<str:action>/', views.PermitResponseView.as_view(), name='permit_response'),
    
    # --- Bitácoras ---
    path('bitacora/register/<int:employee_id>/', views.BitacoraRegisterView.as_view(), name='bitacora_register'),
    path('bitacora/list/<int:employee_id>/', views.BitacoraListView.as_view(), name='bitacora_list'),
    path('bitacora/approve/', views.BitacoraApproveView.as_view(), name='bitacora_approve'),
    path('bitacora/delete/', views.BitacoraDeleteView.as_view(), name='bitacora_delete'),
]
