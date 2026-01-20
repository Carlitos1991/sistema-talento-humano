from django.urls import path
from . import views

app_name = 'employee'

urlpatterns = [
    # Ruta para el buscador del modal de asignación
    path('api/search/', views.search_employee_by_cedula, name='api_search_employee'),
    path('detail/<int:pk>/', views.EmployeeDetailWizardView.as_view(), name='employee_detail'),
    path('api/upload-cv/<int:person_id>/', views.upload_cv_api, name='api_upload_cv'),
    path('partial/cv/<int:person_id>/', views.curriculum_tab_partial, name='partial_cv_tab'),
    # ENDPOINTS DE GUARDADO (POST)
    path('api/cv/add-title/<int:person_id>/', views.add_academic_title_api, name='api_add_title'),
    path('api/cv/add-experience/<int:person_id>/', views.add_work_experience_api, name='api_add_experience'),
    path('api/cv/add-training/<int:person_id>/', views.add_training_api, name='api_add_training'),
    
    # ENDPOINTS DE EDICIÓN (POST)
    path('api/cv/edit-title/<int:title_id>/', views.edit_academic_title_api, name='api_edit_title'),
    path('api/cv/edit-experience/<int:experience_id>/', views.edit_work_experience_api, name='api_edit_experience'),
    path('api/cv/edit-training/<int:training_id>/', views.edit_training_api, name='api_edit_training'),

    # RUTA DE REFRESCO PARCIAL (GET)
    path('partial/cv/<int:person_id>/', views.curriculum_tab_partial, name='partial_cv_tab'),
    path('api/cv/list-titles/<int:person_id>/', views.list_academic_titles_api, name='api_list_titles'),
    path('api/cv/list-experience/<int:person_id>/', views.list_work_experience_api, name='api_list_experience'),
    path('api/cv/list-training/<int:person_id>/', views.list_training_api, name='api_list_training'),
    path('api/cv/delete/<str:item_type>/<int:item_id>/', views.delete_cv_item_api, name='api_delete_cv_item'),
    path('api/cv/delete/<str:item_type>/<int:item_id>/', views.delete_cv_item_api, name='api_delete_cv_item'),
    path('api/cv/detail/<str:item_type>/<int:item_id>/', views.get_cv_item_detail_api, name='api_get_cv_item_detail'),
    path('person/<int:person_id>/add-title-api/', views.add_academic_title_api, name='add_academic_title_api'),
    path('person/<int:person_id>/update-payroll-info/', views.update_payroll_info, name='update_payroll_info'),
    path('person/<int:person_id>/add-bank-account/', views.add_bank_account, name='add_bank_account'),
    path('person/<int:person_id>/get-payroll-info/', views.get_payroll_info_api, name='get_payroll_info'),
    path('person/<int:person_id>/get-bank-account/', views.get_bank_account_api, name='get_bank_account'),
    path('person/<int:person_id>/get-institutional-data/', views.get_institutional_data_api, name='get_institutional_data'),
    path('person/<int:person_id>/save-institutional-data/', views.save_institutional_data_api, name='save_institutional_data'),

]
