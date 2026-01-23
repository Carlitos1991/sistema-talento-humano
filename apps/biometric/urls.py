from django.urls import path
from . import views
from . import adms_views

app_name = 'biometric'

urlpatterns = [
    path('list/', views.BiometricListView.as_view(), name='biometric_list'),
    path('save-ajax/', views.create_biometric_ajax, name='biometric_save_ajax'),
    path('adms/receive/', views.ADMSReceiverView.as_view(), name='adms_receiver'),
    path('get-data/<int:pk>/', views.get_biometric_data, name='get_biometric_data'),
    path('test-connection/<int:pk>/', views.test_connection_ajax, name='test_connection'),
    path('get-time/<int:pk>/', views.get_biometric_time_ajax, name='get_time'),
    path('update-time/<int:pk>/', views.update_biometric_time_ajax, name='update_time'),
    path('adms/receive/', adms_views.adms_receive_attendance, name='adms_receive'),
    path('adms/stats/', adms_views.adms_stats, name='adms_stats'),
    path('upload-file/<int:pk>/', views.upload_biometric_file_ajax, name='upload_file'),
    path('load-attendance/<int:pk>/', views.load_attendance_ajax, name='load_attendance'),

]
