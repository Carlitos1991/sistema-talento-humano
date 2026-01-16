# apps/function_manual/urls.py
from django.urls import path
from . import views

app_name = 'function_manual'

urlpatterns = [
    # --- PERFILES DE PUESTOS ---
    path('profiles/', views.JobProfileListView.as_view(), name='profile_list'),

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

    # --- COMPETENCIAS (YA DEFINIDAS) ---
    path('competencies/', views.CompetencyListView.as_view(), name='competency_list'),
    path('competencies/table/', views.CompetencyTablePartialView.as_view(), name='competency_table_partial'),
    path('competencies/create/', views.CompetencyCreateView.as_view(), name='competency_create'),
    path('competencies/update/<int:pk>/', views.CompetencyUpdateView.as_view(), name='competency_update'),
    path('competencies/toggle-status/<int:pk>/', views.CompetencyToggleStatusView.as_view(), name='competency_toggle'),
]