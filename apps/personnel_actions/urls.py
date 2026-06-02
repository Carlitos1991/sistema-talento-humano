from django.urls import path
from . import views

app_name = 'personnel_actions'

urlpatterns = [
    # Lista Principal
    path('', views.PersonnelActionListView.as_view(), name='action_list'),
    path('create/', views.PersonnelActionCreateView.as_view(), name='action_create'),

    # --- Generar Acción (Lista de Empleados) ---
    path('employees/', views.EmployeeActionListView.as_view(), name='action_employee_list'),

    # --- Historial de Acciones por Empleado ---
    path('history/<int:employee_id>/', views.ActionHistoryView.as_view(), name='action_history'),
    path('<int:pk>/inactivate/', views.ActionInactivateView.as_view(), name='action_inactivate'),

    # --- Detalle, Editar, Registrar, PDF ---
    path('<int:pk>/detail/', views.ActionDetailView.as_view(), name='action_detail'),
    path('<int:pk>/edit/', views.ActionUpdateView.as_view(), name='action_update'),
    path('<int:pk>/register/', views.ActionRegisterView.as_view(), name='action_register'),
    path('<int:pk>/pdf/', views.ActionPDFView.as_view(), name='action_pdf'),

    # --- TIPOS DE ACCIÓN (CRUD VUE) ---
    path('types/', views.ActionTypeListView.as_view(), name='action_type_list'),

    # API Endpoints para Vue
    path('types/api/save/', views.ActionTypeCreateOrUpdateView.as_view(), name='action_type_save'),
    path('types/api/save/<int:pk>/', views.ActionTypeCreateOrUpdateView.as_view(), name='action_type_update'),
    path('types/api/detail/<int:pk>/', views.ActionTypeDetailJsonView.as_view(), name='action_type_detail'),
    path('types/api/delete/<int:pk>/', views.ActionTypeDeleteView.as_view(), name='action_type_delete'),
    path('types/api/toggle/<int:pk>/', views.ActionTypeToggleStatusView.as_view(), name='type_toggle'),

    # --- APIs para Modal de Acciones de Personal ---
    path('api/unit-children/', views.AdministrativeUnitChildrenJsonView.as_view(), name='api_unit_children'),
    path('api/search-budget-lines/', views.SearchBudgetLinesJsonView.as_view(), name='api_search_budget_lines'),
    path('api/users/search/', views.user_search_json, name='api_user_search'),
]
