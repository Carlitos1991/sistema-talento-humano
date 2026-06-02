from django.urls import path
from . import views

app_name = 'employee'

urlpatterns = [
    # Ruta para el buscador del modal de asignación
    path('api/search/', views.search_employee_by_cedula, name='api_search_employee'),
    path('self_dashboard/', views.EmployeeSelfDashboardView.as_view(), name='self_dashboard'),
    path('detail/<int:pk>/', views.EmployeeDetailWizardView.as_view(), name='employee_detail'),
    path('api/upload-cv/<int:person_id>/', views.upload_cv_pdf, name='api_upload_cv'),

    # ENDPOINTS DE CURRICULUM (CRUD)
    path('api/cv/add-title/<int:person_id>/', views.add_academic_title_api, name='api_add_title'),
    path('api/cv/add-experience/<int:person_id>/', views.add_work_experience_api, name='api_add_experience'),
    path('api/cv/add-training/<int:person_id>/', views.add_training_api, name='api_add_training'),
    path('api/cv/edit-title/<int:title_id>/', views.edit_academic_title_api, name='api_edit_title'),
    path('api/cv/edit-experience/<int:experience_id>/', views.edit_work_experience_api, name='api_edit_experience'),
    path('api/cv/edit-training/<int:training_id>/', views.edit_training_api, name='api_edit_training'),
    path('api/cv/list-titles/<int:person_id>/', views.list_academic_titles_api, name='api_list_titles'),
    path('api/cv/list-experience/<int:person_id>/', views.list_work_experience_api, name='api_list_experience'),
    path('api/cv/list-training/<int:person_id>/', views.list_training_api, name='api_list_training'),
    path('api/cv/delete/<str:item_type>/<int:item_id>/', views.delete_cv_item_api, name='api_delete_cv_item'),
    path('api/cv/detail/<str:item_type>/<int:item_id>/', views.get_cv_item_detail_api, name='api_get_cv_item_detail'),

    # ENDPOINTS DE DATOS ECONÓMICOS E INSTITUCIONALES
    path('person/<int:person_id>/update-payroll-info/', views.update_payroll_info, name='update_payroll_info'),
    path('person/<int:person_id>/add-bank-account/', views.add_bank_account, name='add_bank_account'),
    path('person/<int:person_id>/get-payroll-info/', views.get_payroll_info_api, name='get_payroll_info'),
    path('person/<int:person_id>/get-bank-account/', views.get_bank_account_api, name='get_bank_account'),
    path('person/<int:person_id>/get-institutional-data/', views.get_institutional_data_api,
         name='get_institutional_data'),
    path('person/<int:person_id>/save-institutional-data/', views.save_institutional_data_api,
         name='save_institutional_data'),

    # Catálogos y otros
    path('api/areas-list/', views.get_areas_list_api, name='api_areas_list'),
    path('api/employment-statuses/', views.get_employment_statuses_api, name='api_employment_statuses'),
    path('relocate/', views.relocate_employee, name='relocate_employee'),
    path('api/bulk-visibility/', views.bulk_update_tab_visibility, name='bulk_tab_visibility'),

    # VISIBILIDAD DE PERFIL
    path('api/profile-visibility/', views.UpdateProfileVisibilityView.as_view(), name='api_update_profile_visibility'),
]
