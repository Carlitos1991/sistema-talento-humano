"""
Módulo de Enrutamiento para Gestión Institucional (SIGETH).
Estructura las URLs para Unidades Administrativas, Niveles Jerárquicos,
Entregables, Organigrama Oficial y Endpoints API para Select2/AJAX.
"""

from django.urls import path
from . import views

app_name = 'institution'

urlpatterns = [
    # ==========================================================================
    # 1. UNIDADES ADMINISTRATIVAS (CRUD Y DETALLE)
    # ==========================================================================
    path('units/', views.UnitListView.as_view(), name='unit_list'),
    path('units/create/', views.UnitCreateView.as_view(), name='unit_create'),
    path('units/update/<int:pk>/', views.UnitUpdateView.as_view(), name='unit_update'),
    path('units/toggle/<int:pk>/', views.UnitToggleStatusView.as_view(), name='unit_toggle'),
    path('units/change-parent/<int:pk>/', views.UnitChangeParentView.as_view(), name='unit_change_parent'),
    path('units/assign-boss/<int:pk>/', views.UnitAssignBossView.as_view(), name='unit_assign_boss'),

    # Vista integral de detalle de unidad (rutas con y sin sufijo view)
    path('units/detail/<int:pk>/', views.UnitDetailView.as_view(), name='unit_detail'),
    path('units/detail/<int:pk>/view/', views.UnitDetailView.as_view(), name='unit_detail_view'),
    path('units/detail/<int:pk>/json/', views.UnitDetailJsonView.as_view(), name='unit_detail_json'),

    # Recargas parciales y exportación
    path('units/partial_table/', views.unit_partial_table, name='unit_partial_table'),
    path('units/<int:pk>/export-employees/', views.export_unit_employees_excel, name='unit_export_employees'),

    # ==========================================================================
    # 2. NIVELES JERÁRQUICOS
    # ==========================================================================
    path('levels/', views.LevelListView.as_view(), name='level_list'),
    path('levels/create/', views.LevelCreateView.as_view(), name='level_create'),
    path('levels/detail/<int:pk>/', views.LevelDetailView.as_view(), name='level_detail'),
    path('levels/update/<int:pk>/', views.LevelUpdateView.as_view(), name='level_update'),
    path('levels/toggle/<int:pk>/', views.level_toggle_status, name='level_toggle'),
    path('levels/partial_table/', views.level_partial_table, name='level_partial_table'),

    # ==========================================================================
    # 3. GESTIÓN DE ENTREGABLES (DELIVERABLES)
    # ==========================================================================
    path(
        'units/<int:unit_id>/deliverables/partial/',
        views.deliverables_partial_table,
        name='deliverables_partial_table'
    ),
    # Modales CRUD vía AJAX
    path(
        'api/units/<int:unit_id>/deliverables/save/',
        views.DeliverableCreateUpdateView.as_view(),
        name='api_deliverable_create'
    ),
    path(
        'api/units/<int:unit_id>/deliverables/save/<int:pk>/',
        views.DeliverableCreateUpdateView.as_view(),
        name='api_deliverable_update'
    ),
    path(
        'api/deliverables/delete/<int:pk>/',
        views.DeliverableDeleteView.as_view(),
        name='api_deliverable_delete'
    ),
    # Listado serializado JSON (usado por Wizards y componentes Vue/dinámicos)
    path(
        'api/units/<int:unit_id>/deliverables/',
        views.api_unit_deliverables,
        name='api_unit_deliverables'
    ),

    # ==========================================================================
    # 4. ORGANIGRAMA INSTITUCIONAL
    # ==========================================================================
    path('organigram/positional/', views.OrganigramView.as_view(), name='organigram_view'),
    path('organigram/root-list/', views.RootLevelListView.as_view(), name='root_level_list'),
    path('organigram/navigation/', views.RootLevelListView.as_view(), name='organigram_nav'),
    path('organigram/navigation/<int:pk>/', views.RootLevelListView.as_view(), name='organigram_nav_detail'),

    # ==========================================================================
    # 5. ENDPOINTS DE SOPORTE API (SELECT2, COMBOS Y CÓDIGOS CORRELATIVOS)
    # ==========================================================================
    path('api/parents/', views.ParentOptionsJsonView.as_view(), name='api_parents'),
    path('api/employee/search/', views.EmployeeSearchJsonView.as_view(), name='api_employee_search'),
    path('api/unit-children/', views.api_get_administrative_children, name='api_unit_children'),
    path('api/next-code/', views.GetNextCodeJsonView.as_view(), name='api_next_code'),
]
