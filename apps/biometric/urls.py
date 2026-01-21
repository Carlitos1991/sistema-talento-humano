from django.urls import path
from . import views

app_name = 'biometric'

urlpatterns = [
    path('list/', views.BiometricListView.as_view(), name='biometric_list'),
    path('save-ajax/', views.create_biometric_ajax, name='biometric_save_ajax'),
    path('adms/receive/', views.ADMSReceiverView.as_view(), name='adms_receiver'),
]
