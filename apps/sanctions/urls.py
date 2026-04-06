from django.urls import path
from . import views

app_name = 'sanctions'

urlpatterns = [
    # --- Sanction Types (Configuration) ---
    path('types/', views.SanctionTypeListView.as_view(), name='sanction_type_list'),
    path('types/create/', views.SanctionTypeCreateView.as_view(), name='sanction_type_create'),
    path('types/update/<int:pk>/', views.SanctionTypeUpdateView.as_view(), name='sanction_type_update'),
    path('types/delete/<int:pk>/', views.SanctionTypeDeleteView.as_view(), name='sanction_type_delete'),
    path('types/toggle/<int:pk>/', views.SanctionTypeToggleView.as_view(), name='sanction_type_toggle'),

    # --- Employee List to Generate Sanctions ---
    path('employees/', views.EmployeeSanctionListView.as_view(), name='sanction_employee_list'),

    # --- Sanction Creation ---
    path('generate/', views.GenerateSanctionFormView.as_view(), name='generate_sanction'),
    
    # --- Sanction Administration ---
    path('admin/', views.SanctionAdminListView.as_view(), name='sanction_admin'),
    path('admin/employee/<int:employee_id>/', views.SanctionAdminListView.as_view(), name='sanction_admin_by_employee'),
    path('admin/<int:pk>/detail/', views.SanctionDetailView.as_view(), name='sanction_detail'),
    path('admin/<int:pk>/update-status/', views.SanctionUpdateStatusView.as_view(), name='sanction_update_status'),
    path('admin/<int:pk>/edit/', views.EditSanctionView.as_view(), name='sanction_edit'),
    path('admin/<int:pk>/register/', views.RegisterSanctionView.as_view(), name='sanction_register'),
    path('admin/<int:pk>/pdf/', views.SanctionPDFView.as_view(), name='sanction_pdf'),
]
