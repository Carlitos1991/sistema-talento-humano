# --- vacation/urls.py ---
from django.urls import path
from . import views

app_name = 'vacation'

urlpatterns = [
    # Solicitudes
    path('requests/', views.VacationRequestListView.as_view(), name='request_list'),
    path('requests/create/', views.VacationCreateView.as_view(), name='request_create'),
    path('requests/create-first/<int:employee_id>/', views.CreateFirstVacationView.as_view(), name='create_first_vacation'),
    path('requests/create-new/<int:employee_id>/', views.CreateNewVacationPeriodView.as_view(), name='create_new_vacation'),
    path('requests/employee/<int:employee_id>/', views.EmployeeVacationDetailView.as_view(), name='employee_vacation_detail'),

    # Periodos
    path('periods/', views.PeriodListView.as_view(), name='period_list'),
    path('periods/create/', views.PeriodCreateView.as_view(), name='period_create'),
    path('periods/edit/<int:pk>/', views.PeriodUpdateView.as_view(), name='period_edit'),
]
