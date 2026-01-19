# apps/function_manual/urls.py
from django.urls import path
from . import views

app_name = 'function_manual'

urlpatterns = [
    # --- PERFILES DE PUESTOS ---
    path('profiles/', views.JobProfileListView.as_view(), name='profile_list'),
    path('profiles/create/', views.JobProfileCreateView.as_view(), name='profile_create'),  # RUTA FALTANTE
    path('profiles/update/<int:pk>/', views.JobProfileUpdateView.as_view(), name='profile_update'),
    # Útil para la tabla

    # --- ADMINISTRACIÓN / CATÁLOGOS ---
    path('catalogs/', views.ManualCatalogListView.as_view(), name='catalog_list'),
    path('catalogs/create/', views.ManualCatalogCreateView.as_view(), name='catalog_create'),
    path('catalogs/detail/<int:pk>/', views.manual_catalog_detail_json, name='catalog_detail'),
    path('catalogs/update/<int:pk>/', views.ManualCatalogUpdateView.as_view(), name='catalog_update'),
    path('catalogs/toggle/<int:pk>/', views.manual_catalog_toggle_status, name='catalog_toggle'),

    # --- ITEMS DE CATÁLOGO ---
    path('catalogs/<int:catalog_id>/items/', views.manual_catalog_item_list_json, name='catalog_item_list'),
    path('catalogs/items/create/', views.ManualCatalogItemCreateView.as_view(), name='catalog_item_create'),
    path('catalogs/items/detail/<int:pk>/', views.manual_catalog_item_detail_json, name='catalog_item_detail'),
    path('catalogs/items/update/<int:pk>/', views.ManualCatalogItemUpdateView.as_view(), name='catalog_item_update'),
    path('catalogs/items/toggle/<int:pk>/', views.manual_catalog_item_toggle_status, name='catalog_item_toggle'),

    # --- ADMINISTRACIÓN / MATRIZ (ESCALA) ---
    path('matrix/', views.OccupationalMatrixListView.as_view(), name='matrix_list'),

    # --- COMPETENCIAS ---
    path('competencies/', views.CompetencyListView.as_view(), name='competency_list'),
    path('competencies/table/', views.CompetencyTablePartialView.as_view(), name='competency_table_partial'),
    path('competencies/create/', views.CompetencyCreateView.as_view(), name='competency_create'),
    path('competencies/update/<int:pk>/', views.CompetencyUpdateView.as_view(), name='competency_update'),
    path('competencies/toggle-status/<int:pk>/', views.CompetencyToggleStatusView.as_view(), name='competency_toggle'),
    path('api/units/', views.ApiUnitChildrenView.as_view(), name='api_units_root'),
    path('api/units/<int:parent_id>/children/', views.ApiUnitChildrenView.as_view(), name='api_units_children'),
    path('api/units/<int:unit_id>/next-code/', views.ApiNextPositionCodeView.as_view(), name='api_next_code'),
    path('api/valuation-nodes/', views.ApiValuationNodesView.as_view(), name='api_valuation_nodes'),
    path('api/valuation-nodes/detail/<int:pk>/', views.ValuationNodeDetailApi.as_view(), name='api_node_detail'),
    path('api/valuation-nodes/save/', views.ValuationNodeSaveApi.as_view(), name='api_node_save'),
    path('api/profile/save/', views.JobProfileSaveApi.as_view(), name='api_profile_save'),
    path('matrix/manage/', views.OccupationalMatrixListView.as_view(), name='matrix_list'),
    path('api/matrix/save/', views.OccupationalMatrixSaveApi.as_view(), name='api_matrix_save'),
    path('valuation/structure/', views.ValuationNodeListView.as_view(), name='valuation_list'),
    path('api/matrix/detail/<int:pk>/', views.OccupationalMatrixDetailApi.as_view(), name='api_matrix_detail'),
    path('api/matrix/toggle/<int:pk>/', views.occupational_matrix_toggle_status, name='api_matrix_toggle'),
]
