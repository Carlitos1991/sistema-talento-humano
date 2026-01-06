from django.urls import path
from . import views

app_name = 'employee'

urlpatterns = [
    # Ruta para el buscador del modal de asignación
    path('api/search/', views.search_employee_by_cedula, name='api_search_employee'),
]
