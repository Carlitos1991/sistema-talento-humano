from django.urls import path

from . import views

app_name = 'employee_archive'

urlpatterns = [
    path('api/users/search/', views.user_search_json, name='api_user_search'),

    path('employees/', views.EmployeeArchiveListView.as_view(), name='employee_list'),
    path('employees/<int:employee_id>/', views.EmployeeArchiveDetailView.as_view(), name='employee_detail'),
    path('employees/<int:employee_id>/documents/create/', views.EmployeeArchiveDocumentCreateView.as_view(), name='document_create'),
    path('documents/<int:archive_id>/upload/', views.upload_archive_version, name='version_upload'),
    path('scan-tasks/<int:task_id>/upload/', views.upload_scan_task_version, name='scan_task_upload'),
    path('versions/<int:version_id>/open/', views.open_archive_version, name='version_open'),

    path('employees/<int:employee_id>/loan/request/', views.request_archive_loan, name='loan_request'),
    path('employees/<int:employee_id>/loan/manual/', views.create_manual_archive_loan, name='loan_manual_create'),
    path('loans/<int:loan_id>/deliver/', views.deliver_archive_loan, name='loan_deliver'),
    path('loans/<int:loan_id>/return/', views.report_archive_return, name='loan_return_report'),
    path('loans/<int:loan_id>/validate-return/', views.validate_archive_return, name='loan_return_validate'),
    path('loans/', views.EmployeeArchiveLoanListView.as_view(), name='loan_list'),
    path('notifications/', views.EmployeeArchiveNotificationListView.as_view(), name='notification_list'),

    path('document-types/', views.EmployeeDocumentTypeListView.as_view(), name='archive_type_list'),
    path('document-types/create/', views.EmployeeDocumentTypeCreateView.as_view(), name='archive_type_create'),
    path('document-types/<int:pk>/update/', views.EmployeeDocumentTypeUpdateView.as_view(), name='archive_type_update'),
]
