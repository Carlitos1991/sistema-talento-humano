# --- vacation/urls.py ---
from django.urls import path
from . import views

app_name = 'vacation'

urlpatterns = [
    # Solicitudes
    path('requests/', views.VacationRequestListView.as_view(), name='request_list'),
    path('requests/create/', views.VacationCreateView.as_view(), name='request_create'),  # Ojo con el nombre

    # Periodos
    path('periods/', views.PeriodListView.as_view(), name='period_list'),
    path('periods/create/', views.PeriodCreateView.as_view(), name='period_create'),
]
