# apps/function_manual/urls.py
from django.urls import path
from . import views

app_name = 'function_manual'

urlpatterns = [
    # --- PERFILES DE PUESTOS ---
    path('profiles/', views.JobProfileListView.as_view(), name='profile_list'),

    # --- ADMINISTRACIÓN / CATÁLOGOS ---
    path('catalogs/', views.ManualCatalogListView.as_view(), name='catalog_list'),

    # --- ADMINISTRACIÓN / MATRIZ (ESCALA) ---
    path('matrix/', views.OccupationalMatrixListView.as_view(), name='matrix_list'),

    # --- COMPETENCIAS (YA DEFINIDAS) ---
    path('competencies/', views.CompetencyListView.as_view(), name='competency_list'),
    path('competencies/table/', views.CompetencyTablePartialView.as_view(), name='competency_table_partial'),
    path('competencies/create/', views.CompetencyCreateView.as_view(), name='competency_create'),
    path('competencies/update/<int:pk>/', views.CompetencyUpdateView.as_view(), name='competency_update'),
    path('competencies/toggle-status/<int:pk>/', views.CompetencyToggleStatusView.as_view(), name='competency_toggle'),
]