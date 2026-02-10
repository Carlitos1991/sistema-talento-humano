from django.urls import path
from . import views

app_name = 'vacation'

urlpatterns = [
    # Lista de solicitudes de vacaciones
    path('requests/', views.VacationRequestListView.as_view(), name='request_list'),
    
    # Crear solicitud de vacaciones
    path('create/', views.VacationCreateView.as_view(), name='create'),
    
    # Lista de periodos/saldos
    path('periods/', views.PeriodListView.as_view(), name='period_list'),
]