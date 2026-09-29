from django.urls import path
from . import views, adms_views

app_name = 'biometric'

urlpatterns = [
    # --- Front-end Listado y Modales AJAX ---
    path('list/', views.BiometricListView.as_view(), name='biometric_list'),
    path('modal/form/', views.BiometricModalFormView.as_view(), name='biometric_modal_create'),
    path('modal/form/<int:pk>/', views.BiometricModalFormView.as_view(), name='biometric_modal_update'),
    path('modal/time/<int:pk>/', views.BiometricModalTimeView.as_view(), name='biometric_modal_time'),
    path('modal/upload/<int:pk>/', views.BiometricModalUploadView.as_view(), name='biometric_modal_upload'),
    path('modal/adms/<int:pk>/', views.BiometricModalAdmsView.as_view(), name='biometric_modal_adms'),

    # Acciones AJAX
    path('save-ajax/', views.save_biometric_ajax, name='biometric_save_ajax'),
    path('get-data/<int:pk>/', views.get_biometric_data, name='get_biometric_data'),
    path('test-connection/<int:pk>/', views.test_connection_ajax, name='test_connection'),
    path('get-device-time/<int:pk>/', views.get_biometric_time_ajax, name='get_time'),
    path('update-device-time/<int:pk>/', views.update_biometric_time_ajax, name='update_time'),
    path('load-attendance/<int:pk>/', views.load_attendance_ajax, name='load_attendance'),
    path('upload-file/<int:pk>/', views.upload_biometric_file_ajax, name='upload_file'),

    # Offline PWA
    path('offline-access/', views.OfflineAttendanceAccessView.as_view(), name='offline_attendance_access'),
    path('offline-attendance/', views.OfflineAttendanceView.as_view(), name='offline_attendance'),
    path('offline-attendance/manifest.webmanifest', views.offline_attendance_manifest,
         name='offline_attendance_manifest'),
    path('offline-attendance/sw.js', views.offline_attendance_service_worker, name='offline_attendance_sw'),
    path('offline-attendance/sync/', views.offline_attendance_sync, name='offline_attendance_sync'),

    # ADMS
    path('adms/receive/', adms_views.adms_receive_attendance, name='adms_receive'),
    path('adms/stats/', adms_views.adms_stats, name='adms_stats'),
    path('iclock/cdata', adms_views.adms_receive_attendance, name='iclock_cdata'),
    path('iclock/attlog', adms_views.adms_receive_attendance, name='iclock_attlog'),
    path('iclock/operlog', adms_views.adms_receive_attendance, name='iclock_operlog'),
    path('iclock/registry', adms_views.iclock_registry, name='iclock_registry'),
    path('iclock/getrequest', adms_views.iclock_getrequest, name='iclock_getrequest'),
    path('iclock/ping', adms_views.iclock_ping, name='iclock_ping'),
    path('iclock/devicecmd', adms_views.iclock_devicecmd, name='iclock_devicecmd'),
    path('adms-download/<int:pk>/', adms_views.adms_download_command, name='adms_download_command'),

    # Reportes
    path('reports/employees/', views.EmployeeReportListView.as_view(), name='employee_report_list'),
    path('reports/monthly-pdf/', views.generate_monthly_report_pdf, name='generate_monthly_pdf'),
    path('reports/specific-pdf/', views.generate_specific_report_pdf, name='generate_specific_pdf'),
    path('reports/department-pdf/', views.generate_department_report_pdf, name='generate_department_pdf'),
]
