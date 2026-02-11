from django.urls import path
from . import views

app_name = 'sanctions'

urlpatterns = [
    # --- Sanction Types (Configuration) ---
    path('types/', views.SanctionTypeListView.as_view(), name='type_list'),
    path('types/create/', views.SanctionTypeCreateView.as_view(), name='type_create'),
    path('types/update/<int:pk>/', views.SanctionTypeUpdateView.as_view(), name='type_update'),
    path('types/delete/<int:pk>/', views.SanctionTypeDeleteView.as_view(), name='type_delete'),
    path('types/toggle/<int:pk>/', views.SanctionTypeToggleView.as_view(), name='type_toggle'),

    # --- Employee List to Generate Sanctions ---
    path('employees/', views.EmployeeSanctionListView.as_view(), name='employee_list'),
    path('employees/<int:employee_id>/history/', views.EmployeeSanctionHistoryView.as_view(), name='employee_history'),

    # --- Sanction Creation ---
    path('generate/', views.GenerateSanctionFormView.as_view(), name='generate_sanction'),
    
    # --- Sanction Administration ---
    path('admin/', views.SanctionAdminListView.as_view(), name='sanction_admin'),
    path('admin/<int:pk>/detail/', views.SanctionDetailView.as_view(), name='sanction_detail'),
    path('admin/<int:pk>/update-status/', views.SanctionUpdateStatusView.as_view(), name='sanction_update_status'),
]
