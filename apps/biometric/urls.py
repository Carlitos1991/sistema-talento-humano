from django.urls import path
from . import views

app_name = 'biometric'

urlpatterns = [
    path('list/', views.BiometricListView.as_view(), name='biometric_list'),
    path('create/', views.BiometricCreateView.as_view(), name='biometric_create'),
    # Agregaremos estas más adelante cuando completemos el CRUD
    # path('update/<int:pk>/', views.BiometricUpdateView.as_view(), name='biometric_update'),
    # path('delete/<int:pk>/', views.BiometricDeleteView.as_view(), name='biometric_delete'),
]