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
    path('api/employee/search/', views.EmployeeSearchJsonView.as_view(), name='api_employee_search'),
    path('api/unit-children/', views.api_get_administrative_children, name='api_unit_children'),
    path('api/units/<int:unit_id>/deliverables/', views.DeliverableListJsonView.as_view(), name='api_deliverable_list'),
    path('api/units/<int:unit_id>/deliverables/save/', views.DeliverableCreateUpdateView.as_view(),
         name='api_deliverable_create'),
    path('api/units/<int:unit_id>/deliverables/save/<int:pk>/', views.DeliverableCreateUpdateView.as_view(),
         name='api_deliverable_update'),
    path('api/deliverables/delete/<int:pk>/', views.DeliverableDeleteView.as_view(), name='api_deliverable_delete'),
    path('units/detail/<int:pk>/view/', views.UnitDetailView.as_view(), name='unit_detail_view'),
    path('units/detail/<int:pk>/json/', views.UnitDetailJsonView.as_view(), name='unit_detail_json'),
]
