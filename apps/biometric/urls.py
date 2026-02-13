# apps/biometric/urls.py
from django.urls import path
from . import views, adms_views

app_name = 'biometric'

urlpatterns = [
    # --- Vistas del Sistema (Front-end) ---
    path('list/', views.BiometricListView.as_view(), name='biometric_list'),
    path('save-ajax/', views.save_biometric_ajax, name='biometric_save_ajax'),
    path('get-data/<int:pk>/', views.get_biometric_data, name='get_biometric_data'),
    path('test-connection/<int:pk>/', views.test_connection_ajax, name='test_connection'),

    # Time management
    path('get-device-time/<int:pk>/', views.get_biometric_time_ajax, name='get_time'),
    path('update-device-time/<int:pk>/', views.update_biometric_time_ajax, name='update_time'),

    # Attendance Manual/Direct
    path('load-attendance/<int:pk>/', views.load_attendance_ajax, name='load_attendance'),
    path('upload-file/<int:pk>/', views.upload_biometric_file_ajax, name='upload_file'),

    # --- ENDPOINTS ADMS (COMUNICACIÓN CON EL RELOJ) ---
    # Nota: Estos endpoints también se referencian en el urls.py principal
    # para que estén disponibles en /iclock/...
    path('adms/receive/', adms_views.adms_receive_attendance, name='adms_receive'),
    path('adms/stats/', adms_views.adms_stats, name='adms_stats'),

    # Rutas internas de compatibilidad (apuntan a la nueva función adms_receive_attendance)
    path('iclock/cdata', adms_views.adms_receive_attendance, name='iclock_cdata'),
    path('iclock/attlog', adms_views.adms_receive_attendance, name='iclock_attlog'),
    path('iclock/operlog', adms_views.adms_receive_attendance, name='iclock_operlog'),

    # Nuevas rutas de registro y heartbeat
    path('iclock/registry', adms_views.iclock_registry, name='iclock_registry'),
    path('iclock/getrequest', adms_views.iclock_getrequest, name='iclock_getrequest'),
    path('iclock/ping', adms_views.iclock_ping, name='iclock_ping'),

    # Reports
    path('reports/employees/', views.EmployeeReportListView.as_view(), name='employee_report_list'),
    path('reports/monthly-pdf/', views.generate_monthly_report_pdf, name='generate_monthly_pdf'),
    path('reports/specific-pdf/', views.generate_specific_report_pdf, name='generate_specific_pdf'),
]
