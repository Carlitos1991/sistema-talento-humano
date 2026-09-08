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

    path('person/<int:person_id>/academic-titles/', views.AcademicTitleModalListView.as_view(),
         name='academic_title_list'),
    path('person/<int:person_id>/academic-titles/create/', views.AcademicTitleCreateView.as_view(),
         name='academic_title_create'),
    path('academic-titles/<int:pk>/update/', views.AcademicTitleUpdateView.as_view(), name='academic_title_update'),
    path('academic-titles/<int:pk>/delete/', views.AcademicTitleDeleteView.as_view(), name='academic_title_delete'),
    path('person/<int:person_id>/work-experience/', views.WorkExperienceModalListView.as_view(),
         name='work_experience_list'),
    path('person/<int:person_id>/work-experience/create/', views.WorkExperienceCreateView.as_view(),
         name='work_experience_create'),
    path('work-experience/<int:pk>/update/', views.WorkExperienceUpdateView.as_view(), name='work_experience_update'),
    path('work-experience/<int:pk>/delete/', views.WorkExperienceDeleteView.as_view(), name='work_experience_delete'),
    path('api/cv/delete/<str:item_type>/<int:item_id>/', views.delete_cv_item_api, name='api_delete_cv_item'),
    path('api/cv/detail/<str:item_type>/<int:item_id>/', views.get_cv_item_detail_api, name='api_get_cv_item_detail'),
    path('api/cv/stats/<int:person_id>/', views.get_cv_stats_api, name='api_cv_stats'),
    path('person/<int:person_id>/courses/', views.CoursesModalListView.as_view(), name='courses_list'),
    path('person/<int:person_id>/courses/create/', views.CoursesCreateView.as_view(), name='courses_create'),
    path('courses/<int:pk>/update/', views.CoursesUpdateView.as_view(), name='courses_update'),
    path('courses/<int:pk>/delete/', views.CoursesDeleteView.as_view(), name='courses_delete'),
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

    # TELETRABAJO
    path('api/telework/data/<int:person_id>/', views.get_telework_data_api, name='api_telework_data'),
    path('api/telework/add-activity/<int:person_id>/', views.add_telework_activity_api, name='api_telework_add'),
    path('api/telework/mark/<int:person_id>/', views.mark_telework_attendance_api, name='api_telework_mark'),
    path('api/telework/generate-report/<int:person_id>/', views.generate_telework_report_pdf,
         name='api_telework_report'),
]
