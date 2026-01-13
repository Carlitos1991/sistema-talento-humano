from django.urls import path
from . import views

app_name = 'institution'

urlpatterns = [
    path('units/', views.UnitListView.as_view(), name='unit_list'),
    path('units/create/', views.UnitCreateView.as_view(), name='unit_create'),
    path('units/update/<int:pk>/', views.UnitUpdateView.as_view(), name='unit_update'),
    path('units/detail/<int:pk>/', views.UnitDetailView.as_view(), name='unit_detail'),
    path('units/toggle/<int:pk>/', views.UnitToggleStatusView.as_view(), name='unit_toggle'),
    # Niveles Jerárquicos
    path('levels/', views.LevelListView.as_view(), name='level_list'),
    path('levels/create/', views.LevelCreateView.as_view(), name='level_create'),
    path('levels/detail/<int:pk>/', views.LevelDetailView.as_view(), name='level_detail'),
    path('levels/update/<int:pk>/', views.LevelUpdateView.as_view(), name='level_update'),
    path('levels/toggle/<int:pk>/', views.level_toggle_status, name='level_toggle'),
    path('api/parents/', views.ParentOptionsJsonView.as_view(), name='api_parents'),
    path('api/employees/search/', views.EmployeeSearchJsonView.as_view(), name='api_employee_search'),
    path('api/unit-children/', views.api_get_administrative_children, name='api_unit_children'),
]
