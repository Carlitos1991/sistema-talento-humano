from django.urls import path
from . import views

app_name = 'employee'

urlpatterns = [
    # PANEL PRINCIPAL Y BÚSQUEDAS
    path('detail/<int:pk>/', views.EmployeeDetailWizardView.as_view(), name='employee_detail'),
    path('self_dashboard/', views.EmployeeSelfDashboardView.as_view(), name='self_dashboard'),
    path('api/search/', views.search_employee_by_cedula, name='api_search_employee'),
    path('relocate/', views.relocate_employee, name='relocate_employee'),

    # VISIBILIDAD DE PESTAÑAS
    path('api/bulk-visibility/', views.bulk_update_tab_visibility, name='bulk_tab_visibility'),
    path('api/profile-visibility/', views.UpdateProfileVisibilityView.as_view(), name='api_update_profile_visibility'),

    # CURRÍCULUM VITAE (MODALES Y CRUD AJAX)
    path('api/upload-cv/<int:person_id>/', views.upload_cv_pdf, name='api_upload_cv'),
    path('api/cv/stats/<int:person_id>/', views.get_cv_stats_api, name='api_cv_stats'),

    # Títulos Académicos
    path('person/<int:person_id>/academic-titles/', views.AcademicTitleModalListView.as_view(),
         name='academic_title_list'),
    path('person/<int:person_id>/academic-titles/create/', views.AcademicTitleCreateView.as_view(),
         name='academic_title_create'),
    path('academic-titles/<int:pk>/update/', views.AcademicTitleUpdateView.as_view(), name='academic_title_update'),
    path('academic-titles/<int:pk>/delete/', views.AcademicTitleDeleteView.as_view(), name='academic_title_delete'),

    # Experiencia Laboral
    path('person/<int:person_id>/work-experience/', views.WorkExperienceModalListView.as_view(),
         name='work_experience_list'),
    path('person/<int:person_id>/work-experience/create/', views.WorkExperienceCreateView.as_view(),
         name='work_experience_create'),
    path('work-experience/<int:pk>/update/', views.WorkExperienceUpdateView.as_view(), name='work_experience_update'),
    path('work-experience/<int:pk>/delete/', views.WorkExperienceDeleteView.as_view(), name='work_experience_delete'),

    # Cursos y Capacitaciones
    path('person/<int:person_id>/courses/', views.CoursesModalListView.as_view(), name='courses_list'),
    path('person/<int:person_id>/courses/create/', views.CoursesCreateView.as_view(), name='courses_create'),
    path('courses/<int:pk>/update/', views.CoursesUpdateView.as_view(), name='courses_update'),
    path('courses/<int:pk>/delete/', views.CoursesDeleteView.as_view(), name='courses_delete'),

    # DATOS INSTITUCIONALES, ECONÓMICOS Y CONTRATOS (MODALES FORM)
    path('person/<int:person_id>/institutional-data/update/', views.InstitutionalDataUpdateView.as_view(),
         name='institutional_data_update'),
    path('person/<int:person_id>/bank-account/update/', views.BankAccountUpdateView.as_view(),
         name='bank_account_update'),
    path('person/<int:person_id>/payroll-info/update/', views.PayrollInfoUpdateView.as_view(),
         name='payroll_info_update'),
    path('contract/<int:pk>/detail/', views.ContractDetailModalView.as_view(), name='contract_detail_modal'),

    # TELETRABAJO (API & REPORTES)
    path('person/<int:person_id>/telework/data/', views.get_telework_data_api, name='telework_data_api'),
    path('person/<int:person_id>/telework/attendance/mark/', views.mark_telework_attendance_api,
         name='mark_telework_attendance_api'),
    path('person/<int:person_id>/telework/activity/modal/', views.telework_activity_modal_view,
         name='telework_activity_modal'),
    path('person/<int:person_id>/telework/activity/add/', views.add_telework_activity_api,
         name='add_telework_activity_api'),
    path('person/<int:person_id>/telework/report/modal/', views.telework_report_modal_view,
         name='telework_report_modal'),
    path('person/<int:person_id>/telework/report/pdf/', views.generate_telework_report_pdf,
         name='generate_telework_report_pdf'),
    path('person/<int:person_id>/audit/modal/', views.PersonAuditModalView.as_view(), name='person_audit_modal'),
    path('person/<int:person_id>/audit/export-excel/', views.export_person_audit_excel, name='audit_export_excel'),
    path('person/<int:person_id>/audit/tab/', views.log_tab_audit_api, name='log_tab_audit_api'),
    path('person/<int:person_id>/photo/update/', views.upload_person_photo_api, name='upload_person_photo_api'),

]
