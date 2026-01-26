# apps/biometric/urls.py
from django.urls import path
from . import views, adms_views

app_name = 'biometric'

urlpatterns = [
    path('list/', views.BiometricListView.as_view(), name='biometric_list'),
    path('save-ajax/', views.save_biometric_ajax, name='biometric_save_ajax'),
    path('get-data/<int:pk>/', views.get_biometric_data, name='get_biometric_data'),
    path('test-connection/<int:pk>/', views.test_connection_ajax, name='test_connection'),

    # Time management
    path('get-device-time/<int:pk>/', views.get_biometric_time_ajax, name='get_time'),
    path('update-device-time/<int:pk>/', views.update_biometric_time_ajax, name='update_time'),

    # Attendance
    path('load-attendance/<int:pk>/', views.load_attendance_ajax, name='load_attendance'),
    path('upload-file/<int:pk>/', views.upload_biometric_file_ajax, name='upload_file'),

    # ADMS (Push Mode)
    path('adms/receive/', adms_views.adms_receive_attendance, name='adms_receive'),
    path('adms/stats/', adms_views.adms_stats, name='adms_stats'),

    # Reports
    path('reports/employees/', views.EmployeeReportListView.as_view(), name='employee_report_list'),
    path('reports/monthly-pdf/', views.generate_monthly_report_pdf, name='generate_monthly_pdf'),
    path('reports/specific-pdf/', views.generate_specific_report_pdf, name='generate_specific_pdf'),
]
